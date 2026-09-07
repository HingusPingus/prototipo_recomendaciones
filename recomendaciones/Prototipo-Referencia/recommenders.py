"""
Motor de recomendación — ContentBased, Collaborative y Hybrid.
Diagrama: diagrama_motor_recomendacion.md
Spec: sección 4
"""

from __future__ import annotations
from dataclasses import dataclass
from domain import Item, User, UserGeneralTagProfile
from vectorizer import cosine_similarity


# ---------------------------------------------------------------------------
# ScoredItem
# ---------------------------------------------------------------------------

@dataclass
class ScoredItem:
    item: Item
    score: float

    def __repr__(self):
        return f"ScoredItem({self.item.title!r}, score={self.score:.4f})"


# ---------------------------------------------------------------------------
# Interfaz Recommender
# ---------------------------------------------------------------------------

class Recommender:
    def recommend(self, user: User, candidates: list[Item]) -> list[ScoredItem]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# ContentBasedRecommender
# ---------------------------------------------------------------------------

class ContentBasedRecommender(Recommender):
    """
    Similitud coseno entre el perfil del usuario y el tag_vector de cada ítem.
    """

    def score(self, profile_vector: list[float], item_vector: list[float]) -> float:
        return cosine_similarity(profile_vector, item_vector)

    def recommend(
        self,
        user: User,
        candidates: list[Item],
        profile_vector: list[float],
    ) -> list[ScoredItem]:
        results = []
        for item in candidates:
            s = self.score(profile_vector, item.tag_vector)
            results.append(ScoredItem(item=item, score=s))
        return sorted(results, key=lambda x: x.score, reverse=True)


# ---------------------------------------------------------------------------
# CollaborativeRecommender
# ---------------------------------------------------------------------------

class CollaborativeRecommender(Recommender):
    """
    User-based collaborative filtering.
    Compara el perfil del usuario objetivo contra los perfiles de otros usuarios;
    agrega los ítems likeados por los k vecinos más similares que el usuario
    no haya consumido todavía.
    """

    def __init__(self, k: int = 3):
        self.k = k

    def find_similar_users(
        self,
        profile_vector: list[float],
        all_profiles: dict,   # user_id -> profile_vector (list[float])
        exclude_user_id,
    ) -> list[tuple]:
        """Devuelve los k usuarios más similares (user_id, similitud)."""
        scored = []
        for uid, pvec in all_profiles.items():
            if uid == exclude_user_id:
                continue
            sim = cosine_similarity(profile_vector, pvec)
            scored.append((uid, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[: self.k]

    def aggregate_liked_items(
        self,
        similar_users: list[tuple],
        user_feedbacks: dict,  # user_id -> list[Feedback]
        item_map: dict,        # item_id -> Item
        consumed_ids: set,
    ) -> dict:
        """
        Devuelve {item_id: score_agregado} de ítems que gustaron a vecinos
        y que el usuario objetivo no ha consumido.
        """
        scores: dict = {}
        for uid, sim in similar_users:
            for fb in user_feedbacks.get(uid, []):
                if fb.state == "like" and fb.item_id not in consumed_ids:
                    scores[fb.item_id] = scores.get(fb.item_id, 0.0) + sim
        return scores

    def recommend(
        self,
        user: User,
        candidates: list[Item],
        profile_vector: list[float],
        all_profiles: dict,
        user_feedbacks: dict,
        consumed_ids: set,
    ) -> list[ScoredItem]:
        similar = self.find_similar_users(profile_vector, all_profiles, user.id)
        aggregated = self.aggregate_liked_items(
            similar, user_feedbacks, {i.id: i for i in candidates}, consumed_ids
        )

        # Normaliza por el máximo para llevar a [0, 1]
        max_score = max(aggregated.values(), default=1.0) or 1.0
        candidate_map = {item.id: item for item in candidates}

        results = []
        for item in candidates:
            raw = aggregated.get(item.id, 0.0)
            results.append(ScoredItem(item=item, score=raw / max_score))
        return sorted(results, key=lambda x: x.score, reverse=True)


# ---------------------------------------------------------------------------
# HybridRecommender
# ---------------------------------------------------------------------------

class HybridRecommender(Recommender):
    """
    score_final = α·content + β·collaborative + γ·cross_module_boost
    Spec sección 4.
    """

    def __init__(
        self,
        alpha: float = 0.5,
        beta: float = 0.4,
        gamma: float = 0.1,
        k_neighbors: int = 3,
    ):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self._cb = ContentBasedRecommender()
        self._cf = CollaborativeRecommender(k=k_neighbors)

    # -- cross-module boost --------------------------------------------------

    def cross_module_boost(
        self,
        item: Item,
        general_tag_profile: list[UserGeneralTagProfile],
    ) -> float:
        """
        Similitud entre los tags del ítem candidato y el perfil general del usuario.
        Resuelve el cold-start cruzado (ej. usuario de juegos de horror → pelis de horror).
        """
        if not general_tag_profile:
            return 0.0
        item_tags = set(item.tags)
        total_weight = sum(abs(p.weight) for p in general_tag_profile) or 1.0
        boost = sum(
            p.weight for p in general_tag_profile if p.tag in item_tags
        )
        # Normaliza a [-1, 1]
        return max(-1.0, min(1.0, boost / total_weight))

    # -- recomendación principal --------------------------------------------

    def recommend(
        self,
        user: User,
        candidates: list[Item],
        profile_vector: list[float],
        general_tag_profile: list[UserGeneralTagProfile],
        all_profiles: dict,
        user_feedbacks: dict,
        consumed_ids: set,
    ) -> list[ScoredItem]:
        """
        Devuelve la lista de ScoredItem SIN filtrar (filtrado queda en
        BusinessFilter / Diversifier, ver orchestration.py).
        """
        # Scores individuales
        cb_scores = {
            si.item.id: si.score
            for si in self._cb.recommend(user, candidates, profile_vector)
        }
        cf_scores = {
            si.item.id: si.score
            for si in self._cf.recommend(
                user, candidates, profile_vector,
                all_profiles, user_feedbacks, consumed_ids
            )
        }

        results = []
        for item in candidates:
            content_s = cb_scores.get(item.id, 0.0)
            collab_s  = cf_scores.get(item.id, 0.0)
            cross_s   = self.cross_module_boost(item, general_tag_profile)

            final = (
                self.alpha * content_s
                + self.beta  * collab_s
                + self.gamma * cross_s
            )
            results.append(ScoredItem(item=item, score=final))

        return sorted(results, key=lambda x: x.score, reverse=True)
