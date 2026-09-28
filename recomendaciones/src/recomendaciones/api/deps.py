"""Dependencias de la API: autenticación por API key interna (T002, T034)."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

API_KEY_HEADER = "X-Internal-API-Key"

# Un único cuerpo para toda falla de autenticación: ausente, inválida o de otro entorno
# producen la misma respuesta, de modo que el endpoint no es un oráculo (FR-059, T034).
UNAUTHORIZED_DETAIL = {"error": "unauthorized", "message": "credencial de servicio inválida"}


def require_api_key(request: Request, x_internal_api_key: str | None = Header(default=None)) -> None:
    settings = request.app.state.settings
    if not settings.verify_api_key(x_internal_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_DETAIL)
