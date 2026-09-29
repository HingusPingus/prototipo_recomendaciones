"""Pila de API real para tests de contrato: Redis y Postgres de prueba, servicios inyectados."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CONTRACTS = Path(__file__).resolve().parents[2] / "specs" / "001-recomendaciones-precomputadas" / "contracts"


@pytest.fixture(scope="session")
def contract() -> dict:
    return yaml.safe_load((CONTRACTS / "recomendaciones-api.openapi.yaml").read_text(encoding="utf-8"))


def auth(valid_env: dict[str, str]) -> dict[str, str]:
    return {"X-Internal-API-Key": valid_env["RECO_INTERNAL_API_KEY"]}
