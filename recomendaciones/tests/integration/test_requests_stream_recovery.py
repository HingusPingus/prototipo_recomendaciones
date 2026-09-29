"""T046 (hallazgo del runbook) — un worker vivo sobrevive a la pérdida total de Redis (T022, FR-066).

Al escribir el procedimiento de reconstrucción apareció que el consumidor recordaba haber creado el grupo
de `recompute:requests`: tras un `FLUSHALL` cada `XREADGROUP` fallaba con `NOGROUP` hasta reiniciar el
proceso, y el warm-up encolaba solicitudes que nadie atendía.
"""

from __future__ import annotations

import uuid

from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.worker.handler import ModuleOutcome
from recomendaciones.worker.requests_stream import RecomputeRequestConsumer


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, Module, str]] = []

    def recompute(self, user_id: uuid.UUID, module: Module, reason: str) -> ModuleOutcome:
        self.calls.append((user_id, module, reason))
        return ModuleOutcome("written")


def test_consumer_recreates_its_group_after_redis_loses_everything(redis_client) -> None:
    cache = CacheClient(redis_client)
    recorder = _Recorder()
    consumer = RecomputeRequestConsumer(cache, recorder, Metrics(), consumer_name="w1", max_deliveries=5, block_ms=10)
    stream = RecomputeStream(cache, maxlen=1000, ttl_suppress=300)
    before, after = uuid.uuid4(), uuid.uuid4()

    stream.request(before, Module.PELICULAS, "miss")
    consumer.poll_once()
    redis_client.flushall()  # pérdida total: se van el Stream, el grupo y los locks

    stream.request(after, Module.JUEGOS, "warmup")  # el warm-up vuelve a encolar
    consumer.poll_once()  # no debe fallar con NOGROUP
    consumer.poll_once()
    assert [c[0] for c in recorder.calls] == [before, after]
