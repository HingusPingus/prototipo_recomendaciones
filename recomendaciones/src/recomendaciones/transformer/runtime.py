"""Proceso Data Transformer: una corrida de sincronización y, a continuación, el job de vocabulario (T029, T030)."""

from __future__ import annotations

import logging

from recomendaciones.bootstrap import build_runtime
from recomendaciones.config.settings import Settings
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.storage.db.process_runs import recorded_run
from recomendaciones.transformer.client import ApiGeneralClient
from recomendaciones.transformer.pipeline import SyncPipeline
from recomendaciones.transformer.resilience import run_with_retries
from recomendaciones.transformer.vocabulary_sync import VocabularySync

log = logging.getLogger(__name__)


def run_once(settings: Settings, *, transport=None) -> int:  # noqa: ANN001 — httpx.BaseTransport para tests
    runtime = build_runtime(settings, "transformer")
    with recorded_run(runtime.factory, "transformer", runtime.metrics) as outcome:  # T066
        return _run(settings, runtime, transport, outcome)


def _run(settings: Settings, runtime, transport, outcome) -> int:  # noqa: ANN001 — Runtime, httpx.BaseTransport, RunOutcome
    client = ApiGeneralClient(
        settings.api_general_base_url,
        settings.internal_api_key.get_secret_value(),
        timeout_seconds=settings.api_general_timeout_seconds,
        transport=transport,
    )
    try:
        pipeline = SyncPipeline(
            runtime.factory,
            client,
            FiltersCache(runtime.cache, DbFiltersSource(runtime.factory), runtime.ttls.filters),
            runtime.cache,
            runtime.config,
            runtime.metrics,
            volume_delta_ratio=settings.sync_volume_delta_ratio,
            redelivery_window_hours=settings.event_redelivery_window_hours,
        )
        report = run_with_retries(
            pipeline, max_attempts=settings.retry_max_attempts, backoff_base_seconds=settings.retry_backoff_base_seconds
        )
    finally:
        client.close()
    if report.counts:  # hubo datos materializados: el vocabulario y los vectores se reconcilian a continuación
        VocabularySync(runtime.factory, runtime.metrics).run()
    log.info("corrida de sincronización", extra={"status": report.status, "sync_run_id": report.run_id})
    outcome.status = "success" if report.status == "success" else "failed"
    outcome.failure_reason = None if report.status == "success" else report.reason
    return 0 if report.status == "success" else 1
