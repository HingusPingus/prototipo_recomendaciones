"""Perfil de tags del usuario: derivado y reconstruible (T008, T056, FR-087).

La **única** operación pública es reconstruir desde los insumos —la declaración de gustos y las
señales vigentes—; no existe actualización incremental. Reglas:

- Solo `like` y `dislike` construyen el perfil; el consumo no lo altera (FR-022b, P1 del prototipo).
- Por ítem gana la señal de preferencia más reciente (`occurred_at DESC, seq DESC`, FR-029d, DI-22).
- Cada tag declarado —propio o heredado (derivado, RD-97)— aporta **una** señal sintética de `like`
  sobre el centroide de los ítems que lo portan. Es la siembra por feedback sintético de RD-68 sin
  persistir en `user_signals`; acotar su peso a un like por tag es lo que deja que el feedback module
  la declaración (FR-086) y que unos pocos dislikes puedan anular un tag declarado (FR-086b).
  *(Decisión de implementación: T008 cita el mecanismo de `cli_preferencias.py`, un like por cada
  ítem con el tag; con un catálogo real eso ahoga cualquier señal real e incumple FR-086b.)*
- Las señales sobre ítems retirados siguen aportando si el ítem tiene vector (FR-073).
- Resultado L2-normalizado (FR-022c); sin insumo aprovechable ⟹ `None` (perfil vacío).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from recomendaciones.engine.vocabulary import TagVector, Vocabulary, l2_normalize


@dataclass(frozen=True, slots=True)
class ProfileSignal:
    item_id: uuid.UUID
    signal_type: str
    occurred_at: datetime
    seq: int  # desempate estable ante empate temporal (user_signals.id)


@dataclass(frozen=True, slots=True)
class ProfileInputs:
    declared_tags: frozenset[str]
    inherited_tags: frozenset[str]
    signals: tuple[ProfileSignal, ...]


@dataclass(frozen=True, slots=True)
class SignalWeights:
    peso_like: float
    peso_dislike: float


@dataclass(frozen=True, slots=True)
class Profile:
    vector: TagVector
    signal_count: int


_PREFERENCE = ("like", "dislike")


def derive_inherited(declared_other: Iterable[str], shared_tags: Iterable[str]) -> frozenset[str]:
    """Tags declarados en el otro módulo que son compartidos según `tag_modules` (FR-085, RD-97)."""
    return frozenset(declared_other) & frozenset(shared_tags)


def latest_preferences(signals: Iterable[ProfileSignal]) -> dict[uuid.UUID, str]:
    """Señal de preferencia vigente por ítem (FR-029d): el consumo no participa del plano de scoring."""
    latest: dict[uuid.UUID, ProfileSignal] = {}
    for signal in signals:
        kind = str(getattr(signal.signal_type, "value", signal.signal_type))
        if kind not in _PREFERENCE:
            continue
        current = latest.get(signal.item_id)
        if current is None or (signal.occurred_at, signal.seq) > (current.occurred_at, current.seq):
            latest[signal.item_id] = signal
    return {item: str(getattr(s.signal_type, "value", s.signal_type)) for item, s in latest.items()}


def _declared_centroid(
    tag: str,
    item_vectors: Mapping[uuid.UUID, TagVector],
    seed_items: Mapping[uuid.UUID, frozenset[str]],
    dim: int,
) -> np.ndarray | None:
    members = sorted((item for item, tags in seed_items.items() if tag in tags and item in item_vectors), key=str)
    if not members:
        return None  # tag fuera del catálogo vigente: pesa 0 (§2.14)
    total = np.zeros(dim, dtype=np.float64)
    for item in members:
        total += item_vectors[item].values
    return l2_normalize(total)


def build_profile(
    inputs: ProfileInputs,
    item_vectors: Mapping[uuid.UUID, TagVector],
    seed_items: Mapping[uuid.UUID, frozenset[str]],
    vocab: Vocabulary,
    weights: SignalWeights,
) -> Profile | None:
    """Reconstruye el perfil desde sus insumos. Determinista: mismo insumo ⟹ mismo vector."""
    dim = len(vocab)
    total = np.zeros(dim, dtype=np.float64)

    for tag in sorted(inputs.declared_tags | inputs.inherited_tags):
        centroid = _declared_centroid(tag, item_vectors, seed_items, dim)
        if centroid is not None:
            total += weights.peso_like * centroid

    counted = 0
    for item_id, kind in sorted(latest_preferences(inputs.signals).items(), key=lambda kv: str(kv[0])):
        vector = item_vectors.get(item_id)
        if vector is None:
            continue  # ítem sin vector: se ignora sin romper el cálculo (edge case de spec)
        if vector.vocab_version != vocab.version:
            continue
        total += (weights.peso_like if kind == "like" else weights.peso_dislike) * vector.values
        counted += 1

    normalized = l2_normalize(total)
    if normalized is None:
        return None
    return Profile(TagVector(normalized, vocab.version), counted)
