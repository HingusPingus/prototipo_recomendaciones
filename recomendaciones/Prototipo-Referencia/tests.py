"""
Tests del prototipo RecoMe.
Ejecutar:  python3 -m pytest tests.py -v
"""

import math
import pytest
from uuid import UUID
from datetime import date, datetime, timezone
from collections import defaultdict

from domain import Movie, Game, User, Feedback, UserGeneralTagProfile
from vectorizer import TfIdfVectorizer, ProfileBuilder, cosine_similarity
from recommenders import (
    ScoredItem, ContentBasedRecommender,
    CollaborativeRecommender, HybridRecommender,
)
from orchestration import (
    BusinessFilter, Diversifier, ExclusionSet,
    RecommendationCache, RecommendationBatchJob, RecommendationController,
)


# ============================================================
# Fixtures reutilizables
# ============================================================

@pytest.fixture
def small_movies():
    return [
        Movie(UUID("00000000-0000-0000-0000-000000000001"), "HorrorA", "R",    7.0, ["horror", "thriller"]),
        Movie(UUID("00000000-0000-0000-0000-000000000002"), "HorrorB", "R",    6.5, ["horror", "sobrenatural"]),
        Movie(UUID("00000000-0000-0000-0000-000000000003"), "ActionA", "PG-13",8.0, ["accion", "aventura"]),
        Movie(UUID("00000000-0000-0000-0000-000000000004"), "KidsA",   "G",    7.5, ["animacion", "comedia"]),
    ]

@pytest.fixture
def small_games():
    return [
        Game(UUID("00000000-0000-0000-0000-000000000010"), "HorrorGame", "M", 8.0, ["horror", "survival"]),
        Game(UUID("00000000-0000-0000-0000-000000000011"), "ActionGame", "M", 9.0, ["accion", "rpg"]),
        Game(UUID("00000000-0000-0000-0000-000000000012"), "KidsGame",   "G", 7.0, ["sandbox", "multijugador"]),
    ]

@pytest.fixture
def vectorized_movies(small_movies):
    TfIdfVectorizer().fit_transform(small_movies)
    return small_movies

@pytest.fixture
def adult_user():
    return User(UUID("aaaa0000-0000-0000-0000-000000000001"), date(1995, 1, 1))  # ~31 años

@pytest.fixture
def minor_user():
    return User(UUID("aaaa0000-0000-0000-0000-000000000002"), date(2012, 6, 15))  # ~14 años

@pytest.fixture
def movie_map(small_movies):
    return {m.id: m for m in small_movies}

@pytest.fixture
def game_map(small_games):
    return {g.id: g for g in small_games}


# ============================================================
# domain.py
# ============================================================

class TestDomain:
    def test_item_is_abstract(self):
        from domain import Item
        with pytest.raises(TypeError):
            Item(UUID("00000000-0000-0000-0000-000000000099"), "X", "G", 5.0, [])

    def test_user_age(self):
        user = User(UUID("00000000-0000-0000-0000-000000000001"), date(2000, 1, 1))
        assert user.age >= 25   # al menos 25 en 2026

    def test_feedback_weights(self):
        base = UUID("00000000-0000-0000-0000-000000000001")
        assert Feedback(base, base, "movie", "like").weight()    ==  1.0
        assert Feedback(base, base, "movie", "dislike").weight() == -1.0
        assert Feedback(base, base, "movie", "visto").weight()   ==  0.3
        assert Feedback(base, base, "movie", "jugado").weight()  ==  0.3
        assert Feedback(base, base, "movie", "unknown").weight() ==  0.0


# ============================================================
# vectorizer.py
# ============================================================

class TestTfIdfVectorizer:
    def test_idf_penalizes_common_tags(self, small_movies):
        """'horror' aparece en 2/4 ítems → IDF menor que un tag exclusivo."""
        v = TfIdfVectorizer()
        idf = v.compute_idf(small_movies)
        assert idf["horror"] < idf["thriller"]

    def test_tag_vector_unit_norm(self, small_movies):
        v = TfIdfVectorizer()
        idf, vocab = v.fit_transform(small_movies)
        for movie in small_movies:
            norm = math.sqrt(sum(x**2 for x in movie.tag_vector))
            assert abs(norm - 1.0) < 1e-9 or norm == 0.0, f"{movie.title} norm={norm}"

    def test_tag_vector_length_equals_vocab(self, small_movies):
        v = TfIdfVectorizer()
        idf, vocab = v.fit_transform(small_movies)
        for movie in small_movies:
            assert len(movie.tag_vector) == len(vocab)

    def test_zero_vector_for_no_matching_tags(self, small_movies):
        v = TfIdfVectorizer()
        idf, vocab = v.fit_transform(small_movies)
        fake_movie = Movie(UUID("00000000-0000-0000-0000-000000000099"), "X", "G", 5.0, ["zzz_tag"])
        vec = v.build_tag_vector(fake_movie, idf, vocab)
        # Todos los pesos serán 0 porque "zzz_tag" no tiene IDF
        assert all(x == 0.0 for x in vec)


class TestCosينeSimilarity:
    def test_identical_vectors(self):
        v = [0.5, 0.5, 0.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        assert abs(cosine_similarity([1, 0], [0, 1])) < 1e-9

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_opposite_vectors(self):
        assert abs(cosine_similarity([1, 0], [-1, 0]) + 1.0) < 1e-9


class TestProfileBuilder:
    def test_profile_unit_norm(self, vectorized_movies, adult_user, movie_map):
        m = vectorized_movies
        fbs = [
            Feedback(adult_user.id, m[0].id, "movie", "like"),
            Feedback(adult_user.id, m[1].id, "movie", "like"),
        ]
        pb = ProfileBuilder()
        vec = pb.build_profile_vector(fbs, {m[0].id: m[0], m[1].id: m[1]})
        norm = math.sqrt(sum(x**2 for x in vec))
        assert abs(norm - 1.0) < 1e-9

    def test_dislike_reduces_profile(self, vectorized_movies, adult_user):
        m = vectorized_movies
        pb = ProfileBuilder()
        like_only = pb.build_profile_vector(
            [Feedback(adult_user.id, m[0].id, "movie", "like")],
            {m[0].id: m[0]},
        )
        like_and_dislike = pb.build_profile_vector(
            [
                Feedback(adult_user.id, m[0].id, "movie", "like"),
                Feedback(adult_user.id, m[0].id, "movie", "dislike"),
            ],
            {m[0].id: m[0]},
        )
        # Con like + dislike del mismo ítem el vector se cancela → norma 0
        assert like_and_dislike == [] or all(x == 0.0 for x in like_and_dislike)

    def test_empty_feedback_returns_empty(self, adult_user, movie_map):
        pb = ProfileBuilder()
        vec = pb.build_profile_vector([], movie_map)
        assert vec == []

    def test_general_tag_profile_aggregates_across_types(
        self, vectorized_movies, small_games, adult_user
    ):
        TfIdfVectorizer().fit_transform(small_games)
        all_map = {**{m.id: m for m in vectorized_movies}, **{g.id: g for g in small_games}}
        fbs = [
            Feedback(adult_user.id, vectorized_movies[0].id, "movie", "like"),  # horror, thriller
            Feedback(adult_user.id, small_games[0].id,       "game",  "like"),  # horror, survival
        ]
        pb = ProfileBuilder()
        gen = pb.build_general_tag_profile(fbs, all_map)
        tags = [g.tag for g in gen]
        assert "horror" in tags
        horror_weight = next(g.weight for g in gen if g.tag == "horror")
        assert horror_weight == 2.0  # un like de cada módulo


# ============================================================
# recommenders.py
# ============================================================

class TestContentBasedRecommender:
    def test_similar_item_scores_higher(self, vectorized_movies, adult_user, movie_map):
        # El usuario likeó películas de horror → HorrorA y HorrorB deben superar a ActionA
        m = vectorized_movies
        fbs = [Feedback(adult_user.id, m[0].id, "movie", "like")]
        profile = ProfileBuilder().build_profile_vector(fbs, {m[0].id: m[0]})

        cb = ContentBasedRecommender()
        results = cb.recommend(adult_user, m[1:], profile)  # candidatos sin HorrorA

        scores = {si.item.title: si.score for si in results}
        assert scores["HorrorB"] > scores["ActionA"]

    def test_results_sorted_descending(self, vectorized_movies, adult_user):
        m = vectorized_movies
        fbs = [Feedback(adult_user.id, m[0].id, "movie", "like")]
        profile = ProfileBuilder().build_profile_vector(fbs, {m[0].id: m[0]})
        results = ContentBasedRecommender().recommend(adult_user, m, profile)
        scores = [si.score for si in results]
        assert scores == sorted(scores, reverse=True)


class TestCollaborativeRecommender:
    def test_finds_k_similar_users(self, vectorized_movies, adult_user, minor_user):
        m = vectorized_movies
        pb = ProfileBuilder()
        fbs_adult = [Feedback(adult_user.id, m[0].id, "movie", "like")]
        fbs_minor = [Feedback(minor_user.id, m[3].id, "movie", "like")]
        prof_adult = pb.build_profile_vector(fbs_adult, {m[0].id: m[0]})
        prof_minor = pb.build_profile_vector(fbs_minor, {m[3].id: m[3]})

        cf = CollaborativeRecommender(k=1)
        similar = cf.find_similar_users(
            prof_adult,
            {adult_user.id: prof_adult, minor_user.id: prof_minor},
            adult_user.id,
        )
        assert len(similar) == 1
        assert similar[0][0] == minor_user.id

    def test_aggregate_excludes_consumed(self, vectorized_movies, adult_user, minor_user):
        m = vectorized_movies
        similar = [(minor_user.id, 0.9)]
        fbs_minor = [Feedback(minor_user.id, m[0].id, "movie", "like")]
        consumed = {m[0].id}  # El usuario adulto ya consumió HorrorA

        cf = CollaborativeRecommender()
        aggregated = cf.aggregate_liked_items(
            similar,
            {minor_user.id: fbs_minor},
            {m[0].id: m[0]},
            consumed,
        )
        assert m[0].id not in aggregated


class TestHybridRecommender:
    def test_cross_module_boost_uses_general_profile(self, vectorized_movies):
        hybrid = HybridRecommender()
        # Perfil general fuerte en "horror"
        gen = [UserGeneralTagProfile("horror", 3.0), UserGeneralTagProfile("accion", 1.0)]
        horror_movie = vectorized_movies[0]  # tiene tag "horror"
        action_movie = vectorized_movies[2]  # tiene tag "accion", no "horror"
        boost_horror = hybrid.cross_module_boost(horror_movie, gen)
        boost_action = hybrid.cross_module_boost(action_movie, gen)
        assert boost_horror > boost_action

    def test_score_bounded(self, vectorized_movies, adult_user):
        """El score final no debería superar α+β+γ = 1.0 (con scores normalizados)."""
        m = vectorized_movies
        fbs = [Feedback(adult_user.id, m[0].id, "movie", "like")]
        pb = ProfileBuilder()
        profile = pb.build_profile_vector(fbs, {m[0].id: m[0]})
        gen = pb.build_general_tag_profile(fbs, {m[0].id: m[0]})

        hybrid = HybridRecommender(alpha=0.5, beta=0.4, gamma=0.1)
        results = hybrid.recommend(
            user=adult_user,
            candidates=m,
            profile_vector=profile,
            general_tag_profile=gen,
            all_profiles={adult_user.id: profile},
            user_feedbacks={adult_user.id: fbs},
            consumed_ids=set(),
        )
        for si in results:
            assert si.score <= 1.0 + 1e-9, f"Score fuera de rango: {si.score}"


# ============================================================
# orchestration.py
# ============================================================

class TestBusinessFilter:
    def test_filters_r_rated_for_minor(self, vectorized_movies, minor_user):
        bf = BusinessFilter()
        scored = [ScoredItem(m, 1.0) for m in vectorized_movies]
        filtered = bf.filter_by_age(scored, minor_user)
        for si in filtered:
            assert si.item.age_rating not in ("R", "M", "AO")

    def test_adult_sees_all_ratings(self, vectorized_movies, adult_user):
        bf = BusinessFilter()
        scored = [ScoredItem(m, 1.0) for m in vectorized_movies]
        filtered = bf.filter_by_age(scored, adult_user)
        assert len(filtered) == len(vectorized_movies)

    def test_filter_excluded(self, vectorized_movies):
        bf = BusinessFilter()
        exc = ExclusionSet(UUID("aaaa0000-0000-0000-0000-000000000001"))
        exc.add(vectorized_movies[0].id)
        scored = [ScoredItem(m, 1.0) for m in vectorized_movies]
        filtered = bf.filter_excluded(scored, exc)
        ids = [si.item.id for si in filtered]
        assert vectorized_movies[0].id not in ids


class TestDiversifier:
    def test_returns_top_n(self, vectorized_movies):
        d = Diversifier(lambda_mmr=0.7)
        scored = [ScoredItem(m, float(i)) for i, m in enumerate(vectorized_movies)]
        result = d.diversify_mmr(scored, top_n=2)
        assert len(result) == 2

    def test_empty_input(self):
        d = Diversifier()
        assert d.diversify_mmr([], top_n=5) == []

    def test_first_selected_is_highest_score(self, vectorized_movies):
        d = Diversifier(lambda_mmr=0.7)
        scored = sorted(
            [ScoredItem(m, float(i)) for i, m in enumerate(vectorized_movies)],
            key=lambda x: x.score
        )
        result = d.diversify_mmr(scored, top_n=3)
        # El primero elegido debe ser el de mayor score original
        assert result[0].score == max(si.score for si in scored)


class TestExclusionSet:
    def test_add_and_contains(self, vectorized_movies):
        exc = ExclusionSet(UUID("aaaa0000-0000-0000-0000-000000000001"))
        exc.add(vectorized_movies[0].id)
        assert exc.contains(vectorized_movies[0].id)
        assert not exc.contains(vectorized_movies[1].id)

    def test_populate_from_feedbacks(self, vectorized_movies, adult_user):
        fbs = [
            Feedback(adult_user.id, vectorized_movies[0].id, "movie", "like"),
            Feedback(adult_user.id, vectorized_movies[1].id, "movie", "dislike"),
        ]
        exc = ExclusionSet(adult_user.id)
        exc.populate_from_feedbacks(fbs)
        assert exc.contains(vectorized_movies[0].id)
        assert exc.contains(vectorized_movies[1].id)


class TestRecommendationCache:
    def test_save_and_get(self, vectorized_movies):
        cache = RecommendationCache()
        uid = UUID("aaaa0000-0000-0000-0000-000000000001")
        items = [ScoredItem(vectorized_movies[0], 0.9)]
        cache.save_top_n(uid, items)
        assert cache.get_top_n(uid) == items

    def test_get_unknown_user_returns_empty(self):
        cache = RecommendationCache()
        assert cache.get_top_n(UUID("aaaa0000-0000-0000-0000-000000000099")) == []


class TestRecommendationController:
    def test_post_feedback_updates_exclusion(self, vectorized_movies, adult_user):
        cache = RecommendationCache()
        exc_sets = {}
        ctrl = RecommendationController(cache, exc_sets)
        fb = Feedback(adult_user.id, vectorized_movies[0].id, "movie", "like",
                      datetime.now(timezone.utc))
        ctrl.post_feedback(fb)
        assert adult_user.id in exc_sets
        assert exc_sets[adult_user.id].contains(vectorized_movies[0].id)

    def test_get_recommendations_reads_cache(self, vectorized_movies, adult_user):
        cache = RecommendationCache()
        items = [ScoredItem(vectorized_movies[0], 0.8)]
        cache.save_top_n(adult_user.id, items)
        ctrl = RecommendationController(cache, {})
        assert ctrl.get_recommendations(adult_user.id) == items


# ============================================================
# Test de integración end-to-end
# ============================================================

class TestEndToEnd:
    def test_minor_never_receives_adult_content(self, small_movies, small_games, minor_user, adult_user):
        """Un usuario menor de 18 no debe recibir ítems M o R en ningún módulo."""
        TfIdfVectorizer().fit_transform(small_movies)
        TfIdfVectorizer().fit_transform(small_games)

        all_items = small_movies + small_games
        movie_map = {m.id: m for m in small_movies}
        game_map  = {g.id: g for g in small_games}

        fbs = [Feedback(minor_user.id, small_movies[3].id, "movie", "like")]   # KidsA
        pb = ProfileBuilder()
        mp, gp, gen = pb.build_user_profiles(minor_user, fbs, movie_map, game_map)

        all_profiles = {minor_user.id: mp.profile_vector, adult_user.id: []}
        fbs_by_user  = {minor_user.id: fbs}

        exc = ExclusionSet(minor_user.id)
        exc.populate_from_feedbacks(fbs)

        hybrid = HybridRecommender()
        cache  = RecommendationCache()
        batch  = RecommendationBatchJob(
            recommender=hybrid,
            business_filter=BusinessFilter(),
            diversifier=Diversifier(),
            cache=cache,
            top_n=10,
        )
        batch.run(
            users=[minor_user],
            candidates=small_movies,
            user_profiles={minor_user.id: (mp.profile_vector, gen)},
            all_profiles=all_profiles,
            all_feedbacks=fbs_by_user,
            exclusion_sets={minor_user.id: exc},
        )

        recs = cache.get_top_n(minor_user.id)
        for si in recs:
            assert si.item.age_rating not in ("R", "M", "AO"), (
                f"Ítem {si.item.title} ({si.item.age_rating}) no debería llegar al menor"
            )

    def test_cross_module_boost_helps_cold_start(self, small_movies, small_games, adult_user):
        """
        Un usuario con historial solo en juegos de horror debe recibir
        películas de horror en las primeras posiciones (cross-module boost).
        """
        TfIdfVectorizer().fit_transform(small_movies)
        TfIdfVectorizer().fit_transform(small_games)

        movie_map = {m.id: m for m in small_movies}
        game_map  = {g.id: g for g in small_games}

        # Solo feedback de juegos — cold start en películas
        fbs = [Feedback(adult_user.id, small_games[0].id, "game", "like")]  # HorrorGame
        pb = ProfileBuilder()
        mp, gp, gen = pb.build_user_profiles(adult_user, fbs, movie_map, game_map)

        # mp.profile_vector estará vacío (nunca calificó una peli)
        assert mp.profile_vector == []

        # Pero el general profile debe tener "horror"
        tag_names = [g.tag for g in gen]
        assert "horror" in tag_names

        # El cross_module_boost de la peli de horror debe ser > 0
        hybrid = HybridRecommender()
        horror_movie = small_movies[0]   # HorrorA
        action_movie = small_movies[2]   # ActionA
        boost_h = hybrid.cross_module_boost(horror_movie, gen)
        boost_a = hybrid.cross_module_boost(action_movie, gen)
        assert boost_h > boost_a
