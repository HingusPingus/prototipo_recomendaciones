"""T034 — API key interna y no alcanzabilidad desde frontends (FR-007, FR-008, FR-059, FR-060, SC-012)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml
from fastapi.routing import APIRoute
from starlette.routing import Route

from recomendaciones.api.deps import require_api_key

ROOT = Path(__file__).resolve().parents[2]
URL = f"/internal/v1/recommendations/{uuid.uuid4()}?module=peliculas"


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Internal-API-Key": "test.otra-clave-cualquiera-xx"}, {"X-Internal-API-Key": "prod.s3cr3t-0123456789abcdef"}, {"X-Internal-API-Key": ""}],
    ids=["sin-key", "invalida", "otro-entorno", "vacia"],
)
def test_key_matrix_gives_identical_401(api, headers) -> None:  # noqa: ANN001
    client, _ = api
    response = client.get(URL, headers=headers)
    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized", "message": "credencial de servicio inválida"}


def test_every_route_requires_the_key_except_health(api) -> None:  # noqa: ANN001
    """FR-060: ninguna ruta pública fuera de salud (incluye documentación y OpenAPI)."""
    client, _ = api
    unprotected = []
    for route in client.app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/health"):
            continue
        if isinstance(route, APIRoute):
            deps = {d.call for d in route.dependant.dependencies}
            if require_api_key not in deps:
                unprotected.append(path)
        elif isinstance(route, Route):
            unprotected.append(path)  # rutas de Starlette sin dependencias (p. ej. /openapi.json, /docs)
    assert unprotected == [], f"rutas alcanzables sin API key: {unprotected}"


def test_openapi_and_docs_are_not_exposed(api) -> None:  # noqa: ANN001
    client, _ = api
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert client.get(path).status_code in (401, 404)


def test_network_restriction_is_declared_and_auditable() -> None:
    """La inalcanzabilidad se hace cumplir por red y es verificable por máquina (FR-060, SC-012)."""
    policy = yaml.safe_load((ROOT / "ops" / "network-policy.yaml").read_text(encoding="utf-8"))
    assert policy["kind"] == "NetworkPolicy"
    spec = policy["spec"]
    assert "Ingress" in spec["policyTypes"]
    sources = [src for rule in spec["ingress"] for src in rule["from"]]
    labels = [s.get("podSelector", {}).get("matchLabels", {}) for s in sources]
    assert labels and all(label.get("app") in {"api-general"} for label in labels), labels
    assert not any("ipBlock" in s for s in sources), "ningún bloque de IP externo (frontends, internet)"
