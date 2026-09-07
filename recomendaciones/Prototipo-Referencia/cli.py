"""
cli.py — RecoMe interactivo
Pregunta al usuario qué películas y juegos conoce/le gustaron/le disgustaron
y recomienda 1 película y 1 juego personalizados.

Ejecutar:
    python3 cli.py
"""

from __future__ import annotations
import os
from uuid import uuid4
from datetime import date, datetime, timezone
from collections import defaultdict

from data import MOVIES, GAMES
from domain import User, Feedback
from vectorizer import TfIdfVectorizer, ProfileBuilder
from recommenders import HybridRecommender
from orchestration import (
    BusinessFilter, Diversifier, ExclusionSet,
    RecommendationCache, RecommendationBatchJob,
)

# ── Helpers de consola ──────────────────────────────────────────────────────

CYAN   = "\033[96m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def clear():
    os.system("clear")

def header(text: str):
    print(f"\n{BOLD}{CYAN}{'─'*50}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*50}{RESET}\n")

def ask_birth_date() -> date:
    while True:
        raw = input(f"  {YELLOW}¿Cuál es tu fecha de nacimiento? (AAAA-MM-DD){RESET} → ").strip()
        try:
            return date.fromisoformat(raw)
        except ValueError:
            print("  Formato inválido. Intentá de nuevo.")

def ask_item_state(title: str, item_type: str) -> str | None:
    """
    Devuelve el estado elegido por el usuario, o None si quiere saltearlo.
    """
    type_label = "película" if item_type == "movie" else "juego"
    print(f"\n  🎬  {BOLD}{title}{RESET}" if item_type == "movie" else f"\n  🎮  {BOLD}{title}{RESET}")
    print(f"  ¿Qué relación tenés con este/a {type_label}?")
    print("    1) Me gustó  (like)")
    print("    2) No me gustó  (dislike)")
    print("    3) Lo/la vi pero no me generó opinión  (visto/jugado)")
    print("    4) No lo/la conozco / quiero saltearlo")

    while True:
        choice = input(f"  {YELLOW}Opción [1-4]{RESET}: ").strip()
        if choice == "1":
            return "like"
        elif choice == "2":
            return "dislike"
        elif choice == "3":
            return "visto" if item_type == "movie" else "jugado"
        elif choice == "4":
            return None
        print("  Por favor ingresá 1, 2, 3 o 4.")


# ── Pipeline de recomendación ───────────────────────────────────────────────

def run_pipeline(user: User, feedbacks: list[Feedback]) -> tuple:
    """
    Devuelve (top_movie, top_game) o None si no hay recomendación posible.
    """
    # Vectorización
    movie_vectorizer = TfIdfVectorizer()
    game_vectorizer  = TfIdfVectorizer()
    movie_vectorizer.fit_transform(MOVIES)
    game_vectorizer.fit_transform(GAMES)

    movie_map = {m.id: m for m in MOVIES}
    game_map  = {g.id: g for g in GAMES}

    # Perfiles
    pb = ProfileBuilder()
    mp, gp, gen = pb.build_user_profiles(user, feedbacks, movie_map, game_map)

    # ExclusionSet — excluye todo lo que ya tiene opinión
    exc = ExclusionSet(user.id)
    exc.populate_from_feedbacks(feedbacks)

    all_movie_profiles = {user.id: mp.profile_vector}
    all_game_profiles  = {user.id: gp.profile_vector}
    fbs_by_user = {user.id: feedbacks}

    hybrid    = HybridRecommender(alpha=0.5, beta=0.4, gamma=0.1)
    biz       = BusinessFilter()
    diversify = Diversifier(lambda_mmr=0.7)

    # --- Películas ---
    movie_cache = RecommendationCache()
    RecommendationBatchJob(hybrid, biz, diversify, movie_cache, top_n=10).run(
        users=[user],
        candidates=MOVIES,
        user_profiles={user.id: (mp.profile_vector, gen)},
        all_profiles=all_movie_profiles,
        all_feedbacks={user.id: [fb for fb in feedbacks if fb.item_type == "movie"]},
        exclusion_sets={user.id: exc},
    )

    # --- Juegos ---
    game_cache = RecommendationCache()
    RecommendationBatchJob(hybrid, biz, diversify, game_cache, top_n=10).run(
        users=[user],
        candidates=GAMES,
        user_profiles={user.id: (gp.profile_vector, gen)},
        all_profiles=all_game_profiles,
        all_feedbacks={user.id: [fb for fb in feedbacks if fb.item_type == "game"]},
        exclusion_sets={user.id: exc},
    )

    movie_recs = movie_cache.get_top_n(user.id)
    game_recs  = game_cache.get_top_n(user.id)

    top_movie = movie_recs[0] if movie_recs else None
    top_game  = game_recs[0]  if game_recs  else None
    return top_movie, top_game


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    clear()
    header("Bienvenido/a a RecoMe 🎬🎮")
    print("  Respondé algunas preguntas sobre películas y juegos")
    print("  y te recomendamos qué ver o jugar a continuación.\n")

    # Datos del usuario
    birth_date = ask_birth_date()
    user = User(id=uuid4(), birth_date=birth_date)
    print(f"\n  Edad detectada: {BOLD}{user.age} años{RESET}")

    feedbacks: list[Feedback] = []

    # ── Películas ──────────────────────────────────────────────────────────
    header("PELÍCULAS")
    print("  Contanos qué sabés de estas películas:\n")
    for movie in MOVIES:
        state = ask_item_state(movie.title, "movie")
        if state:
            feedbacks.append(Feedback(
                user_id=user.id,
                item_id=movie.id,
                item_type="movie",
                state=state,
                timestamp=datetime.now(timezone.utc),
            ))

    # ── Juegos ────────────────────────────────────────────────────────────
    header("VIDEOJUEGOS")
    print("  Contanos qué sabés de estos juegos:\n")
    for game in GAMES:
        state = ask_item_state(game.title, "game")
        if state:
            feedbacks.append(Feedback(
                user_id=user.id,
                item_id=game.id,
                item_type="game",
                state=state,
                timestamp=datetime.now(timezone.utc),
            ))

    # ── Procesamiento ─────────────────────────────────────────────────────
    print(f"\n  {YELLOW}Calculando recomendaciones...{RESET}")
    top_movie, top_game = run_pipeline(user, feedbacks)

    # ── Resultado ─────────────────────────────────────────────────────────
    header("TUS RECOMENDACIONES PERSONALIZADAS")

    if top_movie:
        m = top_movie.item
        print(f"  🎬  {BOLD}{GREEN}Película:{RESET} {BOLD}{m.title}{RESET}")
        print(f"       Clasificación: {m.age_rating}  |  Score externo: {m.external_score}")
        print(f"       Tags: {', '.join(m.tags)}")
        print(f"       Puntaje calculado: {top_movie.score:.4f}")
    else:
        print("  🎬  No encontramos una película disponible para vos (puede que ya las hayas visto todas).")

    print()

    if top_game:
        g = top_game.item
        print(f"  🎮  {BOLD}{GREEN}Juego:{RESET}    {BOLD}{g.title}{RESET}")
        print(f"       Clasificación: {g.age_rating}  |  Score externo: {g.external_score}")
        print(f"       Tags: {', '.join(g.tags)}")
        print(f"       Puntaje calculado: {top_game.score:.4f}")
    else:
        print("  🎮  No encontramos un juego disponible para vos (puede que ya los hayas jugado todos).")

    print(f"\n  {CYAN}¡Gracias por usar RecoMe!{RESET}\n")


if __name__ == "__main__":
    main()
