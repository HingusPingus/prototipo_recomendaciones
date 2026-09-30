"""T027 — consumo de `recompute:requests` con grupo de consumidores (RD-100, RD-111, FR-092a)."""

from __future__ import annotations

import sqlalchemy as sa

from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.cache.repository import RecommendationRepository
from recomendaciones.worker.handler import Recomputer
from recomendaciones.worker.requests_stream import RecomputeRequestConsumer
from tests.integration import seed

CFG = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")


def _setup(db_factory, redis_client, *, max_deliveries: int = 5):  # noqa: ANN001, ANN202
    with db_factory.begin() as s:
        for tags in (["horror"], ["drama"], ["comedia"], ["scifi"], ["western"]):
            seed.item(s, "peliculas", tags)
        user = seed.user(s)
        seed.declare(s, user, "peliculas", ["horror", "drama", "comedia", "scifi", "western"])
        seed.vectorize_all(s)
    cache = CacheClient(redis_client)
    metrics = Metrics()
    repo = RecommendationRepository(cache, ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)
    recomputer = Recomputer(db_factory, repo, CFG, metrics)
    consumer = RecomputeRequestConsumer(
        cache, recomputer, metrics, consumer_name="w1", max_deliveries=max_deliveries, claim_idle_ms=0, block_ms=10
    )
    stream = RecomputeStream(cache, maxlen=1_000, ttl_suppress=1)
    return user, repo, consumer, stream, metrics, recomputer


def _pending(redis_client) -> int:  # noqa: ANN001
    return redis_client.xpending(keys.RECOMPUTE_STREAM, keys.RECOMPUTE_GROUP)["pending"]


def test_request_is_processed_and_acked_after_writing(db_factory, redis_client) -> None:  # noqa: ANN001
    user, repo, consumer, stream, metrics, _ = _setup(db_factory, redis_client)
    stream.request(user, Module.PELICULAS, "miss")
    assert consumer.poll_once() == 1
    assert repo.read_fresh(CFG.config_version, user, Module.PELICULAS) is not None
    assert _pending(redis_client) == 0
    assert metrics.value("recompute_requests_pending") == 0


def test_failure_leaves_request_pending_and_it_is_dropped_after_max_deliveries(db_factory, redis_client, monkeypatch) -> None:  # noqa: ANN001
    user, _repo, consumer, stream, metrics, recomputer = _setup(db_factory, redis_client, max_deliveries=5)

    def crash(*a: object, **k: object) -> None:
        raise RuntimeError("caída a mitad del recálculo")

    monkeypatch.setattr(recomputer, "recompute", crash)
    stream.request(user, Module.PELICULAS, "miss")
    for _ in range(4):
        consumer.poll_once()
        assert _pending(redis_client) == 1  # no se confirmó: se reentregará
    for _ in range(3):
        consumer.poll_once()
    assert _pending(redis_client) == 0  # agotadas las entregas: se confirma y se descarta
    assert metrics.value("recompute_requests_dropped_total") == 1


def test_request_of_user_under_suppression_is_discarded(db_factory, redis_client) -> None:  # noqa: ANN001
    user, repo, consumer, stream, _, _ = _setup(db_factory, redis_client)
    with db_factory.begin() as s:
        s.execute(sa.text("INSERT INTO user_suppressions (user_id, requested_at, state) VALUES (:u, now(), 'in_progress')"), {"u": user})
    stream.request(user, Module.PELICULAS, "miss")
    consumer.poll_once()
    assert _pending(redis_client) == 0
    assert repo.read_fresh(CFG.config_version, user, Module.PELICULAS) is None


def test_malformed_request_is_acked_and_skipped(db_factory, redis_client) -> None:  # noqa: ANN001
    _, _, consumer, _, _, _ = _setup(db_factory, redis_client)
    redis_client.xadd(keys.RECOMPUTE_STREAM, {"user_id": "no-uuid", "module": "musica", "reason": "?"})
    consumer.poll_once()
    assert _pending(redis_client) == 0


def test_warmup_plus_worker_rebuild_every_entry(db_factory, redis_client) -> None:  # noqa: ANN001
    """SC-008 de punta a punta: tras vaciar Redis, el warm-up y el worker reconstruyen el 100 %."""
    from recomendaciones.batch.warmup import WarmupJob

    user, repo, consumer, _, _, _ = _setup(db_factory, redis_client)
    with db_factory.begin() as s:
        others = [seed.user(s) for _ in range(4)]
        for other in others:
            seed.declare(s, other, "peliculas", ["horror", "drama", "comedia", "scifi", "western"])
    redis_client.flushdb()
    cache = CacheClient(redis_client)
    WarmupJob(
        db_factory,
        RecomputeStream(cache, maxlen=1_000, ttl_suppress=300),
        repo,
        active_version=CFG.config_version,
        rate_per_second=1_000,
    ).run()
    while consumer.poll_once():
        pass
    for u in [user, *others]:
        assert repo.read_fresh(CFG.config_version, u, Module.PELICULAS) is not None
