"""Tipos del dominio compartidos por los tres procesos (T005). Sin SQLAlchemy ni Redis."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Module(str, Enum):
    PELICULAS = "peliculas"
    JUEGOS = "juegos"

    @property
    def opposite(self) -> Module:
        return Module.JUEGOS if self is Module.PELICULAS else Module.PELICULAS


class ProfileScope(str, Enum):
    PELICULAS = "peliculas"
    JUEGOS = "juegos"
    GENERAL = "general"


class SignalType(str, Enum):
    """Tipo de señal (FR-062, DEP-1). Obligatorio: nunca se infiere (FR-064)."""

    LIKE = "like"
    DISLIKE = "dislike"
    CONSUMO = "consumo"


class SignalSource(str, Enum):
    SYNC = "sync"
    EVENTO = "evento"


class ResultType(str, Enum):
    """Los cinco estados de respuesta de FR-056: mutuamente excluyentes, exhaustivos y cerrados.

    El rechazo por falta de declaración (FR-088) NO es un sexto estado: ocurre antes de que la
    precedencia sea aplicable, como error de precondición (`errors.DeclarationRequired`).
    Agregar un estado es cambio incompatible del contrato compartido (FR-057, FR-058).
    """

    EMPTY_PENDING = "empty_pending"
    EMPTY_NO_CANDIDATES = "empty_no_candidates"
    FALLBACK = "fallback"
    PERSONALIZED_STALE = "personalized_stale"
    PERSONALIZED = "personalized"

    @classmethod
    def precedence(cls) -> tuple[ResultType, ...]:
        """Orden estricto de FR-056: (1) pendiente … (5) vigente."""
        return (
            cls.EMPTY_PENDING,
            cls.EMPTY_NO_CANDIDATES,
            cls.FALLBACK,
            cls.PERSONALIZED_STALE,
            cls.PERSONALIZED,
        )


@dataclass(frozen=True, slots=True)
class Signal:
    """Una interacción usuario-ítem, identificada por el identificador del origen (CR-17, DI-21)."""

    origin_interaction_id: str
    user_id: uuid.UUID
    item_id: uuid.UUID
    signal_type: SignalType
    occurred_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_type", SignalType(self.signal_type))
        if not self.origin_interaction_id:
            raise ValueError("origin_interaction_id es obligatorio (DEP-8)")


class ExclusionSet:
    """Conjunto de exclusión de un usuario, con interfaz pública de consulta (T014).

    Corrige la deuda del prototipo, donde el batch leía `exclusion._ids`. Cerrado (`__slots__`).
    La guarda pregunta **pertenencia**, no permanencia (§2.7).
    """

    __slots__ = ("__user_id", "__item_ids")

    def __init__(self, user_id: uuid.UUID, item_ids: Iterable[uuid.UUID]) -> None:
        self.__user_id = user_id
        self.__item_ids = frozenset(item_ids)

    @property
    def user_id(self) -> uuid.UUID:
        return self.__user_id

    @property
    def item_ids(self) -> frozenset[uuid.UUID]:
        return self.__item_ids

    def contains(self, item_id: uuid.UUID) -> bool:
        return item_id in self.__item_ids

    def __contains__(self, item_id: object) -> bool:
        return item_id in self.__item_ids

    def __len__(self) -> int:
        return len(self.__item_ids)


def resolve_exclusion_origin(history: Iterable[str]) -> str | None:
    """Origen de la exclusión de un par (usuario, ítem) dado su historial cronológico (§2.7).

    Toda señal excluye (FR-029a, SC-018). `consumo` es permanente e irreversible (FR-029b). Entre
    `like` y `dislike` gana la más reciente (FR-029c, FR-029d): un like posterior revierte la
    exclusión *por dislike*, pero el ítem sigue excluido —ahora por el like—.
    """
    kinds = [str(getattr(k, "value", k)) for k in history]
    if SignalType.CONSUMO.value in kinds:
        return SignalType.CONSUMO.value
    preferences = [k for k in kinds if k in (SignalType.LIKE.value, SignalType.DISLIKE.value)]
    return preferences[-1] if preferences else None
