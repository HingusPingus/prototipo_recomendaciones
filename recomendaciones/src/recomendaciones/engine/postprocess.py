"""Post-procesamiento obligatorio: edad → exclusión → MMR → cuota de novedades (FR-028).

Milestone 3 (INV-3): ninguna etapa admite una excepción «por performance», y ninguna tiene un
parámetro, flag o rama que la desactive (FR-029, FR-054).
"""

from __future__ import annotations

from collections.abc import Sequence

from recomendaciones.engine.scoring import ScoredCandidate
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
