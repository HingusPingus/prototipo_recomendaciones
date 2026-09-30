"""`process_runs`: resultado de cada corrida de transformer y jobs batch (T066).

Esos procesos corren una vez y terminan sin exponer servidor de métricas: lo que fijaban se perdía y once
alertas no podían dispararse (`docs/validation/alert-threshold-review.md` §2). Cada corrida deja acá su
estado y sus métricas, y el worker las re-expone (Constitución VII, FR-044, FR-068d1).

Revision ID: 0004_process_runs
Revises: 0003_idx_items_retired
Create Date: 2026-09-30
"""

from __future__ import annotations

from alembic import op

revision = "0004_process_runs"
down_revision = "0003_idx_items_retired"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE process_runs (
            id              bigserial PRIMARY KEY,
            component       text NOT NULL,
            started_at      timestamptz NOT NULL,
            finished_at     timestamptz NOT NULL,
            status          text NOT NULL,
            failure_reason  text,
            metrics         jsonb NOT NULL,
            details         jsonb,
            CONSTRAINT ck_process_runs_status CHECK (status IN ('success', 'failed'))
        )
        """
    )
    op.execute("CREATE INDEX idx_process_runs_component ON process_runs (component, finished_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS process_runs")
