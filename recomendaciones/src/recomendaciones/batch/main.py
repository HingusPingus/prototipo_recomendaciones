"""Entrypoint de los jobs batch (`reco-batch <job>`)."""

from __future__ import annotations

import sys


def run(argv: list[str] | None = None) -> None:
    """Ejecuta el job nombrado. Falla con error explícito si falta configuración."""
    from recomendaciones.config.bootstrap import settings_or_exit

    args = sys.argv[1:] if argv is None else argv
    settings = settings_or_exit("batch")
    from recomendaciones.observability.logging import configure_logging

    configure_logging("batch", secrets=(settings.internal_api_key.get_secret_value(),))
    from recomendaciones.batch.runtime import run_job

    raise SystemExit(run_job(settings, args))
