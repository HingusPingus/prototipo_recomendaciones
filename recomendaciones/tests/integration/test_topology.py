"""Topología de las colas propias alineada con la convención del broker de `notificaciones` (RD-110).

El broker declara sus colas como *quorum* con `x-delivery-limit` y `x-message-ttl`; las nuestras siguen la
misma convención. Así la ventana de reentrega que usa FR-068b (`RECO_EVENT_REDELIVERY_WINDOW_HOURS`) es la
configuración real de la cola y no un valor copiado, y una política del broker no choca con la declaración
del worker (`PRECONDITION_FAILED`).
"""

from __future__ import annotations

import asyncio
import json
import uuid

import aio_pika

from recomendaciones.worker.topology import Topology, actualizar_topology, eliminado_topology


def _topology(**limits: int) -> Topology:
    suffix = uuid.uuid4().hex[:8]
    return Topology(f"x.top.{suffix}", f"q.top.{suffix}", f"q.top.{suffix}.dlq", f"q.top.{suffix}.retry", **limits)


def _queues(rabbit_container) -> dict[str, dict]:
    result = rabbit_container.exec("rabbitmqctl list_queues name type arguments --formatter json -q")
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    return {row["name"]: {"type": row["type"], "args": {k: v for k, _t, v in row["arguments"]}} for row in rows}


async def _declare(amqp_url: str, topology: Topology) -> None:
    connection = await aio_pika.connect_robust(amqp_url)
    async with connection:
        await topology.declare(await connection.channel())


async def test_every_queue_is_quorum_and_the_main_one_carries_ttl_delivery_limit_and_dead_letter(amqp_url, rabbit_container) -> None:
    topology = _topology(message_ttl_ms=86_400_000, delivery_limit=5)
    await _declare(amqp_url, topology)
    queues = _queues(rabbit_container)
    for name in (topology.queue, topology.dead_letter_queue, topology.retry_queue):
        assert queues[name]["type"] == "quorum", name
    main = queues[topology.queue]["args"]
    assert main["x-message-ttl"] == 86_400_000
    assert main["x-delivery-limit"] == 5
    assert (main["x-dead-letter-exchange"], main["x-dead-letter-routing-key"]) == ("", topology.dead_letter_queue)
    assert "x-message-ttl" not in queues[topology.dead_letter_queue]["args"]  # la DLQ no pierde mensajes


async def test_declaration_is_idempotent_across_worker_restarts(amqp_url) -> None:
    topology = _topology(message_ttl_ms=60_000, delivery_limit=5)
    await _declare(amqp_url, topology)
    await _declare(amqp_url, topology)  # no PRECONDITION_FAILED


async def test_message_never_consumed_expires_into_our_dead_letter_queue(amqp_url) -> None:
    topology = _topology(message_ttl_ms=300, delivery_limit=5)
    connection = await aio_pika.connect_robust(amqp_url)
    async with connection:
        channel = await connection.channel()
        await topology.declare(channel)
        exchange = await channel.get_exchange(topology.exchange)
        await exchange.publish(aio_pika.Message(b'{"event_id": "x"}'), routing_key="")
        dlq = await channel.get_queue(topology.dead_letter_queue, ensure=False)
        message = None
        for _ in range(30):
            message = await dlq.get(fail=False)
            if message is not None:
                break
            await asyncio.sleep(0.1)
        assert message is not None, "el mensaje vencido no llegó a la DLQ"
        assert message.headers["x-death"][0]["reason"] == "expired"
        await message.ack()


def test_worker_topologies_take_their_limits_from_the_operational_settings(valid_env) -> None:
    from recomendaciones.config.settings import load_settings
    from recomendaciones.worker.topology import broker_limits

    settings = load_settings()
    limits = broker_limits(settings)
    assert limits == {"message_ttl_ms": settings.event_redelivery_window_hours * 3_600_000, "delivery_limit": settings.retry_max_attempts}
    for topology in (actualizar_topology(**limits), eliminado_topology(**limits)):
        assert (topology.message_ttl_ms, topology.delivery_limit) == (limits["message_ttl_ms"], limits["delivery_limit"])


def test_worker_declares_both_event_queues_with_the_broker_limits(valid_env, db_factory, redis_client) -> None:
    from recomendaciones.bootstrap import build_runtime
    from recomendaciones.config.settings import load_settings
    from recomendaciones.storage.cache.client import CacheClient
    from recomendaciones.worker.runtime import build_suppression_consumer, build_worker
    from recomendaciones.worker.topology import broker_limits

    runtime = build_runtime(load_settings(), "worker", factory=db_factory, cache=CacheClient(redis_client))
    limits = broker_limits(runtime.settings)
    events, _requests = build_worker(runtime)
    assert events._topology == actualizar_topology(**limits)
    assert build_suppression_consumer(runtime)._topology == eliminado_topology(**limits)


async def test_v2_exchange_never_reaches_the_v3_queue(amqp_url) -> None:
    """RD-116: `api-general` publica v2 y v3 en exchanges distintos; nuestra cola solo se liga al de v3, así que
    un v2 nunca llega a ella (con un exchange compartido, cada interacción dejaría un v2 en la DLQ)."""
    prefix = f"t{uuid.uuid4().hex[:6]}."
    topology = actualizar_topology(prefix)
    assert topology.exchange == f"{prefix}recomendacion.actualizar.v3"
    connection = await aio_pika.connect_robust(amqp_url)
    async with connection:
        channel = await connection.channel()
        await topology.declare(channel)
        v2 = await channel.declare_exchange(f"{prefix}recomendacion.actualizar", aio_pika.ExchangeType.FANOUT, durable=True)
        await v2.publish(aio_pika.Message(b'{"evento_id": "v2"}'), routing_key="")
        v3 = await channel.get_exchange(topology.exchange)
        await v3.publish(aio_pika.Message(b'{"event_id": "v3"}'), routing_key="")
        queue = await channel.get_queue(topology.queue, ensure=False)
        received = []
        for _ in range(30):
            message = await queue.get(fail=False)
            if message is not None:
                received.append(json.loads(message.body))
                await message.ack()
            elif received:
                break
            else:
                await asyncio.sleep(0.1)
        assert received == [{"event_id": "v3"}]
