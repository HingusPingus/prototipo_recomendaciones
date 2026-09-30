"""T060 — disparador de recálculo por conteo por (usuario, módulo) e invalidación en el mismo acto (FR-080, FR-080a, RD-104)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from recomendaciones.shared.domain import Module, SignalType
from recomendaciones.storage.cache import keys
from recomendaciones.worker.schemas import ActualizarEvent
from recomendaciones.worker.trigger import InteractionTrigger
from tests.integration import seed

T0 = datetime(2026, 9, 28, 10, tzinfo=UTC)


def _event(user: uuid.UUID, item: uuid.UUID, module: Module) -> ActualizarEvent:
    return ActualizarEvent(uuid.uuid4(), f"int-{uuid.uuid4()}", user, module, item, SignalType.LIKE, T0)


def _world(db_factory, n_items: int = 12):  # noqa: ANN001, ANN202
    with db_factory.begin() as s:
        movies = [seed.item(s, "peliculas", [f"m{i}"]) for i in range(n_items)]
        games = [seed.item(s, "juegos", [f"g{i}"]) for i in range(n_items)]
        user = seed.user(s)
    return user, movies, games


def _signal(db_factory, user, item, when: datetime | None = None) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        seed.signal(s, user, item, "like", source="evento", received_at=when)


def test_n_minus_one_signals_do_not_trigger_and_n_do(db_factory, redis_client) -> None:  # noqa: ANN001
    user, movies, _ = _world(db_factory)
    trigger = InteractionTrigger(db_factory, threshold=10)
    for item in movies[:9]:
        _signal(db_factory, user, item)
        assert trigger.should_recompute(_event(user, item, Module.PELICULAS)) is False
    _signal(db_factory, user, movies[9])
    assert trigger.should_recompute(_event(user, movies[9], Module.PELICULAS)) is True


def test_count_is_per_user_and_module(db_factory, redis_client) -> None:  # noqa: ANN001
    """5 señales de películas y 5 de juegos NO disparan (CHK064, RD-104)."""
    user, movies, games = _world(db_factory)
    trigger = InteractionTrigger(db_factory, threshold=10)
    for m, g in zip(movies[:5], games[:5], strict=True):
        _signal(db_factory, user, m)
        _signal(db_factory, user, g)
    assert trigger.should_recompute(_event(user, games[4], Module.JUEGOS)) is False
    assert trigger.should_recompute(_event(user, movies[4], Module.PELICULAS)) is False


def test_count_restarts_after_recomputing_that_module(db_factory, redis_client) -> None:  # noqa: ANN001
    """No hay contador almacenado: el reinicio es consecuencia de escribir el perfil del módulo."""
    user, movies, _ = _world(db_factory)
    trigger = InteractionTrigger(db_factory, threshold=3)
    earlier = datetime.now(UTC) - timedelta(minutes=10)
    for item in movies[:3]:
        _signal(db_factory, user, item, when=earlier)
    assert trigger.should_recompute(_event(user, movies[2], Module.PELICULAS)) is True
    with db_factory.begin() as s:
        s.execute(sa.text("INSERT INTO vocab_versions (version, tag_count, created_at, activated_at) VALUES ('v', 1, now(), now())"))
        s.execute(sa.text("INSERT INTO user_profiles VALUES (:u, 'peliculas', 'v', '[1]', 3, now())"), {"u": user})
    _signal(db_factory, user, movies[3])
    assert trigger.should_recompute(_event(user, movies[3], Module.PELICULAS)) is False
    with db_factory() as s:
        columns = {c["name"] for c in sa.inspect(s.bind).get_columns("user_profiles")} | {c["name"] for c in sa.inspect(s.bind).get_columns("users")}
    assert not {c for c in columns if "count" in c and c != "signal_count"}  # ninguna columna de contador


def test_no_read_between_cause_and_invalidation_returns_the_old_result(db_factory, redis_client) -> None:  # noqa: ANN001
    """FR-080: la invalidación ocurre en el mismo acto que la causa; entre ambas no hay lectura del valor viejo."""
    from recomendaciones.observability.metrics import Metrics
    from recomendaciones.storage.cache.client import CacheClient
    from recomendaciones.storage.cache.filters import FiltersCache
    from recomendaciones.storage.db.exclusions import ExclusionResolver
    from recomendaciones.storage.db.filters_source import DbFiltersSource
    from recomendaciones.worker.handler import ActualizarHandler
    from recomendaciones.worker.idempotency import EventIdempotency
    from recomendaciones.worker.signals import SignalIngestor

    user, movies, _ = _world(db_factory)
    cache = CacheClient(redis_client)
    for version in ("sha256:activa", "sha256:legible-anterior"):
        redis_client.set(keys.reco_key(version, user, Module.PELICULAS), "{}")  # resultados viejos
    observed: list[bool] = []

    class Recompute:
        def on_signal(self, event: ActualizarEvent) -> str:
            observed.append(bool(redis_client.keys(f"reco:v*:{user}:peliculas")))  # ¿se ve el viejo durante el recálculo?
            return "recomputed"

    trigger = InteractionTrigger(db_factory, threshold=2, cache=cache)
    handler = ActualizarHandler(
        idempotency=EventIdempotency(cache, db_factory, ttl_dedupe_seconds=60, retention_hours=1),
        ingestor=SignalIngestor(db_factory, ExclusionResolver(FiltersCache(cache, DbFiltersSource(db_factory), 60).invalidate), Metrics()),
        should_recompute=trigger.should_recompute,
        recompute=Recompute(),
    )
    assert handler(_event(user, movies[0], Module.PELICULAS)) == "signal_recorded"
    assert redis_client.keys(f"reco:v*:{user}:peliculas")  # sin causa, nada se invalida
    assert handler(_event(user, movies[1], Module.PELICULAS)) == "recomputed"
    assert observed == [False]  # toda versión del vigente fue invalidada antes de recalcular (Redis primero)
