"""T041 — health, readiness y liveness por servicio (FR-025d, FR-045, SC-023)."""

from __future__ import annotations

import socket

from fastapi.testclient import TestClient

from recomendaciones.api.app import build_services, create_app
from recomendaciones.config.settings import load_settings
from recomendaciones.observability.health import HealthReport, transformer_health
from recomendaciones.worker.health import worker_health
from recomendaciones.storage.cache.client import CacheClient

SECRET = "s3cr3t-0123456789abcdef"


def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_liveness_does_not_depend_on_redis_and_readiness_does(valid_env, db_factory) -> None:  # noqa: ANN001
    settings = load_settings()
    broken = CacheClient.from_url(f"redis://127.0.0.1:{_closed_port()}/0", timeout_seconds=0.3)
    with TestClient(create_app(settings, build_services(settings, db_factory=db_factory, cache=broken))) as client:
        assert client.get("/health/live").status_code == 200
        ready = client.get("/health/ready")
        assert ready.status_code == 503 and ready.json()["checks"]["redis"] == "unavailable"


def test_health_exposes_active_config_version_without_secrets(api, valid_env) -> None:  # noqa: ANN001
    client, services = api
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["checks"] == {"redis": "ok", "postgres": "ok"}
    health = client.get("/health")
    body = health.json()
    assert body["config_version"] == services.engine_config.config_version  # SC-023
    assert body["component"] == "api"
    for response in (health, ready, client.get("/health/live")):
        assert SECRET not in response.text and "postgresql" not in response.text and "redis://" not in response.text


def test_health_routes_are_public_and_nothing_else_is(api) -> None:  # noqa: ANN001
    client, _ = api
    for path in ("/health", "/health/live", "/health/ready"):
        assert client.get(path).status_code == 200  # sin API key


def test_worker_and_transformer_have_their_own_health(valid_env, db_factory, redis_client, amqp_url) -> None:  # noqa: ANN001
    cache = CacheClient(redis_client)
    worker = worker_health(cache=cache, factory=db_factory, amqp_url=amqp_url, config_version="sha256:v1")
    assert isinstance(worker, HealthReport)
    assert worker.checks == {"redis": "ok", "postgres": "ok", "broker": "ok"} and worker.ready
    down = worker_health(cache=cache, factory=db_factory, amqp_url=f"amqp://guest:guest@127.0.0.1:{_closed_port()}/", config_version="sha256:v1")
    assert down.checks["broker"] == "unavailable" and not down.ready
    transformer = transformer_health(factory=db_factory, config_version="sha256:v1")
    assert transformer.checks == {"postgres": "ok"} and transformer.ready
    assert "guest:guest" not in str(down.to_json())


def test_worker_health_server_answers_over_http(valid_env, db_factory, redis_client) -> None:  # noqa: ANN001
    import json
    import urllib.request

    from recomendaciones.observability.health import start_health_server

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    report = HealthReport("worker", "sha256:v1", {"redis": "ok", "postgres": "ok", "broker": "unavailable"}, critical=("redis", "postgres", "broker"))
    server = start_health_server(port, lambda: report)
    try:
        assert urllib.request.urlopen(f"http://127.0.0.1:{port}/health/live").status == 200
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health/ready")
            raise AssertionError("readiness debía ser 503 con el broker caído")
        except urllib.error.HTTPError as err:
            assert err.code == 503
        body = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health").read())
        assert body["config_version"] == "sha256:v1" and body["checks"]["broker"] == "unavailable"
    finally:
        server.shutdown()
