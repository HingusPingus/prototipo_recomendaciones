"""T039 — métricas Prometheus (FR-042…FR-044, FR-025d, FR-095a)."""

from __future__ import annotations

import asyncio

from recomendaciones.observability.metrics import SPECS, Metrics
from recomendaciones.worker.consumer import EventConsumer
from tests.contract.conftest import auth
from tests.integration import seed
from tests.integration.test_retry_dlq import _body, _publish, _topology

REQUIRED = {
    "reco_cache_hits_total": ("counter", ("result_type",)),
    "reco_request_duration_seconds": ("histogram", ("endpoint",)),
    "reco_recompute_total": ("counter", ("status", "module")),
    "reco_recompute_duration_seconds": ("histogram", ("module",)),
    "reco_dlq_messages_total": ("counter", ("reason",)),
    "reco_queue_depth": ("gauge", ("queue",)),
    "catalog_sync_last_success_timestamp": ("gauge", ()),
    "reco_sync_duration_seconds": ("histogram", ()),
    "reco_cross_module_propagation_total": ("counter", ("propagated",)),
    "reco_active_config_version": ("gauge", ("config_version", "component")),
    # agregadas por RD-100…RD-111: declaradas acá, emitidas por la tarea que produce el hecho
    "recompute_requests_pending": ("gauge", ()),
    "recompute_requests_dropped_total": ("counter", ()),
    "diversity_cap_relaxed_total": ("counter", ("module",)),
    "declarable_tags_total": ("gauge", ("module",)),
    "fallback_new_item_share": ("gauge", ("module", "kind")),
    "suppressions_unverified_total": ("gauge", ()),
}


def test_registry_declares_every_required_metric() -> None:
    for name, (kind, labels) in REQUIRED.items():
        assert name in SPECS, name
        assert SPECS[name].kind == kind and SPECS[name].labels == labels, name


def test_no_label_is_high_cardinality_or_personal() -> None:
    forbidden = {"user_id", "item_id", "event_id", "email", "birth_date", "region", "origin_interaction_id"}
    assert not {label for spec in SPECS.values() for label in spec.labels} & forbidden


def test_api_emits_hits_by_result_type_latency_and_active_version(api, valid_env, db_factory) -> None:
    client, services = api
    metrics: Metrics = services.metrics
    with db_factory.begin() as s:
        user = seed.user(s)
        seed.tags(s, ["horror"])
        seed.declare(s, user, "peliculas", ["horror"])
    client.get(f"/internal/v1/recommendations/{user}", params={"module": "peliculas"}, headers=auth(valid_env))
    assert metrics.value("reco_cache_hits_total", result_type="empty_pending") == 1
    assert metrics.value("reco_request_duration_seconds", endpoint="/internal/v1/recommendations/{user_id}") == 1
    assert metrics.value("reco_active_config_version", config_version=services.engine_config.config_version, component="api") == 1
    assert metrics.value("reco_recompute_signal_failures_total") == 0


async def test_worker_emits_dlq_and_queue_depth(amqp_url: str) -> None:
    metrics = Metrics()
    topology = _topology()
    consumer = EventConsumer(
        amqp_url, topology, lambda e: "recomputed", on_dead_letter=lambda reason: metrics.inc("reco_dlq_messages_total", reason=reason)
    )
    await consumer.start()
    try:
        broken = _body()
        broken.pop("signal_type")
        await _publish(amqp_url, topology, broken)
        for _ in range(50):
            if metrics.value("reco_dlq_messages_total", reason="invalid_payload"):
                break
            await asyncio.sleep(0.1)
        depth = await consumer.queue_depth()
        metrics.set("reco_queue_depth", depth, queue=topology.queue)
    finally:
        await consumer.stop()
    assert metrics.value("reco_dlq_messages_total", reason="invalid_payload") == 1
    assert metrics.value("reco_queue_depth", queue=topology.queue) == 0


async def test_queue_depth_reports_the_messages_actually_waiting(amqp_url: str) -> None:
    """`reco_queue_depth` alimenta QueueDepthGrowth: un valor congelado deja la alerta ciega.

    Una declaración pasiva sobre el canal que ya declaró la cola devuelve el conteo de la primera declaración;
    la profundidad debe leerse en un canal propio.
    """
    import threading

    release = threading.Event()
    started = threading.Event()

    def blocked(event) -> str:
        started.set()
        release.wait(10)
        return "recomputed"

    topology = _topology()
    consumer = EventConsumer(amqp_url, topology, blocked, prefetch=1)
    await consumer.start()
    try:
        for _ in range(5):
            await _publish(amqp_url, topology, _body())
        for _ in range(50):
            if started.is_set():
                break
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.3)
        assert await consumer.queue_depth() == 4  # uno en proceso (sin confirmar), cuatro esperando
    finally:
        release.set()
        await consumer.stop()
