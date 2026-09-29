"""Persistencia de la señal que transporta cada `recomendacion.actualizar` (T064, FR-010, FR-029e, RD-95).

Reemplaza a la T036 retirada: `api-general` registra la actividad y publica el evento; este repositorio
la **proyecta**. Deduplica por `origin_interaction_id` (DI-21) con la comparación de §7.10: fila
idéntica ⟹ reentrega (se descarta y se cuenta); distinta ⟹ incumplimiento de contrato (FR-029e1), que
no se persiste y va a DLQ con su causa. En el mismo acto materializa la exclusión con el resolutor
(T014), que invalida `filters:{user}` antes de escribir: la exclusión es efectiva en la siguiente
lectura (RD-96). Usuario o ítem aún no materializados ⟹ `skipped_not_materialized`, sin reintento ni
DLQ: la sincronización traerá la interacción y la deduplicación impedirá contarla dos veces.
No llama a `api-general` ni publica eventos (INV-4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.errors import ContractViolation
from recomendaciones.storage.db.exclusions import ExclusionResolver, ResolveResult
from recomendaciones.storage.db.models import Item, User, UserSignal, UserSuppression
from recomendaciones.storage.db.session import SessionFactory
from recomendaciones.worker.schemas import ActualizarEvent

RECORDED, DUPLICATE, NOT_MATERIALIZED = "recorded", "duplicate", "skipped_not_materialized"


@dataclass(frozen=True, slots=True)
class IngestOutcome:
    status: str
    resolved: ResolveResult | None = None


class SignalIngestor:
    def __init__(self, factory: SessionFactory, resolver: ExclusionResolver, metrics: Metrics) -> None:
        self._factory = factory
        self._resolver = resolver
        self._metrics = metrics

    def persist(self, event: ActualizarEvent) -> IngestOutcome:
        with self._factory.begin() as s:
            suppressed = s.get(UserSuppression, event.user_id) is not None  # lápida (DI-29)
            user_ok = s.get(User, event.user_id) is not None
            item_ok = s.get(Item, event.item_id) is not None
            if suppressed or not (user_ok and item_ok):
                return IngestOutcome(NOT_MATERIALIZED)
            inserted = s.execute(
                insert(UserSignal)
                .values(
                    origin_interaction_id=event.origin_interaction_id,
                    user_id=event.user_id,
                    item_id=event.item_id,
                    signal_type=event.signal_type.value,
                    occurred_at=event.occurred_at,
                    source="evento",
                )
                .on_conflict_do_nothing(index_elements=[UserSignal.origin_interaction_id])
                .returning(UserSignal.id)
            ).scalar_one_or_none()
            if inserted is None:
                existing = s.execute(
                    sa.select(UserSignal.user_id, UserSignal.item_id, UserSignal.signal_type, UserSignal.occurred_at).where(
                        UserSignal.origin_interaction_id == event.origin_interaction_id
                    )
                ).one()
                same = (existing.user_id, existing.item_id, existing.signal_type, existing.occurred_at) == (
                    event.user_id,
                    event.item_id,
                    event.signal_type.value,
                    event.occurred_at,
                )
                if not same:
                    self._metrics.inc("contract_violations_total", field="origin_interaction_id")
                    raise ContractViolation(
                        "origin_interaction_id reutilizado para otro hecho: el origen emitió una transición con el "
                        "identificador anterior (FR-029e1)"
                    )
                self._metrics.inc("signal_duplicate_rejections_total", source="evento")
                return IngestOutcome(DUPLICATE)
            lag = (datetime.now(UTC) - event.occurred_at).total_seconds()
            self._metrics.observe("signal_ingest_lag_seconds", max(lag, 0.0), source="evento")
            resolved = self._resolver.resolve(s, {event.user_id})
        self._resolver.after_commit(resolved)
        return IngestOutcome(RECORDED, resolved)
