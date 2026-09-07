"""
main.py — Demo del prototipo RecoMe.

Ejecutar:
    python main.py

Muestra el pipeline completo:
  1. Vectorización TF-IDF del catálogo (películas y juegos por separado).
  2. Construcción de perfiles de usuario.
  3. BatchJob: scoring híbrido → filtros → MMR → caché.
  4. Controller: consulta de recomendaciones y registro de nuevo feedback.
"""

from uuid import UUID
from datetime import datetime, timezone

from data import MOVIES, GAMES, USERS, FEEDBACKS
from domain import Feedback
from vectorizer import TfIdfVectorizer, ProfileBuilder
from recommenders import HybridRecommender
from orchestration import (
    BusinessFilter, Diversifier,
    ExclusionSet, RecommendationCache,
    RecommendationBatchJob, RecommendationController,
)


# ============================================================
# 1. Vectorización TF-IDF (espacios separados por módulo)
# ============================================================

print("=" * 60)
print("1. VECTORIZACIÓN TF-IDF")
print("=" * 60)

movie_vectorizer = TfIdfVectorizer()
game_vectorizer  = TfIdfVectorizer()

movie_idf, movie_vocab = movie_vectorizer.fit_transform(MOVIES)
game_idf,  game_vocab  = game_vectorizer.fit_transform(GAMES)

print(f"Vocabulario películas ({len(movie_vocab)} tags): {movie_vocab}")
print(f"Vocabulario juegos   ({len(game_vocab)} tags): {game_vocab}")
print()


# ============================================================
# 2. Construcción de perfiles de usuario
# ============================================================

print("=" * 60)
print("2. PERFILES DE USUARIO")
print("=" * 60)

movie_map = {m.id: m for m in MOVIES}
game_map  = {g.id: g for g in GAMES}

profile_builder = ProfileBuilder()

# Agrupa feedbacks por usuario
from collections import defaultdict
feedbacks_by_user: dict = defaultdict(list)
for fb in FEEDBACKS:
    feedbacks_by_user[fb.user_id].append(fb)

# user_profiles: user_id -> (profile_vector, general_tag_profile)
# all_profiles:  user_id -> profile_vector   (usado por CF)
user_profiles: dict = {}
all_movie_profiles: dict = {}
all_game_profiles:  dict = {}

for user in USERS:
    fbs = feedbacks_by_user[user.id]
    mp, gp, gen = profile_builder.build_user_profiles(user, fbs, movie_map, game_map)
    user_profiles[user.id] = (mp.profile_vector, gp.profile_vector, gen)
    all_movie_profiles[user.id] = mp.profile_vector
    all_game_profiles[user.id]  = gp.profile_vector
    print(f"  Usuario {user.id} (edad {user.age})")
    print(f"    Tags generales: {[(g.tag, round(g.weight,2)) for g in gen[:5]]}")

print()


# ============================================================
# 3. ExclusionSets — inicializados desde el historial
# ============================================================

print("=" * 60)
print("3. EXCLUSION SETS")
print("=" * 60)

exclusion_sets: dict = {}
for user in USERS:
    exc = ExclusionSet(user.id)
    exc.populate_from_feedbacks(feedbacks_by_user[user.id])
    exclusion_sets[user.id] = exc
    print(f"  Usuario {user.id}: {len(exc._ids)} ítem(s) excluidos")

print()


# ============================================================
# 4. BatchJob — pipeline completo para cada usuario
#    (aquí lo corremos por módulo: películas y juegos)
# ============================================================

print("=" * 60)
print("4. BATCH JOB")
print("=" * 60)

cache = RecommendationCache()

# Parámetros del HybridRecommender
# α domina en cold-start, β crece con historial, γ es siempre bajo
hybrid = HybridRecommender(alpha=0.5, beta=0.4, gamma=0.1, k_neighbors=2)

biz_filter  = BusinessFilter()
diversifier = Diversifier(lambda_mmr=0.7)

batch = RecommendationBatchJob(
    recommender=hybrid,
    business_filter=biz_filter,
    diversifier=diversifier,
    cache=cache,
    top_n=5,
)

# ---------- Recomendaciones de PELÍCULAS ----------
print("\n--- Películas ---")

movie_user_profiles = {
    uid: (vec, gen)
    for uid, (mvec, gvec, gen) in user_profiles.items()
    for vec in [mvec]
}

batch.run(
    users=USERS,
    candidates=MOVIES,
    user_profiles={uid: (mvec, gen) for uid, (mvec, gvec, gen) in user_profiles.items()},
    all_profiles=all_movie_profiles,
    all_feedbacks={uid: [fb for fb in fbs if fb.item_type == "movie"]
                   for uid, fbs in feedbacks_by_user.items()},
    exclusion_sets=exclusion_sets,
)

# ---------- Recomendaciones de JUEGOS ----------
# (sobrescribe la caché con juegos; en prod habría claves separadas)
game_cache = RecommendationCache()
game_batch = RecommendationBatchJob(
    recommender=hybrid,
    business_filter=biz_filter,
    diversifier=diversifier,
    cache=game_cache,
    top_n=5,
)

print("\n--- Juegos ---")
game_batch.run(
    users=USERS,
    candidates=GAMES,
    user_profiles={uid: (gvec, gen) for uid, (mvec, gvec, gen) in user_profiles.items()},
    all_profiles=all_game_profiles,
    all_feedbacks={uid: [fb for fb in fbs if fb.item_type == "game"]
                   for uid, fbs in feedbacks_by_user.items()},
    exclusion_sets=exclusion_sets,
)
print()


# ============================================================
# 5. RecommendationController — consulta y feedback nuevo
# ============================================================

print("=" * 60)
print("5. CONTROLLER — CONSULTA DE RECOMENDACIONES")
print("=" * 60)

movie_controller = RecommendationController(cache=cache, exclusion_sets=exclusion_sets)
game_controller  = RecommendationController(cache=game_cache, exclusion_sets=exclusion_sets)

for user in USERS:
    print(f"\n  Usuario {user.id} (edad {user.age}):")

    movie_recs = movie_controller.get_recommendations(user.id)
    print("    🎬 Películas recomendadas:")
    if movie_recs:
        for i, si in enumerate(movie_recs, 1):
            print(f"      {i}. {si.item.title:30s}  score={si.score:.4f}  [{si.item.age_rating}]")
    else:
        print("      (sin recomendaciones)")

    game_recs = game_controller.get_recommendations(user.id)
    print("    🎮 Juegos recomendados:")
    if game_recs:
        for i, si in enumerate(game_recs, 1):
            print(f"      {i}. {si.item.title:30s}  score={si.score:.4f}  [{si.item.age_rating}]")
    else:
        print("      (sin recomendaciones)")

print()


# ============================================================
# 6. Nuevo feedback en tiempo real (sin recalcular)
# ============================================================

print("=" * 60)
print("6. NUEVO FEEDBACK EN TIEMPO REAL")
print("=" * 60)

new_fb = Feedback(
    user_id=USERS[0].id,
    item_id=MOVIES[0].id,   # El Conjuro
    item_type="movie",
    state="like",
    timestamp=datetime.now(timezone.utc),
)
movie_controller.post_feedback(new_fb)
print("  (El perfil se actualizará en el próximo BatchJob)")
