"""
Datos hardcodeados para el prototipo — RecoMe.
Incluye catálogo de películas y juegos, usuarios y feedback de ejemplo.
Spec sección 1.
"""

from uuid import UUID
from datetime import date, datetime, timezone
from domain import Movie, Game, User, Feedback

# ---------------------------------------------------------------------------
# Catálogo de películas (132 títulos)
# ---------------------------------------------------------------------------

MOVIES = [
    # ── Originales (001-032) ────────────────────────────────────────────────
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000001"), "El Conjuro",              "PG-13", 7.8, ["horror", "sobrenatural", "basada_en_hechos_reales"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000002"), "Hereditary",              "R",     7.3, ["horror", "drama", "sobrenatural"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000003"), "Interstellar",            "PG-13", 8.6, ["ciencia_ficcion", "espacio", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000004"), "Avengers: Endgame",       "PG-13", 8.4, ["accion", "superheroes", "aventura"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000005"), "Get Out",                 "R",     7.7, ["horror", "thriller", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000006"), "Toy Story",               "G",     8.3, ["animacion", "aventura", "comedia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000007"), "The Batman",              "PG-13", 7.9, ["accion", "crimen", "thriller", "superheroes"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000008"), "Dune",                    "PG-13", 8.0, ["ciencia_ficcion", "aventura", "epica"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000009"), "Everything Everywhere All at Once", "R", 7.8, ["ciencia_ficcion", "comedia", "drama", "multiverso"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000010"), "Top Gun: Maverick",       "PG-13", 8.3, ["accion", "drama", "militar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000011"), "Oppenheimer",             "R",     8.3, ["drama", "historia", "ciencia", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000012"), "Barbie",                  "PG-13", 6.9, ["comedia", "fantasia", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000013"), "The Witch",               "R",     6.9, ["horror", "periodo", "sobrenatural"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000014"), "Midsommar",               "R",     7.1, ["horror", "drama", "folclore"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000015"), "Nope",                    "R",     6.8, ["horror", "ciencia_ficcion", "misterio"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000016"), "John Wick",               "R",     7.4, ["accion", "crimen", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000017"), "Mad Max: Fury Road",      "R",     8.1, ["accion", "postapocaliptico", "aventura"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000018"), "Spider-Man: No Way Home", "PG-13", 8.2, ["superheroes", "accion", "aventura", "multiverso"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000019"), "Parasite",                "R",     8.5, ["thriller", "drama", "crimen", "social"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000020"), "La La Land",              "PG-13", 8.0, ["drama", "romance", "musical"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000021"), "Knives Out",              "PG-13", 7.9, ["misterio", "comedia", "crimen", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000022"), "1917",                    "R",     8.2, ["belico", "drama", "historia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000023"), "The Menu",                "R",     7.2, ["thriller", "horror", "comedia", "social"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000024"), "Encanto",                 "PG",    7.2, ["animacion", "fantasia", "musical", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000025"), "Doctor Strange in the Multiverse of Madness", "PG-13", 6.9, ["superheroes", "horror", "multiverso"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000026"), "The Northman",            "R",     7.1, ["accion", "historia", "vikingos", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000027"), "Whiplash",                "R",     8.5, ["drama", "musica", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000028"), "Arrival",                 "PG-13", 7.9, ["ciencia_ficcion", "drama", "misterio", "espacio"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000029"), "The Shining",             "R",     8.4, ["horror", "psicologico", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000030"), "Coco",                    "PG",    8.4, ["animacion", "familiar", "musical", "fantasia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000031"), "Blade Runner 2049",       "R",     8.0, ["ciencia_ficcion", "drama", "thriller", "distopia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000032"), "The Truman Show",         "PG",    8.1, ["drama", "comedia", "psicologico", "social"]),
    # ── Nuevas 100 (033-132) ────────────────────────────────────────────────
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000033"), "The Dark Knight",              "PG-13", 9.0, ["accion", "crimen", "thriller", "superheroes"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000034"), "Inception",                    "PG-13", 8.8, ["ciencia_ficcion", "accion", "thriller", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000035"), "The Matrix",                   "R",     8.7, ["ciencia_ficcion", "accion", "distopia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000036"), "Pulp Fiction",                 "R",     8.9, ["crimen", "thriller", "drama", "comedia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000037"), "Forrest Gump",                 "PG-13", 8.8, ["drama", "romance", "historia", "comedia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000038"), "Fight Club",                   "R",     8.8, ["thriller", "drama", "psicologico", "crimen"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000039"), "Goodfellas",                   "R",     8.7, ["crimen", "drama", "historia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000040"), "The Silence of the Lambs",     "R",     8.6, ["thriller", "horror", "crimen", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000041"), "Schindler's List",             "R",     9.0, ["drama", "historia", "belico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000042"), "The Lord of the Rings: The Fellowship of the Ring", "PG-13", 8.8, ["fantasia", "aventura", "epica"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000043"), "The Lord of the Rings: The Return of the King",    "PG-13", 9.0, ["fantasia", "aventura", "epica", "belico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000044"), "Gladiator",                    "R",     8.5, ["accion", "historia", "drama", "epica"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000045"), "The Godfather",                "R",     9.2, ["crimen", "drama", "historia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000046"), "Saving Private Ryan",          "R",     8.6, ["belico", "drama", "historia", "accion"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000047"), "A Beautiful Mind",             "PG-13", 8.2, ["drama", "historia", "psicologico", "romance"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000048"), "No Country for Old Men",       "R",     8.2, ["thriller", "crimen", "drama", "western"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000049"), "There Will Be Blood",          "R",     8.2, ["drama", "historia", "western"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000050"), "2001: A Space Odyssey",        "G",     8.3, ["ciencia_ficcion", "espacio", "drama", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000051"), "Alien",                        "R",     8.5, ["ciencia_ficcion", "horror", "espacio", "survival"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000052"), "Aliens",                       "R",     8.4, ["ciencia_ficcion", "horror", "accion", "espacio"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000053"), "Terminator 2",                 "R",     8.6, ["ciencia_ficcion", "accion", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000054"), "Jurassic Park",                "PG-13", 8.2, ["ciencia_ficcion", "aventura", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000055"), "Back to the Future",           "PG",    8.5, ["ciencia_ficcion", "comedia", "aventura", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000056"), "E.T. the Extra-Terrestrial",   "PG",    7.9, ["ciencia_ficcion", "aventura", "drama", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000057"), "Indiana Jones and the Raiders of the Lost Ark", "PG", 8.4, ["aventura", "accion", "historia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000058"), "Star Wars: A New Hope",        "PG",    8.6, ["ciencia_ficcion", "aventura", "accion", "epica"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000059"), "Star Wars: The Empire Strikes Back", "PG", 8.7, ["ciencia_ficcion", "aventura", "accion", "epica"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000060"), "The Lion King",                "G",     8.5, ["animacion", "aventura", "drama", "familiar", "musical"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000061"), "Finding Nemo",                 "G",     8.2, ["animacion", "aventura", "comedia", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000062"), "Up",                           "PG",    8.3, ["animacion", "aventura", "drama", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000063"), "WALL-E",                       "G",     8.4, ["animacion", "ciencia_ficcion", "romance", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000064"), "Ratatouille",                  "G",     8.1, ["animacion", "comedia", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000065"), "Shrek",                        "PG",    7.9, ["animacion", "comedia", "aventura", "fantasia", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000066"), "Harry Potter and the Sorcerer's Stone", "PG", 7.6, ["fantasia", "aventura", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000067"), "Harry Potter and the Deathly Hallows Part 2", "PG-13", 8.1, ["fantasia", "aventura", "accion", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000068"), "The Hunger Games",             "PG-13", 7.2, ["ciencia_ficcion", "aventura", "distopia", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000069"), "Black Panther",                "PG-13", 7.3, ["superheroes", "accion", "aventura", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000070"), "Iron Man",                     "PG-13", 7.9, ["superheroes", "accion", "ciencia_ficcion"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000071"), "Guardians of the Galaxy",      "PG-13", 8.0, ["superheroes", "accion", "comedia", "ciencia_ficcion"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000072"), "Thor: Ragnarok",               "PG-13", 7.9, ["superheroes", "accion", "comedia", "aventura"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000073"), "Logan",                        "R",     8.1, ["superheroes", "accion", "drama", "western"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000074"), "Joker",                        "R",     8.5, ["drama", "crimen", "thriller", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000075"), "Casino",                       "R",     8.2, ["crimen", "drama", "historia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000076"), "Heat",                         "R",     8.3, ["crimen", "drama", "thriller", "accion"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000077"), "Leon: The Professional",       "R",     8.5, ["accion", "thriller", "crimen", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000078"), "Se7en",                        "R",     8.6, ["thriller", "crimen", "misterio", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000079"), "Memento",                      "R",     8.4, ["thriller", "misterio", "psicologico", "crimen"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000080"), "Gone Girl",                    "R",     8.1, ["thriller", "misterio", "drama", "crimen"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000081"), "Black Swan",                   "R",     8.0, ["thriller", "drama", "psicologico", "horror"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000082"), "Requiem for a Dream",          "R",     8.3, ["drama", "psicologico", "social"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000083"), "A Clockwork Orange",           "R",     8.3, ["ciencia_ficcion", "drama", "thriller", "distopia", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000084"), "Spirited Away",                "PG",    8.6, ["animacion", "fantasia", "aventura", "japon"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000085"), "Princess Mononoke",            "PG-13", 8.4, ["animacion", "fantasia", "aventura", "drama", "japon"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000086"), "My Neighbor Totoro",           "G",     8.2, ["animacion", "fantasia", "familiar", "japon"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000087"), "Akira",                        "R",     8.0, ["animacion", "ciencia_ficcion", "distopia", "accion", "japon"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000088"), "Your Name",                    "PG",    8.4, ["animacion", "romance", "drama", "fantasia", "japon"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000089"), "Demon Slayer: Mugen Train",    "PG-13", 8.2, ["animacion", "accion", "fantasia", "drama", "japon"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000090"), "Seven Samurai",                "PG-13", 8.6, ["accion", "drama", "historia", "samurai", "japon"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000091"), "Oldboy",                       "R",     8.4, ["thriller", "crimen", "drama", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000092"), "Train to Busan",               "R",     7.6, ["horror", "accion", "drama", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000093"), "Pan's Labyrinth",              "R",     8.2, ["fantasia", "drama", "historia", "horror"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000094"), "City of God",                  "R",     8.6, ["crimen", "drama", "historia", "social"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000095"), "Amélie",                       "R",     8.3, ["romance", "comedia", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000096"), "Life is Beautiful",            "PG-13", 8.6, ["drama", "comedia", "romance", "historia", "belico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000097"), "The Grand Budapest Hotel",     "R",     8.1, ["comedia", "misterio", "aventura", "crimen"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000098"), "Moonlight",                    "R",     7.4, ["drama", "romance", "social"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000099"), "Portrait of a Lady on Fire",   "R",     8.1, ["drama", "romance", "historia", "periodo"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000100"), "Dune: Part Two",               "PG-13", 8.5, ["ciencia_ficcion", "aventura", "epica", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000101"), "Poor Things",                  "R",     8.0, ["fantasia", "drama", "comedia", "periodo"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000102"), "The Zone of Interest",         "PG-13", 7.4, ["drama", "historia", "belico", "social"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000103"), "Past Lives",                   "PG-13", 7.8, ["drama", "romance"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000104"), "All Quiet on the Western Front","R",    7.8, ["belico", "drama", "historia"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000105"), "RRR",                          "R",     7.8, ["accion", "aventura", "historia", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000106"), "Tár",                          "R",     7.4, ["drama", "musica", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000107"), "The Whale",                    "R",     7.3, ["drama", "psicologico", "social"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000108"), "Babylon",                      "R",     7.1, ["drama", "historia", "comedia", "musical"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000109"), "Glass Onion: A Knives Out Mystery", "PG-13", 7.1, ["misterio", "comedia", "crimen", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000110"), "The Banshees of Inisherin",    "R",     7.7, ["drama", "comedia", "social"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000111"), "Guillermo del Toro's Pinocchio","PG",   7.7, ["animacion", "fantasia", "drama", "musical", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000112"), "Puss in Boots: The Last Wish", "PG",   7.9, ["animacion", "aventura", "comedia", "fantasia", "familiar"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000113"), "Prey",                         "R",     7.7, ["accion", "thriller", "aventura", "ciencia_ficcion"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000114"), "The Lighthouse",               "R",     7.5, ["horror", "drama", "psicologico", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000115"), "Annihilation",                 "R",     6.8, ["ciencia_ficcion", "horror", "misterio", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000116"), "Us",                           "R",     6.8, ["horror", "thriller", "misterio", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000117"), "Mandy",                        "R",     6.5, ["horror", "accion", "fantasia", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000118"), "X",                            "R",     6.6, ["horror", "thriller", "periodo"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000119"), "Smile",                        "R",     6.6, ["horror", "thriller", "sobrenatural", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000120"), "Talk to Me",                   "R",     7.1, ["horror", "thriller", "sobrenatural", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000121"), "M3GAN",                        "PG-13", 6.3, ["horror", "ciencia_ficcion", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000122"), "Barbarian",                    "R",     7.0, ["horror", "thriller", "misterio"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000123"), "Men",                          "R",     5.8, ["horror", "drama", "folclore", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000124"), "Titane",                       "R",     6.0, ["horror", "thriller", "drama", "psicologico"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000125"), "The Whale",                    "R",     7.3, ["drama", "psicologico", "social"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000126"), "Everything Everywhere All at Once 2 (fan pick)", "R", 7.0, ["ciencia_ficcion", "comedia", "drama"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000127"), "The Wailing",                  "R",     7.5, ["horror", "misterio", "thriller", "sobrenatural"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000128"), "Suspiria (2018)",              "R",     6.8, ["horror", "thriller", "drama", "periodo"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000129"), "The VVitch: A New-England Folktale", "R", 6.9, ["horror", "periodo", "sobrenatural", "folclore"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000130"), "Terrifier 2",                  "R",     6.6, ["horror", "thriller"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000131"), "Dungeons & Dragons: Honor Among Thieves", "PG-13", 7.3, ["fantasia", "aventura", "comedia", "accion"]),
    Movie(UUID("b3f1c2b0-0001-4a5b-9abc-100000000132"), "The Super Mario Bros. Movie",  "PG",    5.8, ["animacion", "aventura", "comedia", "familiar", "videojuegos"]),
]

# ---------------------------------------------------------------------------
# Catálogo de juegos (130 títulos)
# ---------------------------------------------------------------------------

GAMES = [
    # ── Originales (001-030) ────────────────────────────────────────────────
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000001"), "Resident Evil Village",         "M",     8.4, ["horror", "survival", "accion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000002"), "Phasmophobia",                  "M",     8.1, ["horror", "multijugador", "investigacion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000003"), "Elden Ring",                    "M",     9.5, ["rpg", "accion", "aventura", "mundo_abierto"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000004"), "Minecraft",                     "G",     9.0, ["sandbox", "aventura", "multijugador", "construccion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000005"), "Dead Space",                    "M",     8.0, ["horror", "survival", "ciencia_ficcion", "accion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000006"), "FIFA 25",                       "G",     6.5, ["deportes", "multijugador", "simulacion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000007"), "The Last of Us Part I",         "M",     9.0, ["accion", "aventura", "survival", "drama", "postapocaliptico"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000008"), "God of War Ragnarök",           "M",     9.4, ["accion", "aventura", "mitologia", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000009"), "Red Dead Redemption 2",         "M",     9.7, ["mundo_abierto", "accion", "drama", "western"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000010"), "The Witcher 3",                 "M",     9.3, ["rpg", "mundo_abierto", "fantasia", "aventura"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000011"), "Hollow Knight",                 "G",     9.0, ["plataformas", "accion", "aventura", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000012"), "Celeste",                       "G",     9.1, ["plataformas", "indie", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000013"), "Hades",                         "M",     9.5, ["roguelike", "accion", "mitologia", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000014"), "Among Us",                      "G",     7.1, ["multijugador", "estrategia", "social", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000015"), "Fortnite",                      "PG-13", 6.8, ["battle_royale", "multijugador", "accion", "construccion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000016"), "Cyberpunk 2077",                "M",     7.8, ["rpg", "mundo_abierto", "ciencia_ficcion", "distopia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000017"), "Stardew Valley",                "G",     9.3, ["simulacion", "indie", "rpg", "construccion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000018"), "Dark Souls III",                "M",     8.9, ["rpg", "accion", "soulslike", "fantasia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000019"), "Sekiro: Shadows Die Twice",     "M",     8.9, ["accion", "soulslike", "samurai", "aventura"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000020"), "Cuphead",                       "G",     8.0, ["accion", "plataformas", "indie", "dificil"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000021"), "It Takes Two",                  "PG-13", 9.4, ["cooperativo", "aventura", "plataformas", "multijugador"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000022"), "Disco Elysium",                 "M",     9.6, ["rpg", "misterio", "drama", "social", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000023"), "Outer Wilds",                   "G",     9.5, ["aventura", "misterio", "ciencia_ficcion", "espacio", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000024"), "Baldur's Gate 3",               "M",     9.6, ["rpg", "fantasia", "multijugador", "estrategia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000025"), "Alan Wake 2",                   "M",     8.4, ["horror", "thriller", "accion", "misterio", "sobrenatural"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000026"), "Persona 5 Royal",               "M",     9.3, ["rpg", "drama", "social", "japon"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000027"), "Rocket League",                 "G",     8.3, ["deportes", "multijugador", "competitivo"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000028"), "Sea of Stars",                  "G",     8.5, ["rpg", "indie", "fantasia", "aventura"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000029"), "Inscryption",                   "M",     8.7, ["roguelike", "misterio", "estrategia", "indie", "horror"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000030"), "Animal Crossing: New Horizons", "G",     8.7, ["simulacion", "sandbox", "construccion", "multijugador"]),
    # ── Nuevos 100 (031-130) ────────────────────────────────────────────────
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000031"), "The Legend of Zelda: Breath of the Wild", "G", 9.7, ["aventura", "mundo_abierto", "accion", "fantasia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000032"), "The Legend of Zelda: Tears of the Kingdom", "G", 9.6, ["aventura", "mundo_abierto", "accion", "fantasia", "construccion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000033"), "Super Mario Odyssey",           "G",     9.3, ["plataformas", "aventura", "familiar"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000034"), "Super Mario Bros. Wonder",      "G",     9.4, ["plataformas", "aventura", "familiar", "multijugador"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000035"), "Mario Kart 8 Deluxe",           "G",     9.2, ["deportes", "multijugador", "competitivo", "familiar"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000036"), "Metroid Dread",                 "G",     8.9, ["accion", "aventura", "ciencia_ficcion", "plataformas"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000037"), "Pokémon Legends: Arceus",       "G",     8.0, ["rpg", "aventura", "familiar", "mundo_abierto"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000038"), "Fire Emblem: Three Houses",     "PG-13", 8.9, ["rpg", "estrategia", "drama", "fantasia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000039"), "Xenoblade Chronicles 3",        "PG-13", 9.1, ["rpg", "aventura", "fantasia", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000040"), "Kirby and the Forgotten Land",  "G",     8.6, ["plataformas", "aventura", "familiar"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000041"), "Ghost of Tsushima",             "M",     9.0, ["accion", "aventura", "mundo_abierto", "samurai"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000042"), "Spider-Man 2 (PS5)",            "M",     9.2, ["accion", "aventura", "superheroes", "mundo_abierto"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000043"), "Returnal",                      "M",     8.5, ["roguelike", "accion", "ciencia_ficcion", "horror", "dificil"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000044"), "Demon's Souls (Remake)",        "M",     8.8, ["rpg", "accion", "soulslike", "fantasia", "dificil"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000045"), "Ratchet & Clank: Rift Apart",   "G",     8.9, ["accion", "aventura", "ciencia_ficcion", "plataformas"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000046"), "Horizon Forbidden West",        "M",     8.7, ["accion", "aventura", "mundo_abierto", "ciencia_ficcion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000047"), "Gran Turismo 7",                "G",     8.6, ["deportes", "simulacion", "competitivo"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000048"), "Uncharted 4",                   "PG-13", 9.5, ["aventura", "accion", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000049"), "Death Stranding",               "M",     8.3, ["aventura", "ciencia_ficcion", "drama", "mundo_abierto"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000050"), "Detroit: Become Human",         "M",     8.6, ["aventura", "ciencia_ficcion", "drama", "distopia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000051"), "Control",                       "M",     8.3, ["accion", "horror", "sobrenatural", "misterio", "ciencia_ficcion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000052"), "Prey (2017)",                   "M",     8.4, ["accion", "horror", "ciencia_ficcion", "survival"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000053"), "Dishonored 2",                  "M",     8.7, ["accion", "aventura", "sigilo", "fantasia", "distopia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000054"), "Bioshock Infinite",             "M",     8.9, ["accion", "ciencia_ficcion", "distopia", "thriller"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000055"), "Bioshock (2007)",               "M",     9.3, ["accion", "horror", "ciencia_ficcion", "distopia", "thriller"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000056"), "Half-Life: Alyx",               "M",     9.3, ["accion", "ciencia_ficcion", "horror", "realidad_virtual"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000057"), "Portal 2",                      "G",     9.7, ["puzzles", "ciencia_ficcion", "comedia", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000058"), "The Talos Principle 2",         "G",     9.0, ["puzzles", "ciencia_ficcion", "filosofia", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000059"), "Return of the Obra Dinn",       "G",     8.9, ["puzzles", "misterio", "indie", "historia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000060"), "Obra Dinn",                     "G",     8.9, ["puzzles", "misterio", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000061"), "What Remains of Edith Finch",   "G",     8.8, ["aventura", "drama", "indie", "misterio"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000062"), "Firewatch",                     "PG-13", 8.0, ["aventura", "drama", "misterio", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000063"), "Oxenfree",                      "G",     8.1, ["aventura", "horror", "sobrenatural", "misterio", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000064"), "Night in the Woods",            "G",     8.2, ["aventura", "drama", "social", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000065"), "Undertale",                     "G",     9.2, ["rpg", "indie", "comedia", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000066"), "Deltarune",                     "G",     9.0, ["rpg", "indie", "comedia", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000067"), "Omori",                         "PG-13", 9.2, ["rpg", "horror", "drama", "psicologico", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000068"), "Ori and the Will of the Wisps", "G",     9.3, ["plataformas", "aventura", "indie", "fantasia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000069"), "Dead Cells",                    "M",     9.1, ["roguelike", "accion", "plataformas", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000070"), "Slay the Spire",                "PG-13", 9.4, ["roguelike", "estrategia", "indie", "cartas"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000071"), "Monster Hunter: World",         "PG-13", 8.9, ["accion", "rpg", "aventura", "multijugador", "cooperativo"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000072"), "Monster Hunter Rise",           "PG-13", 8.7, ["accion", "rpg", "aventura", "multijugador", "cooperativo"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000073"), "Final Fantasy XVI",             "M",     8.7, ["rpg", "accion", "fantasia", "drama", "epica"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000074"), "Final Fantasy VII Remake",      "PG-13", 8.8, ["rpg", "accion", "ciencia_ficcion", "fantasia", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000075"), "Dragon Age: Origins",           "M",     9.1, ["rpg", "fantasia", "estrategia", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000076"), "Mass Effect 2",                 "M",     9.5, ["rpg", "ciencia_ficcion", "accion", "aventura", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000077"), "Mass Effect: Legendary Edition","M",     9.3, ["rpg", "ciencia_ficcion", "accion", "aventura", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000078"), "Divinity: Original Sin 2",      "M",     9.5, ["rpg", "fantasia", "estrategia", "multijugador"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000079"), "Pillars of Eternity II",        "M",     8.8, ["rpg", "fantasia", "aventura", "estrategia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000080"), "Pathfinder: Wrath of the Righteous", "M", 8.5, ["rpg", "fantasia", "estrategia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000081"), "Valheim",                       "PG-13", 8.7, ["survival", "sandbox", "construccion", "multijugador", "vikingos"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000082"), "Subnautica",                    "G",     9.0, ["survival", "aventura", "ciencia_ficcion", "mundo_abierto"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000083"), "The Forest",                    "M",     8.2, ["survival", "horror", "mundo_abierto", "construccion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000084"), "Rust",                          "M",     7.8, ["survival", "multijugador", "sandbox", "competitivo"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000085"), "DayZ",                          "M",     6.9, ["survival", "horror", "multijugador", "postapocaliptico"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000086"), "Terraria",                      "G",     9.5, ["sandbox", "aventura", "accion", "construccion", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000087"), "No Man's Sky",                  "PG-13", 8.2, ["survival", "aventura", "ciencia_ficcion", "espacio", "sandbox"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000088"), "Starfield",                     "M",     7.4, ["rpg", "ciencia_ficcion", "espacio", "mundo_abierto", "aventura"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000089"), "Overwatch 2",                   "PG-13", 7.5, ["accion", "multijugador", "competitivo", "battle_royale"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000090"), "Apex Legends",                  "M",     8.4, ["battle_royale", "accion", "multijugador", "competitivo"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000091"), "Valorant",                      "M",     8.1, ["accion", "multijugador", "competitivo", "estrategia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000092"), "Counter-Strike 2",              "M",     8.2, ["accion", "multijugador", "competitivo", "estrategia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000093"), "League of Legends",             "PG-13", 7.8, ["estrategia", "multijugador", "competitivo", "fantasia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000094"), "Dota 2",                        "M",     8.4, ["estrategia", "multijugador", "competitivo", "fantasia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000095"), "Hearthstone",                   "G",     7.5, ["estrategia", "multijugador", "cartas", "fantasia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000096"), "Gwent: The Witcher Card Game",  "PG-13", 8.0, ["estrategia", "cartas", "fantasia", "multijugador"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000097"), "NBA 2K25",                      "G",     7.0, ["deportes", "multijugador", "simulacion", "competitivo"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000098"), "WWE 2K24",                      "PG-13", 7.2, ["deportes", "multijugador", "accion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000099"), "F1 25",                         "G",     8.5, ["deportes", "simulacion", "competitivo"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000100"), "Crash Bandicoot 4",             "PG-13", 8.5, ["plataformas", "aventura", "familiar", "dificil"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000101"), "Spyro Reignited Trilogy",       "G",     8.1, ["plataformas", "aventura", "familiar"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000102"), "Rayman Legends",                "G",     9.1, ["plataformas", "aventura", "multijugador", "familiar"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000103"), "Shovel Knight",                 "G",     9.0, ["plataformas", "accion", "indie", "aventura"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000104"), "Hollow Knight: Silksong",       "G",     9.2, ["plataformas", "accion", "aventura", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000105"), "Blasphemous 2",                 "M",     8.4, ["plataformas", "accion", "soulslike", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000106"), "Little Nightmares II",          "M",     8.3, ["horror", "aventura", "plataformas", "psicologico", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000107"), "Limbo",                         "PG-13", 8.5, ["plataformas", "horror", "misterio", "indie", "puzzles"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000108"), "Inside",                        "PG-13", 8.9, ["plataformas", "horror", "distopia", "indie", "puzzles"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000109"), "Layers of Fear (2023)",         "M",     7.6, ["horror", "psicologico", "aventura", "sobrenatural"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000110"), "Observer: System Redux",        "M",     8.0, ["horror", "ciencia_ficcion", "thriller", "distopia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000111"), "Amnesia: The Bunker",           "M",     8.1, ["horror", "survival", "thriller", "investigacion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000112"), "Outlast Trials",                "M",     7.7, ["horror", "survival", "thriller", "multijugador", "cooperativo"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000113"), "Silent Hill 2 (Remake)",        "M",     9.0, ["horror", "psicologico", "aventura", "sobrenatural", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000114"), "Signalis",                      "M",     8.5, ["horror", "ciencia_ficcion", "survival", "indie", "psicologico"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000115"), "Resident Evil 4 (Remake)",      "M",     9.3, ["horror", "accion", "aventura", "survival"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000116"), "The Quarry",                    "M",     8.0, ["horror", "aventura", "drama", "thriller"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000117"), "Until Dawn",                    "M",     8.2, ["horror", "aventura", "thriller", "drama"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000118"), "Dave the Diver",                "G",     9.0, ["aventura", "simulacion", "indie", "comedia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000119"), "Vampire Survivors",             "G",     9.2, ["roguelike", "accion", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000120"), "Luck be a Landlord",            "G",     8.3, ["roguelike", "estrategia", "indie", "cartas"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000121"), "Balatro",                       "PG-13", 9.4, ["roguelike", "estrategia", "indie", "cartas"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000122"), "Hades II",                      "M",     9.4, ["roguelike", "accion", "mitologia", "indie"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000123"), "Kingdom Come: Deliverance II",  "M",     9.0, ["rpg", "mundo_abierto", "historia", "drama", "medieval"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000124"), "Warhammer 40K: Space Marine 2", "M",     8.8, ["accion", "ciencia_ficcion", "multijugador", "cooperativo", "epica"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000125"), "Black Myth: Wukong",            "M",     9.0, ["accion", "soulslike", "aventura", "mitologia", "fantasia"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000126"), "Astro Bot",                     "G",     9.4, ["plataformas", "aventura", "familiar"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000127"), "Metaphor: ReFantazio",          "M",     9.4, ["rpg", "fantasia", "drama", "social", "japon"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000128"), "Indiana Jones and the Great Circle", "M", 8.8, ["aventura", "accion", "historia", "sigilo"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000129"), "Stalker 2: Heart of Chornobyl", "M",     8.3, ["survival", "horror", "mundo_abierto", "ciencia_ficcion"]),
    Game(UUID("9a7e5d40-0002-4f21-8b3a-200000000130"), "Star Wars Outlaws",             "M",     7.5, ["aventura", "accion", "ciencia_ficcion", "mundo_abierto"]),
]

# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

USERS = [
    User(
        id=UUID("aaaa0000-0000-0000-0000-000000000001"),
        birth_date=date(1995, 6, 15),   # ~31 años
    ),
    User(
        id=UUID("aaaa0000-0000-0000-0000-000000000002"),
        birth_date=date(2010, 3, 22),   # ~16 años (menor)
    ),
    User(
        id=UUID("aaaa0000-0000-0000-0000-000000000003"),
        birth_date=date(2000, 11, 5),   # ~25 años
    ),
]

# ---------------------------------------------------------------------------
# Feedback de ejemplo
# ---------------------------------------------------------------------------

U1 = USERS[0].id
U2 = USERS[1].id
U3 = USERS[2].id

def _dt(y, m, d): return datetime(y, m, d, tzinfo=timezone.utc)

FEEDBACKS: list[Feedback] = [
    # --- Usuario 1 (fan del horror) ---
    Feedback(U1, GAMES[0].id,  "game",  "like",    _dt(2026, 7, 1)),   # RE Village
    Feedback(U1, GAMES[1].id,  "game",  "like",    _dt(2026, 7, 5)),   # Phasmophobia
    Feedback(U1, GAMES[4].id,  "game",  "like",    _dt(2026, 7, 10)),  # Dead Space
    Feedback(U1, MOVIES[3].id, "movie", "dislike", _dt(2026, 7, 12)),  # Endgame (no le gustó)

    # --- Usuario 2 (menor, gusta de familiar) ---
    Feedback(U2, GAMES[3].id,  "game",  "like", _dt(2026, 7, 1)),   # Minecraft
    Feedback(U2, MOVIES[5].id, "movie", "like", _dt(2026, 7, 3)),   # Toy Story

    # --- Usuario 3 (acción / RPG) ---
    Feedback(U3, GAMES[2].id,  "game",  "like",   _dt(2026, 7, 1)),  # Elden Ring
    Feedback(U3, MOVIES[3].id, "movie", "like",   _dt(2026, 7, 2)),  # Endgame
    Feedback(U3, GAMES[0].id,  "game",  "jugado", _dt(2026, 7, 8)),  # RE Village (ya jugado)
    Feedback(U3, MOVIES[2].id, "movie", "like",   _dt(2026, 7, 9)),  # Interstellar
]
