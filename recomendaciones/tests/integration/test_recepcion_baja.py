"""T074 — registro de la recepción del evento de baja: el checkpoint de entrega acordado con `api-general`
(FR-095b, FR-080c, RD-115, `data-model.md` §2.15 y §7.11 paso 0)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.worker.idempotency import EventIdempotency
from recomendaciones.worker.schemas import EliminadoEvent
from recomendaciones.worker.suppression import SuppressionHandler, SuppressionProcedure

LAG = "user_deletion_receipt_lag_seconds"


def _handler(db_factory, redis_client, metrics: Metrics) -> tuple[SuppressionProcedure, SuppressionHandler]:  # noqa: ANN001
    cache = CacheClient(redis_client)
    procedure = SuppressionProcedure(db_factory, cache, metrics, max_attempts=3, backoff_base_seconds=0.0)
    idempotency = EventIdempotency(cache, db_factory, ttl_dedupe_seconds=60, retention_hours=24)
    return procedure, SuppressionHandler(procedure, idempotency)


def _receipt(db_factory, user: uuid.UUID):  # noqa: ANN001, ANN202
    with db_factory() as s:
        return s.execute(
            sa.text("SELECT event_id, received_at, requested_at, state::text AS state FROM user_suppressions WHERE user_id = :u"),
            {"u": user},
        ).one_or_none()


def test_valid_event_records_its_receipt_with_the_event_id(db_factory, redis_client) -> None:  # noqa: ANN001
    metrics = Metrics()
    _procedure, handler = _handler(db_factory, redis_client, metrics)
    occurred = datetime.now(UTC) - timedelta(minutes=3)
    event = EliminadoEvent(uuid.uuid4(), uuid.uuid4(), occurred)
    assert handler(event) == "suppressed"
    row = _receipt(db_factory, event.user_id)
    assert row.event_id == event.event_id  # la clave con que api-general cruza el checkpoint con su outbox
    assert row.requested_at == occurred
    assert abs((row.received_at - datetime.now(UTC)).total_seconds()) < 60
    assert metrics.value(LAG) == 1
    assert 170 <= metrics.registry.get_sample_value(f"{LAG}_sum") <= 240  # ~3 minutos de occurred_at a received_at


def test_receipt_is_durable_before_the_suppression_starts(db_factory, redis_client, monkeypatch) -> None:  # noqa: ANN001
    """FR-095b: la recepción se escribe en su propia transacción. Si la supresión cae, el checkpoint ya existe y la
    marca de FR-092a también: el barrido la retoma."""
    procedure, handler = _handler(db_factory, redis_client, Metrics())

    def caida(user_id: uuid.UUID, requested_at: datetime) -> None:
        raise RuntimeError("caída a mitad de la supresión")

    monkeypatch.setattr(procedure, "run", caida)
    event = EliminadoEvent(uuid.uuid4(), uuid.uuid4(), datetime.now(UTC))
    with pytest.raises(RuntimeError):
        handler(event)
    row = _receipt(db_factory, event.user_id)
    assert row is not None and row.event_id == event.event_id
    assert row.state == "in_progress"


def test_another_event_keeps_the_first_receipt_and_a_redelivery_is_not_measured_twice(db_factory, redis_client) -> None:  # noqa: ANN001
    metrics = Metrics()
    _procedure, handler = _handler(db_factory, redis_client, metrics)
    user = uuid.uuid4()
    first = EliminadoEvent(uuid.uuid4(), user, datetime.now(UTC) - timedelta(minutes=1))
    assert handler(first) == "suppressed"
    received = _receipt(db_factory, user).received_at
    assert handler(first) == "duplicate"  # reentrega del broker
    assert handler(EliminadoEvent(uuid.uuid4(), user, datetime.now(UTC))) == "suppressed"  # otra baja del mismo usuario
    row = _receipt(db_factory, user)
    assert (row.event_id, row.received_at) == (first.event_id, received)
    assert metrics.value(LAG) == 1


def test_negative_lag_from_clock_skew_is_recorded_as_zero(db_factory, redis_client) -> None:  # noqa: ANN001
    metrics = Metrics()
    _procedure, handler = _handler(db_factory, redis_client, metrics)
    handler(EliminadoEvent(uuid.uuid4(), uuid.uuid4(), datetime.now(UTC) + timedelta(minutes=2)))
    assert metrics.value(LAG) == 1
    assert metrics.registry.get_sample_value(f"{LAG}_sum") == 0
