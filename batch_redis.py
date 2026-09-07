"""
batch_redis.py — BatchJob que escribe resultados en Redis (paso 4).

Corre el pipeline completo (scoring híbrido → filtros → MMR) para todos
los usuarios hardcodeados y persiste el top-N en Redis.

Ejecutar:
    python3 batch_redis.py            # usa fakeredis (sin infraestructura)
    python3 batch_redis.py --real     # usa Redis real en localhost:6379
"""

from __future__ import annotations
import sys
import time
from collections import defaultdict

from data import MOVIES, GAMES, USERS, FEEDBACKS
from domain import Feedback
from vectorizer import TfIdfVectorizer, ProfileBuilder
from recommenders import HybridRecommender
from orchestration import (
    BusinessFilter, Diversifier, ExclusionSet,
    RecommendationBatchJob, RecommendationCache,
)
from cache_redis import RedisCache, Module

TOP_N  = 10
USE_FAKE = "--real" not in sys.argv


def run_batch(redis: RedisCache) -> float:
    """
    Ejecuta el pipeline completo y escribe en Redis.
    Devuelve el tiempo total en segundos.
    """
    t0 = time.perf_counter()

    # ── 1. Vectorización ─────────────────────────────────────────────────
    TfIdfVectorizer().fit_transform(MOVIES)
    TfIdfVectorizer().fit_transform(GAMES)

    movie_map = {m.id: m for m in MOVIES}
    game_map  = {g.id: g for g in GAMES}

    # ── 2. Perfiles ──────────────────────────────────────────────────────
    pb = ProfileBuilder()
    feedbacks_by_user: dict = defaultdict(list)
    for fb in FEEDBACKS:
        feedbacks_by_user[fb.user_id].append(fb)

    user_profiles: dict = {}
    all_movie_profiles: dict = {}
    all_game_profiles:  dict = {}

    for user in USERS:
        fbs = feedbacks_by_user[user.id]
        mp, gp, gen = pb.build_user_profiles(user, fbs, movie_map, game_map)
        user_profiles[user.id]      = (mp.profile_vector, gp.profile_vector, gen)
        all_movie_profiles[user.id] = mp.profile_vector
        all_game_profiles[user.id]  = gp.profile_vector

    # ── 3. Exclusion sets ────────────────────────────────────────────────
    local_exclusions: dict = {}
    for user in USERS:
        exc = ExclusionSet(user.id)
        exc.populate_from_feedbacks(feedbacks_by_user[user.id])
        local_exclusions[user.id] = exc
        # Persistir en Redis también
        redis.populate_exclusions_from_feedbacks(user.id, feedbacks_by_user[user.id])

    # ── 4. Scoring híbrido + filtros + MMR ───────────────────────────────
    hybrid    = HybridRecommender(alpha=0.5, beta=0.4, gamma=0.1)
    biz       = BusinessFilter()
    diversify = Diversifier(lambda_mmr=0.7)

    for module, catalog, all_profiles in [
        ("movie", MOVIES, all_movie_profiles),
        ("game",  GAMES,  all_game_profiles),
    ]:
        mem_cache = RecommendationCache()
        RecommendationBatchJob(hybrid, biz, diversify, mem_cache, top_n=TOP_N).run(
            users=USERS,
            candidates=catalog,
            user_profiles={
                u.id: (
                    user_profiles[u.id][0] if module == "movie" else user_profiles[u.id][1],
                    user_profiles[u.id][2],
                )
                for u in USERS
            },
            all_profiles=all_profiles,
            all_feedbacks={
                u.id: [fb for fb in feedbacks_by_user[u.id] if fb.item_type == module]
                for u in USERS
            },
            exclusion_sets=local_exclusions,
        )

        # ── 5. Escribir en Redis (paso 4) ─────────────────────────────
        for user in USERS:
            top = mem_cache.get_top_n(user.id)
            redis.save_top_n(user.id, module, top)  # type: ignore[arg-type]

    elapsed = time.perf_counter() - t0
    return elapsed


if __name__ == "__main__":
    print(f"\n{'─'*55}")
    print(f"  RecoMe — Batch con Redis")
    print(f"{'─'*55}")

    redis = RedisCache(use_fake=USE_FAKE)
    print(f"  Modo: {redis.mode}")
    print(f"  Usuarios: {len(USERS)}  |  Películas: {len(MOVIES)}  |  Juegos: {len(GAMES)}\n")

    elapsed = run_batch(redis)

    print(f"\n  ✅  Batch completado en {elapsed:.3f} s")
    print(f"\n  Keys escritas en Redis:")
    for user in USERS:
        for mod in ("movie", "game"):
            key = redis.reco_key(user.id, mod)
            count = len(redis.get_top_n(user.id, mod))  # type: ignore[arg-type]
            ttl   = redis.ttl_remaining(user.id, mod)    # type: ignore[arg-type]
            print(f"    {key}  →  {count} ítems  (TTL {ttl}s)")
    print()
