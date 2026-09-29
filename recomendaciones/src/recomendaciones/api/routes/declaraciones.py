"""`POST /internal/v1/declarations/{user_id}` — declaración de gustos (T053, FR-089)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, status

from recomendaciones.api.errors import ERROR_RESPONSES
from recomendaciones.api.schemas.respuesta import DeclarationRequest, DeclarationResponse

router = APIRouter()


@router.post(
    "/internal/v1/declarations/{user_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=DeclarationResponse,
    responses={code: ERROR_RESPONSES[code] for code in (401, 404, 409, 422, 503)},
    operation_id="declareTastes",
)
def declare(request: Request, user_id: uuid.UUID, body: DeclarationRequest) -> DeclarationResponse:
    outcome = request.app.state.services.declaration_service.declare(user_id, body.module, body.tags)
    return DeclarationResponse(
        user_id=user_id,
        module=body.module,
        declared_tags=list(outcome.declared),
        inherited_tags=list(outcome.inherited),
    )
