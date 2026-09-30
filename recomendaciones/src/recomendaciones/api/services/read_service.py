"""Servicio de lectura del top-N precomputado (T020, T037, T055, T062).

El request path **solo lee**: Redis para el resultado, y Postgres únicamente ante miss de `filters:`
o `retired:` (INV-1). Nunca calcula: no importa `engine/` (T006) ni consulta Postgres ante un miss
de resultado. Orden de la solicitud:

1. `filters:{user}` (edad con su escala, exclusiones, módulos declarados). Usuario desconocido ⟹ 404.
   Escala etaria incompatible con la activa ⟹ se repuebla; si persiste ⟹ 503 (DI-23).
2. Precondición de FR-088: módulo sin declaración ⟹ rechazo, **antes** de toda precedencia (T055).
3. Resolución del resultado y precedencia estricta de FR-056, evaluada sobre la lista **posterior a
   las guardas** (RD-42): pendiente → sin candidatos → respaldo → obsoleto → vigente. Todo miss de
   resultado solicita recálculo por `recompute:requests` con supresión (RD-100).
4. Guardas acotadas sobre ≤ `top_n_max`/`fallback_stored_size` ítems ya ordenados: comparación
   ordinal, pertenencia a exclusiones y diferencia contra `retired:` (FR-033d, §4.2, §4.4). Sin
   similitud, sin recomputar scores, sin reordenar: la lista reducida se sirve tal cual (FR-075).
5. Recorte a `top_n`.

Compatibilidad de escala etaria: se compara el **catálogo** etario, no la identidad de la versión. La
`config_version` es el hash de todo el archivo, de modo que comparar identidades volvería
incomparables a todos los usuarios ante cualquier cambio de pesos, con `503` para todos hasta que el
refresco etario los rederivara. Dos versiones con catálogo idéntico hablan la misma escala (RD-103).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from recomendaciones.api.services.precondiciones import check_preconditions
from recomendaciones.shared.domain import Module, ResultType
from recomendaciones.storage.cache.filters import FiltersCache, RetiredCache, UserFilters
from recomendaciones.storage.cache.recompute import RecomputeSignaler
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ServedItem:
    item_id: uuid.UUID
    position: int
    score: float


@dataclass(frozen=True, slots=True)
class ReadResult:
    result_type: ResultType
    items: tuple[ServedItem, ...]
    config_version: str
    computed_at: datetime | None
    stale_available: bool = False


@dataclass(frozen=True, slots=True)
class _Resolved:
    entry: RecommendationEntry
    readable_hit: bool  # acierto bajo una versión legible anterior: se sirve con su etiqueta, sin señal


class ReadService:
    def __init__(
        self,
        *,
        repository: RecommendationRepository,
        filters: FiltersCache,
        retired: RetiredCache,
        signaler: RecomputeSignaler,
        active_version: str,
        readable_versions: Sequence[str],
        age_compatible_versions: frozenset[str],
        on_signal_failure: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._filters = filters
        self._retired = retired
        self._signaler = signaler
        self._active = active_version
        self._readable = tuple(readable_versions)
        self._compatible = age_compatible_versions
        self._on_signal_failure = on_signal_failure

    # --- resolución del resultado ----------------------------------------------------------------
    def _usable(self, entry: RecommendationEntry | None, filters: UserFilters) -> RecommendationEntry | None:
        """Instantáneo etario (§3.2): mayor que el permiso actual ⟹ descartar como miss."""
        if entry is None:
            return None
        if entry.max_age_ordinal is not None and entry.max_age_ordinal > filters.max_age_ordinal:
            return None
        return entry

    def _resolve(self, reader: Callable[[str], RecommendationEntry | None], filters: UserFilters) -> _Resolved | None:
        for n, version in enumerate((self._active, *self._readable)):
            entry = self._usable(reader(version), filters)
            if entry is not None:
                return _Resolved(entry, readable_hit=n > 0)
        return None

    def _signal(self, user_id: uuid.UUID, module: Module, reason: str) -> None:
        try:
            self._signaler.request(user_id, module, reason)
        except Exception:  # noqa: BLE001 — la lectura nunca falla porque falle la señal (T020)
            log.warning("no se pudo solicitar el recálculo", extra={"user_id": str(user_id), "reco_module": module.value})
            if self._on_signal_failure:
                self._on_signal_failure()

    # --- guardas acotadas (T037) --------------------------------------------------------------------
    def _guard(
        self, items: Sequence[CachedItem], filters: UserFilters, retired: frozenset[uuid.UUID], top_n: int
    ) -> tuple[ServedItem, ...]:
        kept: list[ServedItem] = []
        for item in items:  # lista ya ordenada y acotada: pertenencia y comparación, nada más
            if item.min_age_ordinal > filters.max_age_ordinal:
                continue
            if filters.exclusions.contains(item.item_id) or item.item_id in retired:
                continue
            kept.append(ServedItem(item.item_id, len(kept) + 1, item.score))
            if len(kept) == top_n:
                break
        return tuple(kept)

    def _serve(
        self,
        entry: RecommendationEntry,
        result_type: ResultType,
        filters: UserFilters,
        retired: frozenset[uuid.UUID],
        top_n: int,
        stale_available: bool = False,
    ) -> ReadResult:
        items = self._guard(entry.items, filters, retired, top_n)
        if not items:  # vaciada por las guardas ⟹ sin candidatos (RD-42); reducida ⟹ se sirve (FR-075)
            return ReadResult(ResultType.EMPTY_NO_CANDIDATES, (), entry.config_version, entry.computed_at)
        return ReadResult(result_type, items, entry.config_version, entry.computed_at, stale_available)

    # --- entrada pública ------------------------------------------------------------------------
    def read(self, user_id: uuid.UUID, module: Module, *, top_n: int, prefer_stale: bool = False) -> ReadResult:
        module = Module(module)
        filters = check_preconditions(self._filters, user_id, module, self._compatible)
        retired = self._retired.members(module)

        fresh = self._resolve(lambda v: self._repository.read_fresh(v, user_id, module), filters)
        if fresh is not None:
            snapshot = fresh.entry.max_age_ordinal
            if snapshot is not None and snapshot < filters.max_age_ordinal:
                self._signal(user_id, module, "snapshot")  # seguro pero conservador: servir y recalcular
            return self._serve(fresh.entry, ResultType.PERSONALIZED, filters, retired, top_n)

        # Miss del vigente: casos 1 a 4 de FR-056. Se solicita recálculo (FR-035, RD-100).
        self._signal(user_id, module, "miss")
        stale = self._resolve(lambda v: self._repository.read_stale(v, user_id, module), filters)
        if prefer_stale and stale is not None:  # FR-056a, RD-107: la opción del usuario
            return self._serve(stale.entry, ResultType.PERSONALIZED_STALE, filters, retired, top_n)
        fallback = self._repository.read_fallback(self._active, module)
        if fallback is not None:
            return self._serve(fallback, ResultType.FALLBACK, filters, retired, top_n, stale_available=stale is not None)
        if stale is not None:
            return self._serve(stale.entry, ResultType.PERSONALIZED_STALE, filters, retired, top_n)
        return ReadResult(ResultType.EMPTY_PENDING, (), self._active, None)
