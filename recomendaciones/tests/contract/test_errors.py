"""T035 — errores tipados con códigos estables y sin rastros internos (FR-058, FR-065, T021)."""

from __future__ import annotations

import socket
import uuid

from fastapi.testclient import TestClient

from recomendaciones.api.app import build_services, create_app
from recomendaciones.config.settings import load_settings
from recomendaciones.storage.cache.client import CacheClient
from tests.contract.conftest import auth
from tests.integration import seed

URL = "/internal/v1/recommendations/{}"
LEAKS = ("Traceback", "sqlalchemy", "psycopg", "/home/", "File \"", "SELECT", "redis.exceptions")


def _no_leaks(text: str) -> None:
    assert not [leak for leak in LEAKS if leak in text], text


def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_401_422_404_412_codes_and_shapes(api, valid_env, db_factory) -> None:  # noqa: ANN001
    client, _ = api
    with db_factory.begin() as s:
        undeclared = seed.user(s)
    cases = [
        (client.get(URL.format(uuid.uuid4()), params={"module": "peliculas"}), 401, "unauthorized"),
        (client.get(URL.format(uuid.uuid4()), params={"module": "x"}, headers=auth(valid_env)), 422, "invalid_request"),
        (client.get(URL.format(uuid.uuid4()), params={"module": "juegos"}, headers=auth(valid_env)), 404, "unknown_user"),
        (client.get(URL.format(undeclared), params={"module": "juegos"}, headers=auth(valid_env)), 412, "declaration_required"),
    ]
    for response, status, code in cases:
        assert response.status_code == status
        assert set(response.json()) == {"error", "message"} and response.json()["error"] == code
        _no_leaks(response.text)


def test_redis_down_is_503_with_retry_after_never_200(valid_env, db_factory) -> None:  # noqa: ANN001
    settings = load_settings()
    broken = CacheClient.from_url(f"redis://127.0.0.1:{_closed_port()}/0", timeout_seconds=0.3)
    services = build_services(settings, db_factory=db_factory, cache=broken)
    with TestClient(create_app(settings, services)) as client:
        response = client.get(URL.format(uuid.uuid4()), params={"module": "peliculas"}, headers=auth(valid_env))
    assert response.status_code == 503
    assert int(response.headers["Retry-After"]) > 0
    assert response.json()["error"] == "cache_unavailable"
    _no_leaks(response.text)


def test_unhandled_exception_is_generic_500_without_trace(api, valid_env) -> None:  # noqa: ANN001
    client, services = api

    class Exploding:
        def read(self, *a: object, **k: object) -> None:
            raise RuntimeError('SELECT secret FROM users; File "/home/x/app.py", line 3')

    services.read_service = Exploding()
    with TestClient(client.app, raise_server_exceptions=False) as raw:
        response = raw.get(URL.format(uuid.uuid4()), params={"module": "peliculas"}, headers=auth(valid_env))
    assert response.status_code == 500
    assert response.json() == {"error": "internal_error", "message": "error interno"}
    _no_leaks(response.text)
