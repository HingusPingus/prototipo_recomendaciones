"""
cli_preferencias.py — RecoMe por preferencias de géneros/sagas/temáticas

En lugar de preguntar ítem por ítem, le pregunta al usuario qué géneros,
sagas y temáticas le gustan y usa eso para construir el perfil sintético.
Mínimo 5 selecciones, sin tope.

Ejecutar:
    python3 cli_preferencias.py
"""

from __future__ import annotations
import os
from uuid import uuid4
from datetime import date, datetime, timezone

from data import MOVIES, GAMES
from domain import User, Feedback, UserGeneralTagProfile
from vectorizer import TfIdfVectorizer, ProfileBuilder
from recommenders import HybridRecommender
from orchestration import (
    BusinessFilter, Diversifier, ExclusionSet,
    RecommendationCache, RecommendationBatchJob,
)

# ── Paleta de preferencias disponibles ─────────────────────────────────────
# Cada entrada: (etiqueta visible, lista de tags internos que activa)

PREFERENCES: list[tuple[str, list[str]]] = [
    # Géneros cinematográficos / de juego
    ("Horror / Terror",              ["horror", "sobrenatural", "psicologico"]),
    ("Acción",                       ["accion", "battle_royale"]),
    ("Aventura",                     ["aventura"]),
    ("Thriller / Suspenso",          ["thriller", "misterio"]),
    ("Ciencia Ficción",              ["ciencia_ficcion", "espacio", "distopia", "multiverso"]),
    ("Drama",                        ["drama"]),
    ("Comedia",                      ["comedia"]),
    ("Animación / Familiar",         ["animacion", "familiar"]),
    ("Romance / Musical",            ["romance", "musical", "musica"]),
    ("Fantasía",                     ["fantasia"]),
    ("Crimen / Policial",            ["crimen", "social"]),
    ("Historia / Bélico / Épico",    ["historia", "belico", "epica", "vikingos"]),
    ("Post-apocalíptico",            ["postapocaliptico"]),
    # Géneros y mecánicas de juegos
    ("RPG",                          ["rpg"]),
    ("Mundo abierto",                ["mundo_abierto"]),
    ("Survival",                     ["survival"]),
    ("Horror de supervivencia",      ["horror", "survival"]),
    ("Soulslike / Desafiante",       ["soulslike", "dificil"]),
    ("Roguelike",                    ["roguelike"]),
    ("Indie",                        ["indie"]),
    ("Multijugador / Cooperativo",   ["multijugador", "cooperativo"]),
    ("Deportes / Competitivo",       ["deportes", "competitivo"]),
    ("Construcción / Sandbox",       ["construccion", "sandbox"]),
    ("Simulación",                   ["simulacion"]),
    ("Plataformas",                  ["plataformas"]),
    ("Estrategia",                   ["estrategia"]),
    # Temáticas / sagas
    ("Superhéroes (Marvel / DC)",    ["superheroes"]),
    ("Mitología",                    ["mitologia"]),
    ("Basado en hechos reales",      ["basada_en_hechos_reales"]),
    ("Psicológico / Perturbador",    ["psicologico", "folclore", "periodo"]),
    ("Espacio / Exploración",        ["espacio", "ciencia_ficcion"]),
    ("Japón / Anime-like",           ["japon"]),
    ("Western / Samurai",            ["western", "samurai"]),
    ("Misterio / Investigación",     ["misterio", "investigacion"]),
    ("Social / Crítica social",      ["social"]),
    ("Ciencia / Tecnología",         ["ciencia", "distopia"]),
]

MIN_SELECTIONS = 5

# ── Helpers de consola ──────────────────────────────────────────────────────

CYAN   = "\033[96m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def clear():
    os.system("clear")

def header(text: str):
    print(f"\n{BOLD}{CYAN}{'─'*56}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*56}{RESET}\n")

def ask_birth_date() -> date:
    while True:
        raw = input(f"  {YELLOW}Fecha de nacimiento (AAAA-MM-DD){RESET} → ").strip()
        try:
            return date.fromisoformat(raw)
        except ValueError:
            print("  Formato inválido, intentá de nuevo (ej: 1998-07-24).")

def print_preferences_menu(selected: set[int]):
    """Imprime el menú numerado con los ítems ya seleccionados marcados."""
    print(f"  {'N°':<4} {'✔':<3} {'Preferencia'}")
    print(f"  {'─'*4} {'─'*3} {'─'*40}")
    for i, (label, _) in enumerate(PREFERENCES, 1):
        mark = f"{GREEN}✔{RESET}" if i in selected else " "
        num  = f"{YELLOW}{i:>2}{RESET}"
        print(f"  {num}   {mark}   {label}")
    print()

def ask_preferences() -> set[int]:
    """
    Muestra el menú y permite al usuario togglear preferencias.
    Devuelve el conjunto de índices (1-based) seleccionados.
    """
    selected: set[int] = set()

    while True:
        clear()
        header("¿Qué te gusta ver o jugar?")
        print(f"  Seleccioná al menos {BOLD}{MIN_SELECTIONS}{RESET} géneros o temáticas que te gusten.")
        print(f"  Podés elegir todos los que quieras — escribí el número para marcar/desmarcar.\n")

        print_preferences_menu(selected)

        count = len(selected)
        remaining = max(0, MIN_SELECTIONS - count)
        if remaining > 0:
            status = f"  {RED}Seleccionadas: {count}  (faltan al menos {remaining} más){RESET}"
        else:
            status = f"  {GREEN}Seleccionadas: {count}  ✔  Podés seguir agregando o escribir 'listo'{RESET}"
        print(status)
        print()

        raw = input(f"  {YELLOW}Número para marcar/desmarcar, o 'listo' para continuar{RESET}: ").strip().lower()

        if raw in ("listo", "ok", "done", "continuar", "siguiente"):
            if count < MIN_SELECTIONS:
                print(f"\n  {RED}Necesitás seleccionar al menos {MIN_SELECTIONS}. Tenés {count}.{RESET}")
                input("  Presioná Enter para volver al menú...")
            else:
                break
        else:
            try:
                n = int(raw)
                if 1 <= n <= len(PREFERENCES):
                    if n in selected:
                        selected.discard(n)
                    else:
                        selected.add(n)
                else:
                    input(f"  {RED}Número fuera de rango (1-{len(PREFERENCES)}). Enter para continuar...{RESET}")
            except ValueError:
                input(f"  {RED}Entrada inválida. Enter para continuar...{RESET}")

    return selected


# ── Construcción del perfil sintético desde preferencias ───────────────────

def build_synthetic_feedbacks(
    user: User,
    selected_indices: set[int],
) -> list[Feedback]:
    """
    Por cada preferencia elegida, busca los ítems del catálogo que tengan
    al menos uno de sus tags y genera un Feedback sintético de 'like'.
    Así el ProfileBuilder puede construir el vector de perfil normalmente.
    """
    # Tags activos desde las preferencias seleccionadas
    active_tags: set[str] = set()
    for idx in selected_indices:
        _, tags = PREFERENCES[idx - 1]
        active_tags.update(tags)

    feedbacks: list[Feedback] = []
    now = datetime.now(timezone.utc)

    for movie in MOVIES:
        if active_tags & set(movie.tags):   # intersección no vacía
            feedbacks.append(Feedback(
                user_id=user.id,
                item_id=movie.id,
                item_type="movie",
                state="like",
                timestamp=now,
            ))

    for game in GAMES:
        if active_tags & set(game.tags):
            feedbacks.append(Feedback(
                user_id=user.id,
                item_id=game.id,
                item_type="game",
                state="like",
                timestamp=now,
            ))

    return feedbacks


# ── Pipeline ────────────────────────────────────────────────────────────────

def run_pipeline(user: User, feedbacks: list[Feedback], top_n: int = 3):
    """Devuelve (movie_recs, game_recs) con hasta top_n resultados cada uno."""
    TfIdfVectorizer().fit_transform(MOVIES)
    TfIdfVectorizer().fit_transform(GAMES)

    movie_map = {m.id: m for m in MOVIES}
    game_map  = {g.id: g for g in GAMES}

    pb = ProfileBuilder()
    mp, gp, gen = pb.build_user_profiles(user, feedbacks, movie_map, game_map)

    # Sin exclusiones: el perfil sintético no representa consumo real
    exc = ExclusionSet(user.id)

    hybrid    = HybridRecommender(alpha=0.6, beta=0.2, gamma=0.2)
    biz       = BusinessFilter()
    diversify = Diversifier(lambda_mmr=0.65)

    all_movie_profiles = {user.id: mp.profile_vector}
    all_game_profiles  = {user.id: gp.profile_vector}
    fbs_by_user = {
        user.id: [fb for fb in feedbacks if fb.item_type == "movie"]
    }

    movie_cache = RecommendationCache()
    RecommendationBatchJob(hybrid, biz, diversify, movie_cache, top_n=top_n).run(
        users=[user],
        candidates=MOVIES,
        user_profiles={user.id: (mp.profile_vector, gen)},
        all_profiles=all_movie_profiles,
        all_feedbacks={user.id: [fb for fb in feedbacks if fb.item_type == "movie"]},
        exclusion_sets={user.id: exc},
    )

    game_cache = RecommendationCache()
    RecommendationBatchJob(hybrid, biz, diversify, game_cache, top_n=top_n).run(
        users=[user],
        candidates=GAMES,
        user_profiles={user.id: (gp.profile_vector, gen)},
        all_profiles=all_game_profiles,
        all_feedbacks={user.id: [fb for fb in feedbacks if fb.item_type == "game"]},
        exclusion_sets={user.id: exc},
    )

    return movie_cache.get_top_n(user.id), game_cache.get_top_n(user.id)


# ── Resultado ───────────────────────────────────────────────────────────────

def print_results(movie_recs, game_recs, selected_indices: set[int]):
    clear()
    header("TUS RECOMENDACIONES PERSONALIZADAS 🎬🎮")

    chosen_labels = [PREFERENCES[i - 1][0] for i in sorted(selected_indices)]
    print(f"  Basado en: {CYAN}{', '.join(chosen_labels)}{RESET}\n")

    print(f"  {BOLD}{'─'*24}  PELÍCULAS  {'─'*24}{RESET}\n")
    if movie_recs:
        for i, si in enumerate(movie_recs, 1):
            m = si.item
            print(f"  {BOLD}{GREEN}{i}. {m.title}{RESET}")
            print(f"     {m.age_rating}  ·  ⭐ {m.external_score}  ·  {', '.join(m.tags)}")
            print()
    else:
        print(f"  {RED}No encontramos películas disponibles para tu edad y preferencias.{RESET}\n")

    print(f"  {BOLD}{'─'*24}  JUEGOS  {'─'*26}{RESET}\n")
    if game_recs:
        for i, si in enumerate(game_recs, 1):
            g = si.item
            print(f"  {BOLD}{GREEN}{i}. {g.title}{RESET}")
            print(f"     {g.age_rating}  ·  ⭐ {g.external_score}  ·  {', '.join(g.tags)}")
            print()
    else:
        print(f"  {RED}No encontramos juegos disponibles para tu edad y preferencias.{RESET}\n")

    print(f"  {CYAN}¡Gracias por usar RecoMe!{RESET}\n")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    clear()
    header("Bienvenido/a a RecoMe — Recomendaciones por preferencias")
    print("  Te vamos a recomendar películas y juegos según tus gustos.")
    print("  No hace falta que hayas visto nada — solo contanos qué te gusta.\n")

    birth_date = ask_birth_date()
    user = User(id=uuid4(), birth_date=birth_date)
    print(f"\n  Edad detectada: {BOLD}{user.age} años{RESET}")
    input(f"  {YELLOW}Presioná Enter para elegir tus preferencias...{RESET}")

    selected = ask_preferences()

    clear()
    print(f"\n  {YELLOW}Calculando recomendaciones...{RESET}\n")
    feedbacks = build_synthetic_feedbacks(user, selected)
    movie_recs, game_recs = run_pipeline(user, feedbacks, top_n=5)

    print_results(movie_recs, game_recs, selected)


if __name__ == "__main__":
    main()
