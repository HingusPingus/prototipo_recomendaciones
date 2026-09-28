"""Salud del worker (T041): Redis, Postgres y broker. Separado de `observability.health` para que la API
—que importa aquel módulo— no alcance clientes del broker (DI-9, T006)."""

from __future__ import annotations

import asyncio

from recomendaciones.observability.health import OK, UNAVAILABLE, HealthReport, check_postgres, check_redis
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.db.session import SessionFactory


def check_broker(amqp_url: str, timeout: float = 2.0) -> str:
    import aio_pika

    async def probe() -> str:
        connection = await asyncio.wait_for(aio_pika.connect(amqp_url), timeout)
        await connection.close()
        return OK

    try:
        return asyncio.run(probe())
    except Exception:  # noqa: BLE001
        return UNAVAILABLE


def worker_health(*, cache: CacheClient, factory: SessionFactory, amqp_url: str, config_version: str) -> HealthReport:
    checks = {"redis": check_redis(cache), "postgres": check_postgres(factory), "broker": check_broker(amqp_url)}
    return HealthReport("worker", config_version, checks, critical=("redis", "postgres", "broker"))


