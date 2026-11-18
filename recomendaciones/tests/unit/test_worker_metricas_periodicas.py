"""S11 del plan de pruebas: si el broker o la base se caen, refrescar las métricas no puede tumbar el worker.

Lo encontró la prueba de caos de punta a punta: con RabbitMQ caído, medir la profundidad de la cola pedía un canal a la
conexión que se estaba reconectando, el RuntimeError no se atrapaba y el proceso terminaba con código 1. El worker
quedaba muerto aunque el broker volviera.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from recomendaciones.observability.metrics import Metrics
from recomendaciones.worker.process_metrics import ProcessMetricsState
from recomendaciones.worker.runtime import refrescar_metricas_periodicas
from recomendaciones.worker.topology import actualizar_topology, eliminado_topology


class ColaCaida:
    async def queue_depth(self) -> int:
        raise RuntimeError("Connection was not opened")

    async def dead_letter_depth(self) -> int:
        raise RuntimeError("Connection was not opened")


class ColaSana:
    def __init__(self, listos: int, muertos: int) -> None:
        self.listos, self.muertos = listos, muertos

    async def queue_depth(self) -> int:
        return self.listos

    async def dead_letter_depth(self) -> int:
        return self.muertos


def _base_caida():  # noqa: ANN202
    raise ConnectionError("la base no responde")


def test_un_broker_caido_no_tumba_el_refresco_y_la_otra_cola_se_sigue_midiendo() -> None:
    metrics = Metrics()
    runtime = SimpleNamespace(metrics=metrics, factory=_base_caida)

    asyncio.run(refrescar_metricas_periodicas(runtime, ProcessMetricsState(), ColaCaida(), ColaSana(3, 1)))

    assert metrics.value("reco_queue_depth", queue=eliminado_topology().queue) == 3
    assert metrics.value("reco_dead_letter_depth", queue=eliminado_topology().dead_letter_queue) == 1


def test_con_todo_caido_el_refresco_termina_sin_excepcion() -> None:
    runtime = SimpleNamespace(metrics=Metrics(), factory=_base_caida)
    asyncio.run(refrescar_metricas_periodicas(runtime, ProcessMetricsState(), ColaCaida(), ColaCaida()))
    assert actualizar_topology().queue  # la topología sigue resolviéndose: no hubo nada que reintentar a mano
