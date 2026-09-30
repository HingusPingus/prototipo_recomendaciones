"""T009 — señal content-based (FR-021, FR-022)."""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from recomendaciones.engine.content import CatalogItem, content_scores, vectorize_catalog
from recomendaciones.engine.vocabulary import TagVector, Vocabulary, VocabularyMismatch

HORROR = CatalogItem(uuid.UUID(int=1), "peliculas", frozenset({"horror", "sobrenatural"}))
COMEDY = CatalogItem(uuid.UUID(int=2), "peliculas", frozenset({"comedia", "familiar"}))
NO_VECTOR = uuid.UUID(int=3)


def _setup() -> tuple[Vocabulary, dict[uuid.UUID, TagVector]]:
    vocab = Vocabulary.from_tags(HORROR.tags | COMEDY.tags)
    return vocab, vectorize_catalog([HORROR, COMEDY], vocab)


def test_horror_profile_scores_horror_item_higher() -> None:
    _vocab, vectors = _setup()
    profile = vectors[HORROR.item_id]
    scores = content_scores(profile, {**vectors, NO_VECTOR: None})
    assert scores[HORROR.item_id] > scores[COMEDY.item_id]
    assert scores[NO_VECTOR] == 0.0
    assert all(-1.0 <= s <= 1.0 for s in scores.values())


def test_empty_profile_is_neutral() -> None:
    _, vectors = _setup()
    assert content_scores(None, vectors) == {k: 0.0 for k in vectors}


def test_different_vocab_version_raises() -> None:
    _, vectors = _setup()
    other = TagVector(np.ones(4) / 2, "vocab:otra")
    with pytest.raises(VocabularyMismatch):
        content_scores(other, vectors)


def test_deterministic() -> None:
    _, vectors = _setup()
    assert content_scores(vectors[HORROR.item_id], vectors) == content_scores(vectors[HORROR.item_id], vectors)
