"""T023 — consumo de `recomendacion.actualizar` con validación de schema (FR-009, FR-012, FR-061, FR-064)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import aio_pika
import pytest

from recomendaciones.worker.consumer import EventConsumer
from recomendaciones.worker.schemas import ActualizarEvent, parse_actualizar
from recomendaciones.worker.topology import Topology

CONTRACTS = Path(__file__).resolve().parents[2] / "specs" / "001-recomendaciones-precomputadas" / "contracts"


def _event(**overrides: object) -> dict:
    event = {
        "event_id": str(uuid.uuid4()),
        "origin_interaction_id": f"int-{uuid.uuid4()}",
        "user_id": str(uuid.uuid4()),
        "module": "peliculas",
        "item_id": str(uuid.uuid4()),
        "signal_type": "like",
        "occurred_at": datetime(2026, 9, 28, 12, tzinfo=UTC).isoformat(),
    }
    event.update(overrides)
    return {k: v for k, v in event.items() if v is not None}


def test_packaged_schema_matches_the_contract_copy() -> None:
    import recomendaciones.worker.schemas as schemas

    packaged = Path(schemas.__file__).with_name("contracts") / "recomendacion-actualizar.schema.json"
    assert json.loads(packaged.read_text()) == json.loads((CONTRACTS / "recomendacion-actualizar.schema.json").read_text())


def test_parse_valid_event() -> None:
    raw = _event()
    event = parse_actualizar(json.dumps(raw).encode())
    assert isinstance(event, ActualizarEvent)
    assert str(event.event_id) == raw["event_id"] and event.module.value == "peliculas"
    assert event.occurred_at.tzinfo is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"signal_type": None},
        {"origin_interaction_id": None},
        {"module": "musica"},
        {"signal_type": "visto"},
        {"event_id": "no-uuid"},
        {"occurred_at": "ayer"},
    ],
    ids=["sin-signal_type", "sin-origin_interaction_id", "modulo-desconocido", "tipo-invalido", "event_id-invalido", "fecha-invalida"],
)
def test_invalid_payloads_are_rejected_with_cause(overrides: dict) -> None:
    from recomendaciones.shared.errors import InvalidEventPayload

    with pytest.raises(InvalidEventPayload) as exc:
        parse_actualizar(json.dumps(_event(**overrides)).encode())
    assert exc.value.message


def test_non_json_is_rejected() -> None:
    from recomendaciones.shared.errors import InvalidEventPayload

    with pytest.raises(InvalidEventPayload):
        parse_actualizar(b"\x00no json")


def _topology() -> Topology:
    suffix = uuid.uuid4().hex[:8]
    return Topology(
        exchange=f"recomendacion.actualizar.{suffix}",
        queue=f"recomendaciones.actualizar.{suffix}",
        dead_letter_queue=f"recomendaciones.actualizar.{suffix}.dlq",
    )


async def _drain(url: str, queue: str, timeout: float = 5.0) -> list[aio_pika.abc.AbstractIncomingMessage]:
    connection = await aio_pika.connect_robust(url)
    out = []
    async with connection:
        channel = await connection.channel()
        q = await channel.get_queue(queue, ensure=True)
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            message = await q.get(fail=False)
            if message is None:
                if out:
                    break
                await asyncio.sleep(0.1)
                continue
            await message.ack()
            out.append(message)
    return out


async def test_consumer_processes_valid_and_dead_letters_invalid(amqp_url: str) -> None:
    topology = _topology()
    handled: list[ActualizarEvent] = []
    consumer = EventConsumer(amqp_url, topology, handler=lambda event: handled.append(event) or "recomputed")
    await consumer.start()
    try:
        connection = await aio_pika.connect_robust(amqp_url)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.get_exchange(topology.exchange)
            valid = _event()
            for body in (valid, _event(signal_type=None), _event(module="musica")):
                await exchange.publish(aio_pika.Message(json.dumps(body).encode()), routing_key="")
        for _ in range(50):
            if handled:
                break
            await asyncio.sleep(0.1)
    finally:
        await consumer.stop()
    assert [str(e.event_id) for e in handled] == [valid["event_id"]]  # módulo desconocido: ningún top-N se toca
    dead = await _drain(amqp_url, topology.dead_letter_queue)
    reasons = sorted(m.headers["x-dlq-reason"] for m in dead)
    assert reasons == ["invalid_payload", "invalid_payload"]
    assert all(m.headers.get("x-dlq-cause") for m in dead)
    assert all(m.headers.get("x-event-id") for m in dead)  # extraíble aun siendo inválido
