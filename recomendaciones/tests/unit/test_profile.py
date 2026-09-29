"""T008 — similitud coseno y construcción de perfil (FR-022a…c, FR-029d, FR-085…FR-087, RD-97, RD-109)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from recomendaciones.engine.content import CatalogItem, vectorize_catalog
from recomendaciones.engine.profile import ProfileInputs, ProfileSignal, SignalWeights, build_profile, derive_inherited
from recomendaciones.engine.similarity import cosine
from recomendaciones.engine.vocabulary import TagVector, Vocabulary

T0 = datetime(2026, 9, 1, tzinfo=UTC)
WEIGHTS = SignalWeights(peso_like=1.0, peso_dislike=-1.0)


def _catalog() -> tuple[Vocabulary, dict[uuid.UUID, TagVector], dict[uuid.UUID, frozenset[str]], list[CatalogItem]]:
    specs = [
        ("horror", "h1"), ("horror", "h2"), ("horror", "h3"), ("horror", "h4"), ("horror", "h5"),
        ("comedia", "c1"), ("comedia", "c2"), ("drama", "d1"), ("drama", "d2"),
        ("scifi", "s1"), ("scifi", "s2"), ("anim", "a1"), ("anim", "a2"),
    ]
    items = [CatalogItem(uuid.UUID(int=i + 1), "peliculas", frozenset(tags)) for i, tags in enumerate(specs)]
    vocab = Vocabulary.from_tags({t for it in items for t in it.tags})
    vectors = vectorize_catalog(items, vocab)
    seed = {it.item_id: it.tags for it in items}
    return vocab, vectors, seed, items


def _sig(item: CatalogItem, kind: str, minutes: int, seq: int) -> ProfileSignal:
    return ProfileSignal(item.item_id, kind, T0 + timedelta(minutes=minutes), seq)


def test_null_vector_similarity_is_zero() -> None:
    vocab = Vocabulary.from_tags(["a", "b"])
    zero = TagVector(np.zeros(2), vocab.version)
    one = TagVector(np.array([1.0, 0.0]), vocab.version)
    assert cosine(zero, one) == 0.0
    assert cosine(None, one) == 0.0


@given(
    st.lists(st.floats(-1e6, 1e6, allow_nan=False), min_size=3, max_size=3),
    st.lists(st.floats(-1e6, 1e6, allow_nan=False), min_size=3, max_size=3),
)
def test_cosine_always_within_bounds(a: list[float], b: list[float]) -> None:
    vocab = Vocabulary.from_tags(["x", "y", "z"])
    value = cosine(TagVector(np.array(a), vocab.version), TagVector(np.array(b), vocab.version))
    assert -1.0 <= value <= 1.0


@settings(max_examples=60)
@given(st.lists(st.tuples(st.integers(0, 12), st.sampled_from(["like", "dislike", "consumo"])), min_size=1, max_size=15))
def test_profile_is_l2_normalized_for_any_signals(pairs: list[tuple[int, str]]) -> None:
    vocab, vectors, seed, items = _catalog()
    signals = tuple(_sig(items[i], kind, n, n) for n, (i, kind) in enumerate(pairs))
    profile = build_profile(ProfileInputs(frozenset(), frozenset(), signals), vectors, seed, vocab, WEIGHTS)
    if profile is not None:
        assert np.linalg.norm(profile.vector.values) == pytest.approx(1.0)


def test_consumo_does_not_alter_the_profile() -> None:
    vocab, vectors, seed, items = _catalog()
    base = (_sig(items[0], "like", 0, 1),)
    with_consumo = base + (_sig(items[5], "consumo", 5, 2), _sig(items[0], "consumo", 6, 3))
    a = build_profile(ProfileInputs(frozenset(), frozenset(), base), vectors, seed, vocab, WEIGHTS)
    b = build_profile(ProfileInputs(frozenset(), frozenset(), with_consumo), vectors, seed, vocab, WEIGHTS)
    np.testing.assert_array_equal(a.vector.values, b.vector.values)  # type: ignore[union-attr]
    assert build_profile(
        ProfileInputs(frozenset(), frozenset(), (_sig(items[5], "consumo", 0, 1),)), vectors, seed, vocab, WEIGHTS
    ) is None


def test_later_like_reverts_earlier_dislike() -> None:
    vocab, vectors, seed, items = _catalog()
    only_like = (_sig(items[5], "like", 10, 2),)
    dislike_then_like = (_sig(items[5], "dislike", 0, 1), _sig(items[5], "like", 10, 2))
    a = build_profile(ProfileInputs(frozenset(), frozenset(), only_like), vectors, seed, vocab, WEIGHTS)
    b = build_profile(ProfileInputs(frozenset(), frozenset(), dislike_then_like), vectors, seed, vocab, WEIGHTS)
    np.testing.assert_allclose(a.vector.values, b.vector.values)  # type: ignore[union-attr]


def test_contradictory_signals_with_same_timestamp_resolve_deterministically() -> None:
    vocab, vectors, seed, items = _catalog()
    one = (_sig(items[5], "like", 0, 1), _sig(items[5], "dislike", 0, 2))
    two = tuple(reversed(one))
    a = build_profile(ProfileInputs(frozenset(), frozenset(), one), vectors, seed, vocab, WEIGHTS)
    b = build_profile(ProfileInputs(frozenset(), frozenset(), two), vectors, seed, vocab, WEIGHTS)
    np.testing.assert_array_equal(a.vector.values, b.vector.values)  # type: ignore[union-attr]
    assert a.vector.component(vocab, "comedia") < 0  # type: ignore[union-attr]  # gana seq=2 (dislike)


def test_declaration_without_signals_gives_affine_profile() -> None:
    vocab, vectors, seed, items = _catalog()
    declared = frozenset({"horror", "comedia", "drama", "scifi", "anim"})
    profile = build_profile(ProfileInputs(declared, frozenset(), ()), vectors, seed, vocab, WEIGHTS)
    assert profile is not None
    for tag in declared:
        assert profile.vector.component(vocab, tag) > 0


def test_inherited_tags_are_derived_not_declared() -> None:
    inherited = derive_inherited(declared_other=frozenset({"horror", "rpg"}), shared_tags=frozenset({"horror", "comedia"}))
    assert inherited == frozenset({"horror"})
    vocab, vectors, seed, items = _catalog()
    own = frozenset({"comedia", "drama", "scifi", "anim", "h1"})
    profile = build_profile(ProfileInputs(own, inherited, ()), vectors, seed, vocab, WEIGHTS)
    assert profile.vector.component(vocab, "horror") > 0  # type: ignore[union-attr]


def test_three_dislikes_can_cancel_a_declared_tag_and_a_like_raises_it_again() -> None:
    """FR-086b: el peso puede llegar a cero o negativo; la declaración no se toca."""
    vocab, vectors, seed, items = _catalog()
    declared = frozenset({"horror", "comedia", "drama", "scifi", "anim"})
    inputs = ProfileInputs(declared, frozenset(), tuple(_sig(items[i], "dislike", i, i) for i in range(3)))
    profile = build_profile(inputs, vectors, seed, vocab, WEIGHTS)
    assert profile.vector.component(vocab, "horror") <= 0  # type: ignore[union-attr]
    assert inputs.declared_tags == declared
    relike = ProfileInputs(declared, frozenset(), inputs.signals + (_sig(items[0], "like", 99, 99),))
    after = build_profile(relike, vectors, seed, vocab, WEIGHTS)
    assert after.vector.component(vocab, "horror") > profile.vector.component(vocab, "horror")  # type: ignore[union-attr]


def test_general_profile_aggregates_both_modules() -> None:
    movie = CatalogItem(uuid.UUID(int=100), "peliculas", frozenset({"horror", "drama"}))
    game = CatalogItem(uuid.UUID(int=200), "juegos", frozenset({"rpg", "fantasia"}))
    vocab = Vocabulary.from_tags(movie.tags | game.tags)
    vectors = vectorize_catalog([movie, game], vocab)
    seed = {movie.item_id: movie.tags, game.item_id: game.tags}
    signals = (ProfileSignal(movie.item_id, "like", T0, 1), ProfileSignal(game.item_id, "like", T0, 2))
    general = build_profile(ProfileInputs(frozenset(), frozenset(), signals), vectors, seed, vocab, WEIGHTS)
    assert general.vector.component(vocab, "horror") > 0 and general.vector.component(vocab, "rpg") > 0  # type: ignore[union-attr]


def test_signals_on_items_without_vector_are_ignored_without_failing() -> None:
    vocab, vectors, seed, items = _catalog()
    ghost = ProfileSignal(uuid.uuid4(), "like", T0, 1)
    assert build_profile(ProfileInputs(frozenset(), frozenset(), (ghost,)), vectors, seed, vocab, WEIGHTS) is None


def test_signal_count_counts_preference_items() -> None:
    vocab, vectors, seed, items = _catalog()
    signals = (_sig(items[0], "like", 0, 1), _sig(items[1], "dislike", 1, 2), _sig(items[2], "consumo", 2, 3))
    profile = build_profile(ProfileInputs(frozenset(), frozenset(), signals), vectors, seed, vocab, WEIGHTS)
    assert profile.signal_count == 2  # type: ignore[union-attr]
