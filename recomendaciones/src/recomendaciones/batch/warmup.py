"""Warm-up tras pérdida total de Redis (T022, FR-066, §3.3).

Proceso **dedicado**, invocable manualmente (`reco-batch warmup`); nunca lo dispara el tráfico de
lectura, que es lo que evita la avalancha auto-infligida. Encola una solicitud por cada módulo
declarado de cada usuario en `recompute:requests` con límite de tasa, priorizando a los usuarios con
actividad más reciente. Reconstruye íntegramente desde Postgres (INV-2).

Reanudable sin estado propio: al relanzarlo omite los pares que ya tienen `reco:` vigente bajo la
versión activa (no duplica trabajo) y vuelve a encolar el resto (no pierde usuarios); las solicitudes
en vuelo las suprime `recompute:lock`.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache.recompute import RecomputeSignaler
from recomendaciones.storage.cache.repository import RecommendationRepository

_PRIORITY_SQL = sa.text(
    """
    SELECT d.user_id, d.module::text AS module
    FROM (SELECT DISTINCT user_id, module FROM user_declared_tags) d
    LEFT JOIN (SELECT user_id, max(received_at) AS last_seen FROM user_signals GROUP BY user_id) a
           ON a.user_id = d.user_id
    ORDER BY a.last_seen DESC NULLS LAST, d.user_id, d.module
    """
)


@dataclass
class WarmupReport:
    enqueued: int = 0
    skipped_fresh: int = 0
    suppressed: int = 0


class WarmupJob:
    def __init__(
        self,
        factory: sessionmaker[Session],
        signaler: RecomputeSignaler,
        repository: RecommendationRepository,
        *,
        active_version: str,
        rate_per_second: float,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._factory = factory
        self._signaler = signaler
        self._repository = repository
        self._active = active_version
        self._interval = 1.0 / rate_per_second
        self._monotonic = monotonic
        self._sleep = sleep

    def _pairs(self) -> Iterator[tuple[uuid.UUID, Module]]:
        with self._factory() as s:
            for row in s.execute(_PRIORITY_SQL):
                yield row.user_id, Module(row.module)

    def run(self) -> WarmupReport:
        report = WarmupReport()
        next_slot = self._monotonic()
        for user_id, module in self._pairs():
            if self._repository.read_fresh(self._active, user_id, module) is not None:
                report.skipped_fresh += 1
                continue
            now = self._monotonic()
            if now < next_slot:
                self._sleep(next_slot - now)
            next_slot = max(next_slot, self._monotonic()) + self._interval
            if self._signaler.request(user_id, module, "warmup"):
                report.enqueued += 1
            else:
                report.suppressed += 1
        return report
