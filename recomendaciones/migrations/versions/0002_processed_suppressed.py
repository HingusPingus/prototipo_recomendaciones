"""`processed_result` admite `suppressed`: la baja de cuenta se registra con idempotencia por `event_id` (T058).

El evento de baja (CR-19, RD-101) se consume con la misma idempotencia de evento que `recomendacion.actualizar`
(§7.11). El resultado de la supresión —completada o fallida visible— vive en `user_suppressions`; acá solo
queda la marca de que el evento se procesó.

Revision ID: 0002_processed_suppressed
Revises: 0001_initial
Create Date: 2026-09-28
"""

from __future__ import annotations

from alembic import op

revision = "0002_processed_suppressed"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

_PREVIOUS = ("recomputed", "skipped_no_shared_tag", "signal_recorded", "skipped_not_materialized", "dlq")


def upgrade() -> None:
    op.execute("ALTER TYPE processed_result ADD VALUE IF NOT EXISTS 'suppressed'")


def downgrade() -> None:
    # Postgres no quita valores de un enum: se recrea el tipo. Las marcas borradas no pierden nada: la lápida
    # de `user_suppressions` vuelve inocuo el reproceso del evento.
    labels = ", ".join(f"'{v}'" for v in _PREVIOUS)
    op.execute("DELETE FROM processed_events WHERE result = 'suppressed'")
    op.execute("ALTER TYPE processed_result RENAME TO processed_result_old")
    op.execute(f"CREATE TYPE processed_result AS ENUM ({labels})")
    op.execute("ALTER TABLE processed_events ALTER COLUMN result TYPE processed_result USING result::text::processed_result")
    op.execute("DROP TYPE processed_result_old")
