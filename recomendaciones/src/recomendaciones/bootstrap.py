"""Arranque común de worker, Data Transformer y jobs: configuración del motor y dependencias.

Estos procesos —no la API— registran la versión activa en `engine_config_versions` (el loader es su
escritor único, §2.8): la API la deriva de los archivos desplegados y no toca esa tabla (INV-1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from prometheus_client import CollectorRegistry

from recomendaciones.config.loader import EngineConfig, load_engine_config, validate_operational_windows
from recomendaciones.config.settings import Settings
from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.repository import RecommendationRepository
from recomendaciones.storage.cache.ttl import CacheTTLs
from recomendaciones.storage.db.config_registry import register_in_database
from recomendaciones.storage.db.session import SessionFactory, create_db_engine, session_factory


@dataclass
class Runtime:
    settings: Settings
    config: EngineConfig
    factory: SessionFactory
    cache: CacheClient
    ttls: CacheTTLs
    repository: RecommendationRepository
    metrics: Metrics


def build_runtime(settings: Settings, component: str, *, factory: SessionFactory | None = None, cache: CacheClient | None = None) -> Runtime:
    config = load_engine_config(settings.engine_config_file)
    validate_operational_windows(config, settings)
    factory = factory or session_factory(create_db_engine(settings.database_url.get_secret_value()))
    with factory.begin() as s:
        register_in_database(s, config, datetime.now(UTC))
    cache = cache or CacheClient.from_url(settings.redis_url.get_secret_value(), settings.redis_timeout_seconds)
    ttls = CacheTTLs.from_settings(settings)
    metrics = Metrics(CollectorRegistry())
    metrics.set("reco_active_config_version", 1.0, config_version=config.config_version, component=component)
    repository = RecommendationRepository(cache, ttl_fresh=ttls.fresh, ttl_stale=ttls.stale, ttl_fallback=ttls.fallback)
    return Runtime(settings, config, factory, cache, ttls, repository, metrics)
