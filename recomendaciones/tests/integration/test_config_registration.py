"""T004 — registro en `engine_config_versions`: activación única y rollback hacia adelante (DI-24)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
import yaml
from alembic import command

from recomendaciones.config.errors import ConfigurationError
from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
from recomendaciones.storage.db.config_registry import register_in_database
from recomendaciones.storage.db.session import session_factory
from tests.integration.conftest import alembic_config


@pytest.fixture
def factory(pg_url: str) -> Iterator[object]:
    admin = sa.create_engine(pg_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text("DROP DATABASE IF EXISTS cfgtest"))
        conn.execute(sa.text("CREATE DATABASE cfgtest"))
    admin.dispose()
    url = pg_url.rsplit("/", 1)[0] + "/cfgtest"
    command.upgrade(alembic_config(url), "head")
    eng = sa.create_engine(url)
    yield session_factory(eng)
    eng.dispose()


def test_rollback_to_deactivated_version_fails(factory: object, tmp_path: Path) -> None:
    v1 = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")
    data = yaml.safe_load((ENGINE_CONFIG_DIR / "v1.yaml").read_text())
    (tmp_path / "v2.yaml").write_text(yaml.safe_dump({**data, "version_label": "v2", "k": 25}))
    v2 = load_engine_config(tmp_path / "v2.yaml")
    now = datetime(2026, 9, 28, tzinfo=UTC)
    with factory.begin() as s:  # type: ignore[attr-defined]
        register_in_database(s, v1, now)
    with factory.begin() as s:  # type: ignore[attr-defined]
        register_in_database(s, v1, now)  # arranque repetido: idempotente
    with factory.begin() as s:  # type: ignore[attr-defined]
        register_in_database(s, v2, now)
    with pytest.raises(ConfigurationError, match="hacia adelante"), factory.begin() as s:  # type: ignore[attr-defined]
        register_in_database(s, v1, now)
    with factory.begin() as s:  # type: ignore[attr-defined]
        active = s.execute(
            sa.text("SELECT config_version FROM engine_config_versions WHERE deactivated_at IS NULL")
        ).scalars().all()
    assert active == [v2.config_version]
