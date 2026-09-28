"""`filters:{user_id}` y `retired:{module}` — guardas del request path, con repoblado ante miss (T018).

`filters:` porta el permiso etario (con su escala, §3.1.1), el conjunto de exclusión y los módulos
declarados (RD-96). Se invalida en el mismo acto de toda exclusión o declaración nueva (FR-080c).
`retired:` contiene solo los retirados de la ventana derivada de `TTL_STALE` (RD-39, DI-25).
Ambos son caché: su miss se repuebla por lectura acotada de Postgres, el respaldo degradado que el
Principio III admite (INV-1).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from recomendaciones.shared.domain import ExclusionSet, Module
from recomendaciones.shared.errors import ExclusionSetUnavailable, RecoError
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient

FILTERS_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class UserFilters:
    user_id: uuid.UUID
    max_age_ordinal: int
    age_config_version: str
    exclusions: ExclusionSet
    declared_modules: frozenset[Module]

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": FILTERS_SCHEMA_VERSION,
            "max_age_ordinal": self.max_age_ordinal,
            "age_config_version": self.age_config_version,
            "exclusions": sorted(str(i) for i in self.exclusions.item_ids),
            "declared_modules": sorted(m.value for m in self.declared_modules),
        }

    @classmethod
    def from_json(cls, user_id: uuid.UUID, data: Any) -> UserFilters | None:
        try:
            if data.get("schema_version") != FILTERS_SCHEMA_VERSION:
                return None
            return cls(
                user_id=user_id,
                max_age_ordinal=int(data["max_age_ordinal"]),
                age_config_version=str(data["age_config_version"]),
                exclusions=ExclusionSet(user_id, (uuid.UUID(i) for i in data["exclusions"])),
                declared_modules=frozenset(Module(m) for m in data["declared_modules"]),
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            return None  # entrada ilegible ⟹ miss


class FiltersSource(Protocol):
    def load_user_filters(self, user_id: uuid.UUID) -> UserFilters | None: ...

    def load_retired(self, module: Module, window_seconds: int) -> frozenset[uuid.UUID]: ...


class FiltersCache:
    def __init__(self, cache: CacheClient, source: FiltersSource, ttl_seconds: int) -> None:
        self._cache, self._source, self._ttl = cache, source, ttl_seconds

    def get(self, user_id: uuid.UUID) -> UserFilters | None:
        cached = self._cache.get_json(keys.filters_key(user_id))
        if cached is not None:
            parsed = UserFilters.from_json(user_id, cached)
            if parsed is not None:
                return parsed
        return self.repopulate(user_id)

    def repopulate(self, user_id: uuid.UUID) -> UserFilters | None:
        try:
            fresh = self._source.load_user_filters(user_id)
        except RecoError:
            raise
        except Exception as exc:  # fail-closed: sin filtros no se sirve nada (FR-049, FR-050)
            raise ExclusionSetUnavailable() from exc
        if fresh is not None:
            self._cache.set_json(keys.filters_key(user_id), fresh.to_json(), self._ttl)
        return fresh

    def invalidate(self, user_id: uuid.UUID) -> None:
        self._cache.delete(keys.filters_key(user_id))


class RetiredCache:
    def __init__(self, cache: CacheClient, source: FiltersSource, ttl_seconds: int, window_seconds: int) -> None:
        self._cache, self._source = cache, source
        self._ttl, self._window = ttl_seconds, window_seconds

    def members(self, module: Module) -> frozenset[uuid.UUID]:
        key = keys.retired_key(module)
        cached = self._cache.get_members(key)
        if cached is not None:
            return frozenset(uuid.UUID(m) for m in cached)
        try:
            fresh = self._source.load_retired(Module(module), self._window)
        except RecoError:
            raise
        except Exception as exc:  # sin la guarda de vigencia no se sirve (FR-072)
            raise ExclusionSetUnavailable() from exc
        self._cache.set_members(key, (str(i) for i in fresh), self._ttl)
        return fresh
