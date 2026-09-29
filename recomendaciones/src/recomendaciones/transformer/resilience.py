"""Resiliencia de la sincronización ante `api-general` no disponible (T032, FR-019, FR-040).

La caída del origen degrada la **frescura**, no la disponibilidad: cada intento fallido queda registrado
como corrida `failed` sin tocar el estado materializado (la escritura es una sola transacción, T029), y la
API sigue sirviendo lo precomputado. Se reintenta con backoff exponencial; agotado, la alerta de
frescura (`catalog_sync_last_success_timestamp`, T042) es la que avisa.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Protocol

log = logging.getLogger(__name__)


class _Runnable(Protocol):
    def run(self): ...  # noqa: ANN201


def run_with_retries(
    pipeline: _Runnable,
    *,
    max_attempts: int,
    backoff_base_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
):  # noqa: ANN201 — SyncReport
    report = pipeline.run()
    attempt = 1
    while report.status != "success" and report.failure_reason and "api-general" in report.failure_reason and attempt < max_attempts:
        delay = backoff_base_seconds * 2 ** (attempt - 1)
        log.warning("api-general no disponible; reintento de la sincronización en %.1fs", delay, extra={"attempt": attempt})
        sleep(delay)
        report = pipeline.run()
        attempt += 1
    return report
