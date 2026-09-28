"""Esquema de claves Redis — las ocho familias de data-model.md §3.1 (T018).

Las claves se construyen **solo** por estas funciones tipadas: no hay concatenación ad hoc. Toda clave
de recomendación lleva usuario y módulo (DI-5), y `config_version` va en la clave de `reco:`,
`reco:stale:` y `fallback:` (RD-36, hallazgo F3), de modo que resultados de versiones distintas
coexisten sin colisionar y el cambio de configuración no exige invalidación masiva (SC-022).
"""

from __future__ import annotations

import uuid

from recomendaciones.shared.domain import Module

RECOMPUTE_STREAM = "recompute:requests"
RECOMPUTE_GROUP = "recompute-workers"

FAMILIES = (
    "reco:",
    "reco:stale:",
    "filters:",
    "fallback:",
    "retired:",
    "recompute:lock:",
    "dedupe:event:",
    RECOMPUTE_STREAM,
)


def _module(module: Module | str) -> str:
    if module is None:
        raise TypeError("la clave exige un módulo (DI-5)")
    return Module(module).value


def reco_key(config_version: str, user_id: uuid.UUID, module: Module | str) -> str:
    return f"reco:v{config_version}:{user_id}:{_module(module)}"


def stale_key(config_version: str, user_id: uuid.UUID, module: Module | str) -> str:
    return f"reco:stale:v{config_version}:{user_id}:{_module(module)}"


def filters_key(user_id: uuid.UUID) -> str:
    return f"filters:{user_id}"


def fallback_key(config_version: str, module: Module | str) -> str:
    return f"fallback:v{config_version}:{_module(module)}"


def retired_key(module: Module | str) -> str:
    return f"retired:{_module(module)}"


def lock_key(user_id: uuid.UUID, module: Module | str) -> str:
    return f"recompute:lock:{user_id}:{_module(module)}"


def dedupe_key(event_id: uuid.UUID) -> str:
    return f"dedupe:event:{event_id}"


def user_scoped_patterns(user_id: uuid.UUID) -> tuple[str, ...]:
    """Patrones de las cuatro familias de alcance de usuario, para toda versión y módulo (§7.11)."""
    return (
        f"filters:{user_id}",
        f"reco:v*:{user_id}:*",
        f"reco:stale:v*:{user_id}:*",
        f"recompute:lock:{user_id}:*",
    )
