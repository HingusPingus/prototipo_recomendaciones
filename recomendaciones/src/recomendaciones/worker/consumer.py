"""Consumidor de eventos del broker (T023; reintentos T025, payload inválido T026, baja T058).

Valida contra el schema **antes** de tocar el dominio. Un payload inválido va a la dead-letter con su
causa y **sin reintento** (FR-012); el consumo continúa con el mensaje siguiente. El manejador de
dominio es síncrono (SQLAlchemy, Redis) y corre en un hilo para no bloquear el lazo de eventos.
El worker nunca llama a `api-general` ni publica eventos entre repositorios (INV-4).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Generic, TypeVar

import aio_pika

from recomendaciones.shared.errors import InvalidEventPayload
from recomendaciones.worker.schemas import extract_event_id, parse_actualizar
from recomendaciones.worker.topology import Topology

log = logging.getLogger(__name__)

E = TypeVar("E")


class EventConsumer(Generic[E]):
    def __init__(
        self,
        url: str,
        topology: Topology,
        handler: Callable[[E], Any],
        *,
        parser: Callable[[bytes], E] = parse_actualizar,  # type: ignore[assignment]
        prefetch: int = 16,
        on_dead_letter: Callable[[str], None] | None = None,
    ) -> None:
        self._url = url
        self._topology = topology
        self._handler = handler
        self._parser = parser
        self._prefetch = prefetch
        self._on_dead_letter = on_dead_letter
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._prefetch)
        queue = await self._topology.declare(self._channel)
        await queue.consume(self._on_message)

    async def stop(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage, reason: str, cause: str) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        headers.update({"x-dlq-reason": reason, "x-dlq-cause": cause[:500]})
        event_id = extract_event_id(message.body)
        if event_id:
            headers["x-event-id"] = event_id
        await self._channel.default_exchange.publish(
            aio_pika.Message(message.body, headers=headers, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=self._topology.dead_letter_queue,
        )
        log.warning("evento a dead-letter", extra={"event_id": event_id, "reason": reason, "cause": cause[:200]})
        if self._on_dead_letter:
            self._on_dead_letter(reason)

    async def _on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            event = self._parser(message.body)
        except InvalidEventPayload as exc:
            await self.dead_letter(message, "invalid_payload", exc.message)
            await message.ack()
            return
        try:
            await asyncio.to_thread(self._handler, event)
        except Exception as exc:  # noqa: BLE001 — T025 agrega reintentos con backoff antes de la DLQ
            await self.dead_letter(message, "processing_error", f"{exc.__class__.__name__}: {exc}")
        await message.ack()
