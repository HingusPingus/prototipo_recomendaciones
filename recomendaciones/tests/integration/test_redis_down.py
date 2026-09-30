"""T021 — Redis caído ≠ miss: 503 con Retry-After, nunca Postgres para calcular (FR-065, INV-1)."""

from __future__ import annotations

import socket
import time
import uuid

import pytest

from recomendaciones.api.services.read_service import ReadService
from recomendaciones.shared.domain import Module
from recomendaciones.shared.errors import CacheUnavailable
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache, RetiredCache
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.cache.repository import RecommendationRepository


class SpySource:
    """Espía de accesos a Postgres: el camino de la caída no debe llegar nunca acá."""

    calls = 0

    def load_user_filters(self, user_id: uuid.UUID):  # noqa: ANN201
        SpySource.calls += 1

    def load_retired(self, module: Module, window_seconds: int):  # noqa: ANN201
        SpySource.calls += 1
        return frozenset()


def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]  # el socket se cierra: nadie escucha en ese puerto


def _service(cache: CacheClient) -> ReadService:
    return ReadService(
        repository=RecommendationRepository(cache, ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600),
        filters=FiltersCache(cache, SpySource(), 3_600),
        retired=RetiredCache(cache, SpySource(), 3_600, 8 * 86_400),
        signaler=RecomputeStream(cache, maxlen=100_000, ttl_suppress=300),
        active_version="sha256:v1",
        readable_versions=(),
        age_compatible_versions=frozenset({"sha256:v1"}),
    )


def test_redis_down_raises_503_error_and_never_reaches_postgres() -> None:
    SpySource.calls = 0
    cache = CacheClient.from_url(f"redis://127.0.0.1:{_closed_port()}/0", timeout_seconds=0.5)
    with pytest.raises(CacheUnavailable) as exc:
        _service(cache).read(uuid.uuid4(), Module.PELICULAS, top_n=10)
    assert exc.value.http_status == 503 and exc.value.retry_after_seconds > 0
    assert SpySource.calls == 0


def test_timeout_is_explicit_and_bounded() -> None:
    """Un Redis que no responde no cuelga la solicitud: el timeout es el configurado."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)  # acepta la conexión TCP pero nunca contesta
    try:
        cache = CacheClient.from_url(f"redis://127.0.0.1:{listener.getsockname()[1]}/0", timeout_seconds=0.3)
        started = time.monotonic()
        with pytest.raises(CacheUnavailable):
            cache.get_json("reco:x")
        assert time.monotonic() - started < 2.0
    finally:
        listener.close()


def test_miss_and_down_are_distinguishable(redis_client) -> None:  # noqa: ANN001
    assert CacheClient(redis_client).get_json("reco:inexistente") is None  # miss: None, no excepción
    down = CacheClient.from_url(f"redis://127.0.0.1:{_closed_port()}/0", timeout_seconds=0.3)
    with pytest.raises(CacheUnavailable):
        down.get_json("reco:inexistente")
