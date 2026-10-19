"""Modelos de respuesta del contrato de lectura y declaración (T033, T053, T062)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from recomendaciones.shared.domain import Module, ResultType


class RecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    position: int = Field(ge=1)
    score: float
    config_version: str


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    module: Module
    result_type: ResultType
    computed_at: datetime | None
    config_version: str
    stale_available: bool = Field(
        description="true solo si se sirve respaldo existiendo un personalizado obsoleto (FR-056a). "
        "Campo aparte: NO es un estado (T062)."
    )
    items: list[RecommendationItem]


class DeclarationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Module
    tags: list[str] = Field(min_length=1)


class DeclarationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    module: Module
    declared_tags: list[str]
    inherited_tags: list[str]


class DeletionReceipt(BaseModel):
    """Checkpoint de recepción de una baja (FR-095c): sin ningún dato del usuario (FR-095)."""

    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID
    received_at: datetime
    suppression_state: Literal["in_progress", "completed", "failed"]


class ErrorBody(BaseModel):
    error: str
    message: str
