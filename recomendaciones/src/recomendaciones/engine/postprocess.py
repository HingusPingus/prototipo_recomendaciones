"""Post-procesamiento obligatorio: edad → exclusión → MMR → cuota de novedades (FR-028).

Milestone 3 (INV-3): ninguna etapa admite una excepción «por performance», y ninguna tiene un
parámetro, flag o rama que la desactive (FR-029, FR-054).
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from recomendaciones.engine.scoring import Candidate, ScoredCandidate, ScoringResult, tiebreak_key
from recomendaciones.shared.domain import ExclusionSet
from recomendaciones.shared.errors import ExclusionSetUnavailable


def _age_stage(scored: Sequence[ScoredCandidate], user_max_age_ordinal: int) -> list[ScoredCandidate]:
    """Filtro de edad (T013): `item.min_age_ordinal <= user.max_age_ordinal` y nada más (§4.2).

    El ordinal del ítem ya viene fail-closed (`age.min_age_ordinal_for_rating`, default del esquema).
    """
    return [s for s in scored if s.candidate.min_age_ordinal <= user_max_age_ordinal]


def _exclusion_stage(scored: Sequence[ScoredCandidate], exclusions: ExclusionSet | None) -> list[ScoredCandidate]:
    """Filtro de exclusión (T014). Conjunto no disponible ⟹ se rechaza; nunca se sirve sin filtrar (FR-050)."""
    if exclusions is None:
        raise ExclusionSetUnavailable()
    return [s for s in scored if not exclusions.contains(s.candidate.item_id)]


ClusterOf = Callable[[Candidate], "str | None"]


@dataclass(frozen=True, slots=True)
class MMRResult:
    selected: tuple[ScoredCandidate, ...]
    relaxations: int  # → diversity_cap_relaxed_total (FR-071a)


def max_cluster_share(items: Sequence[ScoredCandidate], cluster_of: ClusterOf) -> float:
    """Métrica de diversidad de FR-071: proporción máxima del top-N atribuible a un cluster."""
    if not items:
        return 0.0
    counts: dict[object, int] = {}
    for n, s in enumerate(items):
        key = cluster_of(s.candidate) or ("sin-cluster", n)
        counts[key] = counts.get(key, 0) + 1
    return max(counts.values()) / len(items)


def _mmr_stage(
    scored: Sequence[ScoredCandidate],
    *,
    lambda_mmr: float,
    max_cluster_share: float,
    limit: int,
    cluster_of: ClusterOf,
) -> MMRResult:
    """MMR con tope de cluster aplicado en la selección (T015, FR-031, FR-071a).

    `MMR(c) = λ·relevancia(c) − (1−λ)·max_{s∈S} sim(c, s)`, con sim = coseno de los vectores de tags.
    En la posición `p` se omite un candidato cuyo cluster superaría `ceil(share·p)`; si todos los
    restantes están topados, el tope se relaja para esa posición y se cuenta. Empates: el orden de
    `tiebreak_key` (FR-070). La salida es un subconjunto de la entrada, verificado por aserción.

    Implementación exacta y perezosa: los vectores de ítem son no negativos, de modo que
    `λ·relevancia` acota por arriba el MMR de cada candidato; recorriendo por relevancia decreciente,
    el barrido se corta en cuanto la cota no puede superar al mejor hallado.
    """
    order = sorted(scored, key=tiebreak_key)
    remaining = list(order)
    selected: list[ScoredCandidate] = []
    counts: dict[str, int] = {}
    maxsim: dict[int, tuple[float, int]] = {}  # id(obj) → (máx. similitud, # seleccionados considerados)
    relaxations = 0

    def similarity_to_selected(s: ScoredCandidate) -> float:
        best, upto = maxsim.get(id(s), (0.0, 0))
        vec = s.candidate.vector
        if vec is not None:
            for chosen in selected[upto:]:
                other = chosen.candidate.vector
                if other is not None:
                    best = max(best, vec.cosine(other))
        maxsim[id(s)] = (best, len(selected))
        return best

    def pick(p: int, capped: bool) -> ScoredCandidate | None:
        cap = math.ceil(max_cluster_share * p)
        best: ScoredCandidate | None = None
        best_value = -math.inf
        for s in remaining:
            upper = lambda_mmr * s.score
            if best is not None and upper <= best_value:
                break
            cluster = cluster_of(s.candidate)
            if capped and cluster is not None and counts.get(cluster, 0) + 1 > cap:
                continue
            value = upper - (1 - lambda_mmr) * similarity_to_selected(s)
            if value > best_value:
                best, best_value = s, value
        return best

    while remaining and len(selected) < limit:
        p = len(selected) + 1
        choice = pick(p, capped=True)
        if choice is None:
            relaxations += 1
            choice = pick(p, capped=False)
        assert choice is not None
        remaining.remove(choice)
        selected.append(choice)
        cluster = cluster_of(choice.candidate)
        if cluster is not None:
            counts[cluster] = counts.get(cluster, 0) + 1

    input_ids = {s.candidate.item_id for s in scored}
    assert {s.candidate.item_id for s in selected} <= input_ids, "MMR reintrodujo un ítem (FR-031)"
    return MMRResult(tuple(selected), relaxations)


# --- Pipeline con orden estructural (T016) ------------------------------------------------------
#
# Cada etapa devuelve un tipo que solo la siguiente acepta: el orden edad → exclusión → MMR (→ cuota,
# T065) es una propiedad de los tipos, no una convención de llamada. La única entrada pública es
# `postprocess`; las etapas no forman parte de la superficie del módulo.


@dataclass(frozen=True, slots=True)
class PostprocessRequest:
    user_max_age_ordinal: int
    exclusions: ExclusionSet | None
    lambda_mmr: float
    max_cluster_share: float
    limit: int  # top_n_max en el personalizado; fallback_stored_size en el respaldo
    cluster_of: ClusterOf


@dataclass(frozen=True, slots=True)
class RankedItem:
    item_id: uuid.UUID
    rank: int
    score: float
    min_age_ordinal: int


@dataclass(frozen=True, slots=True)
class PostprocessResult:
    items: tuple[RankedItem, ...]
    config_version: str
    discarded: dict[str, int]
    relaxations: int

    @property
    def empty(self) -> bool:
        return not self.items


@dataclass(frozen=True, slots=True)
class _AgeFiltered:
    items: tuple[ScoredCandidate, ...]
    config_version: str
    discarded: dict[str, int]


@dataclass(frozen=True, slots=True)
class _ExclusionFiltered:
    items: tuple[ScoredCandidate, ...]
    config_version: str
    discarded: dict[str, int]


@dataclass(frozen=True, slots=True)
class _Diversified:
    items: tuple[ScoredCandidate, ...]
    config_version: str
    discarded: dict[str, int]
    relaxations: int


def _filter_age(scoring: ScoringResult, req: PostprocessRequest) -> _AgeFiltered:
    if not isinstance(scoring, ScoringResult):
        raise TypeError("la etapa de edad recibe la salida del scoring")
    kept = _age_stage(scoring.ranked, req.user_max_age_ordinal)
    return _AgeFiltered(tuple(kept), scoring.config_version, {"age": len(scoring.ranked) - len(kept)})


def _exclude(stage: _AgeFiltered, req: PostprocessRequest) -> _ExclusionFiltered:
    if not isinstance(stage, _AgeFiltered):
        raise TypeError("la exclusión solo corre sobre la salida del filtro de edad (FR-028)")
    kept = _exclusion_stage(stage.items, req.exclusions)
    return _ExclusionFiltered(
        tuple(kept), stage.config_version, {**stage.discarded, "exclusion": len(stage.items) - len(kept)}
    )


def _diversify(stage: _ExclusionFiltered, req: PostprocessRequest) -> _Diversified:
    if not isinstance(stage, _ExclusionFiltered):
        raise TypeError("MMR solo corre sobre candidatos ya filtrados por edad y exclusión (FR-028, FR-031)")
    result = _mmr_stage(
        stage.items,
        lambda_mmr=req.lambda_mmr,
        max_cluster_share=req.max_cluster_share,
        limit=req.limit,
        cluster_of=req.cluster_of,
    )
    dropped = len(stage.items) - len(result.selected) - max(0, len(stage.items) - req.limit)
    return _Diversified(result.selected, stage.config_version, {**stage.discarded, "mmr": dropped}, result.relaxations)


def postprocess(scoring: ScoringResult, req: PostprocessRequest) -> PostprocessResult:
    """Única entrada pública: scoring → edad → exclusión → MMR. Vacío tras filtrar ⟹ vacío explícito."""
    final = _diversify(_exclude(_filter_age(scoring, req), req), req)
    items = tuple(
        RankedItem(s.candidate.item_id, rank, s.score, s.candidate.min_age_ordinal)
        for rank, s in enumerate(final.items, start=1)
    )
    return PostprocessResult(items, final.config_version, final.discarded, final.relaxations)


__all__ = ["postprocess", "PostprocessRequest", "PostprocessResult", "RankedItem", "max_cluster_share"]
