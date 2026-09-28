"""Declaración de gustos (T053, T054): la **única** excepción de escritura de la API.

Constitución v1.1.0, Principio III (RD-98) y FR-089b: valida el mínimo de tags **propios**, resuelve
la herencia —tags declarados en el otro módulo que son compartidos (FR-085)—, persiste y confirma de
forma síncrona (FR-089a). **No ejecuta el motor** ni cómputo proporcional al catálogo: el recálculo se
delega a `recompute:requests` (RD-100). La herencia es **derivada**: se informa y no se escribe, y no
cuenta para el mínimo (RD-97). La declaración es definitiva: una segunda es conflicto (FR-086a).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from recomendaciones.shared.domain import Module
from recomendaciones.shared.errors import DeclarationConflict, InvalidRequest, UnknownUser
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.cache.recompute import RecomputeSignaler
from recomendaciones.storage.db.declarations import DeclarationRepository
from recomendaciones.storage.db.session import SessionFactory


def validate_declaration(tags: Iterable[str], *, declarable: frozenset[str], minimum: int) -> tuple[str, ...]:
    """Tags propios válidos, ordenados. Mínimo `declared_tags_min`, sin máximo (FR-083); solo vocabulario vigente (DEP-10)."""
    own = set(tags)
    unknown = sorted(own - declarable)
    if unknown:
        raise InvalidRequest(f"tags fuera del vocabulario vigente del módulo: {', '.join(unknown)}")
    if len(own) < minimum:
        raise InvalidRequest(f"la declaración exige al menos {minimum} tags propios distintos (FR-083)")
    return tuple(sorted(own))


@dataclass(frozen=True, slots=True)
class DeclarationOutcome:
    declared: tuple[str, ...]
    inherited: tuple[str, ...]


class DeclarationService:
    def __init__(
        self,
        factory: SessionFactory,
        repository: DeclarationRepository,
        filters: FiltersCache,
        signaler: RecomputeSignaler,
        *,
        declared_tags_min: int,
    ) -> None:
        self._factory = factory
        self._repo = repository
        self._filters = filters
        self._signaler = signaler
        self._minimum = declared_tags_min

    def declare(self, user_id: uuid.UUID, module: Module, tags: Iterable[str]) -> DeclarationOutcome:
        module = Module(module)
        with self._factory.begin() as s:
            if not self._repo.lock_user(s, user_id):
                raise UnknownUser()
            if self._repo.declared_tags(s, user_id, module):
                raise DeclarationConflict()
            own = validate_declaration(tags, declarable=self._repo.declarable_tags(s, module), minimum=self._minimum)
            inherited = self._repo.declared_tags(s, user_id, module.opposite) & self._repo.shared_tags(s)
            self._filters.invalidate(user_id)  # Redis primero (FR-080c, RD-96)
            self._repo.insert(s, user_id, module, own)
        self._filters.invalidate(user_id)  # cierra la carrera con un repoblado concurrente previo al commit
        self._signaler.request(user_id, module, "declaration")  # después de confirmar la escritura
        return DeclarationOutcome(own, tuple(sorted(inherited)))
