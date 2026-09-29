"""T010 — señal colaborativa por k vecinos (FR-023, FR-025, FR-070, RD-105)."""

from __future__ import annotations

import importlib
import inspect
import random
import sys
import uuid
from pathlib import Path

import numpy as np

from recomendaciones.engine.collaborative import collaborative_scores
from recomendaciones.engine.content import CatalogItem, vectorize_catalog
from recomendaciones.engine.profile import ProfileInputs, ProfileSignal, SignalWeights, build_profile
from recomendaciones.engine.vocabulary import TagVector, Vocabulary

VOCAB = Vocabulary.from_tags(["a", "b", "c"])


def _v(*values: float) -> TagVector:
    arr = np.array(values, dtype=float)
    return TagVector(arr / np.linalg.norm(arr), VOCAB.version)


I1, I2, I3 = uuid.UUID(int=101), uuid.UUID(int=102), uuid.UUID(int=103)


def test_k_has_no_default_it_comes_from_configuration() -> None:
    assert inspect.signature(collaborative_scores).parameters["k"].default is inspect.Parameter.empty


def test_fewer_users_than_k_uses_available_without_failing() -> None:
    u1, u2 = uuid.UUID(int=1), uuid.UUID(int=2)
    result = collaborative_scores(
        _v(1, 0, 0), {u1: _v(1, 0.1, 0), u2: _v(1, 0, 0.2)}, {u1: frozenset({I1}), u2: frozenset({I2})}, [I1, I2, I3], k=3
    )
    assert len(result.neighbors) == 2
    assert result.scores[I1] > 0 and result.scores[I2] > 0 and result.scores[I3] == 0


def test_zero_neighbors_is_neutral() -> None:
    result = collaborative_scores(_v(1, 0, 0), {}, {}, [I1, I2], k=20)
    assert result.scores == {I1: 0.0, I2: 0.0} and result.neighbors == ()
    assert collaborative_scores(None, {uuid.uuid4(): _v(1, 0, 0)}, {}, [I1], k=20).scores == {I1: 0.0}


def test_neighbor_selection_is_deterministic_under_similarity_ties() -> None:
    target = _v(1, 0, 0)
    users = {uuid.UUID(int=i): _v(1, 1, 0) for i in range(1, 8)}  # todos con idéntica similitud
    likes = {u: frozenset({uuid.UUID(int=500 + n)}) for n, u in enumerate(users)}
    candidates = sorted({i for s in likes.values() for i in s})
    baseline = collaborative_scores(target, users, likes, candidates, k=3)
    for seed in range(100):
        keys = list(users)
        random.Random(seed).shuffle(keys)
        shuffled = {k: users[k] for k in keys}
        again = collaborative_scores(target, shuffled, likes, list(reversed(candidates)), k=3)
        assert again.neighbors == baseline.neighbors and again.scores == baseline.scores


def test_zero_similarity_neighbor_counts_for_nothing() -> None:
    orthogonal, similar = uuid.UUID(int=1), uuid.UUID(int=2)
    result = collaborative_scores(
        _v(1, 0, 0),
        {orthogonal: _v(0, 1, 0), similar: _v(1, 1, 0)},
        {orthogonal: frozenset({I1}), similar: frozenset({I2})},
        [I1, I2],
        k=2,
    )
    assert [n.user_id for n in result.neighbors] == [similar]
    assert result.scores[I1] == 0.0


def test_scores_are_bounded() -> None:
    users = {uuid.UUID(int=i): _v(1, i / 10, 0) for i in range(1, 30)}
    likes = {u: frozenset({I1, I2}) for u in users}
    result = collaborative_scores(_v(1, 0, 0), users, likes, [I1, I2, I3], k=20)
    assert all(-1.0 <= s <= 1.0 for s in result.scores.values())
    assert len(result.neighbors) == 20


def _prototype_data():  # noqa: ANN202
    proto = Path(__file__).resolve().parents[2] / "Prototipo-Referencia"
    sys.path.insert(0, str(proto))
    try:
        for name in ("domain", "data"):
            sys.modules.pop(name, None)
        return importlib.import_module("data")
    finally:
        sys.path.remove(str(proto))
        for name in ("domain", "data"):
            sys.modules.pop(name, None)


def test_all_negative_neighbors_never_raise_an_item() -> None:
    """Regresión del prototipo: el usuario 1 dislikeó Endgame; el 3 la likeó. En el prototipo, normalizar
    por el máximo negativo invertía el signo y Endgame recibía +3,23 (`CollaborativeRecommender`)."""
    data = _prototype_data()
    movies = [CatalogItem(m.id, "peliculas", frozenset(m.tags)) for m in data.MOVIES]
    vocab = Vocabulary.from_tags({t for m in movies for t in m.tags})
    vectors = vectorize_catalog(movies, vocab)
    seed = {m.item_id: m.tags for m in movies}
    weights = SignalWeights(peso_like=1.0, peso_dislike=-1.0)

    def profile(user_id: uuid.UUID) -> TagVector:
        fbs = [f for f in data.FEEDBACKS if f.user_id == user_id and f.item_type == "movie"]
        signals = tuple(ProfileSignal(f.item_id, f.state, f.timestamp, n) for n, f in enumerate(fbs))
        built = build_profile(ProfileInputs(frozenset(), frozenset(), signals), vectors, seed, vocab, weights)
        assert built is not None
        return built.vector

    u1, u3 = data.U1, data.U3
    likes_u3 = frozenset(f.item_id for f in data.FEEDBACKS if f.user_id == u3 and f.state == "like")
    assert profile(u1).cosine(profile(u3)) < 0
    result = collaborative_scores(profile(u1), {u3: profile(u3)}, {u3: likes_u3}, [m.item_id for m in movies], k=20)
    assert result.neighbors == ()
    assert max(result.scores.values()) == 0.0
    endgame = data.MOVIES[3].id
    assert result.scores[endgame] == 0.0
