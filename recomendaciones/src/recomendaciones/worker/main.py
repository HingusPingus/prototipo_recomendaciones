"""Entrypoint del worker (`reco-worker`)."""

from __future__ import annotations


def run() -> None:
    """Arranca el worker. Falla con error explícito si falta configuración (T001, FR-027)."""
    import asyncio

    from recomendaciones.config.bootstrap import settings_or_exit

    settings = settings_or_exit("worker")
    from recomendaciones.worker.runtime import serve

    asyncio.run(serve(settings))
