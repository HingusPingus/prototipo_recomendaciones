"""Entrypoint de la API (`reco-api`)."""

from __future__ import annotations


def run() -> None:
    """Arranca la API. Falla con error explícito si falta configuración (T001, FR-027)."""
    import uvicorn

    from recomendaciones.config.bootstrap import settings_or_exit

    settings = settings_or_exit("api")
    from recomendaciones.api.app import create_app

    uvicorn.run(create_app(settings), host=settings.api_host, port=settings.api_port)
