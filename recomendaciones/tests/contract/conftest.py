"""Pila de API real para tests de contrato: Redis y Postgres de prueba, servicios inyectados."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

CONTRACTS = Path(__file__).resolve().parents[2] / "specs" / "001-recomendaciones-precomputadas" / "contracts"


@pytest.fixture(scope="session")
def contract() -> dict:
    return yaml.safe_load((CONTRACTS / "recomendaciones-api.openapi.yaml").read_text(encoding="utf-8"))


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


def auth(valid_env: dict[str, str]) -> dict[str, str]:
    return {"X-Internal-API-Key": valid_env["RECO_INTERNAL_API_KEY"]}
