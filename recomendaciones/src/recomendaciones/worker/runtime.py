"""Proceso worker: consume `recomendacion.actualizar` y `recompute:requests` (T023, T027)."""

from __future__ import annotations

import asyncio
import logging
import signal
import socket

from prometheus_client import start_http_server

from recomendaciones.bootstrap import Runtime, build_runtime
from recomendaciones.config.settings import Settings
from recomendaciones.shared.errors import CacheUnavailable
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.db.exclusions import ExclusionResolver
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.worker.consumer import EventConsumer
from recomendaciones.worker.handler import ActualizarHandler, Recomputer
from recomendaciones.worker.idempotency import EventIdempotency
from recomendaciones.worker.requests_stream import RecomputeRequestConsumer
from recomendaciones.worker.signals import SignalIngestor
from recomendaciones.worker.topology import actualizar_topology

log = logging.getLogger(__name__)


def build_worker(runtime: Runtime) -> tuple[EventConsumer, RecomputeRequestConsumer]:
    settings = runtime.settings
    recomputer = Recomputer(runtime.factory, runtime.repository, runtime.config, runtime.metrics)
    filters = FiltersCache(runtime.cache, DbFiltersSource(runtime.factory), runtime.ttls.filters)
    handler = ActualizarHandler(
        idempotency=EventIdempotency(
            runtime.cache, runtime.factory, ttl_dedupe_seconds=runtime.ttls.dedupe, retention_hours=settings.idempotency_retention_hours
        ),
        ingestor=SignalIngestor(runtime.factory, ExclusionResolver(filters.invalidate), runtime.metrics),
        should_recompute=lambda event: True,  # Fase 1: recalcula por evento; el umbral de FR-080a llega con T060
        recompute=recomputer,
    )
    events = EventConsumer(
        settings.amqp_url.get_secret_value(),
        actualizar_topology(),
        handler,
        on_dead_letter=lambda reason: runtime.metrics.inc("reco_dlq_messages_total", reason=reason),
    )
    requests = RecomputeRequestConsumer(
        runtime.cache,
        recomputer,
        runtime.metrics,
        consumer_name=socket.gethostname(),
        max_deliveries=settings.recompute_requests_max_deliveries,
        # un XREADGROUP bloqueante más largo que el timeout del socket se leería como caída de Redis
        block_ms=max(1, int(settings.redis_timeout_seconds * 1000 * 0.5)),
    )
    return events, requests


async def serve(settings: Settings, *, stop: asyncio.Event | None = None) -> None:
    runtime = build_runtime(settings, "worker")
    start_http_server(settings.metrics_port, registry=runtime.metrics.registry)
    events, requests = build_worker(runtime)
    stop = stop or asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass
    await events.start()
    log.info("worker en marcha", extra={"config_version": runtime.config.config_version})
    backoff = 0.1
    try:
        while not stop.is_set():
            try:
                handled = await asyncio.to_thread(requests.poll_once)
                backoff = 0.1
            except CacheUnavailable:  # Redis caído: el worker sobrevive y reintenta con backoff
                log.warning("Redis no disponible para recompute:requests; reintento en %.1fs", backoff)
                handled = 0
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, settings.retry_backoff_base_seconds * 32)
            if not handled:
                await asyncio.sleep(0.1)
    finally:
        await events.stop()
