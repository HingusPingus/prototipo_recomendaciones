"""Proceso Data Transformer: una corrida de sincronización y, a continuación, el job de vocabulario (T029, T030)."""

from __future__ import annotations

import logging

from recomendaciones.bootstrap import build_runtime
from recomendaciones.config.settings import Settings
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.transformer.client import ApiGeneralClient
from recomendaciones.transformer.pipeline import SyncPipeline
from recomendaciones.transformer.vocabulary_sync import VocabularySync

log = logging.getLogger(__name__)


def run_once(settings: Settings, *, transport=None) -> int:  # noqa: ANN001 — httpx.BaseTransport para tests
    runtime = build_runtime(settings, "transformer")
    client = ApiGeneralClient(
        settings.api_general_base_url,
        settings.internal_api_key.get_secret_value(),
        timeout_seconds=settings.api_general_timeout_seconds,
        transport=transport,
    )
    try:
        report = SyncPipeline(
            runtime.factory,
            client,
            FiltersCache(runtime.cache, DbFiltersSource(runtime.factory), runtime.ttls.filters),
            runtime.cache,
            runtime.config,
            runtime.metrics,
            volume_delta_ratio=settings.sync_volume_delta_ratio,
            redelivery_window_hours=settings.event_redelivery_window_hours,
        ).run()
    finally:
        client.close()
    if report.counts:  # hubo datos materializados: el vocabulario y los vectores se reconcilian a continuación
        VocabularySync(runtime.factory, runtime.metrics).run()
    log.info("corrida de sincronización", extra={"status": report.status, "sync_run_id": report.run_id})
    return 0 if report.status == "success" else 1
