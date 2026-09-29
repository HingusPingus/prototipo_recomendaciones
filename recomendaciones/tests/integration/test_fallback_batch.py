"""T038 — batch de top-N de respaldo (FR-033a, FR-033a2, FR-033b, FR-033c, FR-033f, DI-12, SC-024, SC-025)."""

from __future__ import annotations

import math
import uuid
from collections import Counter

import sqlalchemy as sa

from recomendaciones.batch.fallback import FallbackJob
from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.repository import RecommendationRepository
from tests.integration import seed

CFG = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")


def _repo(redis_client) -> RecommendationRepository:  # noqa: ANN001
    return RecommendationRepository(CacheClient(redis_client), ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)


def _popularity(s, item: uuid.UUID, score: float, cfg: str | None = None) -> None:  # noqa: ANN001
    s.execute(
        sa.text("INSERT INTO item_popularity VALUES (:i, :c, 0, 0, :p, now()) ON CONFLICT (item_id, config_version) DO UPDATE SET popularity_score = :p"),
        {"i": item, "c": cfg or CFG.config_version, "p": score},
    )


def _job(db_factory, redis_client) -> FallbackJob:  # noqa: ANN001
    return FallbackJob(db_factory, _repo(redis_client), CFG, Metrics())


def _clusters(db_factory, ids: list[uuid.UUID]) -> list[str]:  # noqa: ANN001
    with db_factory() as s:
        tag = dict(s.execute(sa.text("SELECT item_id, min(tag_name) FROM item_tags GROUP BY item_id")).all())
    return [tag[i] for i in ids]


def test_diversity_beats_the_undiversified_ranking(db_factory, redis_client) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        horror = [seed.item(s, "peliculas", ["horror"]) for _ in range(30)]
        others = [seed.item(s, "peliculas", [f"genero{i % 6}"]) for i in range(30)]
        for n, item in enumerate(horror):
            _popularity(s, item, 0.9 - n / 1000)
        for n, item in enumerate(others):
            _popularity(s, item, 0.5 - n / 1000)
        seed.vectorize_all(s)
    _job(db_factory, redis_client).run()
    entry = _repo(redis_client).read_fallback(CFG.config_version, Module.PELICULAS)
    top20 = [i.item_id for i in entry.items[:20]]
    counts = Counter(_clusters(db_factory, top20))
    assert counts["horror"] <= math.ceil(CFG.diversity_max_cluster_share * 20)  # SC-025: mismo tope que SC-011
    undiversified = horror[:20]
    assert max(counts.values()) < Counter(_clusters(db_factory, undiversified))["horror"]


def test_without_likes_the_fallback_exists_ordered_by_tiebreak_and_is_stable(db_factory, redis_client) -> None:  # noqa: ANN001
    """FR-033a2, RD-106: sin evidencia, puntaje 0 y orden por el desempate determinista."""
    with db_factory.begin() as s:
        items = [seed.item(s, "juegos", [f"t{i}"]) for i in range(8)]
        for item in items:
            _popularity(s, item, 0.0)
        seed.vectorize_all(s)
    job = _job(db_factory, redis_client)
    job.run()
    first = [i.item_id for i in _repo(redis_client).read_fallback(CFG.config_version, Module.JUEGOS).items]
    job.run()
    second = [i.item_id for i in _repo(redis_client).read_fallback(CFG.config_version, Module.JUEGOS).items]
    assert len(first) == 8 and first == second


def test_module_without_live_items_has_empty_fallback(db_factory, redis_client) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        retired = seed.item(s, "juegos", ["rpg"], status="retired")
        _popularity(s, retired, 0.9)
        live = seed.item(s, "peliculas", ["drama"])
        _popularity(s, live, 0.1)
        seed.vectorize_all(s)
    _job(db_factory, redis_client).run()
    games = _repo(redis_client).read_fallback(CFG.config_version, Module.JUEGOS)
    assert games is not None and games.items == ()


def test_only_live_items_and_only_active_config_counts(db_factory, redis_client) -> None:  # noqa: ANN001
    """DI-12 y §4.4 punto 2: nunca mezcla ventanas, nunca incluye retirados."""
    with db_factory.begin() as s:
        s.execute(sa.text("INSERT INTO engine_config_versions VALUES ('sha256:vieja', '{}', now(), now())"))
        live = seed.item(s, "peliculas", ["drama"])
        retired = seed.item(s, "peliculas", ["horror"], status="retired")
        only_old = seed.item(s, "peliculas", ["comedia"])
        _popularity(s, live, 0.2)
        _popularity(s, retired, 0.99)
        _popularity(s, only_old, 0.95, cfg="sha256:vieja")
        seed.vectorize_all(s)
    _job(db_factory, redis_client).run()
    ranked = [i.item_id for i in _repo(redis_client).read_fallback(CFG.config_version, Module.PELICULAS).items]
    assert retired not in ranked
    assert ranked[0] == live  # el puntaje de la versión vieja no participa; sin fila activa, puntaje 0


def test_publishes_at_most_fallback_stored_size_items_with_their_ordinals(db_factory, redis_client) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        items = [seed.item(s, "peliculas", [f"g{i % 10}"], rating="+13", ordinal=1) for i in range(130)]
        for n, item in enumerate(items):
            _popularity(s, item, 1 - n / 1000)
        seed.vectorize_all(s)
    _job(db_factory, redis_client).run()
    entry = _repo(redis_client).read_fallback(CFG.config_version, Module.PELICULAS)
    assert len(entry.items) == CFG.fallback_stored_size == 100
    assert {i.min_age_ordinal for i in entry.items} == {1}
    assert entry.user_id is None and entry.max_age_ordinal is None  # global por módulo (FR-033c)
