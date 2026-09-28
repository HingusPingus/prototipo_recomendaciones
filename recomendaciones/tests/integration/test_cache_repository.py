"""T019 — escritura del top-N con score y config_version (FR-004, FR-014, SC-004, §3.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository

CFG = "sha256:v1"
NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _entry(user: uuid.UUID, n: int = 3, cfg: str = CFG) -> RecommendationEntry:
    return RecommendationEntry(
        user_id=user,
        module=Module.PELICULAS,
        config_version=cfg,
        vocab_version="vocab:abc",
        max_age_ordinal=2,
        computed_at=NOW,
        items=tuple(CachedItem(uuid.UUID(int=i + 1), i + 1, 1.0 / (i + 1), i % 3) for i in range(n)),
    )


def _repo(redis_client) -> RecommendationRepository:  # noqa: ANN001
    return RecommendationRepository(CacheClient(redis_client), ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)


def test_round_trip_is_exact_and_carries_config_version(redis_client) -> None:  # noqa: ANN001
    repo, user = _repo(redis_client), uuid.uuid4()
    entry = _entry(user)
    repo.write_personalized(entry)
    fresh = repo.read_fresh(CFG, user, Module.PELICULAS)
    assert fresh == entry
    assert fresh.config_version == CFG and fresh.computed_at == NOW  # SC-004: trazable a la configuración


def test_fresh_and_stale_copies_are_written_together(redis_client) -> None:  # noqa: ANN001
    repo, user = _repo(redis_client), uuid.uuid4()
    repo.write_personalized(_entry(user))
    assert repo.read_stale(CFG, user, Module.PELICULAS) == repo.read_fresh(CFG, user, Module.PELICULAS)
    assert 0 < redis_client.ttl(keys.reco_key(CFG, user, Module.PELICULAS)) <= 86_400
    assert 86_400 < redis_client.ttl(keys.stale_key(CFG, user, Module.PELICULAS)) <= 604_800


def test_stored_length_is_what_the_pipeline_produced(redis_client) -> None:  # noqa: ANN001
    """`min(top_n_max, candidatos)`: el truncado a `top_n` ocurre al servir (§3.2, RD-102)."""
    repo, user = _repo(redis_client), uuid.uuid4()
    repo.write_personalized(_entry(user, n=50))
    assert len(repo.read_fresh(CFG, user, Module.PELICULAS).items) == 50


def test_entry_of_another_version_is_not_found_under_the_active_one(redis_client) -> None:  # noqa: ANN001
    repo, user = _repo(redis_client), uuid.uuid4()
    repo.write_personalized(_entry(user, cfg="sha256:retirada"))
    assert repo.read_fresh(CFG, user, Module.PELICULAS) is None


def test_mislabeled_or_unknown_schema_entries_are_misses(redis_client) -> None:  # noqa: ANN001
    repo, user = _repo(redis_client), uuid.uuid4()
    cache = CacheClient(redis_client)
    good = _entry(user).to_json()
    cache.set_json(keys.reco_key(CFG, user, Module.PELICULAS), {**good, "config_version": "sha256:otra"}, 60)
    assert repo.read_fresh(CFG, user, Module.PELICULAS) is None
    cache.set_json(keys.reco_key(CFG, user, Module.PELICULAS), {**good, "schema_version": 99}, 60)
    assert repo.read_fresh(CFG, user, Module.PELICULAS) is None


def test_fallback_round_trip_without_user(redis_client) -> None:  # noqa: ANN001
    repo = _repo(redis_client)
    entry = RecommendationEntry(
        user_id=None,
        module=Module.JUEGOS,
        config_version=CFG,
        vocab_version="vocab:abc",
        max_age_ordinal=None,
        computed_at=NOW,
        items=(CachedItem(uuid.UUID(int=7), 1, 0.4, 2),),
    )
    repo.write_fallback(entry)
    assert repo.read_fallback(CFG, Module.JUEGOS) == entry
    assert "user_id" not in CacheClient(redis_client).get_json(keys.fallback_key(CFG, Module.JUEGOS))
