"""Fixtures compartidas."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Entorno mínimo válido. Los parámetros operativos de FR-068 son obligatorios y sin default:
# cada test que los necesite parte de este diccionario completo.
VALID_ENV: dict[str, str] = {
    "RECO_ENVIRONMENT": "test",
    "RECO_INTERNAL_API_KEY": "test.s3cr3t-0123456789abcdef",
    "RECO_DATABASE_URL": "postgresql+psycopg://reco:reco@localhost:5432/recomendaciones",
    "RECO_REDIS_URL": "redis://localhost:6379/0",
    "RECO_AMQP_URL": "amqp://guest:guest@localhost:5672/",
    "RECO_API_GENERAL_BASE_URL": "http://api-general.internal",
    "RECO_ENGINE_CONFIG_FILE": "v1.yaml",
    "RECO_TTL_FRESH_SECONDS": "86400",
    "RECO_TTL_STALE_SECONDS": "604800",
    "RECO_TTL_FILTERS_SECONDS": "3600",
    "RECO_TTL_FALLBACK_SECONDS": "21600",
    "RECO_TTL_SUPPRESS_SECONDS": "300",
    "RECO_TTL_DEDUPE_SECONDS": "86400",
    "RECO_IDEMPOTENCY_RETENTION_HOURS": "168",
    "RECO_SIGNAL_RETENTION_DAYS": "730",
    "RECO_SYNC_VOLUME_DELTA_RATIO": "0.9",
    "RECO_INTERACTION_RECALC_THRESHOLD": "10",
    "RECO_RECOMPUTE_REQUESTS_MAXLEN": "100000",
    "RECO_RECOMPUTE_REQUESTS_MAX_DELIVERIES": "5",
    "RECO_EVENT_REDELIVERY_WINDOW_HOURS": "48",
    "RECO_RETRY_MAX_ATTEMPTS": "5",
    "RECO_RETRY_BACKOFF_BASE_SECONDS": "1",
    "RECO_REDIS_TIMEOUT_SECONDS": "0.5",
    "RECO_API_GENERAL_TIMEOUT_SECONDS": "10",
    "RECO_WARMUP_RATE_PER_SECOND": "50",
}


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    return dict(VALID_ENV)


# --- Infraestructura real (Principio VI): Postgres + pgvector, Redis y RabbitMQ ------------------

PG_IMAGE = "pgvector/pgvector:pg16"
REDIS_IMAGE = "redis:7-alpine"
RABBIT_IMAGE = "rabbitmq:3.13-management-alpine"


@pytest.fixture(scope="session")
def pg_container() -> Iterator[object]:
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(PG_IMAGE, username="reco", password="reco", dbname="recomendaciones") as pg:
        yield pg


@pytest.fixture(scope="session")
def pg_url(pg_container: object) -> str:
    url = pg_container.get_connection_url()  # type: ignore[attr-defined]
    return url.replace("postgresql+psycopg2://", "postgresql+psycopg://")


def alembic_config(url: str):  # noqa: ANN201 — alembic.config.Config
    from alembic.config import Config

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture(scope="session")
def redis_container() -> Iterator[object]:
    from testcontainers.community.redis import RedisContainer

    with RedisContainer(REDIS_IMAGE) as rc:
        yield rc


@pytest.fixture(scope="session")
def redis_url(redis_container: object) -> str:
    host = redis_container.get_container_host_ip()  # type: ignore[attr-defined]
    port = redis_container.get_exposed_port(6379)  # type: ignore[attr-defined]
    return f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def rabbit_container() -> Iterator[object]:
    from testcontainers.community.rabbitmq import RabbitMqContainer

    with RabbitMqContainer(RABBIT_IMAGE) as rc:
        yield rc


@pytest.fixture(scope="session")
def amqp_url(rabbit_container: object) -> str:
    host = rabbit_container.get_container_host_ip()  # type: ignore[attr-defined]
    port = rabbit_container.get_exposed_port(5672)  # type: ignore[attr-defined]
    return f"amqp://guest:guest@{host}:{port}/"


def fresh_database(pg_url: str, name: str) -> str:
    """Crea una base vacía y migrada; devuelve su URL."""
    import sqlalchemy as sa
    from alembic import command

    admin = sa.create_engine(pg_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        conn.execute(sa.text(f"CREATE DATABASE {name}"))
    admin.dispose()
    url = pg_url.rsplit("/", 1)[0] + f"/{name}"
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture
def db_factory(pg_url: str, request: pytest.FixtureRequest) -> Iterator[object]:
    """Base migrada por test, con la configuración v1 registrada como activa."""
    import re
    from datetime import UTC, datetime

    import sqlalchemy as sa

    from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
    from recomendaciones.storage.db.config_registry import register_in_database
    from recomendaciones.storage.db.session import session_factory

    name = "t_" + re.sub(r"[^a-z0-9]", "_", request.node.name.lower())[:50]
    url = fresh_database(pg_url, name)
    engine = sa.create_engine(url)
    factory = session_factory(engine)
    with factory.begin() as s:
        register_in_database(s, load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml"), datetime(2026, 9, 1, tzinfo=UTC))
    factory.url = url  # type: ignore[attr-defined]
    yield factory
    engine.dispose()


@pytest.fixture
def redis_client(redis_url: str) -> Iterator[object]:
    import redis

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def api(valid_env, db_factory, redis_client) -> Iterator[tuple[TestClient, object]]:  # noqa: ANN001
    """Devuelve (cliente HTTP, servicios) con la configuración v1 activa."""
    from recomendaciones.api.app import build_services, create_app
    from recomendaciones.config.settings import load_settings
    from recomendaciones.storage.cache.client import CacheClient

    settings = load_settings()
    services = build_services(settings, db_factory=db_factory, cache=CacheClient(redis_client))
    with TestClient(create_app(settings, services)) as client:
        yield client, services
