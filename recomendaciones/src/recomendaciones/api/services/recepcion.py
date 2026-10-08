"""Consulta de la recepción de una baja para el checkpoint de `api-general` (T077, FR-095c, RD-117).

No toca Redis ni el motor: una lectura por clave. Con Postgres caído responde `503` reintentable y nunca `404`,
que `api-general` leería como «la baja no llegó».
"""

from __future__ import annotations

import uuid

from recomendaciones.shared.errors import ReceiptNotFound, ReceiptsUnavailable
from recomendaciones.storage.db.receipts import ReceiptRepository, ReceiptRow, is_database_unavailable
from recomendaciones.storage.db.session import SessionFactory


class ReceiptService:
    def __init__(self, factory: SessionFactory, repository: ReceiptRepository) -> None:
        self._factory = factory
        self._repository = repository

    def _lookup(self, event_id: uuid.UUID) -> ReceiptRow | None:
        with self._factory() as s:
            return self._repository.by_event(s, event_id)

    def get(self, event_id: uuid.UUID) -> ReceiptRow:
        try:
            row = self._lookup(event_id)
        except Exception as exc:
            if is_database_unavailable(exc):
                raise ReceiptsUnavailable() from exc
            raise
        if row is None:
            raise ReceiptNotFound()
        return row
