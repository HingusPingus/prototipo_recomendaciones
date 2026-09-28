"""Vocabulario compartido y vectores de tags (T007).

Un **único** espacio vectorial para ambos módulos (FR-010d): no existe camino que construya un
espacio por módulo. La versión es función del contenido —hash del conjunto ordenado de tags— y las
dimensiones siguen el orden lexicográfico (DI-14, §2.13). Todo vector lleva su `vocab_version`, y
comparar vectores de versiones distintas es un error, no un resultado silencioso (FR-010f, DI-8).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np


class VocabularyMismatch(ValueError):
    """Se intentó comparar vectores de versiones de vocabulario distintas (FR-010f)."""


@dataclass(frozen=True)
class Vocabulary:
    version: str
    tags: tuple[str, ...]
    index: dict[str, int] = field(compare=False, repr=False)

    @classmethod
    def from_tags(cls, tags: Iterable[str]) -> Vocabulary:
        ordered = tuple(sorted(set(tags)))
        digest = hashlib.sha256("\n".join(ordered).encode("utf-8")).hexdigest()
        return cls(version=f"vocab:{digest[:32]}", tags=ordered, index={t: i for i, t in enumerate(ordered)})

    def __len__(self) -> int:
        return len(self.tags)


@dataclass(frozen=True)
class TagVector:
    values: np.ndarray
    vocab_version: str

    def _check(self, other: TagVector) -> None:
        if self.vocab_version != other.vocab_version:
            raise VocabularyMismatch(
                f"vectores de vocabularios distintos: {self.vocab_version} ≠ {other.vocab_version}"
            )

    def cosine(self, other: TagVector) -> float:
        """Coseno acotado a [-1, 1]; un vector nulo da 0 sin dividir por cero (T008)."""
        self._check(other)
        na = float(np.linalg.norm(self.values))
        nb = float(np.linalg.norm(other.values))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.clip(np.dot(self.values, other.values) / (na * nb), -1.0, 1.0))

    def component(self, vocab: Vocabulary, tag: str) -> float:
        if vocab.version != self.vocab_version:
            raise VocabularyMismatch(f"{vocab.version} ≠ {self.vocab_version}")
        i = vocab.index.get(tag)
        return 0.0 if i is None else float(self.values[i])

    def principal_tag(self, vocab: Vocabulary) -> str | None:
        """Cluster del ítem: tag de mayor peso, desempate por nombre (FR-071, RD-108)."""
        if vocab.version != self.vocab_version:
            raise VocabularyMismatch(f"{vocab.version} ≠ {self.vocab_version}")
        if not np.any(self.values > 0):
            return None
        top = float(np.max(self.values))
        return min(t for t, i in vocab.index.items() if self.values[i] == top)


def l2_normalize(values: np.ndarray) -> np.ndarray | None:
    norm = float(np.linalg.norm(values))
    if norm == 0.0:
        return None
    return values / norm
