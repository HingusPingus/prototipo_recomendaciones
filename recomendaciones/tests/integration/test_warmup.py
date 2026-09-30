"""T022 — reconstrucción tras pérdida total de Redis (FR-066, SC-008, §3.3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from recomendaciones.batch.warmup import WarmupJob
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository
from tests.integration import seed


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        self.slept += seconds


def _populate(db_factory, n: int) -> list[uuid.UUID]:  # noqa: ANN001
    with db_factory.begin() as s:
        movie = seed.item(s, "peliculas", ["horror"])
        users = []
        for i in range(n):
            u = seed.user(s)
            seed.declare(s, u, "peliculas", ["horror"])
            if i % 2 == 0:
                seed.declare(s, u, "juegos", ["horror"])
            seed.signal(s, u, movie, "like", received_at=datetime.now(UTC) - timedelta(minutes=n - i))
            users.append(u)
    return users


def _job(db_factory, redis_client, clock: FakeClock, rate: float = 10.0) -> WarmupJob:  # noqa: ANN001
    cache = CacheClient(redis_client)
    with db_factory() as s:
        active = seed.active_config(s)
    return WarmupJob(
        db_factory,
        RecomputeStream(cache, maxlen=100_000, ttl_suppress=300),
        RecommendationRepository(cache, ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600),
        active_version=active,
        rate_per_second=rate,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )


def _requests(redis_client) -> list[tuple[str, str]]:  # noqa: ANN001
    if not redis_client.exists(keys.RECOMPUTE_STREAM):
        return []
    return [(e[1]["user_id"], e[1]["module"]) for e in redis_client.xrange(keys.RECOMPUTE_STREAM)]


def test_enqueues_every_declared_module_prioritizing_active_users(db_factory, redis_client) -> None:  # noqa: ANN001
    users = _populate(db_factory, 6)
    report = _job(db_factory, redis_client, FakeClock()).run()
    requests = _requests(redis_client)
    assert len(requests) == 6 + 3 == report.enqueued
    assert requests[0][0] == str(users[-1])  # el de actividad más reciente primero
    assert all(r[1] in ("peliculas", "juegos") for r in requests)


def test_respects_rate_limit(db_factory, redis_client) -> None:  # noqa: ANN001
    _populate(db_factory, 10)
    clock = FakeClock()
    report = _job(db_factory, redis_client, clock, rate=5.0).run()
    assert report.enqueued == 15
    assert clock.slept >= (report.enqueued - 1) / 5.0 - 1e-9  # nunca más de 5 XADD por segundo


def test_resumable_without_duplicating_work_or_losing_users(db_factory, redis_client) -> None:  # noqa: ANN001
    users = _populate(db_factory, 4)
    with db_factory() as s:
        active = seed.active_config(s)
    repo = RecommendationRepository(CacheClient(redis_client), ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)
    done = users[-1]  # ya reconstruido antes de la «interrupción»
    repo.write_personalized(
        RecommendationEntry(done, Module.PELICULAS, active, "vocab:x", 2, datetime.now(UTC), (CachedItem(uuid.uuid4(), 1, 1.0, 0),))
    )
    report = _job(db_factory, redis_client, FakeClock()).run()
    requests = set(_requests(redis_client))
    assert (str(done), "peliculas") not in requests
    assert {(str(u), "peliculas") for u in users[:-1]} <= requests
    assert report.skipped_fresh == 1


def test_is_not_triggered_by_reads() -> None:
    """FR-066: proceso dedicado e invocable manualmente; la lectura no lo importa."""
    from recomendaciones.api.services import read_service

    assert "warmup" not in read_service.__dict__ and "batch" not in str(read_service.__dict__.get("__file__", ""))
