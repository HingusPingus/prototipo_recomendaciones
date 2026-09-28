"""T065 — cuota de novedades en el top-N personalizado (FR-028 paso 4, FR-033a6…FR-033a8, RD-102)."""

from __future__ import annotations

import math
import uuid

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from recomendaciones.engine.postprocess import PostprocessRequest, postprocess, reserved_positions
from recomendaciones.engine.scoring import Candidate, ScoredCandidate, ScoringResult, tiebreak_key
from recomendaciones.engine.vocabulary import TagVector, Vocabulary
from recomendaciones.shared.domain import ExclusionSet

TAGS = [f"t{i}" for i in range(12)]
VOCAB = Vocabulary.from_tags(TAGS)
RATIO = 0.20
LIMIT = 50


def _cand(n: int, tag: int, score: float) -> ScoredCandidate:
    values = np.zeros(len(VOCAB))
    values[tag] = 1.0
    return ScoredCandidate(Candidate(uuid.UUID(int=n), "peliculas", True, 0, TagVector(values, VOCAB.version), 0.0, frozenset()), score)


def _run(cands: list[ScoredCandidate], emergent: set[int], affinity: dict[int, float] | None = None, ratio: float | None = RATIO, share: float = 1.0):  # noqa: ANN202
    scoring = ScoringResult(tuple(sorted(cands, key=tiebreak_key)), "sha256:t")
    request = PostprocessRequest(
        user_max_age_ordinal=2,
        exclusions=ExclusionSet(uuid.UUID(int=0), ()),
        lambda_mmr=0.7,
        max_cluster_share=share,
        limit=LIMIT,
        cluster_of=lambda c: c.vector.principal_tag(VOCAB),
        emergent_items=frozenset(uuid.UUID(int=i) for i in emergent),
        affinity={uuid.UUID(int=i): a for i, a in (affinity or {}).items()},
        novelty_quota_ratio=ratio,
    )
    return postprocess(scoring, request)


def test_reserved_positions_are_ceil_k_over_ratio() -> None:
    assert reserved_positions(RATIO, LIMIT)[:4] == (5, 10, 15, 20)
    assert len(reserved_positions(RATIO, LIMIT)) == 10


pools = st.integers(60, 120).flatmap(
    lambda n: st.tuples(
        st.just(n),
        st.lists(st.floats(0, 1, allow_nan=False), min_size=n, max_size=n),
        st.lists(st.integers(0, 11), min_size=n, max_size=n),
    )
)


@settings(max_examples=40, deadline=None)
@given(pools)
def test_truncation_to_any_top_n_leaves_exactly_the_quota(pool) -> None:  # noqa: ANN001
    n, scores, tags = pool
    ordinary = [_cand(i + 1, tags[i], 0.5 + scores[i] / 2) for i in range(n)]  # relevantes
    emergents = [_cand(1000 + i, i % 12, 0.01 * scores[i]) for i in range(20)]  # poco relevantes: MMR no los elige
    result = _run(ordinary + emergents, emergent={1000 + i for i in range(20)}, affinity={1000 + i: scores[i] for i in range(20)})
    ids = [item.item_id.int for item in result.items]
    reserved = set(reserved_positions(RATIO, LIMIT))
    for top_n in range(10, 51):
        in_reserved = sum(1 for pos, item_id in enumerate(ids[:top_n], start=1) if pos in reserved and item_id >= 1000)
        assert in_reserved == math.floor(top_n * RATIO)  # FR-033a6a, sin cálculo al servir
    assert len(ids) == len(set(ids)) == LIMIT


def test_zero_emergents_leaves_mmr_output_untouched() -> None:
    cands = [_cand(i + 1, i % 12, 1 - i / 100) for i in range(60)]
    assert _run(cands, emergent=set()).items == _run(cands, emergent=set(), ratio=None).items


def test_maximum_not_minimum_reserved_slots_never_empty() -> None:
    cands = [_cand(i + 1, i % 12, 1 - i / 100) for i in range(60)] + [_cand(1000, 0, 0.001)]
    result = _run(cands, emergent={1000}, affinity={1000: 0.5})
    ids = [item.item_id.int for item in result.items]
    assert len(ids) == LIMIT and ids[4] == 1000  # el único emergente ocupa la primera reservada
    assert all(i < 1000 for pos, i in enumerate(ids, start=1) if pos in (10, 15, 20))  # las demás, orden ordinario


def test_output_is_a_permutation_of_a_subset_and_scores_are_unchanged() -> None:
    cands = [_cand(i + 1, i % 12, 1 - i / 100) for i in range(60)] + [_cand(1000 + i, i, 0.001 * i) for i in range(12)]
    original = {c.candidate.item_id: c.score for c in cands}
    result = _run(cands, emergent={1000 + i for i in range(12)}, affinity={1000 + i: i / 12 for i in range(12)})
    assert {i.item_id for i in result.items} <= set(original)  # FR-031
    assert all(original[i.item_id] == i.score for i in result.items)  # FR-033a7


def test_different_profiles_order_the_same_emergents_differently() -> None:
    """FR-033a6f1/f2: la exposición se reparte por la diversidad de perfiles, sin aleatoriedad."""
    cands = [_cand(i + 1, i % 12, 1 - i / 100) for i in range(60)] + [_cand(1000 + i, i, 0.001) for i in range(10)]
    emergent = {1000 + i for i in range(10)}
    a = _run(cands, emergent, affinity={1000 + i: i for i in range(10)})
    b = _run(cands, emergent, affinity={1000 + i: -i for i in range(10)})
    placed = lambda r: [i.item_id.int for pos, i in enumerate(r.items, start=1) if pos in reserved_positions(RATIO, LIMIT)]  # noqa: E731
    assert placed(a) != placed(b)
    assert placed(a) == placed(_run(cands, emergent, affinity={1000 + i: i for i in range(10)}))  # determinista


def test_emergent_already_in_ordinary_order_is_not_duplicated() -> None:
    cands = [_cand(i + 1, i % 12, 1 - i / 100) for i in range(60)]
    result = _run(cands, emergent={1, 2, 3}, affinity={1: 0.9, 2: 0.8, 3: 0.7})
    ids = [i.item_id.int for i in result.items]
    assert len(ids) == len(set(ids))


def test_emergent_that_would_exceed_the_cluster_cap_is_skipped() -> None:
    ordinary = [_cand(i + 1, 0, 1 - i / 100) for i in range(60)]  # todo el orden ordinario en el cluster 0
    emergents = [_cand(1000, 0, 0.001), _cand(1001, 5, 0.001)]  # el primero superaría el tope en p=5
    result = _run(ordinary + emergents, emergent={1000, 1001}, affinity={1000: 0.9, 1001: 0.1}, share=0.4)
    assert [i.item_id.int for i in result.items][4] == 1001


def test_quota_metric_distinguishes_available_from_occupied() -> None:
    cands = [_cand(i + 1, i % 12, 1 - i / 100) for i in range(60)] + [_cand(1000 + i, i, 0.001) for i in range(3)]
    result = _run(cands, emergent={1000, 1001, 1002}, affinity={1000: 0.3, 1001: 0.2, 1002: 0.1})
    assert result.quota_available == 10 and result.quota_occupied == 3
