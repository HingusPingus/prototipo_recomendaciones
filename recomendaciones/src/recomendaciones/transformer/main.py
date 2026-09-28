"""Entrypoint del Data Transformer (`reco-transformer`)."""

from __future__ import annotations


def run() -> None:
    """Ejecuta una corrida de sincronización. Falla con error explícito si falta configuración."""
    from recomendaciones.config.bootstrap import settings_or_exit

    settings = settings_or_exit("transformer")
    from recomendaciones.observability.logging import configure_logging

    configure_logging("transformer", secrets=(settings.internal_api_key.get_secret_value(),))
    from recomendaciones.transformer.runtime import run_once

    raise SystemExit(run_once(settings))
