"""Señal cross-module (T011, FR-024): sostiene el cold start cruzado (US4, SC-010). Función pura.

El boost de un candidato del módulo M es el coseno entre el **perfil general** del usuario —pesos
por tag agregados sobre ambos módulos (§2.5)— y el vector del ítem, sobre el vocabulario compartido
(FR-010d). Es lo que aporta el historial del otro módulo, de modo que un usuario **sin actividad en
el módulo opuesto** recibe boost 0: sin eso el término γ duplicaría el aporte de α con el mismo
insumo. «Actividad» = cualquier insumo de preferencia (declaración o like/dislike) en ese módulo.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from recomendaciones.engine.vocabulary import TagVector


def cross_module_scores(
    general_profile: TagVector | None,
    candidates: Mapping[uuid.UUID, TagVector | None],
    *,
    has_opposite_activity: bool,
) -> dict[uuid.UUID, float]:
    if general_profile is None or not has_opposite_activity:
        return {item: 0.0 for item in candidates}
    return {item: (0.0 if vec is None else general_profile.cosine(vec)) for item, vec in candidates.items()}
