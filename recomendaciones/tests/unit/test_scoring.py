"""T012 — combinación lineal y desempate determinista (FR-021, FR-025, FR-026, FR-070, FR-072, SC-021)."""

from __future__ import annotations

import ast
import random
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from recomendaciones.engine import scoring
from recomendaciones.engine.scoring import Candidate, combine
from recomendaciones.engine.vocabulary import TagVector


@dataclass(frozen=True)
class W:
    alpha: float
    beta: float
    gamma: float
    config_version: str


V1 = W(0.5, 0.3, 0.2, "sha256:v1")


def _cands(n: int = 30) -> list[Candidate]:
    rng = random.Random(1)
    return [
        Candidate(
            item_id=uuid.UUID(int=i + 1),
            module="peliculas",
            available=True,
            min_age_ordinal=0,
            vector=TagVector(np.array([1.0]), "v"),
            popularity=rng.choice([0.0, 0.1, 0.5]),
            tags=frozenset(),
        )
        for i in range(n)
    ]


def _signals(cands: list[Candidate]) -> tuple[dict, dict, dict]:
    rng = random.Random(2)
    pick = lambda: rng.choice([0.0, 0.25, 0.5])  # noqa: E731 — valores que empatan a propósito
    return ({c.item_id: pick() for c in cands}, {c.item_id: pick() for c in cands}, {c.item_id: pick() for c in cands})


def test_score_is_the_linear_combination() -> None:
    c = _cands(1)[0]
    result = combine([c], {c.item_id: 0.8}, {c.item_id: 0.5}, {c.item_id: -0.25}, V1)
    assert result.ranked[0].score == pytest.approx(0.5 * 0.8 + 0.3 * 0.5 + 0.2 * -0.25)
    assert result.config_version == "sha256:v1"


def test_reproducible_in_100_runs_with_shuffled_input() -> None:
    cands = _cands()
    content, collab, cross = _signals(cands)
    baseline = combine(cands, content, collab, cross, V1)
    for seed in range(100):
        shuffled = cands[:]
        random.Random(seed).shuffle(shuffled)
        again = combine(shuffled, content, collab, cross, V1)
        assert [s.candidate.item_id for s in again.ranked] == [s.candidate.item_id for s in baseline.ranked]
        assert [s.score for s in again.ranked] == [s.score for s in baseline.ranked]


def test_ties_break_by_popularity_then_item_id() -> None:
    a = Candidate(uuid.UUID(int=2), "juegos", True, 0, None, popularity=0.1, tags=frozenset())
    b = Candidate(uuid.UUID(int=1), "juegos", True, 0, None, popularity=0.1, tags=frozenset())
    c = Candidate(uuid.UUID(int=3), "juegos", True, 0, None, popularity=0.9, tags=frozenset())
    zeros = {x.item_id: 0.0 for x in (a, b, c)}
    ranked = combine([a, b, c], zeros, zeros, zeros, V1).ranked
    assert [s.candidate.item_id.int for s in ranked] == [3, 1, 2]


def test_changing_config_changes_result_traceably() -> None:
    cands = _cands()
    content, collab, cross = _signals(cands)
    v2 = W(0.2, 0.3, 0.5, "sha256:v2")
    r1, r2 = combine(cands, content, collab, cross, V1), combine(cands, content, collab, cross, v2)
    assert r1.config_version != r2.config_version
    assert [s.score for s in r1.ranked] != [s.score for s in r2.ranked]


def test_only_available_candidates_enter_the_ranking() -> None:
    live = Candidate(uuid.UUID(int=1), "peliculas", True, 0, None, 0.0, frozenset())
    retired = Candidate(uuid.UUID(int=2), "peliculas", False, 0, None, 0.0, frozenset())
    ranked = combine([live, retired], {}, {}, {}, V1).ranked
    assert [s.candidate.item_id for s in ranked] == [live.item_id]


def test_module_has_no_numeric_constants() -> None:
    tree = ast.parse(Path(scoring.__file__).read_text(encoding="utf-8"))
    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    ]
    assert literals == [], f"constantes numéricas en scoring.py: {literals}"
