"""Recálculo de popularidad por ventana (T063): productora única de `item_popularity` e `item_promotions`.

Puntaje = **límite inferior del intervalo de Wilson** sobre la tasa de conversión a like entre quienes
interactuaron con el ítem dentro de la ventana (FR-033a3, RD-44):

- denominador: usuarios **distintos** con alguna señal (like, dislike o consumo) en la ventana (RD-45);
- numerador: usuarios distintos cuya señal de preferencia vigente en la ventana es un like;
- el consumo participa del denominador y no del numerador (FR-033a3b); `n = 0` ⟹ puntaje 0 (FR-033a4).

Se escribe por `config_version` —cambiar de versión no pisa la anterior (RD-13)— y solo sobre ítems
vigentes (FR-033a1). `computed_at` por fila y escritura por lotes (un módulo por transacción): un batch
parcialmente fallido deja visible qué filas no se recalcularon. La promoción al conjunto general se
**registra** la primera vez que `engaged_user_count` alcanza `emergent_evidence_threshold` y nunca se
borra ni modifica (FR-033a6e, DI-27). Numerador y denominador se persisten junto al puntaje (FR-033a5).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from recomendaciones.config.errors import ConfigurationError
from recomendaciones.config.loader import EngineConfig
from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.db.models import ItemPopularity, ItemPromotion
from recomendaciones.storage.db.session import SessionFactory

MODULES = ("peliculas", "juegos")

_COUNTS_SQL = sa.text(
    """
    WITH w AS (
        SELECT id, user_id, item_id, signal_type, occurred_at FROM user_signals
        WHERE occurred_at >= :start AND occurred_at <= :now
    ),
    engaged AS (SELECT item_id, count(DISTINCT user_id) AS n FROM w GROUP BY item_id),
    vigente AS (
        SELECT DISTINCT ON (user_id, item_id) user_id, item_id, signal_type FROM w
        WHERE signal_type IN ('like', 'dislike')
        ORDER BY user_id, item_id, occurred_at DESC, id DESC
    ),
    likes AS (SELECT item_id, count(*) AS l FROM vigente WHERE signal_type = 'like' GROUP BY item_id)
    SELECT i.id, COALESCE(l.l, 0) AS like_count, COALESCE(e.n, 0) AS engaged
    FROM items i
    LEFT JOIN engaged e ON e.item_id = i.id
    LEFT JOIN likes l ON l.item_id = i.id
    WHERE i.status = 'available' AND i.module = :module
    ORDER BY i.id
    """
)


def wilson_lower_bound(likes: int, n: int, z: float) -> float:
    if n == 0:
        return 0.0
    p = likes / n
    z2 = z * z
    value = (p + z2 / (2 * n) - z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / (1 + z2 / n)
    return min(1.0, max(0.0, value))


class PopularityJob:
    def __init__(
        self,
        factory: SessionFactory,
        config: EngineConfig,
        metrics: Metrics,
        *,
        signal_retention_days: int,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not config.popularity_window_days < signal_retention_days:
            raise ConfigurationError(
                "popularity_window_days debe ser menor que signal_retention_days (FR-068b): "
                f"{config.popularity_window_days} ≥ {signal_retention_days}"
            )
        self._factory = factory
        self._cfg = config
        self.metrics = metrics
        self._now = now

    def _write_chunk(self, s: Session, rows: list[tuple]) -> None:
        now = self._now()
        for item_id, likes, engaged in rows:
            score = wilson_lower_bound(int(likes), int(engaged), self._cfg.popularity_confidence_z)
            stmt = insert(ItemPopularity).values(
                item_id=item_id,
                config_version=self._cfg.config_version,
                like_count=int(likes),
                engaged_user_count=int(engaged),
                popularity_score=score,
                computed_at=now,
            )
            s.execute(
                stmt.on_conflict_do_update(
                    index_elements=[ItemPopularity.item_id, ItemPopularity.config_version],
                    set_={
                        "like_count": stmt.excluded.like_count,
                        "engaged_user_count": stmt.excluded.engaged_user_count,
                        "popularity_score": stmt.excluded.popularity_score,
                        "computed_at": stmt.excluded.computed_at,
                    },
                )
            )
            if int(engaged) >= self._cfg.emergent_evidence_threshold:
                s.execute(
                    insert(ItemPromotion)
                    .values(item_id=item_id, promoted_at=now, config_version=self._cfg.config_version)
                    .on_conflict_do_nothing(index_elements=[ItemPromotion.item_id])  # definitiva: nunca se actualiza
                )

    def run(self) -> int:
        now = self._now()
        start = now - timedelta(days=self._cfg.popularity_window_days)
        written = 0
        for module in MODULES:
            with self._factory.begin() as s:
                rows = [tuple(r) for r in s.execute(_COUNTS_SQL, {"start": start, "now": now, "module": module})]
                if rows:
                    self._write_chunk(s, rows)
                written += len(rows)
        self.metrics.set("catalog_popularity_last_success_timestamp", now.timestamp())
        return written
