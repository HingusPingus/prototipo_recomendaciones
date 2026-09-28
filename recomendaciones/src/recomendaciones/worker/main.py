"""Entrypoint del worker (`reco-worker`)."""

from __future__ import annotations


def run() -> None:
    """Arranca el worker. Falla con error explícito si falta configuración (T001, FR-027)."""
    import asyncio

    from recomendaciones.config.bootstrap import settings_or_exit

    settings = settings_or_exit("worker")
    from recomendaciones.observability.logging import configure_logging

    configure_logging("worker", secrets=(settings.internal_api_key.get_secret_value(),))
    from recomendaciones.worker.runtime import serve

    asyncio.run(serve(settings))
