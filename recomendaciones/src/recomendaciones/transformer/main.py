"""Entrypoint del Data Transformer (`reco-transformer`)."""

from __future__ import annotations


def run() -> None:
    """Ejecuta una corrida de sincronización. Falla con error explícito si falta configuración."""
    from recomendaciones.config.settings import load_settings

    settings = load_settings()
    from recomendaciones.transformer.runtime import run_once

    raise SystemExit(run_once(settings))
