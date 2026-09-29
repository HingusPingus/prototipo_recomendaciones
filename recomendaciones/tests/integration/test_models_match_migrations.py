"""T003 — el espejo ORM (`models.py`) no diverge del DDL de la migración (fuente del esquema)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from recomendaciones.storage.db.models import Base
from tests.integration.conftest import alembic_config


def test_models_match_migration(pg_url: str) -> None:
    admin = sa.create_engine(pg_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text("DROP DATABASE IF EXISTS drifttest"))
        conn.execute(sa.text("CREATE DATABASE drifttest"))
    admin.dispose()
    url = pg_url.rsplit("/", 1)[0] + "/drifttest"
    command.upgrade(alembic_config(url), "head")
    eng = sa.create_engine(url)
    with eng.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True, "compare_server_default": False})
        diff = compare_metadata(ctx, Base.metadata)
    eng.dispose()
    assert diff == [], f"models.py y la migración divergen: {diff}"
