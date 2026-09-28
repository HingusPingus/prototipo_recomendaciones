"""Infraestructura real para integración (Principio VI): Postgres + pgvector, Redis y RabbitMQ.

Los contenedores se levantan una vez por sesión; cada test que escribe limpia lo suyo.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PG_IMAGE = "pgvector/pgvector:pg16"
REDIS_IMAGE = "redis:7-alpine"
RABBIT_IMAGE = "rabbitmq:3.13-management-alpine"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/integration" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.integration)


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
