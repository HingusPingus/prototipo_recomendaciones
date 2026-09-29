"""T032 — la caída de api-general degrada la frescura, no la disponibilidad (FR-019, FR-040, US3-3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from recomendaciones.api.app import build_services, create_app
from recomendaciones.config.settings import load_settings
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry
from recomendaciones.transformer.resilience import run_with_retries
from tests.integration.test_sync_idempotent import FUNCTIONAL, Env, _state


def test_read_keeps_serving_and_materialized_state_is_intact(valid_env, db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    user = env.double.add_user()
    env.double.add_item("peliculas", ["horror"])
    env.pipeline.run()
    with db_factory.begin() as s:
        from tests.integration import seed

        seed.declare(s, user, "peliculas", ["horror"])
    before = _state(env)
    env.double.down = True
    assert env.pipeline.run().status == "failed"  # falla limpia y registrada
    assert _state(env) == before  # nada se corrompe ni se vacía
    settings = load_settings()
    services = build_services(settings, db_factory=db_factory, cache=CacheClient(redis_client))
    services.repository.write_personalized(
        RecommendationEntry(user, Module.PELICULAS, services.engine_config.config_version, "v", 2, datetime.now(UTC), (CachedItem(uuid.uuid4(), 1, 0.5, 0),))
    )
    with TestClient(create_app(settings, services)) as api:
        response = api.get(f"/internal/v1/recommendations/{user}", params={"module": "peliculas"}, headers={"X-Internal-API-Key": valid_env["RECO_INTERNAL_API_KEY"]})
    assert response.status_code == 200 and response.json()["result_type"] == "personalized"
    assert set(before) == set(FUNCTIONAL)


def test_retries_with_exponential_backoff_until_the_origin_returns(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    env.double.add_item("peliculas", ["horror"])
    env.double.down = True
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            env.double.down = False  # el origen vuelve durante los reintentos

    report = run_with_retries(env.pipeline, max_attempts=5, backoff_base_seconds=1.0, sleep=sleep)
    assert report.status == "success"
    assert sleeps == [1.0, 2.0]


def test_gives_up_after_max_attempts_leaving_failed_runs(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    env.double.down = True
    report = run_with_retries(env.pipeline, max_attempts=3, backoff_base_seconds=0.01, sleep=lambda s: None)
    assert report.status == "failed"
    assert env.q("SELECT count(*) FROM sync_runs WHERE status = 'failed'") == [(3,)]
