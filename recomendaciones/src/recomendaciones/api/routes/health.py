"""Rutas de salud: las únicas públicas de la API (FR-060, T034). Sin secretos ni detalles internos."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from recomendaciones.observability.health import api_health

router = APIRouter()


@router.get("/health/live", operation_id="liveness")
def live(request: Request) -> dict[str, str]:
    return {"status": "ok", "component": "api"}  # sin dependencias: el proceso vive


def _report(request: Request):  # noqa: ANN202
    services = request.app.state.services
    return api_health(cache=services.cache, factory=services.db_factory, config_version=services.engine_config.config_version)


@router.get("/health/ready", operation_id="readiness")
def ready(request: Request) -> JSONResponse:
    report = _report(request)
    return JSONResponse(report.to_json(), status_code=200 if report.ready else 503)


@router.get("/health", operation_id="health")
def health(request: Request) -> dict[str, object]:
    return _report(request).to_json()
