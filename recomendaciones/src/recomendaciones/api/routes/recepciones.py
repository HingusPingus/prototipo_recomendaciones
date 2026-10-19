"""`GET /internal/v1/deletion-receipts/{event_id}` — recepción de una baja (T077, FR-095c)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from recomendaciones.api.errors import ERROR_RESPONSES
from recomendaciones.api.schemas.respuesta import DeletionReceipt

router = APIRouter()


@router.get(
    "/internal/v1/deletion-receipts/{event_id}",
    response_model=DeletionReceipt,
    responses={
        **{code: ERROR_RESPONSES[code] for code in (401, 422, 503)},
        404: {"description": "No hay recepción registrada para ese event_id"},
    },
    operation_id="getDeletionReceipt",
)
def deletion_receipt(request: Request, event_id: uuid.UUID) -> DeletionReceipt:
    row = request.app.state.services.receipt_service.get(event_id)
    return DeletionReceipt(event_id=row.event_id, received_at=row.received_at, suppression_state=row.state)
