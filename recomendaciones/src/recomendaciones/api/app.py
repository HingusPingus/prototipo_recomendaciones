"""Fábrica de la aplicación FastAPI y composición de servicios de la API.

La API no importa `engine/` ni registra configuración en Postgres: la versión activa, las legibles
(RD-103) y las de escala etaria compatible se derivan de los archivos desplegados. Postgres solo se
toca por los tres caminos de INV-1 (repoblado de `filters:`/`retired:` y escritura de la declaración).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import Depends, FastAPI, Request

from recomendaciones.api.deps import require_api_key
from recomendaciones.api.errors import install_error_handlers
from recomendaciones.api.services.declaracion import DeclarationService
from recomendaciones.api.services.read_service import ReadService
from recomendaciones.config.loader import (
    EngineConfig,
    age_compatible_versions,
    load_deployed_configs,
    load_engine_config,
    readable_versions_from_files,
    validate_operational_windows,
)
from recomendaciones.config.settings import Settings
from recomendaciones.observability.logging import correlation_scope
from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache, RetiredCache
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.cache.repository import RecommendationRepository
from recomendaciones.storage.cache.ttl import CacheTTLs
from recomendaciones.storage.db.declarations import DeclarationRepository
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.storage.db.session import SessionFactory, create_db_engine, session_factory


@dataclass
class ApiServices:
    settings: Settings
    engine_config: EngineConfig
    cache: CacheClient
    db_factory: SessionFactory
    ttls: CacheTTLs
    repository: RecommendationRepository
    filters: FiltersCache
    retired: RetiredCache
    signaler: RecomputeStream
    read_service: ReadService
    declaration_service: DeclarationService
    readable_versions: tuple[str, ...]
    metrics: Metrics = field(default_factory=Metrics)
    extras: dict[str, object] = field(default_factory=dict)


def build_services(
    settings: Settings,
    *,
    db_factory: SessionFactory | None = None,
    cache: CacheClient | None = None,
) -> ApiServices:
    engine_config = load_engine_config(settings.engine_config_file)
    validate_operational_windows(engine_config, settings)
    deployed = load_deployed_configs()
    readable = readable_versions_from_files(engine_config, deployed)
    compatible = age_compatible_versions(engine_config, deployed)

    factory = db_factory or session_factory(create_db_engine(settings.database_url.get_secret_value()))
    cache = cache or CacheClient.from_url(settings.redis_url.get_secret_value(), settings.redis_timeout_seconds)
    ttls = CacheTTLs.from_settings(settings)
    source = DbFiltersSource(factory)
    repository = RecommendationRepository(cache, ttl_fresh=ttls.fresh, ttl_stale=ttls.stale, ttl_fallback=ttls.fallback)
    filters = FiltersCache(cache, source, ttls.filters)
    metrics = Metrics()
    retired = RetiredCache(
        cache, source, ttls.filters, ttls.retired_window, on_size=lambda m, n: metrics.set("retired_set_size", float(n), module=m.value)
    )
    signaler = RecomputeStream(cache, maxlen=settings.recompute_requests_maxlen, ttl_suppress=ttls.suppress)
    metrics.set("reco_active_config_version", 1.0, config_version=engine_config.config_version, component="api")
    read_service = ReadService(
        repository=repository,
        filters=filters,
        retired=retired,
        signaler=signaler,
        active_version=engine_config.config_version,
        readable_versions=readable,
        age_compatible_versions=compatible,
        on_signal_failure=lambda: metrics.inc("reco_recompute_signal_failures_total"),
    )
    declaration_service = DeclarationService(
        factory, DeclarationRepository(), filters, signaler, declared_tags_min=engine_config.declared_tags_min
    )
    return ApiServices(
        settings,
        engine_config,
        cache,
        factory,
        ttls,
        repository,
        filters,
        retired,
        signaler,
        read_service,
        declaration_service,
        readable,
        metrics,
    )


def create_app(settings: Settings, services: ApiServices | None = None) -> FastAPI:
    from recomendaciones.api.routes import declaraciones, health, recommendations

    services = services or build_services(settings)
    app = FastAPI(
        title="RecoMe · API de Recomendaciones (interna)",
        version="1.0.0",
        # FR-060: ninguna ruta pública fuera de salud; el contrato vive en api-general (T049).
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.services = services
    install_error_handlers(app)

    @app.middleware("http")
    async def measure(request: Request, call_next):  # noqa: ANN001, ANN202 — latencia por endpoint (FR-042)
        started = time.perf_counter()
        with correlation_scope(request.headers.get("X-Correlation-ID")) as correlation_id:
            response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        route = request.scope.get("route")
        endpoint = getattr(route, "path", "sin-ruta")
        services.metrics.observe("reco_request_duration_seconds", time.perf_counter() - started, endpoint=endpoint)
        return response
    app.include_router(health.router)  # única superficie pública (FR-060)
    app.include_router(recommendations.router, dependencies=[Depends(require_api_key)])
    app.include_router(declaraciones.router, dependencies=[Depends(require_api_key)])
    return app
