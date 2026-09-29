"""T054 — la tabla contiene solo lo propio; el insumo del perfil incorpora además lo heredado."""

from __future__ import annotations

import sqlalchemy as sa

from recomendaciones.api.services.declaracion import DeclarationService
from recomendaciones.shared.domain import Module, ProfileScope
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.db.declarations import DeclarationRepository
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.worker.inputs import load_profile_inputs
from tests.integration import seed

SHARED = ["horror", "comedia", "drama", "thriller", "scifi"]


def _catalog(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        for tag in SHARED + ["musical", "romance", "western", "belico", "animacion"]:
            seed.item(s, "peliculas", [tag])
        for tag in SHARED + ["rpg", "survival", "roguelike", "plataformas", "estrategia"]:
            seed.item(s, "juegos", [tag])
        s.execute(sa.text("INSERT INTO tag_modules SELECT DISTINCT it.tag_name, i.module, now() FROM item_tags it JOIN items i ON i.id = it.item_id"))


def _service(db_factory, redis_client) -> DeclarationService:  # noqa: ANN001
    cache = CacheClient(redis_client)
    return DeclarationService(
        db_factory,
        DeclarationRepository(),
        FiltersCache(cache, DbFiltersSource(db_factory), 3_600),
        RecomputeStream(cache, maxlen=1_000, ttl_suppress=300),
        declared_tags_min=5,
    )


def test_table_holds_only_own_and_profile_input_adds_inherited(db_factory, redis_client) -> None:  # noqa: ANN001
    _catalog(db_factory)
    with db_factory.begin() as s:
        user = seed.user(s)
    service = _service(db_factory, redis_client)
    service.declare(user, Module.PELICULAS, SHARED)
    outcome = service.declare(user, Module.JUEGOS, ["rpg", "survival", "roguelike", "plataformas", "estrategia"])
    assert set(outcome.inherited) == set(SHARED)
    with db_factory() as s:
        rows = s.execute(sa.text("SELECT tag_name FROM user_declared_tags WHERE user_id = :u AND module = 'juegos'"), {"u": user}).scalars().all()
        assert sorted(rows) == ["estrategia", "plataformas", "roguelike", "rpg", "survival"]  # los 5 propios, nada más
        inputs = load_profile_inputs(s, user, ProfileScope.JUEGOS)
    assert inputs.declared_tags == {"rpg", "survival", "roguelike", "plataformas", "estrategia"}
    assert inputs.inherited_tags == set(SHARED)


def test_new_shared_tag_in_other_module_is_inherited_without_extra_write(db_factory, redis_client) -> None:  # noqa: ANN001
    _catalog(db_factory)
    with db_factory.begin() as s:
        user = seed.user(s)
        seed.declare(s, user, "juegos", ["rpg", "survival", "roguelike", "plataformas", "estrategia"])
        seed.declare(s, user, "peliculas", ["musical", "romance", "western", "belico", "animacion"])
    with db_factory() as s:
        assert load_profile_inputs(s, user, ProfileScope.JUEGOS).inherited_tags == frozenset()
    with db_factory.begin() as s:  # «musical» pasa a ser compartido al aparecer un juego con ese tag
        seed.item(s, "juegos", ["musical"])
        s.execute(sa.text("INSERT INTO tag_modules VALUES ('musical', 'juegos', now())"))
    with db_factory() as s:
        assert load_profile_inputs(s, user, ProfileScope.JUEGOS).inherited_tags == {"musical"}


def test_feedback_never_alters_declaration_membership(db_factory, redis_client) -> None:  # noqa: ANN001
    """FR-086: un usuario que dislikea ítems de todos sus tags declarados sigue declarado (FR-083)."""
    _catalog(db_factory)
    with db_factory.begin() as s:
        user = seed.user(s)
        seed.declare(s, user, "peliculas", SHARED)
        items = s.execute(sa.text("SELECT id FROM items WHERE module = 'peliculas'")).scalars().all()
        for n, item in enumerate(items):
            seed.signal(s, user, item, "dislike", minutes=n)
    with db_factory() as s:
        declared = s.execute(sa.text("SELECT count(*) FROM user_declared_tags WHERE user_id = :u"), {"u": user}).scalar_one()
        inputs = load_profile_inputs(s, user, ProfileScope.PELICULAS)
    assert declared == 5 and inputs.declared_tags == set(SHARED)
    assert len(inputs.signals) == len(items)


def test_general_scope_aggregates_both_modules_declarations(db_factory) -> None:  # noqa: ANN001
    _catalog(db_factory)
    with db_factory.begin() as s:
        user = seed.user(s)
        seed.declare(s, user, "peliculas", ["musical", "romance", "western", "belico", "animacion"])
        seed.declare(s, user, "juegos", ["rpg", "survival", "roguelike", "plataformas", "estrategia"])
    with db_factory() as s:
        general = load_profile_inputs(s, user, ProfileScope.GENERAL)
    assert len(general.declared_tags) == 10 and general.inherited_tags == frozenset()
