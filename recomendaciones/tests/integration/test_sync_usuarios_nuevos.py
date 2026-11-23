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
from recomendaciones.transformer.pipeline import USERS_WRITE_LOCK_KEY, NewUserMaterializer, SyncPipeline
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


def _materializer(db_factory, double: ApiGeneralDouble, metrics: Metrics | None = None) -> NewUserMaterializer:  # noqa: ANN001
    return NewUserMaterializer(db_factory, _client(double), CFG, metrics or Metrics(), today=lambda: TODAY)


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


# --- `NewUserMaterializer`: el camino de solo inserción --------------------------------------------------------------
def _double_with_catalog() -> ApiGeneralDouble:
    double = ApiGeneralDouble(api_key=KEY, page_size=3)
    double.add_item("peliculas", ["comedia"], rating="ATP")
    return double


def test_new_user_row_matches_full_sync(db_factory, redis_client) -> None:  # noqa: ANN001
    double = _double_with_catalog()
    double.add_user(birth_date=date(1990, 5, 1), region="AR")
    double.add_user(birth_date=date(2014, 1, 1), region="UY")  # menor: otro ordinal
    report = _materializer(db_factory, double).run_once()
    assert (report.status, report.inserted) == ("inserted", 2)
    fast = _rows(db_factory)
    with db_factory.begin() as s:
        s.execute(sa.text("DELETE FROM users"))
    assert _full_sync(db_factory, redis_client, double).run().status == "success"
    assert _rows(db_factory) == fast


def test_existing_user_is_not_updated(db_factory, redis_client) -> None:  # noqa: ANN001
    double = _double_with_catalog()
    double.add_user(region="AR")
    assert _full_sync(db_factory, redis_client, double).run().status == "success"
    sql = "SELECT id, region, synced_at FROM users"
    before = _rows(db_factory, sql)
    double.users[0]["region"] = "UY"  # el cambio lo aplica la sincronización completa, no este camino
    report = _materializer(db_factory, double).run_once()
    assert (report.status, report.inserted) == ("none", 0)
    assert _rows(db_factory, sql) == before


def test_tombstoned_user_is_not_inserted(db_factory) -> None:  # noqa: ANN001
    double = _double_with_catalog()
    gone, kept = double.add_user(), double.add_user()
    with db_factory.begin() as s:
        s.execute(
            sa.text("INSERT INTO user_suppressions (user_id, requested_at, state) VALUES (:u, now(), 'in_progress')"),
            {"u": gone},
        )
    report = _materializer(db_factory, double).run_once()
    assert report.inserted == 1
    assert [row[0] for row in _rows(db_factory)] == [kept]


def test_invalid_users_are_skipped_silently(db_factory) -> None:  # noqa: ANN001
    double = _double_with_catalog()
    double.add_user(birth_date=None)
    double.add_user(region=None)
    valid = double.add_user()
    metrics = Metrics()
    report = _materializer(db_factory, double, metrics).run_once()
    assert report.inserted == 1
    assert [row[0] for row in _rows(db_factory)] == [valid]
    # las violaciones de contrato las sigue contando la sincronización completa, cada 5 minutos
    assert metrics.value("contract_violations_total", field="birth_date") == 0
    assert metrics.value("contract_violations_total", field="region") == 0
    assert metrics.value("reco_new_users_materialized_total") == 1
    assert metrics.value("reco_new_users_sync_last_success_timestamp") > 0


def test_api_general_down_writes_nothing(db_factory) -> None:  # noqa: ANN001
    double = _double_with_catalog()
    double.add_user()
    double.down = True
    metrics = Metrics()
    report = _materializer(db_factory, double, metrics).run_once()
    assert report.status == "failed" and report.reason
    assert _rows(db_factory) == []
    assert metrics.value("reco_new_users_sync_failures_total") == 1
    assert metrics.value("reco_new_users_sync_last_success_timestamp") == 0


def test_busy_lock_skips_tick(db_factory) -> None:  # noqa: ANN001
    double = _double_with_catalog()
    double.add_user()
    holder = _hold_lock(db_factory)
    try:
        report = _materializer(db_factory, double).run_once()
    finally:
        holder.rollback()
        holder.close()
    assert report.status == "busy"
    assert _rows(db_factory) == []


def test_fast_path_writes_no_run_records(db_factory) -> None:  # noqa: ANN001
    double = _double_with_catalog()
    double.add_user()
    counts = "SELECT (SELECT count(*) FROM sync_runs), (SELECT count(*) FROM process_runs)"
    before = _rows(db_factory, counts)
    assert _materializer(db_factory, double).run_once().status == "inserted"
    assert _rows(db_factory, counts) == before


def test_full_sync_after_fast_path_has_no_duplicate(db_factory, redis_client) -> None:  # noqa: ANN001
    double = _double_with_catalog()
    users = [double.add_user(), double.add_user()]
    assert _materializer(db_factory, double).run_once().inserted == 2
    report = _full_sync(db_factory, redis_client, double).run()
    assert report.status == "success"
    assert sorted(row[0] for row in _rows(db_factory)) == sorted(users)


# --- el proceso `reco-sync-usuarios` -----------------------------------------------------------------------------
def test_serve_materializes_a_new_user(db_factory, redis_client, valid_env) -> None:  # noqa: ANN001
    from recomendaciones.bootstrap import build_runtime
    from recomendaciones.config.settings import load_settings
    from recomendaciones.transformer.usuarios_continuo import serve

    settings = load_settings()
    runtime = build_runtime(settings, "sync-usuarios", factory=db_factory, cache=CacheClient(redis_client))
    assert type(runtime.metrics) is Metrics  # proceso largo: RecordingMetrics acumularía cada observación
    double = _double_with_catalog()
    user = double.add_user()
    stop = threading.Event()
    stop.set()  # una sola vuelta
    serve(settings, stop=stop, transport=double.transport(), runtime=runtime)
    assert [row[0] for row in _rows(db_factory)] == [user]
