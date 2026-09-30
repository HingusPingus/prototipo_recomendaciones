"""Auditorías periódicas de invariantes que el esquema no puede sostener (data-model.md §6)."""

from __future__ import annotations

import logging
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from recomendaciones.config.loader import EngineConfig
from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.db.session import SessionFactory

log = logging.getLogger(__name__)

_DECLARED_MINIMUM_SQL = sa.text(
    """
    SELECT user_id, module::text, count(*) AS n
    FROM user_declared_tags
    GROUP BY user_id, module
    HAVING count(*) < :minimum
    ORDER BY user_id, module
    """
)


def declared_minimum_violations(s: Session, minimum: int) -> list[tuple[uuid.UUID, str, int]]:
    """DI-28: todo módulo declarado tiene al menos `declared_tags_min` filas **propias**.

    Es el único invariante que depende enteramente de la capa de aplicación: no hay restricción de
    tabla que exprese un mínimo de filas por grupo. Las heredadas no cuentan porque no se persisten (RD-97).
    """
    return [(r.user_id, r.module, int(r.n)) for r in s.execute(_DECLARED_MINIMUM_SQL, {"minimum": minimum})]


def run_declared_minimum_audit(factory: SessionFactory, config: EngineConfig, metrics: Metrics) -> int:
    """Job `reco-batch audits` (T069): la consulta periódica que §6 exige para DI-28.

    Cada violación se registra con usuario y módulo —nunca los tags declarados— y el total se expone como
    `declared_minimum_violations_total` (esperado 0), también cuando es 0.
    """
    with factory() as s:
        violations = declared_minimum_violations(s, config.declared_tags_min)
    for user_id, module, rows in violations:
        log.warning(
            "DI-28 violado: declaración con menos filas propias que declared_tags_min",
            extra={"reco_user_id": str(user_id), "reco_module": module, "reco_rows": rows},
        )
    metrics.set("declared_minimum_violations_total", float(len(violations)))
    return len(violations)
