"""Combinación lineal y desempate determinista (T012). Función pura, sin constantes numéricas.

`score = α·content + β·collaborative + γ·cross_module`, con los pesos de la configuración versionada
(FR-021, FR-025). El desempate es **fijo** —RD-10 eliminó `tiebreak_criteria`—: a igual score, mayor
`item_popularity.popularity_score`; si persiste, orden lexicográfico por `id` (FR-070, §4). Nunca el
orden de iteración. Solo candidatos vigentes entran al ranking (FR-072, §4.4 punto 1): excluirlos
después sería reordenar una lista ya contaminada.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

from recomendaciones.engine.vocabulary import TagVector

_NEUTRAL = float()  # noqa: UP018 — señal ausente ⟹ aporte nulo; sin literal: el motor no lleva constantes numéricas (FR-025, test_scoring)


class Weights(Protocol):
    alpha: float
    beta: float
    gamma: float
    config_version: str


@dataclass(frozen=True, slots=True)
class Candidate:
    item_id: uuid.UUID
    module: str
    available: bool
    min_age_ordinal: int
    vector: TagVector | None
    popularity: float
    tags: frozenset[str]


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: Candidate
    score: float


@dataclass(frozen=True, slots=True)
class ScoringResult:
    ranked: tuple[ScoredCandidate, ...]
    config_version: str  # viaja en la salida: el resultado es atribuible (SC-004, SC-021)


def tiebreak_key(scored: ScoredCandidate) -> tuple[float, float, str]:
    return (-scored.score, -scored.candidate.popularity, str(scored.candidate.item_id))


def combine(
    candidates: Iterable[Candidate],
    content: Mapping[uuid.UUID, float],
    collaborative: Mapping[uuid.UUID, float],
    cross_module: Mapping[uuid.UUID, float],
    weights: Weights,
) -> ScoringResult:
    scored = [
        ScoredCandidate(
            c,
            weights.alpha * content.get(c.item_id, _NEUTRAL)
            + weights.beta * collaborative.get(c.item_id, _NEUTRAL)
            + weights.gamma * cross_module.get(c.item_id, _NEUTRAL),
        )
        for c in candidates
        if c.available
    ]
    scored.sort(key=tiebreak_key)
    return ScoringResult(tuple(scored), weights.config_version)
