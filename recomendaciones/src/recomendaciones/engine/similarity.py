"""Similitud coseno (T008). Acotada a [-1, 1]; vector nulo o ausente ⟹ 0, sin dividir por cero."""

from __future__ import annotations

from recomendaciones.engine.vocabulary import TagVector


def cosine(a: TagVector | None, b: TagVector | None) -> float:
    if a is None or b is None:
        return 0.0
    return a.cosine(b)
