"""Versiones legibles tras un cambio de configuración (RD-103, FR-025c, SC-022). Función pura.

Legibles = desactivadas hace menos de `TTL_STALE` **con catálogo etario idéntico** al activo, de la
más nueva a la más vieja. Se calcula **al arrancar** (desde `engine_config_versions`, cuyo `payload`
guarda el catálogo), nunca por solicitud: la lectura sigue sin tocar Postgres. Una versión con otro
catálogo etario **nunca** es legible: su instantáneo etario pertenece a otra escala.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timedelta

from recomendaciones.config.loader import ConfigRow


def _catalog(row: ConfigRow) -> str:
    return json.dumps(row.payload.get("age_rating_catalog"), sort_keys=True)


def readable_versions(
    active: str, rows: Iterable[ConfigRow], *, ttl_stale_seconds: int, now: datetime
) -> tuple[str, ...]:
    rows = list(rows)
    by_version = {r.config_version: r for r in rows}
    if active not in by_version:
        return ()
    catalog = _catalog(by_version[active])
    horizon = now - timedelta(seconds=ttl_stale_seconds)
    eligible = [
        r
        for r in rows
        if r.config_version != active
        and r.deactivated_at is not None
        and r.deactivated_at > horizon
        and _catalog(r) == catalog
    ]
    eligible.sort(key=lambda r: (r.deactivated_at, r.config_version), reverse=True)
    return tuple(r.config_version for r in eligible)
