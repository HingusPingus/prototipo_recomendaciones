"""Errores de configuración: impiden el arranque en lugar de aplicar defaults silenciosos (FR-027)."""

from __future__ import annotations


class ConfigurationError(RuntimeError):
    """Configuración ausente, malformada o inconsistente. El componente no arranca."""
