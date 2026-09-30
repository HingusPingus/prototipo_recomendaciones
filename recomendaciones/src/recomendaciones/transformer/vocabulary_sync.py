"""Job de vocabulario y reconciliación de vectores (T030). Proceso propio: el pipeline no lo importa (DI-13).

Escritor único de `tag_modules`, `vocab_versions`, `vocab_version_tags` e `item_vectors`. Corre tras cada
sincronización. Usa la vectorización pura de T007; persiste acá.

1. `tag_modules` se recalcula **solo sobre ítems vigentes**, después de aplicar retiros (RD-20, DI-15).
2. El vocabulario vigente es el conjunto de tags de ítems vigentes; su versión es el hash del contenido
   (DI-14). Si difiere de la activa, la versión nueva se crea **inactiva**, se vectoriza entera y recién
   entonces se activa con un único cambio atómico (FR-010g, RD-22): nunca hay instante con la versión
   activa a medio vectorizar, y una interrupción no la activa.
3. **Reconciliación**: todo ítem vigente con tags y sin vector bajo la versión activa recibe uno —también
   un ítem nuevo cuyos tags ya existían, que no cambia el hash—. El arranque desde vacío es el caso
   degenerado del mismo procedimiento. Los vectores que cambiaron por el corpus (IDF) se reescriben; los
   iguales, no: dos corridas sin cambios no reescriben nada.
4. Los retirados con señales se vectorizan bajo la versión activa: sus señales siguen alimentando el
   perfil (FR-073) aunque el vocabulario cambie.
5. Las versiones desactivadas en corridas anteriores se purgan con sus vectores y perfiles derivados.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from recomendaciones.engine.content import CatalogItem, vectorize_catalog
from recomendaciones.engine.vocabulary import TagVector, Vocabulary
from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.db.models import (
    Item,
    ItemTag,
    ItemVector,
    TagModule,
    UserProfile,
    UserSignal,
    VocabVersion,
    VocabVersionTag,
)
from recomendaciones.storage.db.session import SessionFactory

log = logging.getLogger(__name__)
_EQUAL = 1e-9


@dataclass
class VocabularyReport:
    activated: str | None = None  # versión activada en esta corrida, si hubo transición
    active: str | None = None
    vectors_written: int = 0
    purged_versions: int = 0


class VocabularySync:
    def __init__(self, factory: SessionFactory, metrics: Metrics) -> None:
        self._factory = factory
        self._metrics = metrics

    # --- lectura del catálogo -------------------------------------------------------------------
    def _catalog(self, s: Session) -> list[CatalogItem]:
        tags: dict = {}
        for item_id, tag in s.execute(sa.select(ItemTag.item_id, ItemTag.tag_name)):
            tags.setdefault(item_id, set()).add(tag)
        return [
            CatalogItem(r.id, r.module, frozenset(tags.get(r.id, ())), r.status == "available")
            for r in s.execute(sa.select(Item.id, Item.module, Item.status))
        ]

    def _active_version(self, s: Session) -> str | None:
        return s.scalar(
            sa.select(VocabVersion.version).where(VocabVersion.activated_at.is_not(None), VocabVersion.deactivated_at.is_(None))
        )

    # --- tag_modules ---------------------------------------------------------------------------------
    def _refresh_tag_modules(self, s: Session, items: list[CatalogItem]) -> dict[str, set[str]]:
        desired = {(tag, it.module) for it in items if it.available for tag in it.tags}
        current = {(r.tag_name, r.module) for r in s.execute(sa.select(TagModule.tag_name, TagModule.module))}
        for tag, module in sorted(current - desired):
            s.execute(sa.delete(TagModule).where(TagModule.tag_name == tag, TagModule.module == module))
        for tag, module in sorted(desired - current):
            s.execute(insert(TagModule).values(tag_name=tag, module=module, computed_at=sa.func.now()))
        by_module: dict[str, set[str]] = {"peliculas": set(), "juegos": set()}
        for tag, module in desired:
            by_module[module].add(tag)
        return by_module

    # --- vectores ------------------------------------------------------------------------------------
    def _with_signals(self, s: Session) -> set:
        return set(s.scalars(sa.select(UserSignal.item_id).distinct()))

    def _write_vectors(self, s: Session, version: str, vectors: dict, only_changed: bool) -> int:
        existing: dict = {}
        if only_changed:
            existing = {
                r.item_id: np.asarray(r.vector, dtype=np.float64)
                for r in s.execute(sa.select(ItemVector.item_id, ItemVector.vector).where(ItemVector.vocab_version == version))
            }
        written = 0
        for item_id, vec in sorted(vectors.items(), key=lambda kv: str(kv[0])):
            old = existing.get(item_id)
            if old is not None and old.shape == vec.values.shape and np.allclose(old, vec.values, atol=_EQUAL):
                continue
            stmt = insert(ItemVector).values(
                item_id=item_id, vocab_version=version, vector=[float(x) for x in vec.values], computed_at=sa.func.now()
            )
            s.execute(
                stmt.on_conflict_do_update(
                    index_elements=[ItemVector.item_id, ItemVector.vocab_version],
                    set_={"vector": stmt.excluded.vector, "computed_at": sa.func.now()},
                )
            )
            written += 1
        return written

    def _create_version(self, s: Session, vocab: Vocabulary) -> None:
        s.execute(
            insert(VocabVersion)
            .values(version=vocab.version, tag_count=len(vocab), created_at=sa.func.now())
            .on_conflict_do_nothing(index_elements=[VocabVersion.version])
        )
        for tag, dim in sorted(vocab.index.items(), key=lambda kv: kv[1]):
            s.execute(insert(VocabVersionTag).values(version=vocab.version, tag_name=tag, dimension=dim).on_conflict_do_nothing())

    def _activate(self, s: Session, version: str) -> None:
        s.execute(
            sa.update(VocabVersion)
            .where(VocabVersion.activated_at.is_not(None), VocabVersion.deactivated_at.is_(None))
            .values(deactivated_at=sa.func.now())
        )
        s.execute(
            sa.update(VocabVersion).where(VocabVersion.version == version).values(activated_at=sa.func.now(), deactivated_at=None)
        )

    def _purge_old(self, s: Session, started: datetime) -> int:
        stale = list(
            s.scalars(
                sa.select(VocabVersion.version).where(
                    sa.or_(
                        sa.and_(VocabVersion.deactivated_at.is_not(None), VocabVersion.deactivated_at < started),
                        sa.and_(VocabVersion.activated_at.is_(None), VocabVersion.created_at < started),
                    )
                )
            )
        )
        for version in stale:
            s.execute(sa.delete(UserProfile).where(UserProfile.vocab_version == version))
            s.execute(sa.delete(ItemVector).where(ItemVector.vocab_version == version))
            s.execute(sa.delete(VocabVersion).where(VocabVersion.version == version))
        return len(stale)

    # --- corrida --------------------------------------------------------------------------------------
    def run(self) -> VocabularyReport:
        report = VocabularyReport()
        with self._factory.begin() as s:
            # Reloj de la base: dentro de la transacción `now()` es constante, de modo que la versión
            # desactivada en esta misma corrida nunca cae en la purga (solo las de corridas anteriores).
            started = s.scalar(sa.select(sa.func.now()))
            items = self._catalog(s)
            by_module = self._refresh_tag_modules(s, items)
            vocab = Vocabulary.from_tags({t for it in items if it.available for t in it.tags})
            active = self._active_version(s)
            if not vocab.tags:
                report.active = active
                self._emit(s, active, by_module, items)
                return report
            vectors = vectorize_catalog(items, vocab, also_vectorize=self._with_signals(s))
            if active != vocab.version:
                self._metrics.set("vocab_transition_progress", 0.0)
                self._create_version(s, vocab)
                report.vectors_written = self._write_vectors(s, vocab.version, vectors, only_changed=False)
                self._metrics.set("vocab_transition_progress", 1.0)
                self._activate(s, vocab.version)  # un único cambio atómico, dentro de la misma transacción
                report.activated = vocab.version
                log.info("vocabulario activado", extra={"vocab_version": vocab.version, "tags": len(vocab)})
            else:
                report.vectors_written = self._write_vectors(s, vocab.version, vectors, only_changed=True)
                self._metrics.set("vocab_transition_progress", 1.0)
            report.purged_versions = self._purge_old(s, started)
            report.active = vocab.version
            self._emit(s, vocab.version, by_module, items)
        return report

    def _emit(self, s: Session, version: str | None, by_module: dict[str, set[str]], items: list[CatalogItem]) -> None:
        for module, tags in by_module.items():
            self._metrics.set("declarable_tags_total", float(len(tags)), module=module)
        live = [it.item_id for it in items if it.available and it.tags]
        if version is None:
            self._metrics.set("catalog_unvectorized_ratio", 1.0 if live else 0.0)
            return
        vectorized = set(s.scalars(sa.select(ItemVector.item_id).where(ItemVector.vocab_version == version)))
        missing = [i for i in live if i not in vectorized]
        self._metrics.set("catalog_unvectorized_ratio", (len(missing) / len(live)) if live else 0.0)
        self._metrics.set("vector_recompute_lag_seconds", self._unvectorized_lag(s, version, missing))

    @staticmethod
    def _unvectorized_lag(s: Session, version: str, missing: list) -> float:
        """T070, §7.9: antigüedad del ítem vigente más viejo que debería tener vector bajo la versión activa.

        Debe tenerlo desde lo último entre su primera sincronización y la activación de la versión. Sin
        faltantes vale 0: un catálogo estable no reescribe vectores y no por eso está atrasado.
        """
        if not missing:
            return 0.0
        first_seen = s.scalar(sa.select(sa.func.min(Item.first_synced_at)).where(Item.id.in_(missing)))
        activated = s.scalar(sa.select(VocabVersion.activated_at).where(VocabVersion.version == version))
        since = max(t for t in (first_seen, activated) if t is not None)
        return max((datetime.now(UTC) - since).total_seconds(), 0.0)


__all__ = ["TagVector", "VocabularyReport", "VocabularySync"]
