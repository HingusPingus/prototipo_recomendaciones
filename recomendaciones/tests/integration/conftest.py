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
    from testcontainers.postgres import PostgresContainer

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
    from testcontainers.redis import RedisContainer

    with RedisContainer(REDIS_IMAGE) as rc:
        yield rc


@pytest.fixture(scope="session")
def redis_url(redis_container: object) -> str:
    host = redis_container.get_container_host_ip()  # type: ignore[attr-defined]
    port = redis_container.get_exposed_port(6379)  # type: ignore[attr-defined]
    return f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def rabbit_container() -> Iterator[object]:
    from testcontainers.rabbitmq import RabbitMqContainer

    with RabbitMqContainer(RABBIT_IMAGE) as rc:
        yield rc


@pytest.fixture(scope="session")
def amqp_url(rabbit_container: object) -> str:
    host = rabbit_container.get_container_host_ip()  # type: ignore[attr-defined]
    port = rabbit_container.get_exposed_port(5672)  # type: ignore[attr-defined]
    return f"amqp://guest:guest@{host}:{port}/"
