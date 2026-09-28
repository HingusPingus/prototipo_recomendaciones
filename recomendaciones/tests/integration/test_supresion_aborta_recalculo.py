"""T058 — supresión verificada con aborto del recálculo en curso (FR-091…FR-093, FR-080c, RD-101, `data-model.md` §7.11)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import aio_pika
import sqlalchemy as sa

import recomendaciones.worker.suppression as suppression_module
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module
from recomendaciones.shared.errors import TransientError
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.worker.consumer import EventConsumer, RetryPolicy
from recomendaciones.worker.idempotency import EventIdempotency
from recomendaciones.worker.schemas import EliminadoEvent, parse_eliminado
from recomendaciones.worker.suppression import SuppressionHandler, SuppressionProcedure
from recomendaciones.worker.topology import Topology
from tests.integration import seed
from tests.integration.test_propagation import CFG, _recomputer, _signal, _world

REQUESTED = datetime(2026, 9, 28, 12, tzinfo=UTC)
FIVE_TABLES = ("users", "user_profiles", "user_signals", "user_exclusions", "user_declared_tags")


def _procedure(db_factory, redis_client, metrics: Metrics | None = None, **kwargs) -> SuppressionProcedure:
    return SuppressionProcedure(
        db_factory, CacheClient(redis_client), metrics or Metrics(), max_attempts=3, backoff_base_seconds=0.0, **kwargs
    )


def _rows(db_factory, user: uuid.UUID) -> dict[str, int]:
    with db_factory() as s:
        return {
            t: s.execute(sa.text(f"SELECT count(*) FROM {t} WHERE {'id' if t == 'users' else 'user_id'} = :u"), {"u": user}).scalar_one()
            for t in FIVE_TABLES
        }


def _populated(db_factory, redis_client):
    """Usuario con datos en las cinco tablas y claves en las cuatro familias, bajo dos versiones y ambos módulos."""
    user, movies, _games = _world(db_factory)
    recomputer, _repo = _recomputer(db_factory, redis_client)
    _signal(db_factory, user, movies["conjuro"], "like")
    with db_factory.begin() as s:
        seed.exclusion(s, user, movies["conjuro"], "like")
    for module in (Module.PELICULAS, Module.JUEGOS):
        assert recomputer.recompute(user, module, "miss").status == "written"
        redis_client.set(keys.reco_key("sha256:vieja", user, module), "{}")  # otra config_version (FR-093)
        redis_client.set(keys.lock_key(user, module), "1", ex=300)
    redis_client.set(keys.filters_key(user), "{}")
    cache = CacheClient(redis_client)
    other = uuid.uuid4()
    for who in (user, other, user):
        cache.xadd(keys.RECOMPUTE_STREAM, {"user_id": str(who), "module": "peliculas", "reason": "miss"}, 1000)
    return user, other


def _user_keys(redis_client, user: uuid.UUID) -> list[str]:
    return sorted(k for k in redis_client.scan_iter(match=f"*{user}*"))


def _stream_users(redis_client) -> list[str]:
    return [fields["user_id"] for _id, fields in redis_client.xrange(keys.RECOMPUTE_STREAM)]


def test_suppression_reaches_the_five_tables_and_every_user_key_of_every_version_and_module(db_factory, redis_client) -> None:
    user, other = _populated(db_factory, redis_client)
    assert all(n > 0 for n in _rows(db_factory, user).values())
    assert len(_user_keys(redis_client, user)) >= 7
    outcome = _procedure(db_factory, redis_client).run(user, REQUESTED)
    assert outcome.state == "completed"
    assert _rows(db_factory, user) == dict.fromkeys(FIVE_TABLES, 0)
    assert _user_keys(redis_client, user) == []  # leído en el acto, no esperando el TTL (FR-091)
    assert _stream_users(redis_client) == [str(other)]  # solo se purgan las entradas del usuario (RD-100)


def test_redis_is_cleared_before_postgres(db_factory, redis_client, monkeypatch) -> None:
    user, _ = _populated(db_factory, redis_client)
    seen: list[int] = []
    original = suppression_module.delete_user_scope

    def spy(cache, patterns):
        seen.append(_rows(db_factory, user)["users"])
        return original(cache, patterns)

    monkeypatch.setattr(suppression_module, "delete_user_scope", spy)
    _procedure(db_factory, redis_client).run(user, REQUESTED)
    assert seen and seen[0] == 1  # la primera invalidación ocurre con la fila de origen todavía presente (FR-080c)


def test_marker_is_the_in_progress_row_while_the_procedure_runs(db_factory, redis_client, monkeypatch) -> None:
    user, _ = _populated(db_factory, redis_client)
    states: list[str] = []
    procedure = _procedure(db_factory, redis_client)
    original = procedure.residue

    def spy(user_id):
        with db_factory() as s:
            states.append(s.execute(sa.text("SELECT state::text FROM user_suppressions WHERE user_id = :u"), {"u": user_id}).scalar_one())
        return original(user_id)

    monkeypatch.setattr(procedure, "residue", spy)
    procedure.run(user, REQUESTED)
    assert states[0] == "in_progress"


def test_recompute_in_flight_is_aborted_and_does_not_rewrite_the_suppressed_result(db_factory, redis_client, monkeypatch) -> None:
    user, _ = _populated(db_factory, redis_client)
    recomputer, _repo = _recomputer(db_factory, redis_client)
    procedure = _procedure(db_factory, redis_client)
    original_rank = recomputer._rank

    def rank_while_suppressing(*args, **kwargs):
        entry = original_rank(*args, **kwargs)  # el cómputo ya terminó...
        assert procedure.run(user, REQUESTED).state == "completed"  # ...y la supresión ocurre antes de escribir
        return entry

    monkeypatch.setattr(recomputer, "_rank", rank_while_suppressing)
    assert recomputer.recompute(user, Module.PELICULAS, "miss").status == "aborted_suppressed"
    assert _user_keys(redis_client, user) == []
    assert _rows(db_factory, user) == dict.fromkeys(FIVE_TABLES, 0)


def test_same_event_twice_has_a_single_effect_and_a_new_event_for_a_suppressed_user_is_a_no_op(db_factory, redis_client, monkeypatch) -> None:
    user, _ = _populated(db_factory, redis_client)
    cache = CacheClient(redis_client)
    procedure = _procedure(db_factory, redis_client)
    runs: list[uuid.UUID] = []
    original = procedure.run
    monkeypatch.setattr(procedure, "run", lambda u, r: runs.append(u) or original(u, r))
    handler = SuppressionHandler(procedure, EventIdempotency(cache, db_factory, ttl_dedupe_seconds=60, retention_hours=24))
    event = EliminadoEvent(uuid.uuid4(), user, REQUESTED)
    assert handler(event) == "suppressed"
    assert handler(event) == "duplicate"
    assert handler(EliminadoEvent(uuid.uuid4(), user, REQUESTED)) == "suppressed"  # otro event_id, mismo usuario
    assert len(runs) == 2
    with db_factory() as s:
        row = s.execute(sa.text("SELECT state::text, attempts FROM user_suppressions WHERE user_id = :u"), {"u": user}).one()
    assert row.state == "completed" and row.attempts == 1  # el segundo evento no repitió la verificación


def test_user_never_materialized_still_leaves_a_tombstone(db_factory, redis_client) -> None:
    ghost = uuid.uuid4()
    assert _procedure(db_factory, redis_client).run(ghost, REQUESTED).state == "completed"
    with db_factory() as s:
        assert s.execute(sa.text("SELECT count(*) FROM user_suppressions WHERE user_id = :u"), {"u": ghost}).scalar_one() == 1


def test_recompute_request_for_a_suppressed_user_is_dropped(db_factory, redis_client) -> None:
    user, _ = _populated(db_factory, redis_client)
    _procedure(db_factory, redis_client).run(user, REQUESTED)
    RecomputeStream(CacheClient(redis_client), maxlen=100, ttl_suppress=300).request(user, Module.PELICULAS, "miss")
    recomputer, _repo = _recomputer(db_factory, redis_client)
    assert recomputer.recompute(user, Module.PELICULAS, "miss").status in ("aborted_suppressed", "user_not_found")
    assert [k for k in _user_keys(redis_client, user) if not k.startswith("recompute:lock:")] == []


# --- consumo real del evento de baja (Principio VI): reintentos y DLQ de T025/T026 ------------------


def _topology() -> Topology:
    suffix = uuid.uuid4().hex[:8]
    return Topology(f"usuario.eliminado.{suffix}", f"q.del.{suffix}", f"q.del.{suffix}.dlq", f"q.del.{suffix}.retry")


async def _publish(url: str, topology: Topology, payload: bytes) -> None:
    connection = await aio_pika.connect_robust(url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.get_exchange(topology.exchange)
        await exchange.publish(aio_pika.Message(payload), routing_key="")


async def _drain(url: str, queue: str) -> list[aio_pika.abc.AbstractIncomingMessage]:
    connection = await aio_pika.connect_robust(url)
    out = []
    async with connection:
        channel = await connection.channel()
        q = await channel.get_queue(queue, ensure=True)
        while (message := await q.get(fail=False)) is not None:
            await message.ack()
            out.append(message)
    return out


async def _consume(url: str, topology: Topology, handler, payloads: list[bytes], until) -> None:
    consumer = EventConsumer(url, topology, handler, parser=parse_eliminado, retry=RetryPolicy(max_attempts=5, backoff_base_seconds=0.05))
    await consumer.start()
    try:
        for payload in payloads:
            await _publish(url, topology, payload)
        for _ in range(150):
            if until():
                await asyncio.sleep(0.3)
                break
            await asyncio.sleep(0.1)
    finally:
        await consumer.stop()


def _payload(event_id: uuid.UUID, user: uuid.UUID) -> bytes:
    return json.dumps({"event_id": str(event_id), "user_id": str(user), "occurred_at": REQUESTED.isoformat()}).encode()


async def test_broker_duplicate_delivery_suppresses_once(amqp_url, db_factory, redis_client) -> None:
    user, _ = _populated(db_factory, redis_client)
    procedure = _procedure(db_factory, redis_client)
    runs: list[uuid.UUID] = []
    original = procedure.run
    procedure.run = lambda u, r: runs.append(u) or original(u, r)  # type: ignore[method-assign]
    handler = SuppressionHandler(procedure, EventIdempotency(CacheClient(redis_client), db_factory, ttl_dedupe_seconds=60, retention_hours=24))
    results: list[str] = []
    topology = _topology()
    payload = _payload(uuid.uuid4(), user)
    await _consume(amqp_url, topology, lambda e: results.append(handler(e)) or results[-1], [payload, payload], until=lambda: len(results) >= 2)
    assert sorted(results) == ["duplicate", "suppressed"] and len(runs) == 1
    assert await _drain(amqp_url, topology.dead_letter_queue) == []


async def test_broker_invalid_payload_goes_to_dlq_without_retry(amqp_url) -> None:
    calls: list[object] = []
    topology = _topology()
    bad = json.dumps({"event_id": str(uuid.uuid4()), "occurred_at": REQUESTED.isoformat()}).encode()  # sin user_id
    await _consume(amqp_url, topology, calls.append, [bad], until=lambda: False)
    dead = await _drain(amqp_url, topology.dead_letter_queue)
    assert calls == [] and len(dead) == 1 and dead[0].headers["x-dlq-reason"] == "invalid_payload"


async def test_broker_transient_failure_is_retried(amqp_url) -> None:
    calls: list[int] = []

    def flaky(event: EliminadoEvent) -> str:
        calls.append(1)
        if len(calls) < 3:
            raise TransientError("Postgres momentáneamente caído")
        return "suppressed"

    topology = _topology()
    await _consume(amqp_url, topology, flaky, [_payload(uuid.uuid4(), uuid.uuid4())], until=lambda: len(calls) >= 3)
    assert len(calls) == 3 and await _drain(amqp_url, topology.dead_letter_queue) == []


def test_worker_wires_the_deletion_queue_with_retries_and_dlq(valid_env, db_factory, redis_client) -> None:
    from recomendaciones.bootstrap import build_runtime
    from recomendaciones.config.settings import load_settings
    from recomendaciones.worker.runtime import build_suppression_consumer
    from recomendaciones.worker.topology import broker_limits, eliminado_topology

    runtime = build_runtime(load_settings(), "worker", factory=db_factory, cache=CacheClient(redis_client))
    consumer = build_suppression_consumer(runtime)
    assert consumer._topology == eliminado_topology(**broker_limits(runtime.settings))
    assert consumer._parser is parse_eliminado
    assert consumer._retry is not None and consumer._retry.max_attempts == runtime.settings.retry_max_attempts
    assert CFG.config_version == runtime.config.config_version
