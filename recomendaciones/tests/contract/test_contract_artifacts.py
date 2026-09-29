"""T049 — los artefactos de contrato existen, son válidos y declaran lo que la spec exige."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

CONTRACTS = Path(__file__).resolve().parents[2] / "specs" / "001-recomendaciones-precomputadas" / "contracts"


def _openapi(name: str) -> dict:
    return yaml.safe_load((CONTRACTS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["recomendaciones-api.openapi.yaml", "api-general-sync.openapi.yaml"])
def test_openapi_documents_are_valid(name: str) -> None:
    validate(_openapi(name))


def test_read_endpoint_contract() -> None:
    spec = _openapi("recomendaciones-api.openapi.yaml")
    op = spec["paths"]["/internal/v1/recommendations/{user_id}"]["get"]
    params = {p.get("name"): p for p in op["parameters"] if "name" in p}
    assert params["module"]["required"] is True
    assert (params["top_n"]["schema"]["minimum"], params["top_n"]["schema"]["maximum"]) == (10, 50)
    assert "limit" not in params and "cursor" not in params  # sin paginación (FR-005, RD-107)
    assert {"200", "401", "412", "422", "503"} <= set(op["responses"])
    result_types = spec["components"]["schemas"]["ResultType"]["enum"]
    assert sorted(result_types) == sorted(
        ["empty_pending", "empty_no_candidates", "fallback", "personalized_stale", "personalized"]
    )
    assert "declaration_required" not in result_types  # FR-088: no es un sexto estado
    response = spec["components"]["schemas"]["RecommendationResponse"]
    assert "stale_available" in response["required"] and "next_cursor" not in response["properties"]


def test_declaration_endpoint_contract() -> None:
    op = _openapi("recomendaciones-api.openapi.yaml")["paths"]["/internal/v1/declarations/{user_id}"]["post"]
    assert {"201", "409", "422"} <= set(op["responses"])


def _schema(name: str) -> dict:
    schema = json.loads((CONTRACTS / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def test_event_schema_requires_the_seven_fields_of_fr061() -> None:
    assert set(_schema("recomendacion-actualizar.schema.json")["required"]) == {
        "event_id", "origin_interaction_id", "user_id", "module", "item_id", "signal_type", "occurred_at"
    }


def test_deletion_event_schema() -> None:
    assert set(_schema("usuario-eliminado.schema.json")["required"]) == {"event_id", "user_id", "occurred_at"}


def test_readme_declares_custody_and_pending_publication() -> None:
    readme = (CONTRACTS / "README.md").read_text(encoding="utf-8")
    assert "Custodio: `api-general`" in readme and "copias derivadas" in readme
    for name in ("recomendaciones-api.openapi.yaml", "recomendacion-actualizar.schema.json", "usuario-eliminado.schema.json"):
        assert name in readme
