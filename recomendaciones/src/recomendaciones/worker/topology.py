"""Topología RabbitMQ del consumidor: un exchange/cola por tipo de evento (constitución, Restricciones).

El broker lo opera `notificaciones`; los nombres definitivos se acuerdan con ese repo y con
`api-general`. Las declaraciones son idempotentes y durables.
"""

from __future__ import annotations

from dataclasses import dataclass

import aio_pika


@dataclass(frozen=True, slots=True)
class Topology:
    exchange: str
    queue: str
    dead_letter_queue: str
    retry_queue: str | None = None  # espera con TTL para el backoff (T025)

    async def declare(self, channel: aio_pika.abc.AbstractChannel) -> aio_pika.abc.AbstractQueue:
        exchange = await channel.declare_exchange(self.exchange, aio_pika.ExchangeType.FANOUT, durable=True)
        await channel.declare_queue(self.dead_letter_queue, durable=True)
        queue = await channel.declare_queue(self.queue, durable=True)
        await queue.bind(exchange)
        if self.retry_queue:
            await channel.declare_queue(
                self.retry_queue,
                durable=True,
                arguments={"x-dead-letter-exchange": "", "x-dead-letter-routing-key": self.queue},
            )
        return queue


def actualizar_topology(prefix: str = "") -> Topology:
    return Topology(
        exchange=f"{prefix}recomendacion.actualizar",
        queue=f"{prefix}recomendaciones.recomendacion-actualizar",
        dead_letter_queue=f"{prefix}recomendaciones.recomendacion-actualizar.dlq",
        retry_queue=f"{prefix}recomendaciones.recomendacion-actualizar.retry",
    )


def eliminado_topology(prefix: str = "") -> Topology:
    return Topology(
        exchange=f"{prefix}usuario.eliminado",
        queue=f"{prefix}recomendaciones.usuario-eliminado",
        dead_letter_queue=f"{prefix}recomendaciones.usuario-eliminado.dlq",
        retry_queue=f"{prefix}recomendaciones.usuario-eliminado.retry",
    )
