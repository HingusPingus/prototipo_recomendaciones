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
    insufficient: bool = False  # menos de `collab_min_neighbors` vecinos con peso no despreciable (FR-096)


def regional_weights(target_region: str, regions: Mapping[uuid.UUID, str], factor: float) -> dict[uuid.UUID, float]:
    """Peso por vecino según región (T061, FR-081b): misma región pesa 1; otra, `1 − factor`.

    `factor` es la **intensidad** de la segmentación: `0` es el neutro (FR-090) y `1` —que anularía el aporte
    extrarregional, el filtro duro que FR-081a prohíbe— no es admisible. El peso extrarregional es
    estrictamente positivo en todo el dominio.
    """
    if not 0 <= factor < 1:
        raise ValueError("region_weight_factor debe cumplir 0 <= x < 1 (FR-081b)")
    return {user: (1.0 if region == target_region else 1.0 - factor) for user, region in regions.items()}


def select_neighbors(
    target: TagVector | None,
    others: Mapping[uuid.UUID, TagVector],
    k: int,
    *,
    weights: Mapping[uuid.UUID, float] | None = None,
    min_neighbors: int = 0,
) -> tuple[Neighbor, ...]:
    """Vecindario final: los de mayor similitud efectiva (similitud × peso regional) estrictamente positiva.

    Tamaño `max(k, min_neighbors)`: como todo peso extrarregional es positivo, un vecino de otra región con
    similitud positiva nunca queda fuera por su peso si hacen falta vecinos para llegar al mínimo —el corte
    top-k no convierte un peso ínfimo en cero (FR-081a, FR-096)—.
    """
    if target is None:
        return ()
    scored: list[Neighbor] = []
    for user_id in sorted(others, key=str):
        sim = target.cosine(others[user_id])
        if weights is not None:
            sim *= weights.get(user_id, 1.0)
        if sim > 0:
            scored.append(Neighbor(user_id, sim))
    scored.sort(key=lambda n: (-n.similarity, str(n.user_id)))
    return tuple(scored[: max(k, min_neighbors)])


def score_from_neighbors(
    neighborhood: tuple[Neighbor, ...],
    likes: Mapping[uuid.UUID, frozenset[uuid.UUID]],
    candidates: Iterable[uuid.UUID],
) -> dict[uuid.UUID, float]:
    mass = {item: 0.0 for item in candidates}
    if not neighborhood:
        return mass
    total = sum(n.similarity for n in neighborhood)
    for neighbor in neighborhood:  # orden fijo: la suma en coma flotante es reproducible
        for item in sorted(likes.get(neighbor.user_id, frozenset()), key=str):
            if item in mass:
                mass[item] += neighbor.similarity
    return {item: m / total for item, m in mass.items()}


def collaborative_scores(
    target: TagVector | None,
    others: Mapping[uuid.UUID, TagVector],
    likes: Mapping[uuid.UUID, frozenset[uuid.UUID]],
    candidates: Iterable[uuid.UUID],
    k: int,
    *,
    weights: Mapping[uuid.UUID, float] | None = None,
    min_neighbors: int = 0,
) -> CollaborativeResult:
    neighborhood = select_neighbors(target, others, k, weights=weights, min_neighbors=min_neighbors)
    scores = score_from_neighbors(neighborhood, likes, list(candidates))
    return CollaborativeResult(scores, neighborhood, insufficient=len(neighborhood) < min_neighbors)
