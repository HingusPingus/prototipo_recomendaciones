"""`items.first_synced_at`: desde cuándo existe cada ítem en la proyección (T070).

`vector_recompute_lag_seconds` pasa a medir la antigüedad del ítem vigente más viejo sin vector bajo la versión
activa. `synced_at` no sirve para eso: la sincronización lo reescribe en cada corrida. Las filas existentes
toman su `synced_at` actual como primera sincronización conocida.

Revision ID: 0005_items_first_synced_at
Revises: 0004_process_runs
Create Date: 2026-09-30
"""

from __future__ import annotations

from alembic import op

revision = "0005_items_first_synced_at"
down_revision = "0004_process_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE items ADD COLUMN first_synced_at timestamptz")
    op.execute("UPDATE items SET first_synced_at = synced_at")
    op.execute("ALTER TABLE items ALTER COLUMN first_synced_at SET DEFAULT now()")
    op.execute("ALTER TABLE items ALTER COLUMN first_synced_at SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE items DROP COLUMN IF EXISTS first_synced_at")
