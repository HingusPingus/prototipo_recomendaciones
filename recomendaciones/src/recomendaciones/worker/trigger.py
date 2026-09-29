"""Disparador de recálculo por conteo de interacciones (T060, FR-080a, RD-104).

El contador **no se almacena** (RD-104): se cuentan las señales del usuario sobre ítems del módulo recibidas
después del `computed_at` del perfil de **ese** módulo (`idx_signals_user_received`). El conteo es por
(usuario, módulo) —el módulo es el del ítem de la señal—, y el reinicio es la consecuencia de reescribir el
perfil al recalcular. La consulta se acota al umbral: nunca cuenta más de lo necesario para decidir.

Al alcanzar el umbral, la invalidación ocurre **en el mismo acto** que la causa (FR-080), Redis primero
(FR-080c): se borran las entradas vigentes del par para **toda** versión de configuración —si quedara la de
una versión legible anterior, la lectura la serviría rotulada como vigente—. El top-N vive solo en Redis
(FR-080b): lo que se persiste son sus insumos.
"""

from __future__ import annotations

import sqlalchemy as sa

from recomendaciones.storage.cache.client import CacheClient, delete_user_scope
from recomendaciones.storage.db.session import SessionFactory
from recomendaciones.worker.schemas import ActualizarEvent

_COUNT_SQL = sa.text(
    """
    SELECT count(*) FROM (
        SELECT 1 FROM user_signals s JOIN items i ON i.id = s.item_id
        WHERE s.user_id = :user AND i.module = :module
          AND s.received_at > COALESCE(
              (SELECT max(computed_at) FROM user_profiles WHERE user_id = :user AND scope = CAST(:module AS text)::profile_scope),
              '-infinity'::timestamptz)
        LIMIT :threshold
    ) bounded
    """
)


class InteractionTrigger:
    def __init__(self, factory: SessionFactory, threshold: int, *, cache: CacheClient | None = None) -> None:
        self._factory = factory
        self._threshold = threshold
        self._cache = cache

    def pending(self, user_id, module: str) -> int:  # noqa: ANN001
        with self._factory() as s:
            return int(s.scalar(_COUNT_SQL, {"user": user_id, "module": module, "threshold": self._threshold}))

    def should_recompute(self, event: ActualizarEvent) -> bool:
        if self.pending(event.user_id, event.module.value) < self._threshold:
            return False
        if self._cache is not None:  # mismo acto que la causa, Redis primero
            delete_user_scope(self._cache, (f"reco:v*:{event.user_id}:{event.module.value}",))
        return True
