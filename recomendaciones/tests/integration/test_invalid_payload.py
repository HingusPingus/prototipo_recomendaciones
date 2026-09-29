"""T026 — payload inválido a DLQ sin reintento y sin bloquear la cola (FR-012, SC-007)."""

from __future__ import annotations

import asyncio
import json
import logging


from recomendaciones.worker.consumer import EventConsumer, RetryPolicy
from tests.integration.test_retry_dlq import _body, _dead_letters, _publish, _topology


async def test_interleaved_invalid_messages_never_block_valid_ones(amqp_url: str, caplog) -> None:  # noqa: ANN001
    topology = _topology()
    handled: list[str] = []
    consumer = EventConsumer(
        amqp_url, topology, lambda e: handled.append(str(e.event_id)) or "recomputed", retry=RetryPolicy(5, 0.05)
    )
    valid = [_body() for _ in range(5)]
    invalid = []
    for n in range(5):
        broken = _body()
        broken.pop("signal_type") if n % 2 else broken.update({"module": "musica"})
        invalid.append(broken)
    await consumer.start()
    try:
        with caplog.at_level(logging.WARNING, logger="recomendaciones.worker.consumer"):
            for good, bad in zip(valid, invalid, strict=True):
                await _publish(amqp_url, topology, bad)
                await _publish(amqp_url, topology, good)
            for _ in range(100):
                if len(handled) >= 5:
                    break
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.3)
    finally:
        await consumer.stop()
    assert sorted(handled) == sorted(b["event_id"] for b in valid)  # los 5 válidos, procesados
    dead = await _dead_letters(amqp_url, topology.dead_letter_queue)
    assert sorted(json.loads(m.body)["event_id"] for m in dead) == sorted(b["event_id"] for b in invalid)  # SC-007
    assert all(m.headers["x-dlq-reason"] == "invalid_payload" and m.headers["x-dlq-cause"] for m in dead)
    assert all("x-retry-count" not in (m.headers or {}) for m in dead)  # cero reintentos
    assert await _dead_letters(amqp_url, topology.retry_queue) == []
    logged = {getattr(r, "event_id", None) for r in caplog.records}
    assert {b["event_id"] for b in invalid} <= logged  # el log incluye el event_id cuando es extraíble
