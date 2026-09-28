"""T033 — SC-009 / INV-1: el camino normal de lectura no consulta Postgres ni calcula."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi.testclient import TestClient

from recomendaciones.api.app import build_services, create_app
from recomendaciones.config.settings import load_settings
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry
from tests.integration import seed


def test_normal_path_emits_zero_queries(valid_env, db_factory, redis_client) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        user = seed.user(s)
        seed.tags(s, ["horror"])
        seed.declare(s, user, "peliculas", ["horror"])
    settings = load_settings()
    services = build_services(settings, db_factory=db_factory, cache=CacheClient(redis_client))
    services.repository.write_personalized(
        RecommendationEntry(
            user, Module.PELICULAS, services.engine_config.config_version, "vocab:x", 2,
            datetime(2026, 9, 28, tzinfo=UTC), (CachedItem(uuid.UUID(int=1), 1, 0.9, 0),),
        )
    )
    headers = {"X-Internal-API-Key": valid_env["RECO_INTERNAL_API_KEY"]}
    queries: list[str] = []
    engine = db_factory.kw["bind"]
    with TestClient(create_app(settings, services)) as client:
        url = f"/internal/v1/recommendations/{user}"
        assert client.get(url, params={"module": "peliculas"}, headers=headers).status_code == 200  # puebla filters:/retired:
        sa.event.listen(engine, "before_cursor_execute", lambda *a, **k: queries.append(a[2]))
        for _ in range(20):
            assert client.get(url, params={"module": "peliculas"}, headers=headers).status_code == 200
    sa.event.remove(engine, "before_cursor_execute", queries.append) if False else None
    assert queries == [], f"el camino normal consultó Postgres: {queries[:3]}"
