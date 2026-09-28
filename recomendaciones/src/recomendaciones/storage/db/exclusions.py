"""Resolutor de exclusiones: escritor único de `user_exclusions` (T014, §2.7, DI-13).

Lo invocan la sincronización (T029) y el worker de eventos (T064) tras ingresar señales. Reglas:

- **Aditivo** (DI-20, FR-029b1): nunca trunca ni vacía la tabla; una fila cuya señal fue purgada
  permanece. Las filas `consumo` son permanentes: jamás cambian de origen.
- Señal vigente entre `like`/`dislike` por `occurred_at DESC, id DESC` (DI-22).
- **Redis primero** (FR-080c, RD-96): invalida `filters:{user_id}` antes de escribir. Además, el
  llamador invalida de nuevo tras confirmar la transacción (`after_commit`): sin eso, una lectura
  concurrente entre el borrado y el commit repoblaría `filters:` con el conjunto viejo durante
  `TTL_FILTERS`, y la exclusión dejaría de ser efectiva «en la siguiente lectura».
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from recomendaciones.shared.domain import ExclusionSet
from recomendaciones.storage.db.models import UserExclusion

Invalidate = Callable[[uuid.UUID], None]

_DESIRED_SQL = sa.text(
    """
    WITH vigente AS (
        SELECT DISTINCT ON (user_id, item_id) user_id, item_id, signal_type::text AS kind
        FROM user_signals
        WHERE user_id = ANY(:users) AND signal_type IN ('like', 'dislike')
        ORDER BY user_id, item_id, occurred_at DESC, id DESC
    ),
    consumido AS (
        SELECT DISTINCT user_id, item_id FROM user_signals
        WHERE user_id = ANY(:users) AND signal_type = 'consumo'
    )
    SELECT COALESCE(c.user_id, v.user_id) AS user_id,
           COALESCE(c.item_id, v.item_id) AS item_id,
           CASE WHEN c.item_id IS NOT NULL THEN 'consumo' ELSE v.kind END AS origin
    FROM vigente v FULL OUTER JOIN consumido c ON c.user_id = v.user_id AND c.item_id = v.item_id
    """
)


@dataclass
class ResolveResult:
    affected_users: set[uuid.UUID] = field(default_factory=set)
    written: int = 0


class ExclusionResolver:
    def __init__(self, invalidate_filters: Invalidate) -> None:
        self._invalidate = invalidate_filters

    def resolve(self, session: Session, user_ids: Iterable[uuid.UUID]) -> ResolveResult:
        users = sorted(set(user_ids), key=str)
        result = ResolveResult()
        if not users:
            return result
        desired = {
            (row.user_id, row.item_id): row.origin
            for row in session.execute(_DESIRED_SQL, {"users": users})
        }
        existing = {
            (row.user_id, row.item_id): row.origin
            for row in session.execute(
                sa.select(UserExclusion.user_id, UserExclusion.item_id, UserExclusion.origin).where(
                    UserExclusion.user_id.in_(users)
                )
            )
        }
        changes = [
            {"user_id": u, "item_id": i, "origin": origin}
            for (u, i), origin in sorted(desired.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))
            if existing.get((u, i)) != origin and existing.get((u, i)) != "consumo"
        ]
        if not changes:
            return result
        result.affected_users = {c["user_id"] for c in changes}
        for user in sorted(result.affected_users, key=str):
            self._invalidate(user)  # Redis primero (FR-080c)
        stmt = insert(UserExclusion).values(
            [{**c, "resolved_at": sa.func.now()} for c in changes]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserExclusion.user_id, UserExclusion.item_id],
            set_={"origin": stmt.excluded.origin, "resolved_at": stmt.excluded.resolved_at},
            where=UserExclusion.origin != "consumo",
        )
        session.execute(stmt)
        result.written = len(changes)
        return result

    def after_commit(self, result: ResolveResult) -> None:
        for user in sorted(result.affected_users, key=str):
            self._invalidate(user)


def load_exclusion_set(session: Session, user_id: uuid.UUID) -> ExclusionSet:
    items = session.scalars(sa.select(UserExclusion.item_id).where(UserExclusion.user_id == user_id)).all()
    return ExclusionSet(user_id, items)
