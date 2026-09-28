"""Traducción estable de errores a HTTP (T035, FR-058).

Toda respuesta de error tiene la forma `{"error": <código estable>, "message": <texto>}`. Ningún
cuerpo revela detalles internos (rutas, SQL, versiones de librerías), y ninguna excepción no
manejada escapa como `500` con traza. Redis caído ⟹ `503` con `Retry-After` (FR-065).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from recomendaciones.shared.errors import InvalidRequest, RecoError

log = logging.getLogger(__name__)

ERROR_RESPONSES: dict[int | str, dict] = {
    401: {"model": None, "description": "Sin credencial, inválida o de otro entorno"},
    404: {"description": "Usuario desconocido para el servicio"},
    409: {"description": "El módulo ya tiene declaración (definitiva)"},
    412: {"description": "Módulo sin declaración de gustos: precondición incumplida (FR-088)"},
    422: {"description": "Parámetros inválidos"},
    503: {"description": "Caché o filtros no disponibles; reintentable"},
}


def error_body(code: str, message: str) -> dict[str, str]:
    return {"error": code, "message": message}


def _reco_error(request: Request, exc: RecoError) -> JSONResponse:
    headers = {}
    retry_after = getattr(exc, "retry_after_seconds", None)
    if exc.http_status == 503 and retry_after:
        headers["Retry-After"] = str(retry_after)
        services = getattr(request.app.state, "services", None)
        if services is not None:
            services.metrics.inc("reco_unavailable_responses_total", error=exc.code)  # alerta RedisUnavailable503
    return JSONResponse(error_body(exc.code, exc.message), status_code=exc.http_status, headers=headers)


def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc")})
    message = "parámetros inválidos: " + ", ".join(fields) if fields else InvalidRequest.default_message
    return JSONResponse(error_body(InvalidRequest.code, message), status_code=422)


def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        body = exc.detail
    else:
        body = error_body("not_found" if exc.status_code == 404 else "http_error", "recurso no disponible")
    return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))


def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("error no manejado", exc_info=exc)
    return JSONResponse(error_body("internal_error", "error interno"), status_code=500)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RecoError, _reco_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _http_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled)
