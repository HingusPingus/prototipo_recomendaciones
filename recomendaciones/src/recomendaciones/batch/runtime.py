"""Despachador de jobs batch (`reco-batch <job>`)."""

from __future__ import annotations

import logging

from recomendaciones.batch.age_threshold_refresh import AgeThresholdRefreshJob
from recomendaciones.batch.fallback import FallbackJob
from recomendaciones.batch.popularidad import PopularityJob
from recomendaciones.batch.purga_senales import SignalPurgeJob
from recomendaciones.batch.warmup import WarmupJob
from recomendaciones.bootstrap import build_runtime
from recomendaciones.config.loader import age_compatible_versions, load_deployed_configs
from recomendaciones.config.settings import Settings
from recomendaciones.storage.cache.recompute import RecomputeStream
from recomendaciones.storage.db.process_runs import recorded_run
from recomendaciones.worker.suppression import SuppressionProcedure, SuppressionSweep

log = logging.getLogger(__name__)
JOBS = ("popularity", "fallback", "warmup", "age-refresh", "purge-signals", "suppressions")


def run_job(settings: Settings, args: list[str], **overrides: object) -> int:
    if not args or args[0] not in JOBS:
        log.error("job desconocido; disponibles: %s", ", ".join(JOBS))
        return 2
    runtime = build_runtime(settings, f"batch:{args[0]}", **overrides)  # type: ignore[arg-type]
    with recorded_run(runtime.factory, f"batch:{args[0]}", runtime.metrics) as outcome:  # T066
        _dispatch(settings, runtime, args[0], outcome)
        outcome.status = "success"
    return 0


def _dispatch(settings: Settings, runtime, job: str, outcome) -> None:  # noqa: ANN001 — Runtime, RunOutcome
    if job == "popularity":
        PopularityJob(runtime.factory, runtime.config, runtime.metrics, signal_retention_days=settings.signal_retention_days).run()
    elif job == "fallback":
        FallbackJob(runtime.factory, runtime.repository, runtime.config, runtime.metrics).run()
    elif job == "warmup":
        signaler = RecomputeStream(runtime.cache, maxlen=settings.recompute_requests_maxlen, ttl_suppress=runtime.ttls.suppress)
        WarmupJob(
            runtime.factory, signaler, runtime.repository, active_version=runtime.config.config_version, rate_per_second=settings.warmup_rate_per_second
        ).run()
    elif job == "age-refresh":
        signaler = RecomputeStream(runtime.cache, maxlen=settings.recompute_requests_maxlen, ttl_suppress=runtime.ttls.suppress)
        compatible = age_compatible_versions(runtime.config, load_deployed_configs())
        AgeThresholdRefreshJob(runtime.factory, runtime.cache, signaler, runtime.config, runtime.metrics, compatible_versions=compatible).run()
    elif job == "purge-signals":
        outcome.details = {"signal_retention_days": settings.signal_retention_days}  # constancia de RD-54
        SignalPurgeJob(runtime.factory, runtime.config, settings, runtime.metrics).run()
    elif job == "suppressions":
        procedure = SuppressionProcedure(
            runtime.factory,
            runtime.cache,
            runtime.metrics,
            max_attempts=settings.retry_max_attempts,
            backoff_base_seconds=settings.retry_backoff_base_seconds,
        )
        SuppressionSweep(runtime.factory, procedure, runtime.metrics).run()
