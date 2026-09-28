"""Proceso worker: consume `recomendacion.actualizar` y `recompute:requests` (T023, T027)."""

from __future__ import annotations

import asyncio
import logging
import signal
import socket

from prometheus_client import start_http_server

from recomendaciones.bootstrap import Runtime, build_runtime
from recomendaciones.config.settings import Settings
from recomendaciones.observability.health import start_health_server
from recomendaciones.worker.health import worker_health
from recomendaciones.shared.errors import CacheUnavailable
from recomendaciones.transformer.freshness import refresh_sync_metrics
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.db.exclusions import ExclusionResolver
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.worker.consumer import EventConsumer, RetryPolicy
from recomendaciones.worker.handler import ActualizarHandler, Recomputer
from recomendaciones.worker.idempotency import EventIdempotency
from recomendaciones.worker.requests_stream import RecomputeRequestConsumer
from recomendaciones.worker.signals import SignalIngestor
from recomendaciones.worker.trigger import InteractionTrigger
from recomendaciones.worker.topology import actualizar_topology

log = logging.getLogger(__name__)


def build_worker(runtime: Runtime) -> tuple[EventConsumer, RecomputeRequestConsumer]:
    settings = runtime.settings
    signaler = RecomputeStream(runtime.cache, maxlen=settings.recompute_requests_maxlen, ttl_suppress=runtime.ttls.suppress)
    recomputer = Recomputer(runtime.factory, runtime.repository, runtime.config, runtime.metrics, signaler=signaler)
    filters = FiltersCache(runtime.cache, DbFiltersSource(runtime.factory), runtime.ttls.filters)
    handler = ActualizarHandler(
        idempotency=EventIdempotency(
            runtime.cache, runtime.factory, ttl_dedupe_seconds=runtime.ttls.dedupe, retention_hours=settings.idempotency_retention_hours
        ),
        ingestor=SignalIngestor(runtime.factory, ExclusionResolver(filters.invalidate), runtime.metrics),
        should_recompute=InteractionTrigger(runtime.factory, settings.interaction_recalc_threshold, cache=runtime.cache).should_recompute,
        recompute=recomputer,
    )
    events = EventConsumer(
        settings.amqp_url.get_secret_value(),
        actualizar_topology(),
        handler,
        on_dead_letter=lambda reason: runtime.metrics.inc("reco_dlq_messages_total", reason=reason),
        retry=RetryPolicy(settings.retry_max_attempts, settings.retry_backoff_base_seconds),
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
    health = start_health_server(
        settings.health_port,
        lambda: worker_health(
            cache=runtime.cache,
            factory=runtime.factory,
            amqp_url=settings.amqp_url.get_secret_value(),
            config_version=runtime.config.config_version,
        ),
    )
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
    last_refresh = 0.0
    try:
        while not stop.is_set():
            if loop.time() - last_refresh > 30:  # SC-014: la frescura se expone aunque el Data Transformer no corra
                last_refresh = loop.time()
                with runtime.factory() as s:
                    await asyncio.to_thread(refresh_sync_metrics, s, runtime.metrics)
                runtime.metrics.set("reco_queue_depth", await events.queue_depth(), queue=actualizar_topology().queue)
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
        health.shutdown()
