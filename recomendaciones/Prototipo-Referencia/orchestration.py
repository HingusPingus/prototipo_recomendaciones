"""
Orquestación y caché — BusinessFilter, Diversifier, ExclusionSet,
RecommendationCache, RecommendationBatchJob, RecommendationController.
Diagrama: diagrama_orquestacion.md
Spec: secciones 5 y 6
"""

from __future__ import annotations
from dataclasses import dataclass, field
from domain import Item, User, Feedback, UserGeneralTagProfile
from vectorizer import cosine_similarity
from recommenders import ScoredItem, HybridRecommender


# ---------------------------------------------------------------------------
# Mapeo age_rating → edad mínima requerida
# ---------------------------------------------------------------------------

AGE_RATING_MIN: dict[str, int] = {
    "G":     0,
    "PG":    0,
    "PG-13": 13,
    "R":     17,
    "M":     17,   # ESRB Mature ≈ 17+
    "AO":    18,
}


# ---------------------------------------------------------------------------
# BusinessFilter
# ---------------------------------------------------------------------------

class BusinessFilter:
    """Filtra ítems por edad y por set de exclusión."""

    def filter_by_age(self, items: list[ScoredItem], user: User) -> list[ScoredItem]:
        user_age = user.age
        result = []
        for si in items:
            min_age = AGE_RATING_MIN.get(si.item.age_rating, 0)
            if user_age >= min_age:
                result.append(si)
        return result

    def filter_excluded(self, items: list[ScoredItem], exclusion: "ExclusionSet") -> list[ScoredItem]:
        return [si for si in items if not exclusion.contains(si.item.id)]


# ---------------------------------------------------------------------------
# Diversifier (MMR — Maximal Marginal Relevance)
# ---------------------------------------------------------------------------

class Diversifier:
    """
    MMR: balancea relevancia vs. diversidad.
    score_MMR(i) = λ·relevancia(i) - (1-λ)·max_{j∈S} sim(i, j)
    donde S es el conjunto ya seleccionado.
    Spec sección 5, punto 3.
    """

    def __init__(self, lambda_mmr: float = 0.7):
        self.lambda_mmr = lambda_mmr

    def diversify_mmr(self, items: list[ScoredItem], top_n: int) -> list[ScoredItem]:
        if not items:
            return []

        selected: list[ScoredItem] = []
        remaining = list(items)

        # El primero siempre es el de mayor score
        remaining.sort(key=lambda x: x.score, reverse=True)
        selected.append(remaining.pop(0))

        while remaining and len(selected) < top_n:
            best_si = None
            best_mmr = float("-inf")

            for si in remaining:
                relevance = si.score
                # Similitud máxima con ítems ya seleccionados
                max_sim = max(
                    cosine_similarity(si.item.tag_vector, s.item.tag_vector)
                    for s in selected
                )
                mmr = self.lambda_mmr * relevance - (1 - self.lambda_mmr) * max_sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_si = si

            if best_si:
                selected.append(best_si)
                remaining.remove(best_si)

        return selected


# ---------------------------------------------------------------------------
# ExclusionSet
# ---------------------------------------------------------------------------

class ExclusionSet:
    """Set de ítems que el usuario ya vio, jugó o dislikeó."""

    def __init__(self, user_id):
        self.user_id = user_id
        self._ids: set = set()

    def contains(self, item_id) -> bool:
        return item_id in self._ids

    def add(self, item_id) -> None:
        self._ids.add(item_id)

    def populate_from_feedbacks(self, feedbacks: list[Feedback]) -> None:
        """Inicializa el set a partir del historial de feedback."""
        for fb in feedbacks:
            if fb.state in ("dislike", "visto", "jugado", "like"):
                self._ids.add(fb.item_id)


# ---------------------------------------------------------------------------
# RecommendationCache
# ---------------------------------------------------------------------------

class RecommendationCache:
    """Caché en memoria (en prod sería una tabla en DB Recomendaciones)."""

    def __init__(self):
        self._store: dict = {}   # user_id -> list[ScoredItem]

    def save_top_n(self, user_id, items: list[ScoredItem]) -> None:
        self._store[user_id] = items

    def get_top_n(self, user_id) -> list[ScoredItem]:
        return self._store.get(user_id, [])


# ---------------------------------------------------------------------------
# RecommendationBatchJob
# ---------------------------------------------------------------------------

class RecommendationBatchJob:
    """
    Orquesta el pipeline completo para todos los usuarios:
      Recommender → BusinessFilter → Diversifier → RecommendationCache
    Equivale al worker que se dispara semanalmente (o vía RabbitMQ).
    Spec sección 6.
    """

    def __init__(
        self,
        recommender: HybridRecommender,
        business_filter: BusinessFilter,
        diversifier: Diversifier,
        cache: RecommendationCache,
        top_n: int = 10,
    ):
        self.recommender = recommender
        self.business_filter = business_filter
        self.diversifier = diversifier
        self.cache = cache
        self.top_n = top_n

    def run(
        self,
        users: list[User],
        candidates: list[Item],             # catálogo de candidatos (ya vectorizados)
        user_profiles: dict,                 # user_id -> (profile_vector, general_profile)
        all_profiles: dict,                  # user_id -> profile_vector  (para CF)
        all_feedbacks: dict,                 # user_id -> list[Feedback]
        exclusion_sets: dict,
    ) -> None:
        for user in users:
            profile_vector, general_profile = user_profiles.get(user.id, ([], []))
            exclusion = exclusion_sets.get(user.id, ExclusionSet(user.id))
            consumed_ids = exclusion._ids

            # 1. Scoring híbrido (sin filtrar)
            scored = self.recommender.recommend(
                user=user,
                candidates=candidates,
                profile_vector=profile_vector,
                general_tag_profile=general_profile,
                all_profiles=all_profiles,
                user_feedbacks=all_feedbacks,
                consumed_ids=consumed_ids,
            )

            # 2. Filtros de negocio
            scored = self.business_filter.filter_by_age(scored, user)
            scored = self.business_filter.filter_excluded(scored, exclusion)

            # 3. Diversificación MMR
            scored = self.diversifier.diversify_mmr(scored, self.top_n)

            # 4. Guardar en caché
            self.cache.save_top_n(user.id, scored)

        print(f"[BatchJob] Pipeline completado para {len(users)} usuario(s).")


# ---------------------------------------------------------------------------
# RecommendationController
# ---------------------------------------------------------------------------

class RecommendationController:
    """
    API en tiempo real: SOLO lee del caché y actualiza ExclusionSet.
    No recalcula nada — el recálculo es responsabilidad del BatchJob.
    Spec sección 6.
    """

    def __init__(self, cache: RecommendationCache, exclusion_sets: dict):
        self.cache = cache
        self.exclusion_sets = exclusion_sets

    def get_recommendations(self, user_id) -> list[ScoredItem]:
        return self.cache.get_top_n(user_id)

    def post_feedback(self, feedback: Feedback) -> None:
        """Registra feedback y actualiza el set de exclusión al instante."""
        exc = self.exclusion_sets.setdefault(feedback.user_id, ExclusionSet(feedback.user_id))
        exc.add(feedback.item_id)
        print(
            f"[Controller] Feedback '{feedback.state}' registrado. "
            f"Ítem {feedback.item_id} excluido para usuario {feedback.user_id}."
        )
