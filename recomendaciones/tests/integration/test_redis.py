"""T018 — cliente Redis, TTLs efectivos, `filters:` y `retired:` con repoblado, y el Stream interno."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache, RetiredCache
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.db.filters_source import DbFiltersSource
from tests.integration import seed

TTL_FRESH, TTL_FILTERS, TTL_SUPPRESS = 86_400, 3_600, 300
RETIRED_WINDOW = 8 * 86_400


def test_effective_ttls_and_filters_expire_before_reco(redis_client) -> None:  # noqa: ANN001
    cache = CacheClient(redis_client)
    user = uuid.uuid4()
    cache.set_json(keys.reco_key("sha256:a", user, Module.JUEGOS), {"x": 1}, TTL_FRESH)
    cache.set_json(keys.filters_key(user), {"y": 2}, TTL_FILTERS)
    reco_ttl = redis_client.ttl(keys.reco_key("sha256:a", user, Module.JUEGOS))
    filters_ttl = redis_client.ttl(keys.filters_key(user))
    assert 0 < filters_ttl <= TTL_FILTERS < reco_ttl <= TTL_FRESH
    assert cache.get_json(keys.reco_key("sha256:a", user, Module.JUEGOS)) == {"x": 1}
    assert cache.get_json("reco:inexistente") is None


def test_filters_repopulate_with_new_exclusion_and_declaration_after_invalidation(db_factory, redis_client) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        cfg = seed.active_config(s)
        user = seed.user(s, max_age_ordinal=1)
        item = seed.item(s, "peliculas", ["horror"])
    filters = FiltersCache(CacheClient(redis_client), DbFiltersSource(db_factory), TTL_FILTERS)
    first = filters.get(user)
    assert first is not None
    assert first.max_age_ordinal == 1 and first.age_config_version == cfg
    assert first.exclusions.item_ids == frozenset() and first.declared_modules == frozenset()

    with db_factory.begin() as s:
        seed.exclusion(s, user, item)
        seed.declare(s, user, "peliculas", ["horror"])
    assert filters.get(user).exclusions.item_ids == frozenset()  # sigue cacheado (TTL)
    filters.invalidate(user)
    after = filters.get(user)
    assert after.exclusions.contains(item)
    assert after.declared_modules == frozenset({Module.PELICULAS})


def test_unknown_user_has_no_filters(db_factory, redis_client) -> None:  # noqa: ANN001
    filters = FiltersCache(CacheClient(redis_client), DbFiltersSource(db_factory), TTL_FILTERS)
    assert filters.get(uuid.uuid4()) is None


class CountingSource(DbFiltersSource):
    calls = 0

    def load_retired(self, module: Module, window_seconds: int) -> frozenset[uuid.UUID]:
        CountingSource.calls += 1
        return super().load_retired(module, window_seconds)


def test_retired_set_is_bounded_by_window_and_cached_even_when_empty(db_factory, redis_client) -> None:  # noqa: ANN001
    now = datetime.now(UTC)
    with db_factory.begin() as s:
        recent = seed.item(s, "juegos", ["rpg"], status="retired", retired_at=now - timedelta(days=2))
        seed.item(s, "juegos", ["rpg"], status="retired", retired_at=now - timedelta(days=30))
        seed.item(s, "juegos", ["rpg"])
    CountingSource.calls = 0
    retired = RetiredCache(CacheClient(redis_client), CountingSource(db_factory), TTL_FILTERS, RETIRED_WINDOW)
    assert retired.members(Module.JUEGOS) == frozenset({recent})
    assert retired.members(Module.PELICULAS) == frozenset()  # vacío…
    assert retired.members(Module.PELICULAS) == frozenset()
    assert CountingSource.calls == 2  # …y aun así cacheado: el camino normal no vuelve a Postgres
    assert 0 < redis_client.ttl(keys.retired_key(Module.PELICULAS)) <= TTL_FILTERS


def test_recompute_stream_suppresses_duplicates_and_is_bounded(redis_client) -> None:  # noqa: ANN001
    stream = RecomputeStream(CacheClient(redis_client), maxlen=100, ttl_suppress=TTL_SUPPRESS)
    user = uuid.uuid4()
    assert stream.request(user, Module.PELICULAS, "miss") is True
    assert stream.request(user, Module.PELICULAS, "miss") is False  # recompute:lock vigente
    assert stream.request(user, Module.JUEGOS, "miss") is True
    entries = redis_client.xrange(keys.RECOMPUTE_STREAM)
    assert [e[1]["module"] for e in entries] == ["peliculas", "juegos"]
    assert entries[0][1] == {"user_id": str(user), "module": "peliculas", "reason": "miss"}
    assert 0 < redis_client.ttl(keys.lock_key(user, Module.PELICULAS)) <= TTL_SUPPRESS
    for i in range(1_000):
        stream.request(uuid.uuid4(), Module.JUEGOS, "warmup")
    assert redis_client.xlen(keys.RECOMPUTE_STREAM) < 1_000  # MAXLEN aproximado


def test_invalidation_deletes_the_key(db_factory, redis_client) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        user = seed.user(s)
    filters = FiltersCache(CacheClient(redis_client), DbFiltersSource(db_factory), TTL_FILTERS)
    filters.get(user)
    assert redis_client.exists(keys.filters_key(user))
    filters.invalidate(user)
    assert not redis_client.exists(keys.filters_key(user))
    with db_factory.begin() as s:
        assert s.execute(sa.text("SELECT count(*) FROM users")).scalar_one() == 1
