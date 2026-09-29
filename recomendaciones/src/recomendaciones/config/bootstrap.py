"""Arranque común de los procesos: configuración ausente ⟹ salida explícita, sin traceback (T001)."""

from __future__ import annotations

import sys

from recomendaciones.config.errors import ConfigurationError
from recomendaciones.config.settings import Settings, load_settings


def settings_or_exit(component: str) -> Settings:
    try:
        return load_settings()
    except ConfigurationError as exc:
        print(f"[{component}] no arranca: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
