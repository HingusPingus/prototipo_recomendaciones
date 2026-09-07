"""
Modelo de dominio — RecoMe
Diagrama: diagrama_modelo_dominio.md
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID


# ---------------------------------------------------------------------------
# Ítems
# ---------------------------------------------------------------------------

@dataclass
class Item:
    """Clase abstracta base para ítems del catálogo."""
    id: UUID
    title: str
    age_rating: str          # ej. "PG-13", "M", "G"
    external_score: float
    tags: list[str]
    tag_vector: list[float] = field(default_factory=list)  # calculado por TfIdfVectorizer

    def __post_init__(self):
        if type(self) is Item:
            raise TypeError("Item es abstracta — usá Movie o Game.")

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Item) and self.id == other.id


@dataclass
class Movie(Item):
    """Película."""
    pass


@dataclass
class Game(Item):
    """Videojuego."""
    pass


# ---------------------------------------------------------------------------
# Usuario y feedback
# ---------------------------------------------------------------------------

@dataclass
class User:
    id: UUID
    birth_date: date

    @property
    def age(self) -> int:
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )


@dataclass
class Feedback:
    user_id: UUID
    item_id: UUID
    item_type: str          # "movie" | "game"
    state: str              # "like" | "dislike" | "visto" | "jugado"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Pesos por estado de feedback
    WEIGHTS: dict[str, float] = field(default_factory=lambda: {
        "like":    1.0,
        "visto":   0.3,
        "jugado":  0.3,
        "dislike": -1.0,
    })

    def weight(self) -> float:
        return self.WEIGHTS.get(self.state, 0.0)


# ---------------------------------------------------------------------------
# Perfiles de usuario
# ---------------------------------------------------------------------------

@dataclass
class UserProfile:
    """Clase abstracta — vector que representa las preferencias del usuario."""
    profile_vector: list[float] = field(default_factory=list)

    def __post_init__(self):
        if type(self) is UserProfile:
            raise TypeError("UserProfile es abstracta.")


@dataclass
class UserMovieProfile(UserProfile):
    pass


@dataclass
class UserGameProfile(UserProfile):
    pass


@dataclass
class UserGeneralTagProfile:
    """
    Señal cruzada entre módulos.
    Cada instancia representa un tag general con su peso acumulado.
    """
    tag: str
    weight: float = 0.0
