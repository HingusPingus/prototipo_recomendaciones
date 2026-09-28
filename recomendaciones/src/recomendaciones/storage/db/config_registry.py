"""Registro de versiones de configuración en `engine_config_versions` (§2.8). Escritor único: el loader.

Los tres procesos cargan la configuración al arrancar; el registro se serializa con un advisory lock
transaccional para que dos arranques simultáneos no compitan por activar la misma versión.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from recomendaciones.config.loader import ConfigRow, EngineConfig, register_active_version
from recomendaciones.storage.db.models import EngineConfigVersion

_REGISTRY_LOCK_KEY = 0x5245434F  # "RECO"


class PostgresConfigRegistry:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, config_version: str) -> ConfigRow | None:
        row = self._s.get(EngineConfigVersion, config_version)
        if row is None:
            return None
        return ConfigRow(row.config_version, row.payload, row.activated_at, row.deactivated_at)

    def active(self) -> str | None:
        return self._s.scalar(
            sa.select(EngineConfigVersion.config_version).where(EngineConfigVersion.deactivated_at.is_(None))
        )

    def deactivate(self, config_version: str, at: datetime) -> None:
        self._s.execute(
            sa.update(EngineConfigVersion)
            .where(EngineConfigVersion.config_version == config_version)
            .values(deactivated_at=at)
        )

    def insert(self, row: ConfigRow) -> None:
        self._s.add(
            EngineConfigVersion(
                config_version=row.config_version, payload=row.payload, activated_at=row.activated_at
            )
        )
        self._s.flush()


def register_in_database(session: Session, cfg: EngineConfig, now: datetime) -> None:
    session.execute(sa.text("SELECT pg_advisory_xact_lock(:k)"), {"k": _REGISTRY_LOCK_KEY})
    register_active_version(PostgresConfigRegistry(session), cfg, now)


def load_version_rows(session: Session) -> list[ConfigRow]:
    rows = session.scalars(sa.select(EngineConfigVersion)).all()
    return [ConfigRow(r.config_version, r.payload, r.activated_at, r.deactivated_at) for r in rows]
