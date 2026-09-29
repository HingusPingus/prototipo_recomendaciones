"""T014 — filtro de exclusión (FR-029a…FR-029c, FR-050, SC-003, SC-018)."""

from __future__ import annotations

import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from recomendaciones.engine.postprocess import _exclusion_stage
from recomendaciones.engine.scoring import Candidate, ScoredCandidate
from recomendaciones.shared.domain import ExclusionSet, resolve_exclusion_origin
from recomendaciones.shared.errors import ExclusionSetUnavailable

USER = uuid.UUID(int=999)


def _scored(n: int) -> ScoredCandidate:
    return ScoredCandidate(Candidate(uuid.UUID(int=n), "juegos", True, 0, None, 0.0, frozenset()), 1.0 / (n + 1))


@given(st.sets(st.integers(1, 40)), st.sets(st.integers(1, 40)))
def test_no_excluded_item_survives(candidates: set[int], excluded: set[int]) -> None:
    ex = ExclusionSet(USER, {uuid.UUID(int=i) for i in excluded})
    survivors = _exclusion_stage([_scored(i) for i in sorted(candidates)], ex)
    assert not {s.candidate.item_id for s in survivors} & ex.item_ids
    assert {s.candidate.item_id.int for s in survivors} == candidates - excluded


def test_unavailable_exclusion_set_rejects_instead_of_serving_unfiltered() -> None:
    with pytest.raises(ExclusionSetUnavailable):
        _exclusion_stage([_scored(1)], None)


@pytest.mark.parametrize(
    ("history", "origin"),
    [
        (["like"], "like"),
        (["dislike"], "dislike"),
        (["consumo"], "consumo"),
        (["dislike", "like"], "like"),  # el like posterior revierte la exclusión por dislike…
        (["like", "dislike"], "dislike"),
        (["consumo", "dislike", "like"], "consumo"),  # …pero el consumo es permanente
        (["like", "consumo", "dislike"], "consumo"),
    ],
)
def test_origin_resolution(history: list[str], origin: str) -> None:
    """Las cuatro orígenes excluyen (FR-029a, SC-018); `consumo` es permanente (FR-029b)."""
    assert resolve_exclusion_origin(history) == origin


def test_every_signal_kind_excludes() -> None:
    for kind in ("like", "dislike", "consumo"):
        assert resolve_exclusion_origin([kind]) is not None
    assert resolve_exclusion_origin([]) is None
