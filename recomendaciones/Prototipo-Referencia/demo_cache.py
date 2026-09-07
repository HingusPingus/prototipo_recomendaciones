"""
demo_cache.py — Demuestra el efecto del caché (paso 7).

Mide y compara:
  A) Leer el top-N desde Redis   → microsegundos
  B) Recalcular todo el scoring  → milisegundos / segundos

Ejecutar:
    python3 demo_cache.py            # fakeredis
    python3 demo_cache.py --real     # Redis real en localhost:6379
"""

from __future__ import annotations
import sys
import time
from collections import defaultdict

from data import MOVIES, GAMES, USERS, FEEDBACKS
from vectorizer import TfIdfVectorizer, ProfileBuilder
from recommenders import HybridRecommender
from orchestration import (
    BusinessFilter, Diversifier, ExclusionSet,
    RecommendationBatchJob, RecommendationCache,
)
from cache_redis import RedisCache
from batch_redis import run_batch

CYAN   = "\033[96m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
REPETS = 5      # veces que se repite cada medición para promediar


def time_recalculate() -> tuple[float, list]:
    """Recalcula el pipeline completo para el usuario 0. Devuelve (segundos, recs)."""
    TfIdfVectorizer().fit_transform(MOVIES)
    TfIdfVectorizer().fit_transform(GAMES)

    movie_map = {m.id: m for m in MOVIES}
    game_map  = {g.id: g for g in GAMES}

    fbs_by_user: dict = defaultdict(list)
    for fb in FEEDBACKS:
        fbs_by_user[fb.user_id].append(fb)

    pb = ProfileBuilder()

    # Construir perfiles de TODOS los usuarios (igual que el batch)
    # para que el componente colaborativo tenga la misma señal
    all_movie_profiles: dict = {}
    for user in USERS:
        mp, _, _ = pb.build_user_profiles(user, fbs_by_user[user.id], movie_map, game_map)
        all_movie_profiles[user.id] = mp.profile_vector

    mp, gp, gen = pb.build_user_profiles(USERS[0], fbs_by_user[USERS[0].id], movie_map, game_map)

    exc = ExclusionSet(USERS[0].id)
    exc.populate_from_feedbacks(fbs_by_user[USERS[0].id])

    hybrid    = HybridRecommender()
    biz       = BusinessFilter()
    diversify = Diversifier()
    mem_cache = RecommendationCache()

    t0 = time.perf_counter()
    RecommendationBatchJob(hybrid, biz, diversify, mem_cache, top_n=10).run(
        users=[USERS[0]],
        candidates=MOVIES,
        user_profiles={USERS[0].id: (mp.profile_vector, gen)},
        all_profiles=all_movie_profiles,
        all_feedbacks={
            uid: [fb for fb in fbs if fb.item_type == "movie"]
            for uid, fbs in fbs_by_user.items()
        },
        exclusion_sets={USERS[0].id: exc},
    )
    elapsed = time.perf_counter() - t0
    return elapsed, mem_cache.get_top_n(USERS[0].id)


def time_redis_get(redis: RedisCache) -> tuple[float, list]:
    """Lee el top-N desde Redis. Devuelve (segundos, recs)."""
    t0 = time.perf_counter()
    recs = redis.get_top_n(USERS[0].id, "movie")
    elapsed = time.perf_counter() - t0
    return elapsed, recs


def bar(value: float, max_value: float, width: int = 30) -> str:
    filled = int(round(value / max_value * width)) if max_value > 0 else 0
    return "█" * filled + "░" * (width - filled)


def main():
    use_fake = "--real" not in sys.argv

    print(f"\n{'─'*60}")
    print(f"  {BOLD}RecoMe — Demo de caché Redis{RESET}")
    print(f"{'─'*60}")

    redis = RedisCache(use_fake=use_fake)
    print(f"  Modo Redis : {CYAN}{redis.mode}{RESET}")
    print(f"  Catálogo   : {len(MOVIES)} películas · {len(GAMES)} juegos · {len(USERS)} usuarios")
    print(f"  Repeticiones por medición: {REPETS}\n")

    # ── Paso 6: poblar Redis con el batch ────────────────────────────────
    print(f"  {YELLOW}[1/3] Ejecutando batch para poblar Redis...{RESET}")
    batch_time = run_batch(redis)
    print(f"        Batch completado en {batch_time*1000:.1f} ms\n")

    # ── Paso 7A: medir GET desde Redis ───────────────────────────────────
    print(f"  {YELLOW}[2/3] Midiendo lectura desde Redis ({REPETS}x)...{RESET}")
    redis_times = []
    for _ in range(REPETS):
        t, recs_redis = time_redis_get(redis)
        redis_times.append(t)
    avg_redis = sum(redis_times) / REPETS

    # ── Paso 7B: medir recálculo completo ────────────────────────────────
    print(f"  {YELLOW}[3/3] Midiendo recálculo completo ({REPETS}x)...{RESET}\n")
    recalc_times = []
    for _ in range(REPETS):
        t, recs_recalc = time_recalculate()
        recalc_times.append(t)
    avg_recalc = sum(recalc_times) / REPETS

    speedup = avg_recalc / avg_redis if avg_redis > 0 else float("inf")
    max_t   = max(avg_redis, avg_recalc)

    # ── Resultado ────────────────────────────────────────────────────────
    print(f"{'─'*60}")
    print(f"  {BOLD}RESULTADOS{RESET}")
    print(f"{'─'*60}\n")

    print(f"  {GREEN}GET Redis{RESET}           {avg_redis*1000:>8.3f} ms   {bar(avg_redis, max_t)}")
    print(f"  {RED}Recálculo completo{RESET}  {avg_recalc*1000:>8.3f} ms   {bar(avg_recalc, max_t)}\n")

    print(f"  {BOLD}Speedup: ×{speedup:.0f} más rápido con caché{RESET}\n")

    print(f"  Desglose Redis (mín / prom / máx):")
    print(f"    {min(redis_times)*1000:.3f} ms  /  {avg_redis*1000:.3f} ms  /  {max(redis_times)*1000:.3f} ms")
    print(f"  Desglose Recálculo (mín / prom / máx):")
    print(f"    {min(recalc_times)*1000:.3f} ms  /  {avg_recalc*1000:.3f} ms  /  {max(recalc_times)*1000:.3f} ms\n")

    # ── Verificación de consistencia ─────────────────────────────────────
    titles_redis   = {si.item.title for si in recs_redis}
    titles_recalc  = {si.item.title for si in recs_recalc}
    coinciden      = len(titles_redis & titles_recalc)
    print(f"  Consistencia: {coinciden}/{max(len(titles_redis), len(titles_recalc))} ítems coinciden entre caché y recálculo\n")

    # ── Mostrar top-5 del caché ──────────────────────────────────────────
    print(f"  {BOLD}Top-5 películas desde Redis para usuario '{USERS[0].id}':{RESET}")
    for i, si in enumerate(recs_redis[:5], 1):
        print(f"    {i}. {si.item.title:<42} score={si.score:.4f}")

    print(f"\n  {CYAN}TTL restante de la key: {redis.ttl_remaining(USERS[0].id, 'movie')} s{RESET}\n")


if __name__ == "__main__":
    main()
