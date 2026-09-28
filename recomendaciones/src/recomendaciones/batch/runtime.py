"""Despachador de jobs batch (`reco-batch <job>`)."""

from __future__ import annotations

import logging

from recomendaciones.batch.fallback import FallbackJob
from recomendaciones.batch.popularidad import PopularityJob
from recomendaciones.batch.warmup import WarmupJob
from recomendaciones.bootstrap import build_runtime
from recomendaciones.config.settings import Settings
from recomendaciones.storage.cache.recompute import RecomputeStream

log = logging.getLogger(__name__)
JOBS = ("popularity", "fallback", "warmup")


def run_job(settings: Settings, args: list[str], **overrides: object) -> int:
    if not args or args[0] not in JOBS:
        log.error("job desconocido; disponibles: %s", ", ".join(JOBS))
        return 2
    runtime = build_runtime(settings, f"batch:{args[0]}", **overrides)  # type: ignore[arg-type]
    job = args[0]
    if job == "popularity":
        PopularityJob(runtime.factory, runtime.config, runtime.metrics, signal_retention_days=settings.signal_retention_days).run()
    elif job == "fallback":
        FallbackJob(runtime.factory, runtime.repository, runtime.config, runtime.metrics).run()
    elif job == "warmup":
        signaler = RecomputeStream(runtime.cache, maxlen=settings.recompute_requests_maxlen, ttl_suppress=runtime.ttls.suppress)
        WarmupJob(
            runtime.factory, signaler, runtime.repository, active_version=runtime.config.config_version, rate_per_second=settings.warmup_rate_per_second
        ).run()
    return 0
