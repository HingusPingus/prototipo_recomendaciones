"""T002 — el rechazo devuelve 401 genérico, sin revelar si la key es inválida o de otro entorno."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from recomendaciones.api.deps import API_KEY_HEADER, require_api_key
from recomendaciones.config.settings import load_settings


def _client() -> TestClient:
    app = FastAPI()
    app.state.settings = load_settings()

    @app.get("/protegido", dependencies=[Depends(require_api_key)])
    def protegido() -> dict[str, str]:
        return {"ok": "si"}

    return TestClient(app)


def test_rejections_are_indistinguishable(valid_env: dict[str, str]) -> None:
    client = _client()
    missing = client.get("/protegido")
    invalid = client.get("/protegido", headers={API_KEY_HEADER: "test.otra-clave-cualquiera-xx"})
    other_env = client.get("/protegido", headers={API_KEY_HEADER: "prod.s3cr3t-0123456789abcdef"})
    assert missing.status_code == invalid.status_code == other_env.status_code == 401
    assert missing.json() == invalid.json() == other_env.json()
    assert "s3cr3t" not in missing.text


def test_valid_key_passes(valid_env: dict[str, str]) -> None:
    ok = _client().get("/protegido", headers={API_KEY_HEADER: valid_env["RECO_INTERNAL_API_KEY"]})
    assert ok.status_code == 200
