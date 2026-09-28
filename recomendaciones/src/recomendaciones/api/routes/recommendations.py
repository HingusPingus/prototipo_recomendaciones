"""`GET /internal/v1/recommendations/{user_id}` — lectura del top-N precomputado (T033, T055, T062).

Cache-first y sin cómputo (FR-002, FR-003). `top_n` es el único parámetro de tamaño, validado en
`[top_n_min, top_n_max]` por **ambos** extremos (FR-005, FR-006a); `limit` y `cursor` no son parte del
contrato y se rechazan (RD-107). La declaración de gustos se exige como precondición (FR-088, T055).
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Query, Request

from recomendaciones.api.errors import ERROR_RESPONSES
from recomendaciones.api.schemas.respuesta import RecommendationItem, RecommendationResponse
from recomendaciones.shared.domain import Module
from recomendaciones.shared.errors import InvalidRequest

router = APIRouter()

_FORBIDDEN_PARAMS = ("limit", "cursor")


@router.get(
    "/internal/v1/recommendations/{user_id}",
    response_model=RecommendationResponse,
    responses={code: ERROR_RESPONSES[code] for code in (401, 404, 412, 422, 503)},
    operation_id="getRecommendations",
)
def get_recommendations(
    request: Request,
    user_id: uuid.UUID,
    module: Module = Query(...),
    top_n: int | None = Query(default=None, ge=10, le=50),
    prefer: Literal["stale"] | None = Query(default=None),
) -> RecommendationResponse:
    services = request.app.state.services
    cfg = services.engine_config
    forbidden = [p for p in _FORBIDDEN_PARAMS if p in request.query_params]
    if forbidden:
        raise InvalidRequest(f"parámetros no admitidos por el contrato: {', '.join(forbidden)} (FR-005)")
    size = cfg.top_n_default if top_n is None else top_n
    if not cfg.top_n_min <= size <= cfg.top_n_max:
        raise InvalidRequest(f"top_n debe estar en [{cfg.top_n_min}, {cfg.top_n_max}] (FR-006a)")
    result = services.read_service.read(user_id, module, top_n=size, prefer_stale=prefer == "stale")
    return RecommendationResponse(
        user_id=user_id,
        module=module,
        result_type=result.result_type,
        computed_at=result.computed_at,
        config_version=result.config_version,
        stale_available=result.stale_available,
        items=[
            RecommendationItem(
                item_id=i.item_id, position=i.position, score=i.score, config_version=result.config_version
            )
            for i in result.items
        ],
    )
