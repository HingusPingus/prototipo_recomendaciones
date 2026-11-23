"""Alta rápida (RD-128): los usuarios nuevos se materializan entre corridas de la sincronización completa.

El proceso `reco-sync-usuarios` solo inserta usuarios que todavía no existen; la sincronización completa sigue siendo la
autoridad para todo lo demás. Los dos escriben `users` con el mismo advisory lock tomado.
"""

from __future__ import annotations

import threading
import time
from datetime import date

import sqlalchemy as sa

from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.transformer.client import ApiGeneralClient
from recomendaciones.transformer.pipeline import USERS_WRITE_LOCK_KEY, SyncPipeline
from tests.support.api_general_double import ApiGeneralDouble

KEY = "test.s3cr3t-0123456789abcdef"
CFG = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")
TODAY = date(2026, 11, 22)
USERS_SQL = "SELECT id, birth_date, max_age_ordinal, age_config_version, region FROM users ORDER BY id"


def _client(double: ApiGeneralDouble) -> ApiGeneralClient:
    return ApiGeneralClient("http://api-general.internal", KEY, timeout_seconds=5, transport=double.transport())


def _full_sync(db_factory, redis_client, double: ApiGeneralDouble) -> SyncPipeline:  # noqa: ANN001
    cache = CacheClient(redis_client)
    return SyncPipeline(
        db_factory,
        _client(double),
        FiltersCache(cache, DbFiltersSource(db_factory), 3_600),
        cache,
        CFG,
        Metrics(),
        volume_delta_ratio=0.9,
        redelivery_window_hours=48,
        today=lambda: TODAY,
    )


def _rows(db_factory, sql: str = USERS_SQL) -> list[tuple]:  # noqa: ANN001
    with db_factory() as s:
        return [tuple(r) for r in s.execute(sa.text(sql)).all()]


def _hold_lock(db_factory):  # noqa: ANN001, ANN202 — Session que retiene el lock hasta confirmarse
    s = db_factory()
    s.execute(sa.text("SELECT pg_advisory_xact_lock(:k)"), {"k": USERS_WRITE_LOCK_KEY})
    return s


def _someone_waits_for_an_advisory_lock(db_factory) -> bool:  # noqa: ANN001
    sql = (
        "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted"
        " AND database = (SELECT oid FROM pg_database WHERE datname = current_database())"
    )
    with db_factory() as s:
        return bool(s.scalar(sa.text(sql)))


def test_full_sync_waits_for_user_write_lock(db_factory, redis_client) -> None:  # noqa: ANN001
    double = ApiGeneralDouble(api_key=KEY, page_size=3)
    user = double.add_user(birth_date=date(1990, 5, 1), region="AR")
    double.add_item("peliculas", ["comedia"], rating="ATP")
    pipeline = _full_sync(db_factory, redis_client, double)
    reports = []
    runner = threading.Thread(target=lambda: reports.append(pipeline.run()))
    holder = _hold_lock(db_factory)
    try:
        runner.start()
        deadline = time.monotonic() + 10
        while not _someone_waits_for_an_advisory_lock(db_factory):
            assert time.monotonic() < deadline, "la sincronización completa escribió sin esperar el lock de usuarios"
            assert runner.is_alive(), "la sincronización completa terminó sin tomar el lock de usuarios"
            time.sleep(0.05)
        assert _rows(db_factory) == []
    finally:
        holder.commit()
        holder.close()
    runner.join(timeout=10)
    assert not runner.is_alive()
    assert reports[0].status == "success"
    assert [row[0] for row in _rows(db_factory)] == [user]
