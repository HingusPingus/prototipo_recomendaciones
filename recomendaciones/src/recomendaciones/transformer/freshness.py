"""Métricas de frescura y del catálogo materializado, derivadas de la base (T031, §7.7, §7.12).

El Data Transformer es un proceso de una corrida: sus métricas mueren con él. Para que la antigüedad de
la última sincronización exitosa esté disponible el 100 % del tiempo (SC-014), cualquier proceso de larga
vida (el worker) las recalcula periódicamente con esta función, sobre índices dedicados.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from recomendaciones.observability.metrics import Metrics

_LAST_SUCCESS = sa.text("SELECT max(finished_at) FROM sync_runs WHERE status = 'success'")
_CATALOG = sa.text(
    """
    SELECT count(*) FILTER (WHERE status = 'available') AS live,
           count(*) FILTER (WHERE status = 'available' AND age_rating_source = 'unknown_defaulted') AS unrated,
           count(*) FILTER (WHERE status = 'retired') AS retired
    FROM items
    """
)
# Señales cuyo par (usuario, ítem) todavía no tiene exclusión materializada (§7.12): toda señal excluye.
_UNRESOLVED = sa.text(
    """
    SELECT min(s.received_at) FROM user_signals s
    WHERE NOT EXISTS (SELECT 1 FROM user_exclusions e WHERE e.user_id = s.user_id AND e.item_id = s.item_id)
    """
)


def refresh_sync_metrics(s: Session, metrics: Metrics) -> None:
    last = s.scalar(_LAST_SUCCESS)
    if last is not None:
        metrics.set("catalog_sync_last_success_timestamp", last.timestamp())
    live, unrated, retired = s.execute(_CATALOG).one()
    metrics.set("catalog_unrated_ratio", (unrated / live) if live else 0.0)
    metrics.set("catalog_retired_total", float(retired))
    oldest = s.scalar(_UNRESOLVED)
    metrics.set("exclusion_resolve_lag_seconds", max((datetime.now(UTC) - oldest).total_seconds(), 0.0) if oldest else 0.0)
