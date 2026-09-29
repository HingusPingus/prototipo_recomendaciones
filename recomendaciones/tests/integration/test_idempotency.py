"""T024 — idempotencia por event_id: marca en Redis respaldada por processed_events (FR-011, FR-069, DI-6)."""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.worker.idempotency import EventIdempotency


def _idem(db_factory, redis_client, *, ttl: int = 86_400, retention_hours: int = 168) -> EventIdempotency:  # noqa: ANN001
    return EventIdempotency(CacheClient(redis_client), db_factory, ttl_dedupe_seconds=ttl, retention_hours=retention_hours)


def test_same_event_ten_times_processes_once(db_factory, redis_client) -> None:  # noqa: ANN001
    idem, calls, event = _idem(db_factory, redis_client), [], uuid.uuid4()
    results = [idem.process_once(event, lambda: calls.append(1) or "recomputed") for _ in range(10)]
    assert len(calls) == 1
    assert results[0] == "recomputed" and results[1:] == [None] * 9
    with db_factory() as s:
        row = s.execute(sa.text("SELECT result::text, expires_at > now() FROM processed_events WHERE event_id = :e"), {"e": event}).one()
    assert row == ("recomputed", True)
    assert redis_client.exists(keys.dedupe_key(event))


def test_losing_redis_does_not_break_idempotency(db_factory, redis_client) -> None:  # noqa: ANN001
    idem, calls, event = _idem(db_factory, redis_client), [], uuid.uuid4()
    idem.process_once(event, lambda: calls.append(1) or "signal_recorded")
    redis_client.flushdb()  # pérdida total de Redis (INV-2)
    assert idem.process_once(event, lambda: calls.append(1) or "signal_recorded") is None
    assert len(calls) == 1
    assert redis_client.exists(keys.dedupe_key(event))  # la marca caliente se repone desde Postgres


def test_duplicate_after_mark_expiry_is_reprocessed_and_converges(db_factory, redis_client) -> None:  # noqa: ANN001
    """FR-069: tras expirar la marca, reprocesar produce un resultado equivalente."""
    idem, event, state = _idem(db_factory, redis_client), uuid.uuid4(), set()

    def work() -> str:
        state.add("señal-única")  # convergente: el conjunto no duplica
        return "recomputed"

    idem.process_once(event, work)
    redis_client.delete(keys.dedupe_key(event))
    with db_factory.begin() as s:
        s.execute(sa.text("UPDATE processed_events SET expires_at = now() - interval '1 second' WHERE event_id = :e"), {"e": event})
    assert idem.process_once(event, work) == "recomputed"
    assert state == {"señal-única"}
    with db_factory() as s:
        assert s.execute(sa.text("SELECT count(*) FROM processed_events WHERE event_id = :e"), {"e": event}).scalar_one() == 1


def test_retention_is_configurable(db_factory, redis_client) -> None:  # noqa: ANN001
    idem, event = _idem(db_factory, redis_client, ttl=120, retention_hours=2), uuid.uuid4()
    idem.process_once(event, lambda: "recomputed")
    assert 0 < redis_client.ttl(keys.dedupe_key(event)) <= 120
    with db_factory() as s:
        hours = s.execute(sa.text("SELECT extract(epoch FROM expires_at - processed_at) / 3600 FROM processed_events")).scalar_one()
    assert round(float(hours)) == 2


def test_failed_work_leaves_no_mark(db_factory, redis_client) -> None:  # noqa: ANN001
    idem, event = _idem(db_factory, redis_client), uuid.uuid4()

    def boom() -> str:
        raise RuntimeError("fallo transitorio")

    try:
        idem.process_once(event, boom)
    except RuntimeError:
        pass
    assert not redis_client.exists(keys.dedupe_key(event))
    assert idem.process_once(event, lambda: "recomputed") == "recomputed"  # se reintenta de verdad
