"""Idempotencia de **evento** por `event_id` (T024, FR-011, DI-6, §2.10, §7.10).

La marca vive en Redis (`dedupe:event:{id}`, `TTL_DEDUPE`) **y** en `processed_events`
(`expires_at` = retención configurable): perder Redis degrada latencia, no corrección (INV-2). Es un
nivel distinto de la idempotencia de **señal** por `origin_interaction_id` (DI-21, T064): esta protege
el recálculo; aquella, la ingesta. Tras expirar la marca, un duplicado tardío se reprocesa y el
resultado converge, porque la señal se deduplica y el recálculo es determinista (FR-069).
La marca se escribe solo si el trabajo terminó: un fallo no deja el evento «visto».
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.db.models import ProcessedEvent
from recomendaciones.storage.db.session import SessionFactory

_LOCK = sa.text("SELECT pg_advisory_lock(hashtextextended(:k, 0))")
_UNLOCK = sa.text("SELECT pg_advisory_unlock(hashtextextended(:k, 0))")


class EventIdempotency:
    def __init__(
        self, cache: CacheClient, factory: SessionFactory, *, ttl_dedupe_seconds: int, retention_hours: int
    ) -> None:
        self._cache = cache
        self._factory = factory
        self._ttl = ttl_dedupe_seconds
        self._retention = timedelta(hours=retention_hours)

    def seen(self, event_id: uuid.UUID) -> bool:
        if self._cache.exists(keys.dedupe_key(event_id)):
            return True
        with self._factory() as s:
            alive = s.scalar(
                sa.select(sa.literal(True)).where(
                    ProcessedEvent.event_id == event_id, ProcessedEvent.expires_at > sa.func.now()
                )
            )
        if alive:
            self._cache.set_json(keys.dedupe_key(event_id), 1, self._ttl)  # repone la copia caliente
            return True
        return False

    def record(self, event_id: uuid.UUID, result: str) -> None:
        with self._factory.begin() as s:
            now = sa.func.now()
            stmt = insert(ProcessedEvent).values(
                event_id=event_id, processed_at=now, result=result, expires_at=now + self._retention
            )
            s.execute(
                stmt.on_conflict_do_update(
                    index_elements=[ProcessedEvent.event_id],
                    set_={"processed_at": now, "result": result, "expires_at": now + self._retention},
                    where=ProcessedEvent.expires_at <= sa.func.now(),  # solo reemplaza una marca vencida
                )
            )
        self._cache.set_json(keys.dedupe_key(event_id), 1, self._ttl)

    def process_once(self, event_id: uuid.UUID, work: Callable[[], str]) -> str | None:
        """Ejecuta `work` una sola vez por evento vigente; `None` si ya estaba procesado (ACK sin recomputar).

        El consumidor procesa en paralelo: dos entregas simultáneas del mismo evento pasarían ambas el chequeo.
        Un advisory lock de Postgres por `event_id` hace atómicos chequeo, trabajo y registro; el acierto de
        la marca caliente en Redis no lo necesita.
        """
        if self._cache.exists(keys.dedupe_key(event_id)):
            return None
        lock = {"k": f"event:{event_id}"}
        with self._factory() as s:
            s.execute(_LOCK, lock)
            try:
                if self.seen(event_id):
                    return None
                result = work()
                self.record(event_id, result)
                return result
            finally:
                s.execute(_UNLOCK, lock)
