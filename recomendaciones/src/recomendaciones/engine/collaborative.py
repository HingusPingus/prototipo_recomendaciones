"""Señal colaborativa por k vecinos (T010) y ponderación regional (T061). Función pura.

Recibe la matriz de perfiles, no la consulta. Reglas:

- `k` viene de la configuración versionada: sin default (FR-025).
- Solo cuentan vecinos con similitud efectiva **> 0** (FR-023, RD-105): un vecino ortogonal no aporta
  evidencia y uno opuesto no es evidencia negativa confiable. Esto cierra la regresión del prototipo,
  donde normalizar por un máximo negativo invertía el signo.
- Selección determinista ante empates: `(-similitud, user_id)` (FR-070); nunca el orden de iteración.
- `score(ítem) = Σ sim(u)·[u likeó el ítem] / Σ sim(u)` sobre el vecindario final: acotado a [0, 1],
  comparable con las otras dos señales. Cero vecinos ⟹ señal neutra.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from recomendaciones.engine.vocabulary import TagVector


@dataclass(frozen=True, slots=True)
class Neighbor:
    user_id: uuid.UUID
    similarity: float  # similitud efectiva (× peso regional cuando aplica)


@dataclass(frozen=True, slots=True)
class CollaborativeResult:
    scores: dict[uuid.UUID, float]
    neighbors: tuple[Neighbor, ...]


def collaborative_scores(
    target: TagVector | None,
    others: Mapping[uuid.UUID, TagVector],
    likes: Mapping[uuid.UUID, frozenset[uuid.UUID]],
    candidates: Iterable[uuid.UUID],
    k: int,
    *,
    weights: Mapping[uuid.UUID, float] | None = None,
) -> CollaborativeResult:
    candidate_list = list(candidates)
    zero = {item: 0.0 for item in candidate_list}
    if target is None:
        return CollaborativeResult(zero, ())

    scored: list[Neighbor] = []
    for user_id in sorted(others, key=str):
        sim = target.cosine(others[user_id])
        if weights is not None:
            sim *= weights.get(user_id, 1.0)
        if sim > 0:
            scored.append(Neighbor(user_id, sim))
    scored.sort(key=lambda n: (-n.similarity, str(n.user_id)))
    neighborhood = tuple(scored[:k])
    if not neighborhood:
        return CollaborativeResult(zero, ())

    total = sum(n.similarity for n in neighborhood)
    mass = dict(zero)
    for neighbor in neighborhood:  # orden fijo: la suma en coma flotante es reproducible
        for item in sorted(likes.get(neighbor.user_id, frozenset()), key=str):
            if item in mass:
                mass[item] += neighbor.similarity
    return CollaborativeResult({item: m / total for item, m in mass.items()}, neighborhood)
