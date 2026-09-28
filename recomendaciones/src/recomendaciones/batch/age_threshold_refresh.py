"""Job `age_threshold_refresh`: refresco de derivados etarios (T051, `data-model.md` §7.5).

La edad no se almacena: `max_age_ordinal` es un derivado de `birth_date` que caduca sin que nadie escriba
nada. Dos criterios de selección **separados**, porque son dos causas distintas:

- **A — cruce de umbral**: igualdad exacta sobre `birth_date` (`idx_users_birth_date`) con las fechas de
  quienes cumplen hoy la edad de un umbral del catálogo. No deja rastro de escritura: unificarlo con B lo
  perdería. Quien nació un 29 de febrero cumple el 1 de marzo de los años comunes.
- **B — escala no compatible**: `age_config_version` fuera de las versiones con catálogo etario idéntico al
  activo (§3.1.1). Normalmente vacío; se puebla al activar un catálogo nuevo.

Por usuario afectado: Redis primero (FR-080c) —`filters:`, `reco:` y `reco:stale:` de toda versión y
módulo (DI-2c)—, luego Postgres, una segunda invalidación de `filters:` tras confirmar (la carrera del
resolutor de exclusiones) y la solicitud de recálculo por `recompute:requests` con `reason =
'age_threshold'` para cada módulo declarado, respetando `recompute:lock` (RD-100). `recompute:lock` no se
borra: es lo que suprime la solicitud duplicada. Si la solicitud se pierde, el siguiente miss la reemite.

Idempotente: un usuario cuyo ordinal ya es el correcto no se toca ni se solicita. `age_derived_at` se
escribe y no se lee (RD-6). `items.min_age_ordinal` lo rederiva la sincronización, su único escritor (DI-13).
"""

from __future__ import annotations

import calendar
import logging
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import sqlalchemy as sa

from recomendaciones.config.loader import EngineConfig
from recomendaciones.engine.age import derive_max_age_ordinal
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient, delete_user_scope
from recomendaciones.storage.cache.recompute import RecomputeSignaler
from recomendaciones.storage.db.models import User, UserDeclaredTag
from recomendaciones.storage.db.session import SessionFactory

log = logging.getLogger(__name__)
_CHUNK = 1000


def birth_dates_turning(today: date, ages: Iterable[int]) -> tuple[date, ...]:
    """Fechas de nacimiento de quienes cumplen hoy exactamente cada edad (causa A)."""
    found: list[date] = []
    for age in ages:
        year = today.year - age
        if today.month != 2 or today.day != 29 or calendar.isleap(year):
            found.append(date(year, today.month, today.day))
        if (today.month, today.day) == (3, 1) and not calendar.isleap(today.year) and calendar.isleap(year):
            found.append(date(year, 2, 29))
    return tuple(sorted(set(found)))


def _invalidation_patterns(user_id: uuid.UUID) -> tuple[str, ...]:
    return tuple(p for p in keys.user_scoped_patterns(user_id) if not p.startswith("recompute:lock:"))


@dataclass(frozen=True, slots=True)
class AgeRefreshReport:
    threshold_crossings: int
    stale_config_rederived: int
    recompute_requested: int


class AgeThresholdRefreshJob:
    def __init__(
        self,
        factory: SessionFactory,
        cache: CacheClient,
        signaler: RecomputeSignaler,
        config: EngineConfig,
        metrics: Metrics,
        *,
        compatible_versions: frozenset[str],
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self._factory = factory
        self._cache = cache
        self._signaler = signaler
        self._cfg = config
        self.metrics = metrics
        self._compatible = compatible_versions | {config.config_version}
        self._today = today

    def _select(self, today: date) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
        columns = (User.id, User.birth_date, User.max_age_ordinal, User.age_config_version)
        dates = birth_dates_turning(today, self._cfg.age_thresholds)
        with self._factory() as s:
            crossing_rows = s.execute(sa.select(*columns).where(User.birth_date.in_(dates))).all() if dates else []
            stale_rows = s.execute(sa.select(*columns).where(User.age_config_version.not_in(sorted(self._compatible)))).all()
        stale = {r.id: derive_max_age_ordinal(r.birth_date, today, self._cfg) for r in stale_rows}
        crossing = {}
        for r in crossing_rows:
            ordinal = derive_max_age_ordinal(r.birth_date, today, self._cfg)
            if r.id not in stale and ordinal != r.max_age_ordinal:
                crossing[r.id] = ordinal
        return crossing, stale

    def _apply(self, changes: dict[uuid.UUID, int]) -> int:
        requested = 0
        ordered = sorted(changes, key=str)
        for start in range(0, len(ordered), _CHUNK):
            chunk = ordered[start : start + _CHUNK]
            for user_id in chunk:  # Redis primero (FR-080c, DI-2c)
                delete_user_scope(self._cache, _invalidation_patterns(user_id))
            with self._factory.begin() as s:
                for user_id in chunk:
                    s.execute(
                        sa.update(User)
                        .where(User.id == user_id)
                        .values(max_age_ordinal=changes[user_id], age_config_version=self._cfg.config_version, age_derived_at=sa.func.now())
                    )
                declared = s.execute(
                    sa.select(UserDeclaredTag.user_id, UserDeclaredTag.module).where(UserDeclaredTag.user_id.in_(chunk)).distinct()
                ).all()
            self._cache.delete(*(keys.filters_key(u) for u in chunk))  # tras confirmar: cierra la carrera del repoblado
            for user_id, module in sorted(declared, key=lambda r: (str(r[0]), r[1])):
                requested += self._signaler.request(user_id, Module(module), "age_threshold")
        return requested

    def run(self) -> AgeRefreshReport:
        today = self._today()
        crossing, stale = self._select(today)
        log.info(
            "refresco etario: selección",
            extra={"reco_threshold_crossings": len(crossing), "reco_stale_config_users": len(stale), "reco_today": today.isoformat()},
        )
        requested = self._apply(crossing | stale)
        with self._factory() as s:
            remaining = s.scalar(sa.select(sa.func.count()).select_from(User).where(User.age_config_version.not_in(sorted(self._compatible))))
        self.metrics.inc("age_threshold_crossings_total", len(crossing))
        self.metrics.set("age_stale_config_users_total", float(remaining or 0))
        self.metrics.set("age_refresh_last_success_timestamp", datetime.now(UTC).timestamp())
        report = AgeRefreshReport(len(crossing), len(stale), requested)
        log.info(
            "refresco etario: fin",
            extra={
                "reco_threshold_crossings": report.threshold_crossings,
                "reco_stale_config_rederived": report.stale_config_rederived,
                "reco_recompute_requested": report.recompute_requested,
            },
        )
        return report
