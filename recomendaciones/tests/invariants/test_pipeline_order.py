"""T016 — pipeline de post-proceso con orden garantizado (FR-028, FR-031, FR-033, INV-3)."""

from __future__ import annotations

import uuid

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import recomendaciones.engine.postprocess as pp
from recomendaciones.engine.postprocess import PostprocessRequest, postprocess
from recomendaciones.engine.scoring import Candidate, ScoredCandidate, ScoringResult
from recomendaciones.engine.vocabulary import TagVector, Vocabulary
from recomendaciones.shared.domain import ExclusionSet

VOCAB = Vocabulary.from_tags(["a", "b", "c", "d"])
USER = uuid.UUID(int=4242)


def _scoring(rows: list[tuple[int, int, float]]) -> ScoringResult:
    ranked = []
    for n, (ordinal, tag, score) in enumerate(rows, start=1):
        values = np.zeros(4)
        values[tag] = 1.0
        cand = Candidate(uuid.UUID(int=n), "peliculas", True, ordinal, TagVector(values, VOCAB.version), 0.0, frozenset())
        ranked.append(ScoredCandidate(cand, score))
    ranked.sort(key=lambda s: (-s.score, str(s.candidate.item_id)))
    return ScoringResult(tuple(ranked), "sha256:test")


def _request(user_ordinal: int, excluded: set[int], limit: int = 50) -> PostprocessRequest:
    return PostprocessRequest(
        user_max_age_ordinal=user_ordinal,
        exclusions=ExclusionSet(USER, {uuid.UUID(int=i) for i in excluded}),
        lambda_mmr=0.7,
        max_cluster_share=0.4,
        limit=limit,
        cluster_of=lambda c: c.vector.principal_tag(VOCAB) if c.vector is not None else None,
    )


rows = st.lists(st.tuples(st.integers(0, 2), st.integers(0, 3), st.floats(-1, 1, allow_nan=False)), max_size=60)


@settings(max_examples=100)
@given(rows, st.integers(0, 2), st.sets(st.integers(1, 60)), st.integers(10, 50))
def test_output_satisfies_age_exclusion_and_subset_simultaneously(
    data: list[tuple[int, int, float]], user_ordinal: int, excluded: set[int], limit: int
) -> None:
    scoring = _scoring(data)
    result = postprocess(scoring, _request(user_ordinal, excluded, limit))
    by_id = {s.candidate.item_id: s.candidate for s in scoring.ranked}
    for item in result.items:
        assert item.item_id in by_id  # subconjunto (FR-031)
        assert by_id[item.item_id].min_age_ordinal <= user_ordinal  # edad
        assert item.item_id.int not in excluded  # exclusión
    assert [i.rank for i in result.items] == list(range(1, len(result.items) + 1))
    assert len(result.items) <= limit
    assert result.config_version == "sha256:test"


def test_stages_are_not_part_of_the_public_surface() -> None:
    public = {name for name in dir(pp) if not name.startswith("_")}
    assert set(pp.__all__) == {"postprocess", "PostprocessRequest", "PostprocessResult", "RankedItem", "max_cluster_share"}
    assert not {n for n in public if "stage" in n.lower()}


def test_order_is_a_property_of_the_types() -> None:
    """No es posible invocar MMR (ni la exclusión) sobre algo que no pasó por las etapas previas."""
    scoring = _scoring([(0, 0, 0.5)])
    with pytest.raises(TypeError):
        pp._diversify(scoring, _request(2, set()))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        pp._exclude(scoring, _request(2, set()))  # type: ignore[arg-type]


def test_each_stage_records_discards() -> None:
    scoring = _scoring([(2, 0, 0.9), (0, 1, 0.8), (0, 2, 0.7), (0, 3, 0.6)])
    result = postprocess(scoring, _request(user_ordinal=0, excluded={2}, limit=10))
    assert result.discarded == {"age": 1, "exclusion": 1, "mmr": 0}


def test_empty_after_filtering_is_explicit_empty_never_padding() -> None:
    scoring = _scoring([(2, 0, 0.9), (2, 1, 0.8)])
    result = postprocess(scoring, _request(user_ordinal=0, excluded=set()))
    assert result.items == () and result.empty is True
