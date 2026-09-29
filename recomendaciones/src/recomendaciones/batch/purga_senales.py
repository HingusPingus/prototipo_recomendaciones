"""Purga de señales por retención con guarda de exclusión (T057, FR-068…FR-068d1, `data-model.md` §7.10).

Única rutina, junto con la supresión (T058), autorizada a borrar filas de `user_signals` (FR-068e). El
procedimiento es el de §7.10, en su orden:

1. Una señal de `consumo` se purga solo si su exclusión ya está materializada con `origin = 'consumo'`
   (FR-068c). La guarda vive **dentro** del `DELETE`: no hay ventana entre verificarla y borrar. Las que
   no la cumplen se difieren al ciclo siguiente y se cuentan en `signals_purge_deferred_total`.
2. Se purgan las señales cuyo `occurred_at` supera `signal_retention_days` —la antigüedad del hecho, la
   misma marca con la que la popularidad define su ventana—.
3. `user_exclusions` no se toca: no tiene FK hacia `user_signals` y la reconstrucción es aditiva (DI-20).

La retención no tiene default: llega de la configuración operativa y el arranque falla si no supera
estrictamente las tres ventanas de FR-068b (RD-110). Cada corrida registra el valor vigente, para que una
reducción no aprobada sea detectable después (RD-54). Además purga `processed_events` vencidos
(`expires_at`, §2.10), que ninguna otra tarea consumía.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from recomendaciones.config.loader import EngineConfig, OperationalWindows, validate_operational_windows
from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.db.session import SessionFactory

log = logging.getLogger(__name__)

_MATERIALIZED = """
    EXISTS (SELECT 1 FROM user_exclusions e
            WHERE e.user_id = s.user_id AND e.item_id = s.item_id AND e.origin = 'consumo')
"""

_DEFERRED_SQL = sa.text(
    f"SELECT count(*) FROM user_signals s WHERE s.occurred_at < :cutoff AND s.signal_type = 'consumo' AND NOT {_MATERIALIZED}"
)

_PURGE_SQL = sa.text(
    f"""
    DELETE FROM user_signals WHERE id IN (
        SELECT s.id FROM user_signals s
        WHERE s.occurred_at < :cutoff AND (s.signal_type <> 'consumo' OR {_MATERIALIZED})
        ORDER BY s.id
        LIMIT :batch
    )
    """
)

_ORPHANED_SQL = sa.text(
    """
    SELECT count(*) FROM user_exclusions e
    WHERE e.origin = 'consumo' AND NOT EXISTS (
        SELECT 1 FROM user_signals s
        WHERE s.user_id = e.user_id AND s.item_id = e.item_id AND s.signal_type = 'consumo'
    )
    """
)

_EXPIRED_EVENTS_SQL = sa.text("DELETE FROM processed_events WHERE expires_at < :now")


@dataclass(frozen=True, slots=True)
class PurgeReport:
    retention_days: int
    cutoff: datetime
    purged: int
    deferred: int
    orphaned_permanent: int
    processed_events_purged: int


class SignalPurgeJob:
    def __init__(
        self,
        factory: SessionFactory,
        config: EngineConfig,
        windows: OperationalWindows,
        metrics: Metrics,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        batch_size: int = 10_000,
    ) -> None:
        validate_operational_windows(config, windows)  # FR-068b: el arranque falla nombrando la ventana
        self._factory = factory
        self._retention_days = windows.signal_retention_days
        self.metrics = metrics
        self._now = now
        self._batch = batch_size

    def run(self) -> PurgeReport:
        now = self._now()
        cutoff = now - timedelta(days=self._retention_days)
        log.info(
            "purga de señales: inicio",
            extra={"reco_signal_retention_days": self._retention_days, "reco_cutoff": cutoff.isoformat()},
        )
        with self._factory() as s:
            deferred = int(s.execute(_DEFERRED_SQL, {"cutoff": cutoff}).scalar_one())
        purged = 0
        while True:  # por lotes: cada lote es su propia transacción y no retiene la tabla entera
            with self._factory.begin() as s:
                n = s.execute(_PURGE_SQL, {"cutoff": cutoff, "batch": self._batch}).rowcount
            purged += n
            if n < self._batch:
                break
        with self._factory.begin() as s:
            events = s.execute(_EXPIRED_EVENTS_SQL, {"now": now}).rowcount
        with self._factory() as s:
            orphaned = int(s.execute(_ORPHANED_SQL).scalar_one())
        if deferred:
            self.metrics.inc("signals_purge_deferred_total", deferred)
            log.warning("purga de señales: consumos diferidos sin exclusión materializada (FR-068c)", extra={"reco_deferred": deferred})
        self.metrics.set("exclusions_orphaned_permanent_total", orphaned)
        report = PurgeReport(self._retention_days, cutoff, purged, deferred, orphaned, events)
        log.info(
            "purga de señales: fin",
            extra={
                "reco_signal_retention_days": self._retention_days,
                "reco_purged": purged,
                "reco_deferred": deferred,
                "reco_orphaned_permanent": orphaned,
                "reco_processed_events_purged": events,
            },
        )
        return report
