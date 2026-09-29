"""Índice parcial para el repoblado de `retired:{module}` (T050).

La consulta de §3.1 —retirados del módulo dentro de la ventana de RD-39— recorría `items` entero: el
repoblado de `retired:` ante miss crecía con el catálogo (p95 7,97 → 18,55 ms de 1× a 10×). Con el índice
parcial el costo queda proporcional a los retirados de la ventana, que es lo que §4.4 declara.

Revision ID: 0003_idx_items_retired
Revises: 0002_processed_suppressed
Create Date: 2026-09-28
"""

from __future__ import annotations

from alembic import op

revision = "0003_idx_items_retired"
down_revision = "0002_processed_suppressed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX idx_items_retired ON items (module, retired_at) WHERE status = 'retired'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_items_retired")
