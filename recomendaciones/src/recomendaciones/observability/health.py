"""Salud por proceso (T041, FR-045): liveness sin dependencias; readiness con las dependencias críticas.

- API: Redis (Postgres informativo: solo se usa ante miss de `filters:`/`retired:` y para declarar).
- Worker: Redis, Postgres y broker.
- Data Transformer: Postgres.

Todos exponen la `config_version` activa (FR-025d, SC-023). Ningún reporte incluye cadenas de conexión,
credenciales ni detalles de la excepción: solo `ok` / `unavailable` por dependencia.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import sqlalchemy as sa

from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.db.session import SessionFactory

OK, UNAVAILABLE = "ok", "unavailable"


@dataclass
class HealthReport:
    component: str
    config_version: str
    checks: dict[str, str] = field(default_factory=dict)
    critical: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return all(self.checks.get(name) == OK for name in self.critical)

    def to_json(self) -> dict[str, object]:
        return {
            "status": "ok" if self.ready else "unavailable",
            "component": self.component,
            "config_version": self.config_version,
            "checks": dict(self.checks),
        }


def check_redis(cache: CacheClient) -> str:
    try:
        return OK if cache.ping() else UNAVAILABLE
    except Exception:  # noqa: BLE001 — el detalle no se expone
        return UNAVAILABLE


def check_postgres(factory: SessionFactory) -> str:
    try:
        with factory() as s:
            s.execute(sa.text("SELECT 1"))
        return OK
    except Exception:  # noqa: BLE001
        return UNAVAILABLE


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


def api_health(*, cache: CacheClient, factory: SessionFactory, config_version: str) -> HealthReport:
    return HealthReport("api", config_version, {"redis": check_redis(cache), "postgres": check_postgres(factory)}, critical=("redis",))


def worker_health(*, cache: CacheClient, factory: SessionFactory, amqp_url: str, config_version: str) -> HealthReport:
    checks = {"redis": check_redis(cache), "postgres": check_postgres(factory), "broker": check_broker(amqp_url)}
    return HealthReport("worker", config_version, checks, critical=("redis", "postgres", "broker"))


def transformer_health(*, factory: SessionFactory, config_version: str) -> HealthReport:
    return HealthReport("transformer", config_version, {"postgres": check_postgres(factory)}, critical=("postgres",))


def start_health_server(port: int, report: callable) -> object:  # type: ignore[valid-type]
    """Servidor HTTP mínimo de salud para procesos sin API (worker): /health/live, /health/ready, /health."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health/live":
                status, body = 200, {"status": "ok"}
            elif self.path in ("/health/ready", "/health"):
                current: HealthReport = report()
                body = current.to_json()
                status = 200 if (self.path == "/health" or current.ready) else 503
            else:
                status, body = 404, {"error": "not_found"}
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: object) -> None:
            return None

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
