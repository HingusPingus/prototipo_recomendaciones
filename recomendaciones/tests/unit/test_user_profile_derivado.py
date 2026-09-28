"""T056 — perfil vectorial derivado puro: solo se reconstruye desde sus insumos (FR-087)."""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime

import numpy as np

import recomendaciones.engine.profile as profile_module
from recomendaciones.engine.content import CatalogItem, vectorize_catalog
from recomendaciones.engine.profile import ProfileInputs, ProfileSignal, SignalWeights, build_profile
from recomendaciones.engine.vocabulary import Vocabulary

INCREMENTAL = ("update", "partial", "incremental", "delta", "apply", "add_signal", "accumulate", "merge")


def test_the_only_public_operation_is_rebuild_from_inputs() -> None:
    public_functions = {n for n, obj in inspect.getmembers(profile_module, inspect.isfunction) if not n.startswith("_") and obj.__module__ == profile_module.__name__}
    assert public_functions == {"build_profile", "derive_inherited", "latest_preferences"}
    offenders = [n for n in dir(profile_module) if any(word in n.lower() for word in INCREMENTAL)]
    assert offenders == [], offenders  # falla si se agrega un camino de actualización incremental


def test_build_profile_takes_no_previous_profile() -> None:
    params = set(inspect.signature(build_profile).parameters)
    assert not {p for p in params if "profile" in p or "previous" in p or "current" in p}


def test_rebuilding_twice_on_the_same_inputs_gives_the_same_vector() -> None:
    items = [CatalogItem(uuid.UUID(int=i), "peliculas", frozenset({f"t{i % 4}", "comun"})) for i in range(1, 9)]
    vocab = Vocabulary.from_tags({t for it in items for t in it.tags})
    vectors = vectorize_catalog(items, vocab)
    seed = {it.item_id: it.tags for it in items}
    inputs = ProfileInputs(
        frozenset({"t0", "t1"}),
        frozenset({"t2"}),
        tuple(ProfileSignal(it.item_id, "like" if n % 2 else "dislike", datetime(2026, 9, 1, tzinfo=UTC), n) for n, it in enumerate(items)),
    )
    a = build_profile(inputs, vectors, seed, vocab, SignalWeights(1.0, -1.0))
    b = build_profile(inputs, vectors, seed, vocab, SignalWeights(1.0, -1.0))
    np.testing.assert_array_equal(a.vector.values, b.vector.values)


def test_the_persisted_profile_is_never_an_input_of_its_own_reconstruction() -> None:
    """El perfil en `user_profiles` es caché descartable: los insumos no lo leen (FR-087, INV-2)."""
    import recomendaciones.worker.inputs as inputs_module

    source = inspect.getsource(inputs_module)
    assert "UserProfile" not in source and "user_profiles" not in source


def test_profile_is_reconstructible_from_the_declaration_alone_after_purge() -> None:
    """FR-087: si las señales se purgan, el perfil sigue siendo reconstruible desde la declaración."""
    items = [CatalogItem(uuid.UUID(int=i), "juegos", frozenset({f"t{i % 3}"})) for i in range(1, 7)]
    vocab = Vocabulary.from_tags({t for it in items for t in it.tags})
    vectors = vectorize_catalog(items, vocab)
    purged = ProfileInputs(frozenset({"t0", "t1", "t2"}), frozenset(), ())
    assert build_profile(purged, vectors, {it.item_id: it.tags for it in items}, vocab, SignalWeights(1.0, -1.0)) is not None
