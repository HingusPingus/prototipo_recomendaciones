"""Supresión de usuario a pedido, verificada (T058, T059, `data-model.md` §7.11, FR-091…FR-095a).

La dispara el evento de baja de cuenta que publica `api-general` (CR-19, DEP-12, RD-101), con idempotencia
por `event_id`. El procedimiento, en su orden:

0. **Recepción** (FR-095b, RD-115): apenas el evento pasa el schema, en una transacción propia, la fila de
   `user_suppressions` con `event_id`, `received_at` y la marca `in_progress`. Es el checkpoint de entrega que
   consulta `api-general`. No borra ni reemplaza datos, así que no contradice «Redis primero» (FR-080c); otra
   baja del mismo usuario conserva la primera recepción.
1. **Redis primero** (FR-080c): las cuatro familias de alcance de usuario —`filters:`, `reco:`, `reco:stale:`
   y `recompute:lock:`— para **toda** versión y módulo, y las entradas del usuario en `recompute:requests`.
2. y 3. En una transacción: la **marca** (`user_suppressions`, `state = 'in_progress'`) y el borrado de la
   fila de `users`, cuyo `CASCADE` alcanza `user_profiles`, `user_signals`, `user_exclusions` y
   `user_declared_tags`. El recálculo consulta la marca inmediatamente antes y después de escribir
   (`Recomputer`, FR-092a): una corrida en vuelo se aborta en lugar de esperarse.
4. **Verificación** de las cinco tablas, las claves y el Stream, leídos en el acto —nunca se delega en un
   TTL (FR-091)—. Con residuo, se limpia de nuevo y se reverifica con backoff exponencial, hasta
   `max_attempts` verificaciones (`attempts`).
5. **Constancia** (FR-095): sin residuo, `verified_at` y `state = 'completed'`. Agotados los intentos,
   `state = 'failed'` —el fallido visible de FR-095a— y `user_deletion_residual_keys_total`, con alerta.

La fila queda como lápida con solo identificador y marcas temporales: la sincronización no rematerializa ese
`user_id` (DI-29). `retired:` y `fallback:` no se tocan: no llevan `user_id` (§3.1). El barrido
(`reco-batch suppressions`) retoma las supresiones trabadas o fallidas.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from redis.exceptions import ResponseError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient, delete_user_scope
from recomendaciones.storage.db.models import User, UserDeclaredTag, UserExclusion, UserProfile, UserSignal, UserSuppression
from recomendaciones.storage.db.session import SessionFactory
from recomendaciones.worker.idempotency import EventIdempotency
from recomendaciones.worker.schemas import EliminadoEvent

log = logging.getLogger(__name__)

# Las cinco tablas de §7.11 y la columna que las liga al usuario.
_TABLES = {
    "users": User.id,
    "user_profiles": UserProfile.user_id,
    "user_signals": UserSignal.user_id,
    "user_exclusions": UserExclusion.user_id,
    "user_declared_tags": UserDeclaredTag.user_id,
}
_STREAM_CHUNK = 1000
_LOCK = sa.text("SELECT pg_advisory_lock(hashtextextended(:k, 0))")
_UNLOCK = sa.text("SELECT pg_advisory_unlock(hashtextextended(:k, 0))")


@dataclass(frozen=True, slots=True)
class Residue:
    tables: dict[str, int]
    keys: tuple[str, ...]
    stream_entries: int

    @property
    def empty(self) -> bool:
        return not any(self.tables.values()) and not self.keys and not self.stream_entries

    @property
    def count(self) -> int:
        return sum(self.tables.values()) + len(self.keys) + self.stream_entries


@dataclass(frozen=True, slots=True)
class SuppressionOutcome:
    state: str  # completed | failed
    attempts: int
    residue: Residue | None = None


def refresh_suppression_metrics(s: Session, metrics: Metrics) -> None:
    """`suppressions_unverified_total`: toda supresión sin constancia; el `for` de la alerta es la gracia."""
    open_count = s.scalar(sa.select(sa.func.count()).select_from(UserSuppression).where(UserSuppression.state != "completed"))
    metrics.set("suppressions_unverified_total", float(open_count or 0))


class SuppressionProcedure:
    def __init__(
        self,
        factory: SessionFactory,
        cache: CacheClient,
        metrics: Metrics,
        *,
        max_attempts: int,
        backoff_base_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._factory = self.factory = factory
        self._cache = cache
        self.metrics = metrics
        self._max = max_attempts
        self._backoff = backoff_base_seconds
        self._sleep = sleep

    # --- Redis -----------------------------------------------------------------------------------
    def _stream_entries(self, user_id: uuid.UUID) -> list[str]:
        """Entradas del usuario en `recompute:requests`: recorrido acotado por `MAXLEN` (RD-100)."""
        wanted, found, start = str(user_id), [], "-"
        while True:
            batch = self._cache.call(lambda s=start: self._cache.raw.xrange(keys.RECOMPUTE_STREAM, min=s, count=_STREAM_CHUNK))
            found.extend(entry_id for entry_id, fields in batch if fields.get("user_id") == wanted)
            if len(batch) < _STREAM_CHUNK:
                return found
            start = f"({batch[-1][0]}"

    def _clear_redis(self, user_id: uuid.UUID) -> None:
        delete_user_scope(self._cache, keys.user_scoped_patterns(user_id))
        entries = self._stream_entries(user_id)
        if not entries:
            return
        try:
            self._cache.call(lambda: self._cache.raw.xack(keys.RECOMPUTE_STREAM, keys.RECOMPUTE_GROUP, *entries))
        except ResponseError:
            pass  # sin grupo todavía: no hay pendientes que confirmar
        self._cache.call(lambda: self._cache.raw.xdel(keys.RECOMPUTE_STREAM, *entries))

    # --- Postgres --------------------------------------------------------------------------------
    def record_receipt(self, event_id: uuid.UUID, user_id: uuid.UUID, requested_at: datetime) -> bool:
        """Paso 0: registra la recepción si el usuario no tiene constancia; mide el lag una sola vez (FR-095b)."""
        with self._factory.begin() as s:
            received_at = s.execute(
                insert(UserSuppression)
                .values(
                    user_id=user_id,
                    requested_at=requested_at,
                    state="in_progress",
                    attempts=0,
                    event_id=event_id,
                    received_at=sa.func.now(),
                )
                .on_conflict_do_nothing()
                .returning(UserSuppression.received_at)
            ).scalar_one_or_none()
        if received_at is None:
            return False
        self.metrics.observe("user_deletion_receipt_lag_seconds", max((received_at - requested_at).total_seconds(), 0.0))
        log.info("recepción de baja registrada", extra={"event_id": str(event_id), "user_id": str(user_id)})
        return True

    def _mark_and_delete(self, user_id: uuid.UUID, requested_at: datetime) -> None:
        with self._factory.begin() as s:
            stmt = insert(UserSuppression).values(user_id=user_id, requested_at=requested_at, state="in_progress", attempts=0)
            s.execute(
                stmt.on_conflict_do_update(
                    index_elements=[UserSuppression.user_id], set_={"state": "in_progress", "verified_at": None}
                )
            )
            s.execute(sa.delete(User).where(User.id == user_id))  # CASCADE: las otras cuatro tablas (§2.14, RD-51)

    def _record(self, user_id: uuid.UUID, state: str | None) -> None:
        values: dict[str, object] = {"attempts": UserSuppression.attempts + 1}
        if state == "completed":
            values.update(state="completed", verified_at=sa.func.now())
        elif state == "failed":
            values.update(state="failed")
        with self._factory.begin() as s:
            s.execute(sa.update(UserSuppression).where(UserSuppression.user_id == user_id).values(**values))

    # --- verificación (T059) -------------------------------------------------------------------
    def residue(self, user_id: uuid.UUID) -> Residue:
        with self._factory() as s:
            tables = {name: int(s.scalar(sa.select(sa.func.count()).where(column == user_id)) or 0) for name, column in _TABLES.items()}
        found = self._cache.call(
            lambda: sorted({k for pattern in keys.user_scoped_patterns(user_id) for k in self._cache.raw.scan_iter(match=pattern, count=500)})
        )
        return Residue(tables, tuple(found), len(self._stream_entries(user_id)))

    def run(self, user_id: uuid.UUID, requested_at: datetime) -> SuppressionOutcome:
        with self._factory() as s:
            existing = s.get(UserSuppression, user_id)
            if existing is not None and existing.state == "completed":
                return SuppressionOutcome("completed", existing.attempts)  # ya verificada: nada que repetir
        self._clear_redis(user_id)  # 1. Redis primero
        self._mark_and_delete(user_id, requested_at)  # 2 y 3
        attempt = 0
        while True:
            attempt += 1
            residue = self.residue(user_id)  # 4
            if residue.empty:
                self._record(user_id, "completed")  # 5
                log.info("supresión verificada", extra={"user_id": str(user_id), "attempts": attempt})
                return self._finish(SuppressionOutcome("completed", attempt))
            if attempt >= self._max:
                self._record(user_id, "failed")
                self.metrics.inc("user_deletion_residual_keys_total", residue.count)
                log.error(
                    "supresión con residuo tras agotar los reintentos: estado fallido visible (FR-095a)",
                    extra={"user_id": str(user_id), "attempts": attempt, "residual_keys": list(residue.keys), "residual_rows": residue.tables},
                )
                return self._finish(SuppressionOutcome("failed", attempt, residue))
            self._record(user_id, None)
            log.warning("residuo en la verificación de supresión; se limpia y reverifica", extra={"user_id": str(user_id), "attempt": attempt})
            self._clear_redis(user_id)
            with self._factory.begin() as s:
                s.execute(sa.delete(User).where(User.id == user_id))
            self._sleep(self._backoff * 2 ** (attempt - 1))

    def _finish(self, outcome: SuppressionOutcome) -> SuppressionOutcome:
        with self._factory() as s:
            refresh_suppression_metrics(s, self.metrics)
        return outcome


class SuppressionHandler:
    """Manejador del evento de baja: idempotencia por `event_id` y, además, por lápida completada.

    El consumidor procesa mensajes en paralelo (`prefetch`): dos entregas simultáneas del mismo evento pasarían
    ambas el chequeo de «ya visto». Un advisory lock de Postgres por usuario serializa el procedimiento, y el
    chequeo ocurre con el lock tomado.
    """

    def __init__(self, procedure: SuppressionProcedure, idempotency: EventIdempotency) -> None:
        self._procedure = procedure
        self._idempotency = idempotency

    def _work(self, event: EliminadoEvent) -> str:
        # Completada o fallida visible, el evento queda procesado: el resultado vive en `user_suppressions`, la
        # falla alerta y el barrido la retoma. Reintentarla por el broker duplicaría el mecanismo.
        self._procedure.run(event.user_id, event.occurred_at)
        return "suppressed"

    def __call__(self, event: EliminadoEvent) -> str:
        key = {"k": f"suppression:{event.user_id}"}
        with self._procedure.factory() as s:
            s.execute(_LOCK, key)
            try:
                self._procedure.record_receipt(event.event_id, event.user_id, event.occurred_at)  # paso 0, antes de todo
                result = self._idempotency.process_once(event.event_id, lambda: self._work(event))
            finally:
                s.execute(_UNLOCK, key)
        return "duplicate" if result is None else result


class SuppressionSweep:
    """Retoma supresiones trabadas (`in_progress` antigua) o fallidas: la verificación es re-ejecutable (FR-095)."""

    def __init__(
        self,
        factory: SessionFactory,
        procedure: SuppressionProcedure,
        metrics: Metrics,
        *,
        stale_after: timedelta = timedelta(minutes=30),
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._factory = factory
        self._procedure = procedure
        self.metrics = metrics
        self._stale_after = stale_after
        self._now = now

    def run(self) -> int:
        cutoff = self._now() - self._stale_after
        with self._factory() as s:
            rows = s.execute(
                sa.select(UserSuppression.user_id, UserSuppression.requested_at)
                .where(UserSuppression.state != "completed", UserSuppression.requested_at < cutoff)
                .order_by(UserSuppression.requested_at)
            ).all()
        for row in rows:
            outcome = self._procedure.run(row.user_id, row.requested_at)
            log.info("supresión retomada por el barrido", extra={"user_id": str(row.user_id), "state": outcome.state})
        with self._factory() as s:
            refresh_suppression_metrics(s, self.metrics)
        return len(rows)
