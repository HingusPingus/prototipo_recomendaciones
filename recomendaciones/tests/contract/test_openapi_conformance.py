"""T049/T033 — el OpenAPI que genera la aplicación es compatible con el contrato publicado.

Falla si una ruta, un método, un código de estado o un campo requerido de la respuesta divergen.
La implementación se ajusta al contrato, nunca al revés.
"""

from __future__ import annotations

import pytest

OPERATIONS = [("/internal/v1/recommendations/{user_id}", "get"), ("/internal/v1/declarations/{user_id}", "post")]


def _resolve(schema: dict, spec: dict) -> dict:
    while "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = spec["components"]["schemas"][name]
    return schema


@pytest.mark.parametrize(("path", "method"), OPERATIONS)
def test_operation_conforms(api, contract, path: str, method: str) -> None:  # noqa: ANN001
    client, _ = api
    generated = client.app.openapi()
    assert path in generated["paths"], f"falta la ruta {path}"
    ours, theirs = generated["paths"][path][method], contract["paths"][path][method]
    assert set(ours["responses"]) == set(theirs["responses"]), "códigos de estado divergentes"
    ok = next(code for code in theirs["responses"] if code.startswith("2"))
    their_schema = _resolve(theirs["responses"][ok]["content"]["application/json"]["schema"], contract)
    our_schema = _resolve(ours["responses"][ok]["content"]["application/json"]["schema"], generated)
    assert set(our_schema.get("required", [])) == set(their_schema.get("required", []))
    their_params = {(p["name"], p["in"], p.get("required", False)) for p in theirs["parameters"] if "name" in p}
    our_params = {(p["name"], p["in"], p.get("required", False)) for p in ours.get("parameters", [])}
    assert their_params <= our_params, "parámetros del contrato ausentes o con otra obligatoriedad"
