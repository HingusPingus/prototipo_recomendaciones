"""Re-exposición en el worker de las métricas de los procesos de una corrida (T066, §2.17).

Transformer y jobs batch terminan sin exponer servidor; cada corrida deja lo que fijó en `process_runs`. El
worker, que sí expone, lo publica en el mismo ciclo de 30 s de la frescura del catálogo (SC-014):

- **Gauges**: el último valor conocido de cada serie, sin importar cuándo se fijó. Un job que dejó de correr
  conserva su último timestamp y su alerta de vencimiento puede dispararse.
- **Contadores e histogramas**: los incrementos y observaciones de las corridas terminadas desde que este
  worker arrancó, más las de la última `lookback` (1 h, la ventana de las alertas por `increase`). Un
  worker reiniciado no re-aplica la historia entera: Prometheus ve un reinicio del contador, no un salto
  espurio que dispararía alertas por incrementos ya observados.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from recomendaciones.observability.metrics import SPECS, Metrics

# Series que el worker ya calcula desde la base por su cuenta (§7.7, FR-095a, FR-025d): no se pisan con el
# valor que un proceso fijó en su corrida.
WORKER_DERIVED = frozenset(
    {
        "catalog_sync_last_success_timestamp",
        "catalog_unrated_ratio",
        "catalog_retired_total",
        "exclusion_resolve_lag_seconds",
        "suppressions_unverified_total",
        "reco_active_config_version",
    }
)

_ALL = sa.text("SELECT metrics FROM process_runs ORDER BY id")
_RECENT = sa.text("SELECT id, metrics FROM process_runs WHERE finished_at >= now() - make_interval(secs => :secs) ORDER BY id")
_AFTER = sa.text("SELECT id, metrics FROM process_runs WHERE id > :last ORDER BY id")
_MAX_ID = sa.text("SELECT max(id) FROM process_runs")


@dataclass
class ProcessMetricsState:
    """Hasta qué corrida ya se aplicaron contadores e histogramas en este worker."""

    last_id: int | None = None
    lookback: timedelta = timedelta(hours=1)


def _known(name: str) -> bool:
    return name in SPECS and name not in WORKER_DERIVED


def refresh_process_metrics(s: Session, metrics: Metrics, state: ProcessMetricsState) -> None:
    latest: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
    for (data,) in s.execute(_ALL):
        for name, labels, value in data.get("gauges", []):
            if _known(name):
                latest[(name, tuple(sorted(labels.items())))] = value
    for (name, labels), value in latest.items():
        metrics.set(name, value, **dict(labels))

    if state.last_id is None:
        rows = s.execute(_RECENT, {"secs": state.lookback.total_seconds()}).all()
        state.last_id = s.scalar(_MAX_ID) or 0
    else:
        rows = s.execute(_AFTER, {"last": state.last_id}).all()
    for run_id, data in rows:
        for name, labels, amount in data.get("counters", []):
            if _known(name) and amount > 0:
                metrics.inc(name, amount, **labels)
        for name, labels, values in data.get("histograms", []):
            if _known(name):
                for value in values:
                    metrics.observe(name, value, **labels)
        state.last_id = max(state.last_id, run_id)


__all__ = ["WORKER_DERIVED", "ProcessMetricsState", "refresh_process_metrics"]
