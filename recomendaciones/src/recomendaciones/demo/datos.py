"""Datos de la demo: catálogo, personas y actividad inicial que sirve el `api-general` simulado.

Los identificadores son UUID deterministas (uuid5), así que se mantienen entre reinicios: el Transformer
ve siempre los mismos usuarios e ítems. La actividad inicial también es determinista dentro del mismo día.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

_NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://recome.demo/")

PELICULAS = "peliculas"
JUEGOS = "juegos"


@dataclass(frozen=True)
class Item:
    id: uuid.UUID
    titulo: str
    module: str
    tags: tuple[str, ...]
    age_rating: str


@dataclass(frozen=True)
class Usuario:
    alias: str
    id: uuid.UUID
    nombre: str
    birth_date: date
    region: str
    descripcion: str
    perfil: str | None = None  # perfil de gustos de los usuarios de fondo; None para las personas de la demo


@dataclass(frozen=True)
class Perfil:
    nombre: str
    tags: dict[str, tuple[str, ...]] = field(default_factory=dict)


# (título, tags, clasificación)
_PELICULAS: list[tuple[str, tuple[str, ...], str]] = [
    ("El conjuro", ("terror", "sobrenatural", "suspenso"), "+18"),
    ("El exorcista", ("terror", "sobrenatural", "drama"), "+18"),
    ("Hereditary", ("terror", "sobrenatural", "drama", "misterio"), "+18"),
    ("It", ("terror", "sobrenatural", "aventura"), "+13"),
    ("Un lugar en silencio", ("terror", "suspenso", "ciencia-ficcion"), "+13"),
    ("Scream", ("terror", "suspenso", "misterio"), "+18"),
    ("Coraline", ("animacion", "fantasia", "terror", "familiar"), "ATP"),
    ("Los otros", ("terror", "sobrenatural", "misterio", "drama"), "+13"),
    ("Alien", ("terror", "ciencia-ficcion", "suspenso"), "+18"),
    ("Interestelar", ("ciencia-ficcion", "drama", "aventura"), "ATP"),
    ("Matrix", ("ciencia-ficcion", "accion"), "+13"),
    ("Blade Runner 2049", ("ciencia-ficcion", "drama", "misterio"), "+13"),
    ("Volver al futuro", ("ciencia-ficcion", "aventura", "comedia", "familiar"), "ATP"),
    ("Mad Max: Furia en el camino", ("accion", "aventura", "ciencia-ficcion"), "+18"),
    ("Duro de matar", ("accion", "suspenso"), "+18"),
    ("John Wick", ("accion", "suspenso"), "+18"),
    ("Misión imposible", ("accion", "aventura", "suspenso"), "+13"),
    ("Indiana Jones: Los cazadores del arca perdida", ("aventura", "accion", "fantasia"), "ATP"),
    ("Jurassic Park", ("aventura", "ciencia-ficcion", "suspenso", "familiar"), "ATP"),
    ("El señor de los anillos", ("fantasia", "aventura", "accion"), "+13"),
    ("Harry Potter y la piedra filosofal", ("fantasia", "aventura", "familiar"), "ATP"),
    ("El laberinto del fauno", ("fantasia", "drama", "terror"), "+18"),
    ("Toy Story", ("animacion", "comedia", "familiar"), "ATP"),
    ("Buscando a Nemo", ("animacion", "aventura", "familiar"), "ATP"),
    ("Intensa-Mente", ("animacion", "comedia", "drama", "familiar"), "ATP"),
    ("Shrek", ("animacion", "comedia", "fantasia", "familiar"), "ATP"),
    ("El viaje de Chihiro", ("animacion", "fantasia", "aventura"), "ATP"),
    ("Supercool", ("comedia",), "+18"),
    ("¿Qué pasó ayer?", ("comedia", "aventura"), "+18"),
    ("Relatos salvajes", ("comedia", "drama", "suspenso"), "+18"),
    ("Esperando la carroza", ("comedia", "drama"), "ATP"),
    ("Titanic", ("romance", "drama"), "+13"),
    ("Diario de una pasión", ("romance", "drama"), "+13"),
    ("La La Land", ("romance", "comedia", "drama"), "ATP"),
    ("Orgullo y prejuicio", ("romance", "drama"), "ATP"),
    ("El secreto de sus ojos", ("misterio", "drama", "suspenso", "romance"), "+13"),
    ("Nueve reinas", ("suspenso", "misterio", "drama"), "+13"),
    ("Pecados capitales", ("suspenso", "misterio", "drama"), "+18"),
    ("Perdida", ("suspenso", "misterio", "drama"), "+18"),
    ("Sherlock Holmes", ("misterio", "accion", "aventura", "comedia"), "+13"),
]

_JUEGOS: list[tuple[str, tuple[str, ...], str]] = [
    ("Resident Evil 4", ("terror", "supervivencia", "accion"), "+18"),
    ("Silent Hill 2", ("terror", "supervivencia", "puzzle"), "+18"),
    ("Outlast", ("terror", "supervivencia"), "+18"),
    ("Dead Space", ("terror", "ciencia-ficcion", "accion", "supervivencia"), "+18"),
    ("Alan Wake 2", ("terror", "aventura", "puzzle"), "+18"),
    ("Five Nights at Freddy's", ("terror", "puzzle"), "+13"),
    ("Little Nightmares", ("terror", "puzzle", "aventura"), "+13"),
    ("The Last of Us", ("supervivencia", "accion", "aventura", "terror"), "+18"),
    ("Minecraft", ("supervivencia", "mundo-abierto", "familiar", "multijugador"), "ATP"),
    ("Subnautica", ("supervivencia", "ciencia-ficcion", "mundo-abierto"), "ATP"),
    ("The Legend of Zelda: Breath of the Wild", ("aventura", "mundo-abierto", "fantasia", "familiar"), "ATP"),
    ("Elden Ring", ("rpg", "fantasia", "mundo-abierto", "accion"), "+18"),
    ("The Witcher 3", ("rpg", "fantasia", "mundo-abierto"), "+18"),
    ("Skyrim", ("rpg", "fantasia", "mundo-abierto"), "+18"),
    ("Final Fantasy VII Remake", ("rpg", "fantasia", "accion"), "+13"),
    ("Pokémon Escarlata", ("rpg", "aventura", "familiar"), "ATP"),
    ("Mass Effect", ("rpg", "ciencia-ficcion", "accion"), "+18"),
    ("Cyberpunk 2077", ("rpg", "ciencia-ficcion", "mundo-abierto", "accion"), "+18"),
    ("Halo", ("accion", "ciencia-ficcion", "multijugador"), "+13"),
    ("Doom", ("accion", "ciencia-ficcion", "terror"), "+18"),
    ("Uncharted 4", ("accion", "aventura"), "+13"),
    ("God of War", ("accion", "aventura", "fantasia"), "+18"),
    ("Fortnite", ("accion", "multijugador", "supervivencia"), "+13"),
    ("Civilization VI", ("estrategia", "multijugador"), "ATP"),
    ("Age of Empires II", ("estrategia", "multijugador"), "ATP"),
    ("StarCraft II", ("estrategia", "ciencia-ficcion", "multijugador"), "+13"),
    ("XCOM 2", ("estrategia", "ciencia-ficcion"), "+13"),
    ("FIFA 24", ("deportes", "multijugador", "familiar"), "ATP"),
    ("NBA 2K24", ("deportes", "multijugador"), "ATP"),
    ("Rocket League", ("deportes", "carreras", "multijugador", "familiar"), "ATP"),
    ("Mario Kart 8", ("carreras", "multijugador", "familiar"), "ATP"),
    ("Gran Turismo 7", ("carreras",), "ATP"),
    ("Forza Horizon 5", ("carreras", "mundo-abierto"), "ATP"),
    ("Portal 2", ("puzzle", "ciencia-ficcion", "aventura"), "ATP"),
    ("Tetris Effect", ("puzzle", "familiar"), "ATP"),
    ("Super Mario Odyssey", ("aventura", "familiar", "fantasia"), "ATP"),
]

# Perfiles de gustos de los usuarios de fondo. Cada uno declara 5 tags por módulo (declared_tags_min de v1).
PERFILES: dict[str, Perfil] = {
    p.nombre: p
    for p in (
        Perfil("terror", {PELICULAS: ("terror", "sobrenatural", "suspenso", "misterio", "drama"),
                          JUEGOS: ("terror", "supervivencia", "puzzle", "accion", "aventura")}),
        Perfil("accion y ciencia ficción", {PELICULAS: ("accion", "ciencia-ficcion", "aventura", "suspenso", "fantasia"),
                                            JUEGOS: ("accion", "ciencia-ficcion", "rpg", "mundo-abierto", "multijugador")}),
        Perfil("familiar", {PELICULAS: ("animacion", "familiar", "comedia", "fantasia", "aventura"),
                            JUEGOS: ("familiar", "aventura", "carreras", "puzzle", "deportes")}),
        Perfil("drama y romance", {PELICULAS: ("romance", "drama", "comedia", "misterio", "suspenso"),
                                   JUEGOS: ("estrategia", "puzzle", "rpg", "aventura", "fantasia")}),
    )
}

_USUARIOS_POR_PERFIL = 6
_REGIONES_FONDO = ("AR", "AR", "AR", "UY", "CL", "AR")


def _item_id(module: str, titulo: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"item/{module}/{titulo}")


def _user_id(alias: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"usuario/{alias}")


def catalogo() -> list[Item]:
    items = [Item(_item_id(PELICULAS, t), t, PELICULAS, tags, r) for t, tags, r in _PELICULAS]
    items += [Item(_item_id(JUEGOS, t), t, JUEGOS, tags, r) for t, tags, r in _JUEGOS]
    _verificar(items)
    return items


def tags_por_modulo(items: list[Item]) -> dict[str, list[str]]:
    out: dict[str, set[str]] = {PELICULAS: set(), JUEGOS: set()}
    for item in items:
        out[item.module].update(item.tags)
    return {m: sorted(t) for m, t in out.items()}


def _verificar(items: list[Item]) -> None:
    """Cada tag de un perfil existe en el catálogo de su módulo: si no, la declaración se rechazaría (DEP-10)."""
    vocab = tags_por_modulo(items)
    for perfil in PERFILES.values():
        for module, tags in perfil.tags.items():
            faltan = set(tags) - set(vocab[module])
            if faltan:
                raise ValueError(f"perfil {perfil.nombre!r}: tags sin ítems en {module}: {sorted(faltan)}")


def usuarios() -> list[Usuario]:
    personas = [
        Usuario("ana", _user_id("ana"), "Ana", date(1994, 3, 10), "AR",
                "Adulta, recién registrada: todavía no declaró gustos."),
        Usuario("tomas", _user_id("tomas"), "Tomás", date(2011, 5, 20), "AR",
                "Menor de edad (15 años): nunca debe recibir ítems +18."),
    ]
    fondo = []
    for p, perfil in enumerate(PERFILES):
        for n in range(_USUARIOS_POR_PERFIL):
            alias = f"fondo-{p * _USUARIOS_POR_PERFIL + n + 1:02d}"
            fondo.append(
                Usuario(alias, _user_id(alias), f"Usuario de fondo {alias[-2:]}", date(1980 + p * 4 + n, 1 + n, 10),
                        _REGIONES_FONDO[n], f"Usuario de fondo con gustos de {perfil}.", perfil)
            )
    return personas + fondo


def actividad_inicial(items: list[Item], users: list[Usuario]) -> list[dict]:
    """Likes, dislikes y consumos de los usuarios de fondo: alimentan la popularidad y el término colaborativo."""
    hoy = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    rows: list[dict] = []
    for user in users:
        if user.perfil is None:
            continue
        rng = random.Random(user.alias)
        n = 0
        for module, gustos in PERFILES[user.perfil].tags.items():
            del_modulo = [i for i in items if i.module == module]
            afines = [i for i in del_modulo if len(set(i.tags) & set(gustos)) >= 2]
            ajenos = [i for i in del_modulo if not set(i.tags) & set(gustos)]
            likes = rng.sample(afines, min(6, len(afines)))
            restantes = [i for i in afines if i not in likes]
            elegidos = [(i, "like") for i in likes]
            elegidos += [(i, "dislike") for i in rng.sample(ajenos, min(2, len(ajenos)))]
            elegidos += [(i, "consumo") for i in rng.sample(restantes, min(2, len(restantes)))]
            for item, kind in elegidos:
                n += 1
                cuando = hoy - timedelta(days=rng.randint(1, 30), minutes=rng.randint(0, 1439))
                rows.append({
                    "origin_interaction_id": f"demo-{user.alias}-{n:03d}",
                    "user_id": str(user.id),
                    "item_id": str(item.id),
                    "module": item.module,
                    "signal_type": kind,
                    "occurred_at": cuando.isoformat(),
                })
    return rows
