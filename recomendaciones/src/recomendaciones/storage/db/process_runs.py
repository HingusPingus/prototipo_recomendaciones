"""Registro de corridas de los procesos de una corrida —transformer y jobs batch— (T066, §2.17).

Escritor único de `process_runs`: cada proceso deja su fila al terminar, también cuando falla, y poda las
suyas viejas. La poda conserva la última corrida exitosa y la última fallida de cada componente: un job que
dejó de correr hace más de la retención no debe perder el timestamp del que depende su alerta de
vencimiento.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from recomendaciones.storage.db.models import ProcessRun
from recomendaciones.storage.db.session import SessionFactory

log = logging.getLogger(__name__)

RETENTION_DAYS = 30

_PRUNE = sa.text(
    """
    DELETE FROM process_runs
    WHERE component = :component
      AND finished_at < now() - make_interval(days => :days)
      AND id NOT IN (SELECT max(id) FROM process_runs WHERE component = :component GROUP BY status)
    """
)


def record_process_run(
    factory: SessionFactory,
    component: str,
    *,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    failure_reason: str | None,
    metrics: dict[str, Any],
    details: dict[str, Any] | None = None,
) -> None:
    """Persiste la corrida y poda las viejas del mismo componente. Nunca enmascara la falla del proceso."""
    try:
        with factory.begin() as s:
            s.add(
                ProcessRun(
                    component=component,
                    started_at=started_at,
                    finished_at=finished_at,
                    status=status,
                    failure_reason=failure_reason,
                    metrics=metrics,
                    details=details,
                )
            )
            s.flush()
            s.execute(_PRUNE, {"component": component, "days": RETENTION_DAYS})
    except Exception:  # noqa: BLE001 — sin base no hay dónde registrar; la corrida conserva su propio resultado
        log.exception("no se pudo registrar la corrida en process_runs", extra={"component": component, "status": status})


@dataclass
class RunOutcome:
    """Lo que el cuerpo de la corrida declara. Sin declaración explícita de éxito, la corrida es fallida."""

    status: str = "failed"
    failure_reason: str | None = None
    details: dict[str, Any] | None = None


@contextmanager
def recorded_run(factory: SessionFactory, component: str, metrics: object) -> Iterator[RunOutcome]:
    """Envuelve una corrida de transformer o batch y la registra al salir, haya terminado o no (FR-044)."""
    outcome = RunOutcome()
    started = datetime.now(UTC)
    try:
        yield outcome
    except BaseException as exc:
        outcome.status = "failed"
        outcome.failure_reason = outcome.failure_reason or f"{type(exc).__name__}: {exc}"
        raise
    finally:
        snapshot = metrics.snapshot() if hasattr(metrics, "snapshot") else {}
        record_process_run(
            factory,
            component,
            started_at=started,
            finished_at=datetime.now(UTC),
            status=outcome.status,
            failure_reason=outcome.failure_reason,
            metrics=snapshot,
            details=outcome.details,
        )
