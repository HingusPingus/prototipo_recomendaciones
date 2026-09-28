"""Post-procesamiento obligatorio: edad → exclusión → MMR → cuota de novedades (FR-028).

Milestone 3 (INV-3): ninguna etapa admite una excepción «por performance», y ninguna tiene un
parámetro, flag o rama que la desactive (FR-029, FR-054).
"""

from __future__ import annotations

from collections.abc import Sequence

from recomendaciones.engine.scoring import ScoredCandidate


def _age_stage(scored: Sequence[ScoredCandidate], user_max_age_ordinal: int) -> list[ScoredCandidate]:
    """Filtro de edad (T013): `item.min_age_ordinal <= user.max_age_ordinal` y nada más (§4.2).

    El ordinal del ítem ya viene fail-closed (`age.min_age_ordinal_for_rating`, default del esquema).
    """
    return [s for s in scored if s.candidate.min_age_ordinal <= user_max_age_ordinal]
