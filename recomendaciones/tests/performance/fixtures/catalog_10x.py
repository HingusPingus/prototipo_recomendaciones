"""Generador reproducible de catálogo y usuarios a escala para SC-001 (T050).

1× = 10 000 ítems por módulo (línea base de SC-001, RD-111); 10× = 100 000. Los usuarios escalan en la misma
proporción (`users_per_item`), y una fracción del catálogo queda retirada dentro de la ventana de `retired:`
—es lo único del catálogo que el request path lee (la diferencia contra `retired:{module}`, §4.4)—.

Todo sale de un `random.Random(seed)` y de UUID derivados del índice: dos corridas con la misma semilla
generan exactamente los mismos datos. La escritura usa `COPY` y es incremental: `grow(to=10×)` agrega lo
que falta sobre una base ya generada a 1×.
"""

from __future__ import annotations

import io
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

import sqlalchemy as sa

BASE_ITEMS_PER_MODULE = 10_000
MODULES = ("peliculas", "juegos")
TAGS_PER_MODULE = 60
_NS = uuid.UUID("7d1c2a3e-0000-4000-8000-00000000c0de")


def item_id(module: str, n: int) -> uuid.UUID:
    return uuid.uuid5(_NS, f"item:{module}:{n}")


def user_id(n: int) -> uuid.UUID:
    return uuid.uuid5(_NS, f"user:{n}")


def tag_name(module: str, n: int) -> str:
    return f"{module}-tag-{n:03d}"


@dataclass
class Scale:
    items_per_module: int
    users: int


@dataclass
class Population:
    config_version: str
    seed: int = 42
    retired_ratio: float = 0.01
    users_per_item: float = 0.2
    generated_items: int = 0  # por módulo
    generated_users: int = 0
    rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)

    def scale(self, factor: int) -> Scale:
        items = BASE_ITEMS_PER_MODULE * factor
        return Scale(items, int(items * self.users_per_item))


def _copy(conn, table: str, columns: tuple[str, ...], rows) -> None:
    buffer = io.StringIO()
    for row in rows:
        buffer.write("\t".join("\\N" if v is None else str(v) for v in row) + "\n")
    buffer.seek(0)
    with conn.cursor() as cur, cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy:
        copy.write(buffer.read())


def grow(engine: sa.Engine, population: Population, factor: int) -> Scale:
    """Lleva la base a `factor`× agregando solo lo que falta. Devuelve la escala alcanzada."""
    target = population.scale(factor)
    rng = population.rng
    raw = engine.raw_connection()
    try:
        conn = raw.driver_connection
        if population.generated_items == 0:
            _copy(conn, "tags", ("name", "synced_at"),
                  ((tag_name(m, t), "2026-09-01T00:00:00Z") for m in MODULES for t in range(TAGS_PER_MODULE)))
        start = population.generated_items
        for module in MODULES:
            items, links = [], []
            for n in range(start, target.items_per_module):
                retired = rng.random() < population.retired_ratio
                rating, ordinal = rng.choice((("ATP", 0), ("ATP", 0), ("+13", 1), ("+18", 2)))
                items.append((
                    item_id(module, n), module, "retired" if retired else "available",
                    "2026-09-27T00:00:00Z" if retired else None, ordinal, population.config_version, rating, "declared",
                    "2026-09-01T00:00:00Z",
                ))
                for t in rng.sample(range(TAGS_PER_MODULE), rng.randint(1, 3)):
                    links.append((item_id(module, n), tag_name(module, t)))
            _copy(conn, "items", ("id", "module", "status", "retired_at", "min_age_ordinal", "age_config_version",
                                  "age_rating", "age_rating_source", "synced_at"), items)
            _copy(conn, "item_tags", ("item_id", "tag_name"), links)
        users = [
            (user_id(n), date(1960, 1, 1) + timedelta(days=rng.randint(0, 20_000)), 2, population.config_version,
             "2026-09-01T00:00:00Z", rng.choice(("AR", "UY", "CL", "MX", "ES")), "2026-09-01T00:00:00Z")
            for n in range(population.generated_users, target.users)
        ]
        _copy(conn, "users", ("id", "birth_date", "max_age_ordinal", "age_config_version", "age_derived_at", "region", "synced_at"), users)
        raw.commit()
    finally:
        raw.close()
    # Los retirados de esta prueba se retiraron «hace un día»: dentro de la ventana de `retired:` (RD-39).
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE items SET retired_at = now() - interval '1 day' WHERE status = 'retired'"))
        conn.execute(sa.text("ANALYZE items; ANALYZE users; ANALYZE item_tags"))
    population.generated_items, population.generated_users = target.items_per_module, target.users
    return target


def declare_sample(engine: sa.Engine, population: Population, sample: list[uuid.UUID], exclusions_per_user: int = 50) -> None:
    """Declaración en ambos módulos y exclusiones para los usuarios medidos (el resto no se lee)."""
    rng = random.Random(population.seed + 1)
    raw = engine.raw_connection()
    try:
        conn = raw.driver_connection
        _copy(conn, "user_declared_tags", ("user_id", "module", "tag_name", "declared_at"),
              ((u, m, tag_name(m, t), "2026-09-01T00:00:00Z") for u in sample for m in MODULES for t in range(5)))
        rows = []
        for u in sample:
            for n in rng.sample(range(BASE_ITEMS_PER_MODULE), exclusions_per_user):
                rows.append((u, item_id(MODULES[n % 2], n), "consumo", "2026-09-01T00:00:00Z"))
        _copy(conn, "user_exclusions", ("user_id", "item_id", "origin", "resolved_at"), rows)
        raw.commit()
    finally:
        raw.close()
