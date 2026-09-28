"""Manejador de `recomendacion.actualizar` (T024 + T064 + T027; umbral de FR-080a con T060).

1. Idempotencia de evento por `event_id` (T024): un evento vigente ya procesado se confirma sin recalcular.
2. Persistencia de la señal y su exclusión (T064).
3. Si corresponde recalcular —umbral de interacciones por (usuario, módulo), FR-080a—, recálculo del
   módulo de la actividad y, si algún tag del ítem es compartido, del opuesto (T027, FR-010a).
4. Registro del resultado en `processed_events` (auditoría accionable de FR-010c).

Un crash entre 2 y 4 hace que el evento se reentregue: la señal se deduplica y el recálculo converge.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from recomendaciones.worker.idempotency import EventIdempotency
from recomendaciones.worker.schemas import ActualizarEvent
from recomendaciones.worker.signals import NOT_MATERIALIZED, SignalIngestor


class RecomputeOnSignal(Protocol):
    def on_signal(self, event: ActualizarEvent) -> str: ...


class ActualizarHandler:
    def __init__(
        self,
        *,
        idempotency: EventIdempotency,
        ingestor: SignalIngestor,
        should_recompute: Callable[[ActualizarEvent], bool],
        recompute: RecomputeOnSignal,
    ) -> None:
        self._idempotency = idempotency
        self._ingestor = ingestor
        self._should_recompute = should_recompute
        self._recompute = recompute

    def _work(self, event: ActualizarEvent) -> str:
        outcome = self._ingestor.persist(event)
        if outcome.status == NOT_MATERIALIZED:
            return "skipped_not_materialized"
        if not self._should_recompute(event):
            return "signal_recorded"  # umbral de FR-080a no alcanzado (RD-95)
        return self._recompute.on_signal(event)

    def __call__(self, event: ActualizarEvent) -> str:
        result = self._idempotency.process_once(event.event_id, lambda: self._work(event))
        return "duplicate" if result is None else result
