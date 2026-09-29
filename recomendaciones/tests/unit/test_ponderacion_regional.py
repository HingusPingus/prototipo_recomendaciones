"""T061 — ponderación regional del término colaborativo (FR-081…FR-081b, FR-090, FR-090a, FR-096, SC-031)."""

from __future__ import annotations

import uuid

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from recomendaciones.engine.collaborative import collaborative_scores, regional_weights
from recomendaciones.engine.vocabulary import TagVector, Vocabulary

VOCAB = Vocabulary.from_tags(["a", "b", "c"])


def _v(*values: float) -> TagVector:
    arr = np.array(values, dtype=float)
    return TagVector(arr / np.linalg.norm(arr), VOCAB.version)


def _population(n_local: int, n_foreign: int):  # noqa: ANN202
    rng = np.random.default_rng(7)
    users, regions, likes = {}, {}, {}
    for i in range(n_local + n_foreign):
        uid = uuid.UUID(int=i + 1)
        users[uid] = _v(1.0, float(rng.uniform(0, 1)), float(rng.uniform(0, 1)))
        regions[uid] = "AR" if i < n_local else "UY"
        likes[uid] = frozenset({uuid.UUID(int=1000 + (i % 7))})
    return users, regions, likes


CANDIDATES = [uuid.UUID(int=1000 + i) for i in range(7)]


def test_factor_zero_is_identical_to_no_segmentation() -> None:
    users, regions, likes = _population(5, 30)
    plain = collaborative_scores(_v(1, 0.5, 0.2), users, likes, CANDIDATES, k=20, min_neighbors=10)
    neutral = collaborative_scores(
        _v(1, 0.5, 0.2), users, likes, CANDIDATES, k=20, min_neighbors=10, weights=regional_weights("AR", regions, 0.0)
    )
    assert neutral.scores == plain.scores and neutral.neighbors == plain.neighbors  # SC-031, FR-090


@given(st.floats(min_value=0.0, max_value=0.999999, exclude_max=False))
def test_extraregional_weight_is_positive_for_every_admissible_factor(factor: float) -> None:
    weights = regional_weights("AR", {uuid.UUID(int=1): "AR", uuid.UUID(int=2): "UY"}, factor)
    assert weights[uuid.UUID(int=1)] == 1.0 and 0 < weights[uuid.UUID(int=2)] <= 1.0  # FR-081a, FR-081b


def test_small_region_is_completed_with_extraregional_neighbors() -> None:
    """El criterio falsable de FR-096: región con 3 usuarios ⟹ vecindario ≥ collab_min_neighbors."""
    users, regions, likes = _population(3, 40)
    result = collaborative_scores(
        _v(1, 0.5, 0.2), users, likes, CANDIDATES, k=20, min_neighbors=10, weights=regional_weights("AR", regions, 0.1)
    )
    assert len(result.neighbors) >= 10 and not result.insufficient
    assert sum(regions[n.user_id] == "UY" for n in result.neighbors) >= 7


def test_tiny_positive_weight_is_not_cut_as_if_it_were_zero() -> None:
    """El riesgo señalado al cerrar FR-081a: tras el corte top-k, un peso ínfimo no equivale a cero."""
    users, regions, likes = _population(2, 30)
    result = collaborative_scores(
        _v(1, 0.5, 0.2), users, likes, CANDIDATES, k=20, min_neighbors=10, weights=regional_weights("AR", regions, 0.999)
    )
    assert len(result.neighbors) >= 10
    assert all(n.similarity > 0 for n in result.neighbors)


def test_insufficient_neighbors_is_recorded() -> None:
    users, regions, likes = _population(2, 3)
    result = collaborative_scores(_v(1, 0.5, 0.2), users, likes, CANDIDATES, k=20, min_neighbors=10, weights=regional_weights("AR", regions, 0.1))
    assert result.insufficient is True and len(result.neighbors) == 5


def test_factor_sweep_has_no_discontinuities() -> None:
    users, regions, likes = _population(6, 30)
    target = _v(1, 0.5, 0.2)
    previous = None
    for factor in np.linspace(0, 0.99, 100):
        scores = collaborative_scores(target, users, likes, CANDIDATES, k=20, min_neighbors=10, weights=regional_weights("AR", regions, float(factor))).scores
        vector = np.array([scores[c] for c in CANDIDATES])
        if previous is not None:
            assert np.max(np.abs(vector - previous)) < 0.1, factor  # sin saltos: degradación continua
        previous = vector


def test_factor_one_is_rejected_by_the_loader_not_by_the_engine() -> None:
    with pytest.raises(ValueError):
        regional_weights("AR", {uuid.UUID(int=1): "UY"}, 1.0)
