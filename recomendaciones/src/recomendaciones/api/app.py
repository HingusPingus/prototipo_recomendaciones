"""Fábrica de la aplicación FastAPI y composición de servicios de la API.

La API no importa `engine/` ni registra configuración en Postgres: la versión activa, las legibles
(RD-103) y las de escala etaria compatible se derivan de los archivos desplegados. Postgres solo se
toca por los tres caminos de INV-1 (repoblado de `filters:`/`retired:` y escritura de la declaración).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, FastAPI
from recomendaciones.api.deps import require_api_key
from recomendaciones.api.errors import install_error_handlers
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
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache, RetiredCache
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.cache.repository import RecommendationRepository
from recomendaciones.storage.cache.ttl import CacheTTLs
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
    readable_versions: tuple[str, ...]
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
    retired = RetiredCache(cache, source, ttls.filters, ttls.retired_window)
    signaler = RecomputeStream(cache, maxlen=settings.recompute_requests_maxlen, ttl_suppress=ttls.suppress)
    read_service = ReadService(
        repository=repository,
        filters=filters,
        retired=retired,
        signaler=signaler,
        active_version=engine_config.config_version,
        readable_versions=readable,
        age_compatible_versions=compatible,
    )
    return ApiServices(
        settings, engine_config, cache, factory, ttls, repository, filters, retired, signaler, read_service, readable
    )


def create_app(settings: Settings, services: ApiServices | None = None) -> FastAPI:
    from recomendaciones.api.routes import recommendations

    services = services or build_services(settings)
    app = FastAPI(
        title="RecoMe · API de Recomendaciones (interna)",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.services = services
    install_error_handlers(app)
    app.include_router(recommendations.router, dependencies=[Depends(require_api_key)])
    return app
