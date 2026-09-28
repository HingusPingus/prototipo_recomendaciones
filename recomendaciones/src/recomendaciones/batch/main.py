"""Entrypoint de los jobs batch (`reco-batch <job>`)."""

from __future__ import annotations

import sys


def run(argv: list[str] | None = None) -> None:
    """Ejecuta el job nombrado. Falla con error explícito si falta configuración."""
    from recomendaciones.config.settings import load_settings

    args = sys.argv[1:] if argv is None else argv
    settings = load_settings()
    from recomendaciones.batch.runtime import run_job

    raise SystemExit(run_job(settings, args))
