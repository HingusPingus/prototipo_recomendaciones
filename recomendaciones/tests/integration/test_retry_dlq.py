"""T025 — reintentos con backoff exponencial y dead-letter (FR-013, FR-067, FR-068, Principio VII)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import aio_pika

from recomendaciones.shared.domain import Module
from recomendaciones.shared.errors import TransientError
from recomendaciones.worker.consumer import EventConsumer, RetryPolicy
from recomendaciones.worker.topology import Topology


def _topology() -> Topology:
    suffix = uuid.uuid4().hex[:8]
    return Topology(
        exchange=f"x.{suffix}", queue=f"q.{suffix}", dead_letter_queue=f"q.{suffix}.dlq", retry_queue=f"q.{suffix}.retry"
    )


def _body() -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "origin_interaction_id": f"int-{uuid.uuid4()}",
        "user_id": str(uuid.uuid4()),
        "module": "peliculas",
        "item_id": str(uuid.uuid4()),
        "signal_type": "like",
        "occurred_at": datetime(2026, 9, 28, tzinfo=UTC).isoformat(),
    }


async def _publish(url: str, topology: Topology, body: dict) -> None:
    connection = await aio_pika.connect_robust(url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.get_exchange(topology.exchange)
        await exchange.publish(aio_pika.Message(json.dumps(body).encode()), routing_key="")


async def _dead_letters(url: str, queue: str) -> list[aio_pika.abc.AbstractIncomingMessage]:
    connection = await aio_pika.connect_robust(url)
    out = []
    async with connection:
        channel = await connection.channel()
        q = await channel.get_queue(queue, ensure=True)
        while (message := await q.get(fail=False)) is not None:
            await message.ack()
            out.append(message)
    return out


async def _run(url: str, handler, *, until, timeout: float = 15.0) -> Topology:  # noqa: ANN001
    topology = _topology()
    consumer = EventConsumer(url, topology, handler, retry=RetryPolicy(max_attempts=5, backoff_base_seconds=0.05))
    await consumer.start()
    try:
        await _publish(url, topology, _body())
        for _ in range(int(timeout * 10)):
            if until():
                break
            await asyncio.sleep(0.1)
    finally:
        await consumer.stop()
    return topology


async def test_transient_failure_is_retried_until_success(amqp_url: str) -> None:
    calls: list[int] = []

    def flaky(event) -> str:  # noqa: ANN001
        calls.append(1)
        if len(calls) < 3:
            raise TransientError("base de datos momentáneamente caída")
        return "recomputed"

    topology = await _run(amqp_url, flaky, until=lambda: len(calls) >= 3)
    assert len(calls) == 3
    assert await _dead_letters(amqp_url, topology.dead_letter_queue) == []


async def test_permanent_failure_goes_to_dlq_after_five_attempts_with_intact_payload(amqp_url: str) -> None:
    calls: list[str] = []

    def broken(event) -> str:  # noqa: ANN001
        calls.append(str(event.event_id))
        raise TransientError("siempre falla")

    topology = _topology()
    consumer = EventConsumer(amqp_url, topology, broken, retry=RetryPolicy(max_attempts=5, backoff_base_seconds=0.02))
    await consumer.start()
    body = _body()
    try:
        await _publish(amqp_url, topology, body)
        for _ in range(150):
            if len(calls) >= 5:
                await asyncio.sleep(0.5)
                break
            await asyncio.sleep(0.1)
    finally:
        await consumer.stop()
    assert len(calls) == 5  # máximo configurable (FR-068): cinco intentos, luego DLQ
    dead = await _dead_letters(amqp_url, topology.dead_letter_queue)
    assert len(dead) == 1
    assert json.loads(dead[0].body) == body  # payload íntegro para reproceso manual
    assert dead[0].headers["x-dlq-reason"] == "retries_exhausted" and "siempre falla" in dead[0].headers["x-dlq-cause"]


def test_backoff_is_exponential() -> None:
    policy = RetryPolicy(max_attempts=5, backoff_base_seconds=1)
    assert [policy.delay_seconds(n) for n in (1, 2, 3, 4)] == [1, 2, 4, 8]


def test_opposite_module_failure_keeps_primary_and_requeues_only_the_opposite(db_factory, redis_client, monkeypatch) -> None:  # noqa: ANN001
    """FR-067: sin atomicidad cruzada; el opuesto se reencola solo, por el canal interno."""
    from recomendaciones.storage.cache import keys
    from tests.integration.test_propagation import CFG, _event, _recomputer, _signal, _world

    user, movies, _ = _world(db_factory)
    recomputer, repo = _recomputer(db_factory, redis_client)
    original = recomputer.recompute

    def failing(user_id, module, reason):  # noqa: ANN001, ANN202
        if module is Module.JUEGOS:
            raise TransientError("fallo transitorio en el opuesto")
        return original(user_id, module, reason)

    monkeypatch.setattr(recomputer, "recompute", failing)
    _signal(db_factory, user, movies["conjuro"], "like")
    assert recomputer.on_signal(_event(user, movies["conjuro"], Module.PELICULAS)) == "recomputed"
    assert repo.read_fresh(CFG.config_version, user, Module.PELICULAS) is not None
    requests = [{k: v for k, v in e[1].items() if k != "correlation_id"} for e in redis_client.xrange(keys.RECOMPUTE_STREAM)]
    assert requests == [{"user_id": str(user), "module": "juegos", "reason": "opposite_retry"}]
