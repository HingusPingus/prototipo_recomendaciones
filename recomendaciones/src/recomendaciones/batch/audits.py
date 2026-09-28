"""Auditorías periódicas de invariantes que el esquema no puede sostener (data-model.md §6)."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

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
