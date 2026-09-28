"""T020 — política de cache miss y señalización de recálculo (FR-034, FR-035, FR-038, FR-056, RD-100, RD-103)."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from recomendaciones.api.services.read_service import ReadService
from recomendaciones.shared.domain import ExclusionSet, Module, ResultType
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache, RetiredCache, UserFilters
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository

ACTIVE, PREVIOUS = "sha256:v2", "sha256:v1"
NOW = datetime(2026, 9, 28, tzinfo=UTC)


class StaticSource:
    """Fuente de filtros en memoria: estos tests ejercitan la precedencia, no el repoblado."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, UserFilters] = {}
        self.retired: dict[Module, frozenset[uuid.UUID]] = {}

    def add(self, user: uuid.UUID, *, ordinal: int = 2, excluded: set[uuid.UUID] = frozenset(), version: str = ACTIVE) -> None:  # type: ignore[assignment]
        self.users[user] = UserFilters(user, ordinal, version, ExclusionSet(user, excluded), frozenset(Module))

    def load_user_filters(self, user_id: uuid.UUID) -> UserFilters | None:
        return self.users.get(user_id)

    def load_retired(self, module: Module, window_seconds: int) -> frozenset[uuid.UUID]:
        return self.retired.get(module, frozenset())


def _items(*ns: int, ordinal: int = 0) -> tuple[CachedItem, ...]:
    return tuple(CachedItem(uuid.UUID(int=n), rank, 1.0 / rank, ordinal) for rank, n in enumerate(ns, start=1))


def _entry(user: uuid.UUID | None, items: tuple[CachedItem, ...], cfg: str = ACTIVE, snapshot: int | None = 2) -> RecommendationEntry:
    return RecommendationEntry(user, Module.PELICULAS, cfg, "vocab:x", snapshot if user else None, NOW, items)


@pytest.fixture
def env(redis_client):  # noqa: ANN001, ANN201
    cache = CacheClient(redis_client)
    source = StaticSource()
    repo = RecommendationRepository(cache, ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)
    service = ReadService(
        repository=repo,
        filters=FiltersCache(cache, source, 3_600),
        retired=RetiredCache(cache, source, 3_600, 8 * 86_400),
        signaler=RecomputeStream(cache, maxlen=100_000, ttl_suppress=300),
        active_version=ACTIVE,
        readable_versions=(PREVIOUS,),
        age_compatible_versions=frozenset({ACTIVE, PREVIOUS}),
    )
    return service, repo, source, redis_client


def _stream_len(redis_client) -> int:  # noqa: ANN001
    return redis_client.xlen(keys.RECOMPUTE_STREAM) if redis_client.exists(keys.RECOMPUTE_STREAM) else 0


def test_state_table(env) -> None:  # noqa: ANN001
    service, repo, source, _ = env
    pending, vigente, stale_only, fallback_only, vaciado = (uuid.uuid4() for _ in range(5))
    for u in (pending, vigente, stale_only, fallback_only, vaciado):
        source.add(u, excluded={uuid.UUID(int=9)} if u == vaciado else set())
    repo.write_personalized(_entry(vigente, _items(1, 2, 3)))
    repo.write_personalized(_entry(vaciado, _items(9)))
    repo.write_personalized(_entry(stale_only, _items(4, 5)))
    service._repository._cache.delete(keys.reco_key(ACTIVE, stale_only, Module.PELICULAS))  # vence el vigente

    assert service.read(pending, Module.PELICULAS, top_n=10).result_type is ResultType.EMPTY_PENDING
    assert service.read(vigente, Module.PELICULAS, top_n=10).result_type is ResultType.PERSONALIZED
    assert service.read(stale_only, Module.PELICULAS, top_n=10).result_type is ResultType.PERSONALIZED_STALE
    assert service.read(vaciado, Module.PELICULAS, top_n=10).result_type is ResultType.EMPTY_NO_CANDIDATES
    repo.write_fallback(_entry(None, _items(20, 21)))
    fb = service.read(fallback_only, Module.PELICULAS, top_n=10)
    assert fb.result_type is ResultType.FALLBACK and fb.stale_available is False


def test_fallback_precedes_stale_and_signals_it(env) -> None:  # noqa: ANN001
    service, repo, source, _ = env
    user = uuid.uuid4()
    source.add(user)
    repo.write_personalized(_entry(user, _items(4, 5)))
    service._repository._cache.delete(keys.reco_key(ACTIVE, user, Module.PELICULAS))
    repo.write_fallback(_entry(None, _items(20, 21)))
    result = service.read(user, Module.PELICULAS, top_n=10)
    assert result.result_type is ResultType.FALLBACK and result.stale_available is True


def test_fallback_empty_after_filters_is_no_candidates(env) -> None:  # noqa: ANN001
    service, repo, source, _ = env
    minor = uuid.uuid4()
    source.add(minor, ordinal=0)
    repo.write_fallback(_entry(None, _items(20, 21, ordinal=2)))
    assert service.read(minor, Module.PELICULAS, top_n=10).result_type is ResultType.EMPTY_NO_CANDIDATES


def test_fifty_concurrent_misses_produce_one_request(env) -> None:  # noqa: ANN001
    service, _, source, redis_client = env
    user = uuid.uuid4()
    source.add(user)
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: service.read(user, Module.PELICULAS, top_n=10), range(50)))
    assert {r.result_type for r in results} == {ResultType.EMPTY_PENDING}
    assert _stream_len(redis_client) == 1  # SC-015


def test_previous_version_with_same_age_catalog_is_served_with_its_label_without_signal(env) -> None:  # noqa: ANN001
    service, repo, source, redis_client = env
    user = uuid.uuid4()
    source.add(user)
    repo.write_personalized(_entry(user, _items(1, 2), cfg=PREVIOUS))
    result = service.read(user, Module.PELICULAS, top_n=10)
    assert result.result_type is ResultType.PERSONALIZED
    assert result.config_version == PREVIOUS
    assert _stream_len(redis_client) == 0


def test_signal_write_failure_never_fails_the_read(env) -> None:  # noqa: ANN001
    service, _, source, _ = env

    class Broken:
        def request(self, *a: object, **k: object) -> bool:
            raise RuntimeError("el Stream no acepta escrituras")

    service._signaler = Broken()
    user = uuid.uuid4()
    source.add(user)
    assert service.read(user, Module.PELICULAS, top_n=10).result_type is ResultType.EMPTY_PENDING


def test_two_consecutive_reads_on_same_state_are_identical(env) -> None:  # noqa: ANN001
    """FR-038, US6-5: la respuesta degradada es determinística."""
    service, repo, source, _ = env
    user = uuid.uuid4()
    source.add(user)
    repo.write_fallback(_entry(None, _items(20, 21, 22)))
    assert service.read(user, Module.PELICULAS, top_n=10) == service.read(user, Module.PELICULAS, top_n=10)


def test_restricted_snapshot_is_discarded_as_miss(env) -> None:  # noqa: ANN001
    """§3.2: instantáneo etario mayor que el permiso actual ⟹ descartar como miss y pedir recálculo."""
    service, repo, source, redis_client = env
    user = uuid.uuid4()
    source.add(user, ordinal=1)
    repo.write_personalized(_entry(user, _items(1), snapshot=2))
    assert service.read(user, Module.PELICULAS, top_n=10).result_type is ResultType.EMPTY_PENDING
    assert _stream_len(redis_client) == 1
