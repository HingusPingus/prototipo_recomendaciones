"""T037 — filtrado de salida sobre el respaldo: edad, exclusión y vigencia, acotado (FR-033d, FR-036, FR-050, FR-072, FR-075)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from recomendaciones.api.services.read_service import ReadService
from recomendaciones.shared.domain import ExclusionSet, Module, ResultType
from recomendaciones.shared.errors import ExclusionSetUnavailable
from recomendaciones.storage.cache.filters import FiltersCache, RetiredCache, UserFilters
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry

ACTIVE = "sha256:v1"
NOW = datetime(2026, 9, 28, tzinfo=UTC)


class MemoryCache:
    """Doble mínimo de CacheClient: el invariante no depende de Redis, sino de las guardas."""

    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.sets: dict[str, frozenset[str]] = {}

    def get_json(self, key: str):  # noqa: ANN201
        return self.data.get(key)

    def set_json(self, key: str, value: object, ttl: int) -> None:
        self.data[key] = value

    def delete(self, *keys: str) -> int:
        return sum(self.data.pop(k, None) is not None for k in keys)

    def get_members(self, key: str):  # noqa: ANN201
        return self.sets.get(key)

    def set_members(self, key: str, members, ttl: int) -> None:  # noqa: ANN001
        self.sets[key] = frozenset(members)


class Source:
    def __init__(self, filters: UserFilters | None, retired: frozenset[uuid.UUID] = frozenset(), fail: bool = False) -> None:
        self.filters, self.retired, self.fail = filters, retired, fail

    def load_user_filters(self, user_id: uuid.UUID):  # noqa: ANN201
        if self.fail:
            import sqlalchemy.exc

            raise sqlalchemy.exc.OperationalError("SELECT", {}, Exception("postgres caído"))
        return self.filters

    def load_retired(self, module: Module, window_seconds: int) -> frozenset[uuid.UUID]:
        return self.retired


class Repo:
    def __init__(self, fallback: RecommendationEntry | None, fresh: RecommendationEntry | None = None) -> None:
        self.fallback, self.fresh = fallback, fresh

    def read_fresh(self, version, user, module):  # noqa: ANN001, ANN201
        return self.fresh if version == ACTIVE else None

    def read_stale(self, version, user, module):  # noqa: ANN001, ANN201
        return None

    def read_fallback(self, version, module):  # noqa: ANN001, ANN201
        return self.fallback


class NoSignal:
    def request(self, *a: object, **k: object) -> bool:
        return True


def _service(repo: Repo, source: Source) -> ReadService:
    cache = MemoryCache()
    return ReadService(
        repository=repo,  # type: ignore[arg-type]
        filters=FiltersCache(cache, source, 3_600),  # type: ignore[arg-type]
        retired=RetiredCache(cache, source, 3_600, 8 * 86_400),  # type: ignore[arg-type]
        signaler=NoSignal(),
        active_version=ACTIVE,
        readable_versions=(),
        age_compatible_versions=frozenset({ACTIVE}),
    )


def _fallback(ordinals: list[int]) -> RecommendationEntry:
    items = tuple(CachedItem(uuid.UUID(int=n + 1), n + 1, 1.0 - n / 1000, o) for n, o in enumerate(ordinals))
    return RecommendationEntry(None, Module.PELICULAS, ACTIVE, "vocab:x", None, NOW, items)


def _filters(user: uuid.UUID, ordinal: int, excluded: set[int] = frozenset()) -> UserFilters:  # type: ignore[assignment]
    return UserFilters(user, ordinal, ACTIVE, ExclusionSet(user, {uuid.UUID(int=i) for i in excluded}), frozenset(Module))


@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
@given(
    ordinals=st.lists(st.integers(0, 2), min_size=1, max_size=100),
    user_ordinal=st.integers(0, 2),
    excluded=st.sets(st.integers(1, 100)),
    retired=st.sets(st.integers(1, 100)),
    top_n=st.integers(10, 50),
)
def test_fallback_never_violates_age_exclusion_or_retirement(ordinals, user_ordinal, excluded, retired, top_n) -> None:  # noqa: ANN001
    """SC-026: 0 % de respaldos servidos viola el filtro de edad o de exclusión; SC-027: siempre no personalizado."""
    user = uuid.uuid4()
    source = Source(_filters(user, user_ordinal, excluded), frozenset(uuid.UUID(int=i) for i in retired))
    result = _service(Repo(_fallback(ordinals)), source).read(user, Module.PELICULAS, top_n=top_n)
    by_id = {uuid.UUID(int=n + 1): o for n, o in enumerate(ordinals)}
    for item in result.items:
        assert by_id[item.item_id] <= user_ordinal
        assert item.item_id.int not in excluded and item.item_id.int not in retired
    assert result.result_type in (ResultType.FALLBACK, ResultType.EMPTY_NO_CANDIDATES)
    assert len(result.items) <= top_n
    positions_in_source = [item.item_id.int for item in result.items]
    assert positions_in_source == sorted(positions_in_source)  # sin reordenar (FR-033d)


def test_minor_never_receives_adult_content_via_fallback() -> None:
    user = uuid.uuid4()
    result = _service(Repo(_fallback([2, 2, 1, 0, 2])), Source(_filters(user, 0))).read(user, Module.PELICULAS, top_n=10)
    assert [i.item_id.int for i in result.items] == [4]


def test_reduced_list_is_served_as_is_without_padding() -> None:
    """FR-075: 7 de 20 tras las guardas se sirven 7, con el estado de su frescura."""
    user = uuid.uuid4()
    fallback = _fallback([0] * 7 + [2] * 13)
    result = _service(Repo(fallback), Source(_filters(user, 0))).read(user, Module.PELICULAS, top_n=20)
    assert len(result.items) == 7 and result.result_type is ResultType.FALLBACK


def test_emptied_fallback_is_no_candidates() -> None:
    user = uuid.uuid4()
    result = _service(Repo(_fallback([2, 2])), Source(_filters(user, 0))).read(user, Module.PELICULAS, top_n=10)
    assert result.result_type is ResultType.EMPTY_NO_CANDIDATES and result.items == ()


def test_item_retired_after_precompute_is_not_served() -> None:
    """El tercer punto de §4.4: el único que alcanza a un resultado ya precomputado."""
    user = uuid.uuid4()
    fresh = RecommendationEntry(user, Module.PELICULAS, ACTIVE, "vocab:x", 2, NOW, tuple(CachedItem(uuid.UUID(int=i), i, 1.0, 0) for i in (1, 2, 3)))
    result = _service(Repo(None, fresh), Source(_filters(user, 2), frozenset({uuid.UUID(int=2)}))).read(user, Module.PELICULAS, top_n=10)
    assert [i.item_id.int for i in result.items] == [1, 3] and result.result_type is ResultType.PERSONALIZED


def test_unavailable_exclusion_set_rejects_with_retryable_error() -> None:
    """FR-050: si la exclusión no está disponible, error explícito y reintentable; nunca sin filtrar."""
    with pytest.raises(ExclusionSetUnavailable):
        _service(Repo(_fallback([0])), Source(None, fail=True)).read(uuid.uuid4(), Module.PELICULAS, top_n=10)
