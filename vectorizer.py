"""
Vectorización TF-IDF y construcción de perfiles de usuario.
Diagrama: diagrama_motor_recomendacion.md  (TfIdfVectorizer, ProfileBuilder)
Spec: secciones 2 y 3
"""

from __future__ import annotations
import math
from domain import (
    Item, User, Feedback,
    UserMovieProfile, UserGameProfile, UserGeneralTagProfile,
)


# ---------------------------------------------------------------------------
# Utilidades vectoriales
# ---------------------------------------------------------------------------

def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _normalize(v: list[float]) -> list[float]:
    n = _norm(v)
    if n == 0.0:
        return v[:]
    return [x / n for x in v]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    return max(-1.0, min(1.0, _dot(a, b) / ((_norm(a) * _norm(b)) or 1e-9)))


# ---------------------------------------------------------------------------
# TfIdfVectorizer
# ---------------------------------------------------------------------------

class TfIdfVectorizer:
    """
    Calcula IDF sobre el catálogo y construye tag-vectors normalizados
    para cada ítem.  Los espacios vectoriales de películas y juegos son
    independientes (vocabulario propio por módulo).
    """

    def compute_idf(self, catalog: list[Item]) -> dict[str, float]:
        """
        idf(tag) = log( N / (1 + df(tag)) )
        donde N = cantidad de ítems en el catálogo y df = ítems que tienen el tag.
        """
        n = len(catalog)
        df: dict[str, int] = {}
        for item in catalog:
            for tag in set(item.tags):
                df[tag] = df.get(tag, 0) + 1

        return {
            tag: math.log(n / (1 + count))
            for tag, count in df.items()
        }

    def build_tag_vector(
        self,
        item: Item,
        idf: dict[str, float],
        vocabulary: list[str],
    ) -> list[float]:
        """
        Construye el vector TF-IDF del ítem sobre el vocabulario dado
        y lo normaliza a norma L2 = 1.
        TF binario: 1.0 si el tag está en el ítem, 0.0 si no.
        """
        vec = []
        for tag in vocabulary:
            tf = 1.0 if tag in item.tags else 0.0
            vec.append(tf * idf.get(tag, 0.0))
        return _normalize(vec)

    def fit_transform(self, catalog: list[Item]) -> tuple[dict[str, float], list[str]]:
        """
        Devuelve (idf_map, vocabulary) y actualiza tag_vector en cada ítem.
        """
        idf = self.compute_idf(catalog)
        vocabulary = sorted(idf.keys())
        for item in catalog:
            item.tag_vector = self.build_tag_vector(item, idf, vocabulary)
        return idf, vocabulary


# ---------------------------------------------------------------------------
# ProfileBuilder
# ---------------------------------------------------------------------------

class ProfileBuilder:
    """
    Construye los tres perfiles de un usuario a partir de su historial de feedback.
    Spec sección 3:
        profile = Σ (tag_vector_item × peso_feedback),  normalizado L2.
    """

    def build_profile_vector(
        self,
        feedbacks: list[Feedback],
        item_map: dict,          # item_id (UUID) -> Item
    ) -> list[float]:
        """
        Suma ponderada de vectores de ítems según peso de feedback.
        Devuelve el vector resultante normalizado.
        """
        if not feedbacks:
            return []

        # Determina dimensión del espacio desde el primer ítem disponible
        dim = 0
        for fb in feedbacks:
            item = item_map.get(fb.item_id)
            if item and item.tag_vector:
                dim = len(item.tag_vector)
                break

        if dim == 0:
            return []

        profile = [0.0] * dim
        for fb in feedbacks:
            item = item_map.get(fb.item_id)
            if item and item.tag_vector:
                w = fb.weight()
                for i, v in enumerate(item.tag_vector):
                    profile[i] += v * w

        return _normalize(profile)

    def build_general_tag_profile(
        self,
        feedbacks: list[Feedback],
        item_map: dict,
    ) -> list[UserGeneralTagProfile]:
        """
        Acumula pesos de tags across módulos (señal cruzada).
        Devuelve una lista de UserGeneralTagProfile ordenada por peso desc.
        """
        tag_weights: dict[str, float] = {}
        for fb in feedbacks:
            item = item_map.get(fb.item_id)
            if item:
                w = fb.weight()
                for tag in item.tags:
                    tag_weights[tag] = tag_weights.get(tag, 0.0) + w

        return sorted(
            [UserGeneralTagProfile(tag=t, weight=w) for t, w in tag_weights.items()],
            key=lambda x: x.weight,
            reverse=True,
        )

    def build_user_profiles(
        self,
        user: User,
        feedbacks: list[Feedback],
        movie_map: dict,
        game_map: dict,
    ) -> tuple[UserMovieProfile, UserGameProfile, list[UserGeneralTagProfile]]:
        """Construye los tres perfiles del usuario de una sola vez."""
        movie_fbs = [fb for fb in feedbacks if fb.item_type == "movie"]
        game_fbs  = [fb for fb in feedbacks if fb.item_type == "game"]
        all_item_map = {**movie_map, **game_map}

        movie_profile = UserMovieProfile(
            profile_vector=self.build_profile_vector(movie_fbs, movie_map)
        )
        game_profile = UserGameProfile(
            profile_vector=self.build_profile_vector(game_fbs, game_map)
        )
        general_profile = self.build_general_tag_profile(feedbacks, all_item_map)

        return movie_profile, game_profile, general_profile
