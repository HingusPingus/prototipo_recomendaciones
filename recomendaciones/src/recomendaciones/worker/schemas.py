"""Validación de los eventos consumidos contra su JSON Schema antes de tocar el dominio (T023, FR-009).

Las copias en `worker/contracts/` son derivadas de `specs/.../contracts/` (T049), que a su vez derivan
del contrato publicado en `api-general` (Principio II). Un test verifica que no diverjan.
Un evento inválido nunca se reintenta ni se descarta en silencio: va a dead-letter con su causa
(FR-012, T026). `signal_type` y `origin_interaction_id` son obligatorios: jamás se infieren (FR-064).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from recomendaciones.shared.domain import Module, SignalType
from recomendaciones.shared.errors import InvalidEventPayload

_CONTRACTS = Path(__file__).with_name("contracts")


@cache
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((_CONTRACTS / name).read_text(encoding="utf-8")))


@dataclass(frozen=True, slots=True)
class ActualizarEvent:
    event_id: uuid.UUID
    origin_interaction_id: str
    user_id: uuid.UUID
    module: Module
    item_id: uuid.UUID
    signal_type: SignalType
    occurred_at: datetime
    correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class EliminadoEvent:
    event_id: uuid.UUID
    user_id: uuid.UUID
    occurred_at: datetime
    correlation_id: str | None = None


def extract_event_id(body: bytes) -> str | None:
    """`event_id` de un mensaje, aun inválido, para el log y la DLQ (T026)."""
    try:
        value = json.loads(body).get("event_id")
    except (ValueError, AttributeError, TypeError):
        return None
    return value if isinstance(value, str) else None


def _load(body: bytes, schema: str) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except (ValueError, TypeError) as exc:
        raise InvalidEventPayload(f"el cuerpo no es JSON válido: {exc.__class__.__name__}") from None
    errors = sorted(_validator(schema).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        where = ".".join(str(p) for p in first.path) or "(raíz)"
        raise InvalidEventPayload(f"{where}: {first.message}")
    return data


def _uuid(data: dict[str, Any], field: str) -> uuid.UUID:
    try:
        return uuid.UUID(data[field])
    except (ValueError, TypeError, AttributeError):
        raise InvalidEventPayload(f"{field}: no es un UUID válido") from None


def _instant(data: dict[str, Any], field: str) -> datetime:
    try:
        value = datetime.fromisoformat(str(data[field]))  # Python ≥ 3.11 admite el sufijo Z
    except ValueError:
        raise InvalidEventPayload(f"{field}: no es una marca temporal ISO 8601") from None
    if value.tzinfo is None:
        raise InvalidEventPayload(f"{field}: la marca temporal debe llevar zona horaria")
    return value


def parse_actualizar(body: bytes) -> ActualizarEvent:
    data = _load(body, "recomendacion-actualizar.schema.json")
    return ActualizarEvent(
        event_id=_uuid(data, "event_id"),
        origin_interaction_id=data["origin_interaction_id"],
        user_id=_uuid(data, "user_id"),
        module=Module(data["module"]),
        item_id=_uuid(data, "item_id"),
        signal_type=SignalType(data["signal_type"]),
        occurred_at=_instant(data, "occurred_at"),
        correlation_id=data.get("correlation_id"),
    )


def parse_eliminado(body: bytes) -> EliminadoEvent:
    data = _load(body, "usuario-eliminado.schema.json")
    return EliminadoEvent(
        event_id=_uuid(data, "event_id"),
        user_id=_uuid(data, "user_id"),
        occurred_at=_instant(data, "occurred_at"),
        correlation_id=data.get("correlation_id"),
    )
