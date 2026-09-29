"""Jerarquía de errores tipados (T005). Cada error declara su código HTTP y un código estable.

La API los traduce a respuestas con forma fija (T035); ninguna excepción genérica escapa como 500.
Los mensajes nunca incluyen detalles internos (rutas, SQL, versiones de librerías).
"""

from __future__ import annotations

from typing import ClassVar


class RecoError(Exception):
    http_status: ClassVar[int] = 500
    code: ClassVar[str] = "internal_error"
    default_message: ClassVar[str] = "error interno"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message


class InvalidRequest(RecoError):
    http_status = 422
    code = "invalid_request"
    default_message = "parámetros de la solicitud inválidos"


class Unauthorized(RecoError):
    http_status = 401
    code = "unauthorized"
    default_message = "credencial de servicio inválida"


class UnknownUser(RecoError):
    """Usuario inexistente para el servicio: diferenciado de «usuario conocido sin resultados»."""

    http_status = 404
    code = "unknown_user"
    default_message = "usuario desconocido para el servicio"


class DeclarationRequired(RecoError):
    """FR-088: módulo sin declaración de gustos. Precondición incumplida, no un estado de resultado."""

    http_status = 412
    code = "declaration_required"
    default_message = "el usuario no declaró sus gustos en este módulo"


class DeclarationConflict(RecoError):
    """FR-086a: la declaración de un módulo es definitiva; una segunda se rechaza sin cambios."""

    http_status = 409
    code = "declaration_already_exists"
    default_message = "el módulo ya tiene una declaración de gustos"


class _Unavailable(RecoError):
    http_status = 503
    retry_after_seconds: ClassVar[int] = 5


class CacheUnavailable(_Unavailable):
    """FR-065: Redis caído ≠ miss. Nunca se recurre a Postgres para calcular en línea."""

    code = "cache_unavailable"
    default_message = "servicio temporalmente no disponible"


class ExclusionSetUnavailable(_Unavailable):
    """FR-050: sin conjunto de exclusión o datos de edad no se sirve nada sin filtrar."""

    code = "filters_unavailable"
    default_message = "servicio temporalmente no disponible"


class StaleAgeScale(_Unavailable):
    """DI-23: el ordinal del usuario se derivó bajo una escala no activa; no se compara."""

    code = "filters_unavailable"
    default_message = "servicio temporalmente no disponible"


class UpstreamError(RecoError):
    """Error HTTP de `api-general` traducido (T028). Nunca escapa a la API de lectura."""

    http_status = 502
    code = "upstream_error"
    default_message = "error del servicio de origen"


class UpstreamUnavailable(UpstreamError):
    http_status = 503
    code = "upstream_unavailable"
    default_message = "servicio de origen no disponible"


class InvalidEventPayload(RecoError):
    """Evento que no valida contra su schema: va a DLQ sin reintento (FR-012, T026)."""

    http_status = 422
    code = "invalid_event_payload"
    default_message = "el evento no valida contra su schema"


class ContractViolation(RecoError):
    """Incumplimiento de contrato del origen (p. ej. FR-029e1): se rechaza, nunca se absorbe."""

    http_status = 422
    code = "contract_violation"
    default_message = "incumplimiento de contrato del origen"


class TransientError(RecoError):
    """Fallo transitorio (DB/Redis): se reintenta con backoff (FR-013, T025)."""

    http_status = 503
    code = "transient_error"
    default_message = "fallo transitorio"
