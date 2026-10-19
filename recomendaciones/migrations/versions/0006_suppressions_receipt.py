"""`user_suppressions.event_id` y `received_at`: la recepción del evento de baja como checkpoint (T074).

FR-095b: al recibir una baja válida se registra su recepción antes de la supresión. `api-general` cruza el
checkpoint con su outbox por `event_id` y mide desde `occurred_at` hasta `received_at` (RD-115).

Las dos columnas admiten nulo solo para las constancias anteriores a esta migración, que no tienen evento
registrado: inventarles un `event_id` haría pasar por recibido un evento que nadie consultó. El `CHECK` exige
que estén las dos o ninguna.

Revision ID: 0006_suppressions_receipt
Revises: 0005_items_first_synced_at
Create Date: 2026-10-05
"""

from __future__ import annotations

from alembic import op

revision = "0006_suppressions_receipt"
down_revision = "0005_items_first_synced_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_suppressions ADD COLUMN event_id uuid")
    op.execute("ALTER TABLE user_suppressions ADD COLUMN received_at timestamptz")
    op.execute("ALTER TABLE user_suppressions ADD CONSTRAINT uq_suppressions_event_id UNIQUE (event_id)")
    op.execute(
        "ALTER TABLE user_suppressions ADD CONSTRAINT ck_suppressions_receipt "
        "CHECK ((event_id IS NULL) = (received_at IS NULL))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE user_suppressions DROP CONSTRAINT IF EXISTS ck_suppressions_receipt")
    op.execute("ALTER TABLE user_suppressions DROP CONSTRAINT IF EXISTS uq_suppressions_event_id")
    op.execute("ALTER TABLE user_suppressions DROP COLUMN IF EXISTS received_at")
    op.execute("ALTER TABLE user_suppressions DROP COLUMN IF EXISTS event_id")
