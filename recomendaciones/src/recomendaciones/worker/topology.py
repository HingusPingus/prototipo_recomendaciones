"""Topología RabbitMQ del consumidor: un exchange/cola por tipo de evento (constitución, Restricciones).

El broker lo opera `notificaciones`; los nombres, los permisos y el vhost por entorno, sin prefijo, están
acordados con ese repo y con `api-general` (RD-120). Las declaraciones son idempotentes y durables.

Convención del broker (RD-110): colas **quorum** —requisito de RabbitMQ para `x-delivery-limit`— con
`x-message-ttl` y dead-letter. La cola principal la sigue:

- `x-message-ttl` = `RECO_EVENT_REDELIVERY_WINDOW_HOURS`: un evento nunca consumido vence a la DLQ propia.
  Así la ventana de reentrega que FR-068b compara con la retención de señales es la configuración real de
  la cola, no un valor copiado.
- `x-delivery-limit` = `RECO_RETRY_MAX_ATTEMPTS`: el worker confirma siempre y reintenta con backoff por la
  cola de espera (T025), de modo que el límite solo actúa ante reentregas sin confirmación —un mensaje que
  tumba al proceso una y otra vez—, que así terminan en la DLQ en lugar de ciclar.

La DLQ no lleva TTL: lo que llega ahí se conserva para el reproceso (runbook, «Reproceso desde DLQ»).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import aio_pika

from recomendaciones.worker.schemas import transport_headers

_QUORUM = {"x-queue-type": "quorum"}


@dataclass(frozen=True, slots=True)
class Topology:
    exchange: str
    queue: str
    dead_letter_queue: str
    retry_queue: str | None = None  # espera con TTL por mensaje para el backoff (T025)
    message_ttl_ms: int | None = None
    delivery_limit: int | None = None
    required_headers: Mapping[str, str] | None = None  # headers AMQP que exige el contrato del evento (RD-116)

    def transport_mismatch(self, headers: Mapping[str, Any] | None) -> str | None:
        """Causa para la DLQ si el mensaje no trae los headers que exige el contrato; `None` si cumple."""
        received = dict(headers or {})
        for name, expected in (self.required_headers or {}).items():
            value = received.get(name)
            value = value.decode() if isinstance(value, bytes) else value
            if value != expected:
                return f"{name}: se esperaba {expected!r} y llegó {value!r}"
        return None

    def queue_arguments(self) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            **_QUORUM,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": self.dead_letter_queue,
        }
        if self.message_ttl_ms is not None:
            arguments["x-message-ttl"] = self.message_ttl_ms
        if self.delivery_limit is not None:
            arguments["x-delivery-limit"] = self.delivery_limit
        return arguments

    async def declare(self, channel: aio_pika.abc.AbstractChannel) -> aio_pika.abc.AbstractQueue:
        exchange = await channel.declare_exchange(self.exchange, aio_pika.ExchangeType.FANOUT, durable=True)
        await channel.declare_queue(self.dead_letter_queue, durable=True, arguments=dict(_QUORUM))
        queue = await channel.declare_queue(self.queue, durable=True, arguments=self.queue_arguments())
        await queue.bind(exchange)
        if self.retry_queue:
            await channel.declare_queue(
                self.retry_queue,
                durable=True,
                arguments={**_QUORUM, "x-dead-letter-exchange": "", "x-dead-letter-routing-key": self.queue},
            )
        return queue


class _BrokerSettings(Protocol):
    event_redelivery_window_hours: int
    retry_max_attempts: int


def broker_limits(settings: _BrokerSettings) -> dict[str, int]:
    """Límites de la cola principal desde la configuración operativa (una sola fuente para FR-068b y la cola)."""
    return {
        "message_ttl_ms": settings.event_redelivery_window_hours * 3_600_000,
        "delivery_limit": settings.retry_max_attempts,
    }


def actualizar_topology(prefix: str = "", *, message_ttl_ms: int | None = None, delivery_limit: int | None = None) -> Topology:
    """`recomendacion.actualizar.v3` (RD-116): exchange propio, separado del de v2, que este worker no consume.

    Las colas conservan su nombre: son nuestras y no forman parte del contrato.
    """
    return Topology(
        exchange=f"{prefix}recomendacion.actualizar.v3",
        queue=f"{prefix}recomendaciones.recomendacion-actualizar",
        dead_letter_queue=f"{prefix}recomendaciones.recomendacion-actualizar.dlq",
        retry_queue=f"{prefix}recomendaciones.recomendacion-actualizar.retry",
        message_ttl_ms=message_ttl_ms,
        delivery_limit=delivery_limit,
        required_headers=transport_headers(),
    )


def eliminado_topology(prefix: str = "", *, message_ttl_ms: int | None = None, delivery_limit: int | None = None) -> Topology:
    return Topology(
        exchange=f"{prefix}usuario.eliminado",
        queue=f"{prefix}recomendaciones.usuario-eliminado",
        dead_letter_queue=f"{prefix}recomendaciones.usuario-eliminado.dlq",
        retry_queue=f"{prefix}recomendaciones.usuario-eliminado.retry",
        message_ttl_ms=message_ttl_ms,
        delivery_limit=delivery_limit,
    )
