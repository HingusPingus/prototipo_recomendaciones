"""Batch de top-N de respaldo (T038): **consumidor** de `item_popularity`, nunca productor (T063 produce).

Por módulo y de forma global —nunca por usuario (FR-033c)—: toma los ítems **vigentes** del módulo
(FR-033a1, §4.4 punto 2) con su `popularity_score` bajo la versión de configuración **activa** (DI-12:
jamás mezcla ventanas), los ordena por ese puntaje —no por `like_count` (RD-12)— con el desempate fijo,
los diversifica por MMR con el tope de cluster (FR-033b, FR-071a, SC-025) y publica
`min(fallback_stored_size, candidatos)` ítems en `fallback:v{cfg}:{module}` (FR-033f). Sin likes el
respaldo existe igual: todos los puntajes son 0 y ordena el desempate (FR-033a2, RD-106). Vive solo en
Redis: ante pérdida se recomputa corriendo este batch (§3.3). **No** lleva cuota de novedades (RD-102).
Los filtros de cada usuario se aplican al servir (FR-033d, T037), no acá.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import numpy as np
import sqlalchemy as sa

from recomendaciones.config.loader import EngineConfig
from recomendaciones.engine.postprocess import PostprocessRequest, postprocess
from recomendaciones.engine.scoring import Candidate, ScoredCandidate, ScoringResult, tiebreak_key
from recomendaciones.engine.vocabulary import TagVector, Vocabulary
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import ExclusionSet, Module
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository
from recomendaciones.storage.db.models import ItemVector, VocabVersion, VocabVersionTag
from recomendaciones.storage.db.session import SessionFactory

_CANDIDATES_SQL = sa.text(
    """
    SELECT i.id, i.min_age_ordinal, COALESCE(p.popularity_score, 0) AS score
    FROM items i
    LEFT JOIN item_popularity p ON p.item_id = i.id AND p.config_version = :cfg
    WHERE i.status = 'available' AND i.module = :module
    """
)
_NOBODY = uuid.UUID(int=0)  # el respaldo no tiene usuario: los filtros de cada uno se aplican al servir


class FallbackJob:
    def __init__(self, factory: SessionFactory, repository: RecommendationRepository, config: EngineConfig, metrics: Metrics) -> None:
        self._factory = factory
        self._repository = repository
        self._cfg = config
        self._metrics = metrics

    def _vocabulary(self, s) -> tuple[Vocabulary | None, dict[uuid.UUID, TagVector]]:  # noqa: ANN001
        version = s.scalar(
            sa.select(VocabVersion.version).where(VocabVersion.activated_at.is_not(None), VocabVersion.deactivated_at.is_(None))
        )
        if version is None:
            return None, {}
        dims = s.execute(
            sa.select(VocabVersionTag.tag_name, VocabVersionTag.dimension).where(VocabVersionTag.version == version).order_by(VocabVersionTag.dimension)
        ).all()
        vocab = Vocabulary(version, tuple(t for t, _ in dims), {t: d for t, d in dims})
        vectors = {
            r.item_id: TagVector(np.asarray(r.vector, dtype=np.float64), version)
            for r in s.execute(sa.select(ItemVector.item_id, ItemVector.vector).where(ItemVector.vocab_version == version))
        }
        return vocab, vectors

    def build(self, module: Module) -> RecommendationEntry:
        with self._factory() as s:
            vocab, vectors = self._vocabulary(s)
            rows = s.execute(_CANDIDATES_SQL, {"cfg": self._cfg.config_version, "module": module.value}).all()
        ranked = sorted(
            (
                ScoredCandidate(
                    Candidate(r.id, module.value, True, r.min_age_ordinal, vectors.get(r.id), float(r.score), frozenset()),
                    float(r.score),
                )
                for r in rows
            ),
            key=tiebreak_key,
        )
        result = postprocess(
            ScoringResult(tuple(ranked), self._cfg.config_version),
            PostprocessRequest(
                user_max_age_ordinal=self._cfg.max_ordinal,  # sin filtro etario acá: se aplica al servir
                exclusions=ExclusionSet(_NOBODY, ()),
                lambda_mmr=self._cfg.lambda_mmr,
                max_cluster_share=self._cfg.diversity_max_cluster_share,
                limit=self._cfg.fallback_stored_size,
                cluster_of=(lambda c: c.vector.principal_tag(vocab) if c.vector is not None and vocab else None),
            ),
        )
        if result.relaxations:
            self._metrics.inc("diversity_cap_relaxed_total", result.relaxations, module=module.value)
        return RecommendationEntry(
            user_id=None,
            module=module,
            config_version=self._cfg.config_version,
            vocab_version=vocab.version if vocab else "",
            max_age_ordinal=None,
            computed_at=datetime.now(UTC),
            items=tuple(CachedItem(i.item_id, i.rank, i.score, i.min_age_ordinal) for i in result.items),
        )

    def run(self) -> dict[Module, int]:
        published: dict[Module, int] = {}
        for module in Module:
            entry = self.build(module)
            self._repository.write_fallback(entry)
            published[module] = len(entry.items)
        return published
