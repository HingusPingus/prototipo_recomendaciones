"""Instantánea del catálogo para el recálculo: vocabulario activo, vectores, vigencia y popularidad.

Cargar todos los vectores en cada recálculo sería el costo dominante; la instantánea se cachea en el
proceso y se recarga solo cuando cambia una huella barata (versión activa de vocabulario, volumen y
última escritura de vectores, sincronización del catálogo, popularidad y pertenencia a módulos).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass

import numpy as np
import sqlalchemy as sa
from sqlalchemy.orm import Session

from recomendaciones.engine.vocabulary import TagVector, Vocabulary
from recomendaciones.storage.db.models import Item, ItemPopularity, ItemPromotion, ItemTag, ItemVector, VocabVersion, VocabVersionTag


@dataclass(frozen=True, slots=True)
class CatalogItemRow:
    item_id: uuid.UUID
    module: str
    available: bool
    min_age_ordinal: int
    tags: frozenset[str]


@dataclass(frozen=True)
class CatalogSnapshot:
    vocab: Vocabulary
    vectors: dict[uuid.UUID, TagVector]
    items: dict[uuid.UUID, CatalogItemRow]
    popularity: dict[uuid.UUID, float]
    shared_tags: frozenset[str]
    promoted: frozenset[uuid.UUID] = frozenset()  # conjunto general (DI-27); el resto vigente es emergente

    def seed_items(self, modules: tuple[str, ...]) -> dict[uuid.UUID, frozenset[str]]:
        """Ítems de los módulos dados con vector: fuente de los centroides de la declaración (T008).

        Incluye a los retirados que conservan vector: si el retiro sacara al ítem del centroide de un tag
        declarado, retirar un ítem alteraría el perfil de quien lo declaró, contra DI-11 y FR-073.
        """
        return {i.item_id: i.tags for i in self.items.values() if i.module in modules and i.item_id in self.vectors}


_FINGERPRINT_SQL = sa.text(
    """
    WITH active AS (
        SELECT version FROM vocab_versions WHERE activated_at IS NOT NULL AND deactivated_at IS NULL
    )
    SELECT (SELECT version FROM active),
           (SELECT count(*) FROM item_vectors WHERE vocab_version = (SELECT version FROM active)),
           (SELECT max(computed_at) FROM item_vectors WHERE vocab_version = (SELECT version FROM active)),
           (SELECT max(synced_at) FROM items),
           (SELECT count(*) FROM items WHERE status = 'retired'),
           (SELECT max(computed_at) FROM item_popularity WHERE config_version = :cfg),
           (SELECT max(computed_at) FROM tag_modules),
           (SELECT count(*) FROM tag_modules),
           (SELECT count(*) FROM item_promotions)
    """
)


def load_snapshot(s: Session, config_version: str) -> CatalogSnapshot | None:
    version = s.scalar(
        sa.select(VocabVersion.version).where(
            VocabVersion.activated_at.is_not(None), VocabVersion.deactivated_at.is_(None)
        )
    )
    if version is None:
        return None
    dims = s.execute(
        sa.select(VocabVersionTag.tag_name, VocabVersionTag.dimension)
        .where(VocabVersionTag.version == version)
        .order_by(VocabVersionTag.dimension)
    ).all()
    tags = tuple(t for t, _ in dims)
    vocab = Vocabulary(version=version, tags=tags, index={t: d for t, d in dims})
    vectors = {
        row.item_id: TagVector(np.asarray(row.vector, dtype=np.float64), version)
        for row in s.execute(sa.select(ItemVector.item_id, ItemVector.vector).where(ItemVector.vocab_version == version))
    }
    tag_rows: dict[uuid.UUID, set[str]] = {}
    for item_id, tag in s.execute(sa.select(ItemTag.item_id, ItemTag.tag_name)):
        tag_rows.setdefault(item_id, set()).add(tag)
    items = {
        r.id: CatalogItemRow(r.id, r.module, r.status == "available", r.min_age_ordinal, frozenset(tag_rows.get(r.id, ())))
        for r in s.execute(sa.select(Item.id, Item.module, Item.status, Item.min_age_ordinal))
    }
    popularity = dict(
        s.execute(
            sa.select(ItemPopularity.item_id, ItemPopularity.popularity_score).where(
                ItemPopularity.config_version == config_version
            )
        ).all()
    )
    shared = frozenset(
        s.scalars(sa.text("SELECT tag_name FROM tag_modules GROUP BY tag_name HAVING count(*) > 1"))
    )
    promoted = frozenset(s.scalars(sa.select(ItemPromotion.item_id)))
    return CatalogSnapshot(vocab, vectors, items, popularity, shared, promoted)


class CatalogCache:
    """Instantánea compartida por los recálculos del proceso, recargada cuando cambia la huella."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._key: tuple | None = None
        self._snapshot: CatalogSnapshot | None = None

    def get(self, s: Session, config_version: str) -> CatalogSnapshot | None:
        key = tuple(s.execute(_FINGERPRINT_SQL, {"cfg": config_version}).one())
        with self._lock:
            if key != self._key:
                self._snapshot = load_snapshot(s, config_version)
                self._key = key
            return self._snapshot
