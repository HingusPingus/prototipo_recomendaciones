"""T007 — TF-IDF sobre vocabulario compartido (FR-010d, FR-010f, FR-022, RD-25, RD-105)."""

from __future__ import annotations

import math
import random
import uuid

import numpy as np
import pytest

from recomendaciones.engine.content import CatalogItem, compute_idf, vectorize, vectorize_catalog
from recomendaciones.engine.vocabulary import TagVector, Vocabulary, VocabularyMismatch


def _item(module: str, *tags: str, available: bool = True) -> CatalogItem:
    return CatalogItem(item_id=uuid.uuid4(), module=module, tags=frozenset(tags), available=available)


CATALOG = [
    _item("peliculas", "horror", "sobrenatural"),
    _item("peliculas", "horror", "drama"),
    _item("peliculas", "comedia"),
    _item("juegos", "horror", "survival"),
    _item("juegos", "rpg", "fantasia"),
    _item("juegos", "survival"),
]


def test_vocabulary_is_deterministic_regardless_of_input_order() -> None:
    tags = ["horror", "rpg", "drama", "comedia", "survival"]
    shuffled = tags[:]
    random.Random(7).shuffle(shuffled)
    a, b = Vocabulary.from_tags(tags), Vocabulary.from_tags(shuffled)
    assert a.version == b.version
    assert a.tags == b.tags == tuple(sorted(tags))
    assert Vocabulary.from_tags(tags + ["nuevo"]).version != a.version


def test_single_space_shared_by_both_modules() -> None:
    vocab = Vocabulary.from_tags({t for item in CATALOG for t in item.tags})
    vectors = vectorize_catalog(CATALOG, vocab)
    movie, game = vectors[CATALOG[0].item_id], vectors[CATALOG[3].item_id]
    assert movie.vocab_version == game.vocab_version == vocab.version
    assert movie.values.shape == game.values.shape == (len(vocab.tags),)
    assert movie.cosine(game) > 0  # comparables: comparten «horror»


def test_tag_of_a_single_module_still_has_a_dimension() -> None:
    vocab = Vocabulary.from_tags({t for item in CATALOG for t in item.tags})
    assert "rpg" in vocab.index and "comedia" in vocab.index


def test_comparing_vectors_of_different_versions_raises() -> None:
    v1 = Vocabulary.from_tags(["a", "b"])
    v2 = Vocabulary.from_tags(["a", "b", "c"])
    x = TagVector(np.array([1.0, 0.0]), v1.version)
    y = TagVector(np.array([1.0, 0.0, 0.0]), v2.version)
    with pytest.raises(VocabularyMismatch):
        x.cosine(y)


def test_idf_formula_and_tag_in_every_item_weighs_exactly_one() -> None:
    items = [_item("peliculas", "drama", "x"), _item("peliculas", "drama"), _item("peliculas", "drama", "y")]
    idf = compute_idf(items, "peliculas")
    assert idf["drama"] == pytest.approx(1.0)  # ln((1+3)/(1+3)) + 1 — el prototipo daba −0,405
    assert idf["x"] == pytest.approx(math.log(4 / 2) + 1)
    assert all(w > 0 for w in idf.values())


def test_retired_items_do_not_participate_in_corpus_weighting() -> None:
    live = [_item("peliculas", "drama"), _item("peliculas", "drama", "x")]
    with_retired = live + [_item("peliculas", "x", available=False), _item("peliculas", "x", available=False)]
    assert compute_idf(live, "peliculas") == compute_idf(with_retired, "peliculas")


def test_vectors_are_l2_normalized_and_item_without_known_tags_has_no_vector() -> None:
    vocab = Vocabulary.from_tags(["horror", "drama"])
    idf = compute_idf(CATALOG, "peliculas")
    vec = vectorize(CATALOG[1], vocab, idf)
    assert vec is not None and np.linalg.norm(vec.values) == pytest.approx(1.0)
    assert vectorize(_item("peliculas", "desconocido"), vocab, idf) is None  # RD-24


def test_vectorization_is_deterministic_under_shuffling() -> None:
    vocab = Vocabulary.from_tags({t for item in CATALOG for t in item.tags})
    shuffled = CATALOG[:]
    random.Random(3).shuffle(shuffled)
    a, b = vectorize_catalog(CATALOG, vocab), vectorize_catalog(shuffled, vocab)
    assert a.keys() == b.keys()
    for key in a:
        np.testing.assert_array_equal(a[key].values, b[key].values)


def test_retired_items_get_no_vector_from_catalog_vectorization() -> None:
    retired = _item("juegos", "rpg", available=False)
    vocab = Vocabulary.from_tags(["rpg"])
    assert retired.item_id not in vectorize_catalog([retired, _item("juegos", "rpg")], vocab)


def test_retired_items_with_signals_can_be_vectorized_with_live_idf() -> None:
    """FR-073: las señales sobre retirados siguen alimentando el perfil, también tras cambiar de versión."""
    retired = _item("juegos", "rpg", "fantasia", available=False)
    live = [_item("juegos", "rpg"), _item("juegos", "fantasia"), _item("juegos", "rpg", "fantasia")]
    vocab = Vocabulary.from_tags(["rpg", "fantasia"])
    vectors = vectorize_catalog([retired, *live], vocab, also_vectorize={retired.item_id})
    assert retired.item_id in vectors
    assert compute_idf([retired, *live], "juegos") == compute_idf(live, "juegos")
