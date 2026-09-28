"""Escala etaria: derivación de ordinales (§4.1, §7.5). Funciones puras; la fecha se recibe, no se lee.

Un solo mapeo, dos usos: `min_age` deriva el ordinal del usuario y `rating` el del ítem, de modo que
ambos hablan la misma escala por construcción. El catálogo es la **única** fuente (FR-053).
"""

from __future__ import annotations

from datetime import date
from typing import Protocol


class AgeCatalog(Protocol):
    @property
    def max_ordinal(self) -> int: ...

    def ordinal_for_rating(self, rating: object) -> int | None: ...

    def max_age_ordinal_for_age(self, age_years: int) -> int: ...


def age_on(birth_date: date, on: date) -> int:
    return on.year - birth_date.year - ((on.month, on.day) < (birth_date.month, birth_date.day))


def derive_max_age_ordinal(birth_date: date, on: date, catalog: AgeCatalog) -> int:
    """Ordinal más alto cuyo `min_age` ≤ edad del usuario en la fecha `on`."""
    return catalog.max_age_ordinal_for_age(age_on(birth_date, on))


def min_age_ordinal_for_rating(rating: object, catalog: AgeCatalog) -> int:
    """Ordinal del ítem. Ausente, vacío, basura o fuera del catálogo ⟹ el más restrictivo (FR-051).

    Nunca el permisivo: corrige P2 del prototipo, cuyo mapeo devolvía edad mínima 0 ante lo desconocido.
    """
    ordinal = catalog.ordinal_for_rating(rating)
    return catalog.max_ordinal if ordinal is None else ordinal
