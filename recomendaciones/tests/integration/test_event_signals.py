"""T064 — persistencia de la señal del evento y materialización de su exclusión (FR-010, FR-029e, RD-95, RD-96)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from recomendaciones.api.services.read_service import ReadService
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module, SignalType
from recomendaciones.shared.errors import ContractViolation
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache, RetiredCache
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository
from recomendaciones.storage.db.exclusions import ExclusionResolver
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.worker.handler import ActualizarHandler
from recomendaciones.worker.idempotency import EventIdempotency
from recomendaciones.worker.schemas import ActualizarEvent
from recomendaciones.worker.signals import SignalIngestor
from tests.integration import seed

T0 = datetime(2026, 9, 28, 10, tzinfo=UTC)


class FakeRecompute:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, Module]] = []

    def on_signal(self, event: ActualizarEvent) -> str:
        self.calls.append((event.user_id, event.module))
        return "recomputed"


class Stack:
    def __init__(self, db_factory, redis_client, *, threshold_reached: bool = True) -> None:  # noqa: ANN001
        self.cache = CacheClient(redis_client)
        self.filters = FiltersCache(self.cache, DbFiltersSource(db_factory), 3_600)
        self.metrics = Metrics()
        self.recompute = FakeRecompute()
        self.handler = ActualizarHandler(
            idempotency=EventIdempotency(self.cache, db_factory, ttl_dedupe_seconds=86_400, retention_hours=168),
            ingestor=SignalIngestor(db_factory, ExclusionResolver(self.filters.invalidate), self.metrics),
            should_recompute=lambda event: threshold_reached,
            recompute=self.recompute,
        )
        self.db = db_factory


def _event(user: uuid.UUID, item: uuid.UUID, kind: str = "dislike", *, oid: str | None = None, minutes: int = 0) -> ActualizarEvent:
    return ActualizarEvent(
        event_id=uuid.uuid4(),
        origin_interaction_id=oid or f"int-{uuid.uuid4()}",
        user_id=user,
        module=Module.PELICULAS,
        item_id=item,
        signal_type=SignalType(kind),
        occurred_at=T0 + timedelta(minutes=minutes),
    )


def _signals(db_factory, user: uuid.UUID) -> list[tuple]:  # noqa: ANN001
    with db_factory() as s:
        return s.execute(
            sa.text("SELECT origin_interaction_id, signal_type::text, source::text, occurred_at, received_at FROM user_signals WHERE user_id = :u"),
            {"u": user},
        ).all()


def _result(db_factory, event: ActualizarEvent) -> str:  # noqa: ANN001
    with db_factory() as s:
        return s.execute(sa.text("SELECT result::text FROM processed_events WHERE event_id = :e"), {"e": event.event_id}).scalar_one()


@pytest.fixture
def world(db_factory):  # noqa: ANN001, ANN201
    with db_factory.begin() as s:
        user = seed.user(s)
        item = seed.item(s, "peliculas", ["horror"])
    return user, item


def test_valid_event_persists_one_row_from_the_event_source(db_factory, redis_client, world) -> None:  # noqa: ANN001
    user, item = world
    stack = Stack(db_factory, redis_client)
    event = _event(user, item)
    assert stack.handler(event) == "recomputed"
    rows = _signals(db_factory, user)
    assert len(rows) == 1
    oid, kind, source, occurred_at, received_at = rows[0]
    assert (oid, kind, source) == (event.origin_interaction_id, "dislike", "evento")
    assert occurred_at == event.occurred_at and received_at > occurred_at  # occurred_at del origen, received_at local
    assert _result(db_factory, event) == "recomputed"


def test_same_event_twice_leaves_one_row(db_factory, redis_client, world) -> None:  # noqa: ANN001
    user, item = world
    stack = Stack(db_factory, redis_client)
    event = _event(user, item)
    stack.handler(event)
    assert stack.handler(event) == "duplicate"
    assert len(_signals(db_factory, user)) == 1 and len(stack.recompute.calls) == 1


def test_interaction_that_arrived_first_by_sync_is_not_duplicated(db_factory, redis_client, world) -> None:  # noqa: ANN001
    user, item = world
    oid = f"int-{uuid.uuid4()}"
    with db_factory.begin() as s:
        s.execute(
            sa.text("INSERT INTO user_signals (origin_interaction_id, user_id, item_id, signal_type, occurred_at, source) "
                    "VALUES (:o, :u, :i, 'dislike', :t, 'sync')"),
            {"o": oid, "u": user, "i": item, "t": T0},
        )
    stack = Stack(db_factory, redis_client)
    stack.handler(_event(user, item, oid=oid))
    assert len(_signals(db_factory, user)) == 1
    assert stack.metrics.value("signal_duplicate_rejections_total", source="evento") == 1


def test_reused_identifier_with_other_content_is_a_contract_violation(db_factory, redis_client, world) -> None:  # noqa: ANN001
    user, item = world
    stack = Stack(db_factory, redis_client)
    oid = f"int-{uuid.uuid4()}"
    stack.handler(_event(user, item, "like", oid=oid))
    with pytest.raises(ContractViolation):
        stack.handler(_event(user, item, "dislike", oid=oid))  # el consumidor lo deriva a DLQ con la causa
    assert [r[1] for r in _signals(db_factory, user)] == ["like"]
    assert stack.metrics.value("contract_violations_total", field="origin_interaction_id") == 1


def test_not_materialized_item_is_recorded_without_retry(db_factory, redis_client, world) -> None:  # noqa: ANN001
    user, _ = world
    stack = Stack(db_factory, redis_client)
    event = _event(user, uuid.uuid4())
    assert stack.handler(event) == "skipped_not_materialized"
    assert _signals(db_factory, user) == [] and stack.recompute.calls == []
    assert _result(db_factory, event) == "skipped_not_materialized"


def test_below_threshold_is_signal_recorded(db_factory, redis_client, world) -> None:  # noqa: ANN001
    user, item = world
    stack = Stack(db_factory, redis_client, threshold_reached=False)
    event = _event(user, item, "like")
    assert stack.handler(event) == "signal_recorded"
    assert stack.recompute.calls == [] and _result(db_factory, event) == "signal_recorded"


def test_next_read_excludes_the_disliked_item_even_with_populated_filters(db_factory, redis_client, world) -> None:  # noqa: ANN001
    """Con el TTL solo, este test pasa en rojo durante una hora: obliga a invalidar (RD-96)."""
    user, item = world
    with db_factory.begin() as s:
        seed.declare(s, user, "peliculas", ["horror"])
        active = seed.active_config(s)
    stack = Stack(db_factory, redis_client, threshold_reached=False)
    repo = RecommendationRepository(stack.cache, ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)
    other = uuid.uuid4()
    repo.write_personalized(
        RecommendationEntry(user, Module.PELICULAS, active, "vocab:x", 2, T0, (CachedItem(item, 1, 0.9, 0), CachedItem(other, 2, 0.8, 0)))
    )
    service = ReadService(
        repository=repo,
        filters=stack.filters,
        retired=RetiredCache(stack.cache, DbFiltersSource(db_factory), 3_600, 8 * 86_400),
        signaler=RecomputeStream(stack.cache, maxlen=1_000, ttl_suppress=300),
        active_version=active,
        readable_versions=(),
        age_compatible_versions=frozenset({active}),
    )
    assert item in {i.item_id for i in service.read(user, Module.PELICULAS, top_n=10).items}  # filters: poblado
    stack.handler(_event(user, item, "dislike"))
    assert item not in {i.item_id for i in service.read(user, Module.PELICULAS, top_n=10).items}


def test_reprocessing_leaves_one_signal_and_the_same_exclusion(db_factory, redis_client, world) -> None:  # noqa: ANN001
    user, item = world
    stack = Stack(db_factory, redis_client)
    event = _event(user, item, "consumo")
    stack.handler(event)
    redis_client.flushdb()
    with db_factory.begin() as s:
        s.execute(sa.text("DELETE FROM processed_events"))  # marca vencida y purgada
    stack.handler(event)
    with db_factory() as s:
        exclusions = s.execute(sa.text("SELECT item_id, origin::text FROM user_exclusions WHERE user_id = :u"), {"u": user}).all()
    assert len(_signals(db_factory, user)) == 1 and exclusions == [(item, "consumo")]
