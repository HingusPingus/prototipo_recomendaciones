"""Lectura de la constancia de recepción de una baja (T077): uno de los accesos a Postgres de la API (INV-1).

Excepción de lectura del Principio III (constitución v1.2.0): una fila por clave de `user_suppressions`, por el
índice único de `event_id`, sin cómputo y sin datos del usuario (FR-095, FR-095c).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from recomendaciones.storage.db.models import UserSuppression


@dataclass(frozen=True, slots=True)
class ReceiptRow:
    event_id: uuid.UUID
    received_at: datetime
    state: str


def is_database_unavailable(exc: BaseException) -> bool:
    """La base no respondió (conexión, timeout, caída): la API la traduce a `503` sin importar el driver (INV-1)."""
    return isinstance(exc, DBAPIError)


class ReceiptRepository:
    def by_event(self, s: Session, event_id: uuid.UUID) -> ReceiptRow | None:
        row = s.execute(
            sa.select(UserSuppression.event_id, UserSuppression.received_at, UserSuppression.state).where(
                UserSuppression.event_id == event_id
            )
        ).one_or_none()
        return None if row is None else ReceiptRow(row.event_id, row.received_at, str(row.state))
