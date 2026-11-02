"""T079 — la sincronización evalúa el umbral de FR-080a con las señales que trae (RD-125).

Con los eventos apagados, las interacciones llegan solo por la sincronización, y el umbral solo se evaluaba al
recibir un evento: una lista vigente quedaba sin recalcular hasta vencer. La sincronización cuenta, por (usuario,
módulo) con señales nuevas, igual que el worker; al alcanzar el umbral invalida la lista y pide el recálculo.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.transformer.client import ApiGeneralClient
from recomendaciones.transformer.pipeline import SyncPipeline
from recomendaciones.worker.trigger import InteractionTrigger
from tests.support.api_general_double import ApiGeneralDouble

KEY = "test.s3cr3t-0123456789abcdef"
CFG = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")
T0 = datetime(2026, 11, 2, 12, tzinfo=UTC)
THRESHOLD = 3


class Env:
    def __init__(self, db_factory, redis_client) -> None:  # noqa: ANN001
        self.double = ApiGeneralDouble(api_key=KEY, page_size=50)
        self.redis = redis_client
        cache = CacheClient(redis_client)
        self.repo = RecommendationRepository(cache, ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)
        self.pipeline = SyncPipeline(
            db_factory,
            ApiGeneralClient("http://api-general.internal", KEY, timeout_seconds=5, transport=self.double.transport()),
            FiltersCache(cache, DbFiltersSource(db_factory), 3_600),
            cache,
            CFG,
            Metrics(),
            volume_delta_ratio=0.9,
            redelivery_window_hours=48,
            interactions_reached=InteractionTrigger(db_factory, THRESHOLD, cache=cache).reached,
            signaler=RecomputeStream(cache, maxlen=1_000, ttl_suppress=300),
        )

    def fresh(self, user: uuid.UUID, module: Module, items: list[uuid.UUID]) -> None:
        entry = RecommendationEntry(
            user, module, CFG.config_version, "vocab:x", 2, T0,
            tuple(CachedItem(item, rank, 1.0 / rank, 0) for rank, item in enumerate(items, start=1)),
        )
        self.repo.write_personalized(entry)

    def has_fresh(self, user: uuid.UUID, module: Module) -> bool:
        return self.repo.read_fresh(CFG.config_version, user, module) is not None

    def requests(self) -> list[dict[str, str]]:
        return [fields for _id, fields in self.redis.xrange(keys.RECOMPUTE_STREAM)]


def _world(env: Env, n: int = 5) -> tuple[uuid.UUID, list[uuid.UUID], list[uuid.UUID]]:
    user = env.double.add_user(birth_date=date(1990, 5, 1), region="AR")
    movies = [env.double.add_item("peliculas", [f"m{i}"]) for i in range(n)]
    games = [env.double.add_item("juegos", [f"g{i}"]) for i in range(n)]
    return user, movies, games


def test_reaching_the_threshold_through_sync_invalidates_and_requests_recompute(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    user, movies, _ = _world(env)
    assert env.pipeline.run().status == "success"  # materializa usuario e ítems
    env.fresh(user, Module.PELICULAS, movies)
    for movie in movies[:THRESHOLD]:
        env.double.add_interaction(user, movie, "consumo", T0)

    report = env.pipeline.run()

    assert report.status == "success" and report.recompute_requested == 1
    assert not env.has_fresh(user, Module.PELICULAS)  # Redis primero: la lista vieja no se sirve (FR-080c)
    assert env.requests() == [{"user_id": str(user), "module": "peliculas", "reason": "sync_signals"}]


def test_below_the_threshold_keeps_the_list_and_requests_nothing(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    user, movies, _ = _world(env)
    env.pipeline.run()
    env.fresh(user, Module.PELICULAS, movies)
    for movie in movies[: THRESHOLD - 1]:
        env.double.add_interaction(user, movie, "like", T0)

    assert env.pipeline.run().recompute_requested == 0
    assert env.has_fresh(user, Module.PELICULAS)
    assert env.requests() == []


def test_count_is_per_module_and_only_the_module_that_reached_it_is_recomputed(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    user, movies, games = _world(env)
    env.pipeline.run()
    env.fresh(user, Module.PELICULAS, movies)
    env.fresh(user, Module.JUEGOS, games)
    for game in games[:THRESHOLD]:
        env.double.add_interaction(user, game, "consumo", T0)
    for movie in movies[: THRESHOLD - 1]:
        env.double.add_interaction(user, movie, "consumo", T0)

    env.pipeline.run()

    assert env.has_fresh(user, Module.PELICULAS) and not env.has_fresh(user, Module.JUEGOS)
    assert [r["module"] for r in env.requests()] == ["juegos"]


def test_signals_already_received_are_not_counted_again(db_factory, redis_client) -> None:  # noqa: ANN001
    """Una corrida que no trae señales nuevas no evalúa nada: lo ya recibido (por evento o por otra corrida) no se recuenta."""
    env = Env(db_factory, redis_client)
    user, movies, _ = _world(env)
    for movie in movies[:THRESHOLD]:
        env.double.add_interaction(user, movie, "consumo", T0)
    env.pipeline.run()
    redis_client.flushdb()
    env.fresh(user, Module.PELICULAS, movies)

    assert env.pipeline.run().recompute_requested == 0
    assert env.has_fresh(user, Module.PELICULAS)
    assert env.requests() == []


def test_without_trigger_the_sync_behaves_as_before(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    env.pipeline._interactions_reached = None
    user, movies, _ = _world(env)
    env.pipeline.run()
    env.fresh(user, Module.PELICULAS, movies)
    for movie in movies[:THRESHOLD]:
        env.double.add_interaction(user, movie, "consumo", T0)

    assert env.pipeline.run().recompute_requested == 0
    assert env.has_fresh(user, Module.PELICULAS)
