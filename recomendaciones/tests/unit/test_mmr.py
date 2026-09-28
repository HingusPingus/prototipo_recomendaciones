"""T015 — diversificación MMR con tope de cluster en la selección (FR-031, FR-071, FR-071a, SC-011)."""

from __future__ import annotations

import inspect
import math
import uuid
from collections import Counter

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from recomendaciones.engine.postprocess import _mmr_stage, max_cluster_share
from recomendaciones.engine.scoring import Candidate, ScoredCandidate, tiebreak_key
from recomendaciones.engine.vocabulary import TagVector, Vocabulary

TAGS = ["accion", "comedia", "drama", "horror", "rpg"]
VOCAB = Vocabulary.from_tags(TAGS)


def _cand(n: int, tag_weights: dict[str, float], score: float) -> ScoredCandidate:
    values = np.zeros(len(VOCAB))
    for tag, w in tag_weights.items():
        values[VOCAB.index[tag]] = w
    vec = TagVector(values / np.linalg.norm(values), VOCAB.version)
    return ScoredCandidate(Candidate(uuid.UUID(int=n), "peliculas", True, 0, vec, 0.0, frozenset(tag_weights)), score)


def _cluster(c: Candidate) -> str | None:
    return c.vector.principal_tag(VOCAB) if c.vector is not None else None


candidate_lists = st.lists(
    st.tuples(st.sampled_from(TAGS), st.sampled_from(TAGS), st.floats(0, 1, allow_nan=False)),
    min_size=1,
    max_size=40,
).map(lambda rows: [_cand(i + 1, {a: 1.0, b: 0.5} if a != b else {a: 1.0}, s) for i, (a, b, s) in enumerate(rows)])


def test_lambda_and_share_have_no_defaults() -> None:
    params = inspect.signature(_mmr_stage).parameters
    for name in ("lambda_mmr", "max_cluster_share", "limit"):
        assert params[name].default is inspect.Parameter.empty


@settings(max_examples=80)
@given(candidate_lists, st.floats(0, 1), st.integers(1, 50))
def test_output_is_subset_of_input(cands: list[ScoredCandidate], lam: float, limit: int) -> None:
    out = _mmr_stage(cands, lambda_mmr=lam, max_cluster_share=0.4, limit=limit, cluster_of=_cluster)
    ids = [s.candidate.item_id for s in out.selected]
    assert set(ids) <= {s.candidate.item_id for s in cands}
    assert len(ids) == len(set(ids)) == min(limit, len(cands))


def test_lambda_one_without_cap_is_pure_relevance_order() -> None:
    cands = [_cand(i + 1, {TAGS[i % 2]: 1.0}, s) for i, s in enumerate([0.9, 0.9, 0.7, 0.5, 0.5, 0.1])]
    out = _mmr_stage(cands, lambda_mmr=1.0, max_cluster_share=1.0, limit=6, cluster_of=_cluster)
    assert [s.candidate.item_id for s in out.selected] == [s.candidate.item_id for s in sorted(cands, key=tiebreak_key)]


@settings(max_examples=80)
@given(candidate_lists, st.floats(0, 1))
def test_every_prefix_respects_cluster_cap_unless_relaxed(cands: list[ScoredCandidate], lam: float) -> None:
    out = _mmr_stage(cands, lambda_mmr=lam, max_cluster_share=0.4, limit=50, cluster_of=_cluster)
    counts: Counter[str | None] = Counter()
    violations = 0
    for p, s in enumerate(out.selected, start=1):
        cluster = _cluster(s.candidate)
        counts[cluster] += 1
        if counts[cluster] > math.ceil(0.4 * p):
            violations += 1
    assert violations <= out.relaxations


def test_cap_holds_exactly_when_other_clusters_are_available() -> None:
    horror = [_cand(i, {"horror": 1.0}, 0.99 - i / 1000) for i in range(1, 21)]
    others = [_cand(100 + i, {TAGS[i % 4]: 1.0}, 0.1) for i in range(20)]
    out = _mmr_stage(horror + others, lambda_mmr=1.0, max_cluster_share=0.4, limit=20, cluster_of=_cluster)
    assert out.relaxations == 0
    for n in range(1, 21):
        prefix = out.selected[:n]
        assert sum(_cluster(s.candidate) == "horror" for s in prefix) <= math.ceil(0.4 * n)


def test_diversity_improves_over_undiversified_top_n() -> None:
    dominant = [_cand(i, {"horror": 1.0, "drama": 0.2}, 1.0 - i / 100) for i in range(1, 16)]
    variety = [_cand(50 + i, {TAGS[i % 5]: 1.0}, 0.5 - i / 100) for i in range(15)]
    pool = dominant + variety
    top = sorted(pool, key=tiebreak_key)[:10]
    out = _mmr_stage(pool, lambda_mmr=0.7, max_cluster_share=0.4, limit=10, cluster_of=_cluster)
    assert max_cluster_share(out.selected, _cluster) < max_cluster_share(top, _cluster)


def test_deterministic_under_ties_and_input_order() -> None:
    cands = [_cand(i, {TAGS[i % 3]: 1.0}, 0.5) for i in range(1, 25)]
    base = _mmr_stage(cands, lambda_mmr=0.7, max_cluster_share=0.4, limit=12, cluster_of=_cluster)
    again = _mmr_stage(list(reversed(cands)), lambda_mmr=0.7, max_cluster_share=0.4, limit=12, cluster_of=_cluster)
    assert [s.candidate.item_id for s in base.selected] == [s.candidate.item_id for s in again.selected]


def test_relaxation_is_counted_when_only_capped_clusters_remain() -> None:
    only_horror = [_cand(i, {"horror": 1.0}, 1.0 - i / 100) for i in range(1, 11)]
    out = _mmr_stage(only_horror, lambda_mmr=0.7, max_cluster_share=0.4, limit=10, cluster_of=_cluster)
    assert len(out.selected) == 10  # relajar antes que acortar la lista (FR-071a)
    assert out.relaxations > 0
