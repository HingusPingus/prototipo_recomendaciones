"""Vectorización TF-IDF (T007) y señal content-based (T009). Funciones puras: sin I/O ni reloj.

IDF suavizado `ln((1 + N) / (1 + df)) + 1` (FR-022, RD-105), con `N` = ítems vigentes del módulo y
`df` = ítems vigentes del módulo que portan el tag: nunca divide por cero, nunca es negativo, y un tag
presente en todo el catálogo pesa exactamente 1. Los retirados no participan de la ponderación del
corpus (RD-25). TF binario (la pertenencia es binaria, RD-48); vectores L2-normalizados (RD-26).
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np

from recomendaciones.engine.vocabulary import TagVector, Vocabulary, l2_normalize


@dataclass(frozen=True, slots=True)
class CatalogItem:
    item_id: uuid.UUID
    module: str
    tags: frozenset[str]
    available: bool = True


def compute_idf(items: Iterable[CatalogItem], module: str) -> dict[str, float]:
    live = [item for item in items if item.available and item.module == module]
    n = len(live)
    df: dict[str, int] = {}
    for item in live:
        for tag in item.tags:
            df[tag] = df.get(tag, 0) + 1
    return {tag: math.log((1 + n) / (1 + count)) + 1 for tag, count in sorted(df.items())}


def vectorize(item: CatalogItem, vocab: Vocabulary, idf: Mapping[str, float]) -> TagVector | None:
    """Vector TF-IDF L2-normalizado; `None` si ningún tag del ítem tiene dimensión (RD-24)."""
    values = np.zeros(len(vocab), dtype=np.float64)
    for tag in sorted(item.tags):
        i = vocab.index.get(tag)
        if i is not None:
            # Un tag con dimensión pero sin df en el corpus vigente del módulo (p. ej. un retirado
            # que solo él porta) pesa como el más raro posible, nunca 0 ni negativo.
            values[i] = idf.get(tag, _max_idf(idf))
    normalized = l2_normalize(values)
    return None if normalized is None else TagVector(normalized, vocab.version)


def _max_idf(idf: Mapping[str, float]) -> float:
    return max(idf.values()) if idf else 1.0


def vectorize_catalog(
    items: Iterable[CatalogItem], vocab: Vocabulary, *, also_vectorize: Iterable[uuid.UUID] = ()
) -> dict[uuid.UUID, TagVector]:
    """Vectores de todo ítem vigente con tags, más los retirados pedidos explícitamente.

    Los retirados con señales se vectorizan con el IDF del corpus vigente: sus señales siguen
    alimentando el perfil (FR-073) aunque cambie la versión de vocabulario.
    """
    items = sorted(items, key=lambda it: str(it.item_id))
    extra = set(also_vectorize)
    idf_by_module = {module: compute_idf(items, module) for module in sorted({it.module for it in items})}
    out: dict[uuid.UUID, TagVector] = {}
    for item in items:
        if not (item.available or item.item_id in extra):
            continue
        vec = vectorize(item, vocab, idf_by_module[item.module])
        if vec is not None:
            out[item.item_id] = vec
    return out
