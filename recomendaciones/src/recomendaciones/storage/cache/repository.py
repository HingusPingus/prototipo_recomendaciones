"""Repositorio del top-N precomputado en Redis (T019, data-model.md §3.2).

El top-N vive **solo** en Redis (FR-080b): se recomputa ante pérdida, no se restaura. Cada entrada
lleva `config_version` y `computed_at` (Q4, SC-004) y se escribe junto con su copia obsoleta en una
única transacción (`MULTI`), de modo que ambas son consistentes. `items` guarda lo que produjo el
pipeline —`min(top_n_max, candidatos)` en `reco:`, `min(fallback_stored_size, candidatos)` en
`fallback:`—: el truncado a `top_n` ocurre al servir, después de las guardas.

Cada ítem lleva además su `min_age_ordinal`. §3.2 no lo enumera, pero la guarda etaria del request
path sobre el respaldo (FR-033d, T037) necesita comparar ordinales sin consultar Postgres (INV-1).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CachedItem:
    item_id: uuid.UUID
    rank: int
    score: float
    min_age_ordinal: int


@dataclass(frozen=True, slots=True)
class RecommendationEntry:
    user_id: uuid.UUID | None  # ausente en fallback:
    module: Module
    config_version: str
    vocab_version: str  # forense, sin lógica (RD-41)
    max_age_ordinal: int | None  # instantáneo etario; ausente en fallback:
    computed_at: datetime
    items: tuple[CachedItem, ...]

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "module": self.module.value,
            "config_version": self.config_version,
            "vocab_version": self.vocab_version,
            "computed_at": self.computed_at.isoformat(),
            "items": [
                {"item_id": str(i.item_id), "rank": i.rank, "score": i.score, "min_age_ordinal": i.min_age_ordinal}
                for i in self.items
            ],
        }
        if self.user_id is not None:
            data["user_id"] = str(self.user_id)
        if self.max_age_ordinal is not None:
            data["max_age_ordinal"] = self.max_age_ordinal
        return data

    @classmethod
    def from_json(cls, data: Any, *, expected_config_version: str) -> RecommendationEntry | None:
        """Entrada ilegible, de esquema desconocido o mal rotulada ⟹ miss (§3.2)."""
        try:
            if data.get("schema_version") != SCHEMA_VERSION:
                return None
            if data["config_version"] != expected_config_version:
                return None
            return cls(
                user_id=uuid.UUID(data["user_id"]) if "user_id" in data else None,
                module=Module(data["module"]),
                config_version=data["config_version"],
                vocab_version=str(data["vocab_version"]),
                max_age_ordinal=int(data["max_age_ordinal"]) if "max_age_ordinal" in data else None,
                computed_at=datetime.fromisoformat(data["computed_at"]),
                items=tuple(
                    CachedItem(uuid.UUID(i["item_id"]), int(i["rank"]), float(i["score"]), int(i["min_age_ordinal"]))
                    for i in data["items"]
                ),
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            return None


class RecommendationRepository:
    def __init__(self, cache: CacheClient, *, ttl_fresh: int, ttl_stale: int, ttl_fallback: int) -> None:
        self._cache = cache
        self._ttl_fresh, self._ttl_stale, self._ttl_fallback = ttl_fresh, ttl_stale, ttl_fallback

    def write_personalized(self, entry: RecommendationEntry) -> None:
        assert entry.user_id is not None
        payload = json.dumps(entry.to_json(), separators=(",", ":"))
        fresh = keys.reco_key(entry.config_version, entry.user_id, entry.module)
        stale = keys.stale_key(entry.config_version, entry.user_id, entry.module)

        def write() -> None:
            pipe = self._cache.raw.pipeline(transaction=True)
            pipe.set(fresh, payload, ex=self._ttl_fresh)
            pipe.set(stale, payload, ex=self._ttl_stale)
            pipe.execute()

        self._cache.call(write)

    def write_fallback(self, entry: RecommendationEntry) -> None:
        self._cache.set_json(keys.fallback_key(entry.config_version, entry.module), entry.to_json(), self._ttl_fallback)

    def _read(self, key: str, config_version: str) -> RecommendationEntry | None:
        data = self._cache.get_json(key)
        return None if data is None else RecommendationEntry.from_json(data, expected_config_version=config_version)

    def read_fresh(self, config_version: str, user_id: uuid.UUID, module: Module) -> RecommendationEntry | None:
        return self._read(keys.reco_key(config_version, user_id, module), config_version)

    def read_stale(self, config_version: str, user_id: uuid.UUID, module: Module) -> RecommendationEntry | None:
        return self._read(keys.stale_key(config_version, user_id, module), config_version)

    def read_fallback(self, config_version: str, module: Module) -> RecommendationEntry | None:
        return self._read(keys.fallback_key(config_version, module), config_version)
