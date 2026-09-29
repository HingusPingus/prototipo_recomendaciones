"""T051 — refresco de derivados etarios por cruce de umbral (A) y por escala no compatible (B) (§7.5, FR-080c)."""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, date, datetime

import recomendaciones.batch.age_threshold_refresh as refresh_module
import sqlalchemy as sa
from recomendaciones.batch.age_threshold_refresh import AgeThresholdRefreshJob

from recomendaciones.config.loader import load_engine_config
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.recompute import RecomputeStream
from tests.integration import seed

CFG = load_engine_config("v1.yaml")
TODAY = date(2026, 9, 28)
OLD_SCALE = "sha256:escala-anterior"


def _job(db_factory, redis_client, metrics: Metrics | None = None, today: date = TODAY) -> AgeThresholdRefreshJob:
    cache = CacheClient(redis_client)
    stream = RecomputeStream(cache, maxlen=1000, ttl_suppress=300)
    return AgeThresholdRefreshJob(
        db_factory, cache, stream, CFG, metrics or Metrics(), compatible_versions=frozenset({CFG.config_version}), today=lambda: today
    )


def _user(db_factory, birth: date, ordinal: int, *, config_version: str | None = None, declared=("peliculas",)) -> uuid.UUID:
    with db_factory.begin() as s:
        uid = seed.user(s, birth_date=birth, max_age_ordinal=ordinal, config_version=config_version)
        for module in declared:
            names = [f"{module}-t{i}" for i in range(5)]
            seed.tags(s, names)
            seed.declare(s, uid, module, names)
    return uid


def _row(db_factory, uid: uuid.UUID):
    with db_factory() as s:
        return s.execute(sa.text("SELECT max_age_ordinal, age_config_version FROM users WHERE id = :u"), {"u": uid}).one()


def _requests(redis_client) -> list[dict[str, str]]:
    return [fields for _id, fields in redis_client.xrange(keys.RECOMPUTE_STREAM)]


def _old_scale(db_factory) -> None:
    with db_factory.begin() as s:
        s.execute(
            sa.text("INSERT INTO engine_config_versions VALUES (:v, '{}'::jsonb, :a, :d)"),
            {"v": OLD_SCALE, "a": datetime(2025, 1, 1, tzinfo=UTC), "d": datetime(2025, 6, 1, tzinfo=UTC)},
        )


def test_user_who_turns_a_threshold_today_without_any_write_is_selected_by_cause_a(db_factory, redis_client) -> None:
    turns_13 = _user(db_factory, date(2013, 9, 28), ordinal=0)
    turns_18 = _user(db_factory, date(2008, 9, 28), ordinal=1)
    not_today = _user(db_factory, date(2013, 9, 29), ordinal=0)  # cumple mañana
    report = _job(db_factory, redis_client).run()
    assert _row(db_factory, turns_13).max_age_ordinal == 1
    assert _row(db_factory, turns_18).max_age_ordinal == 2
    assert _row(db_factory, not_today).max_age_ordinal == 0
    assert report.threshold_crossings == 2


def test_threshold_is_computed_against_birth_date_never_a_materialized_age(db_factory, redis_client) -> None:
    source = inspect.getsource(refresh_module)
    assert "age_derived_at <" not in source and "age_derived_at >" not in source  # no es selección por antigüedad
    with db_factory() as s:
        columns = {c["name"] for c in sa.inspect(s.bind).get_columns("users")}
    assert not {c for c in columns if c in ("age", "edad", "age_years")}


def test_user_under_a_non_compatible_scale_is_rederived_by_cause_b(db_factory, redis_client) -> None:
    _old_scale(db_factory)
    stale = _user(db_factory, date(1990, 1, 1), ordinal=0, config_version=OLD_SCALE)
    report = _job(db_factory, redis_client).run()
    assert tuple(_row(db_factory, stale)) == (2, CFG.config_version)
    assert report.stale_config_rederived == 1 and report.threshold_crossings == 0


def test_both_criteria_are_queried_and_reported_separately(db_factory, redis_client) -> None:
    _old_scale(db_factory)
    _user(db_factory, date(2013, 9, 28), ordinal=0)
    _user(db_factory, date(1990, 1, 1), ordinal=0, config_version=OLD_SCALE)
    metrics = Metrics()
    report = _job(db_factory, redis_client, metrics).run()
    assert (report.threshold_crossings, report.stale_config_rederived) == (1, 1)
    assert metrics.value("age_threshold_crossings_total") == 1
    assert metrics.value("age_stale_config_users_total") == 0  # verificación posterior: la escala quedó sin mezclar


def test_cache_is_invalidated_redis_first_and_recompute_requested_on_the_stream(db_factory, redis_client) -> None:
    uid = _user(db_factory, date(2013, 9, 28), ordinal=0, declared=("peliculas", "juegos"))
    for key in (keys.filters_key(uid), keys.reco_key(CFG.config_version, uid, Module.PELICULAS), keys.stale_key("sha256:x", uid, Module.JUEGOS)):
        redis_client.set(key, "{}")
    _job(db_factory, redis_client).run()
    assert [k for k in redis_client.keys(f"*{uid}*") if not k.startswith("recompute:lock:")] == []  # DI-2c
    requests = _requests(redis_client)
    assert sorted((r["module"], r["reason"]) for r in requests) == [("juegos", "age_threshold"), ("peliculas", "age_threshold")]
    assert all(r["user_id"] == str(uid) for r in requests)


def test_recompute_is_requested_only_for_declared_modules_and_respects_the_lock(db_factory, redis_client) -> None:
    uid = _user(db_factory, date(2013, 9, 28), ordinal=0, declared=("peliculas",))
    redis_client.set(keys.lock_key(uid, Module.PELICULAS), "1", ex=300)  # ya hay una solicitud en curso
    _job(db_factory, redis_client).run()
    assert _requests(redis_client) == []
    assert _row(db_factory, uid).max_age_ordinal == 1  # el derivado se corrige igual


def test_two_consecutive_runs_do_not_produce_duplicate_recomputes(db_factory, redis_client) -> None:
    _user(db_factory, date(2013, 9, 28), ordinal=0)
    first = _job(db_factory, redis_client).run()
    redis_client.delete(*redis_client.keys("recompute:lock:*"))  # aun sin el lock, no hay nada que cambiar
    second = _job(db_factory, redis_client).run()
    assert (first.threshold_crossings, second.threshold_crossings) == (1, 0)
    assert len(_requests(redis_client)) == 1


def test_run_over_an_empty_set_still_emits_the_liveness_metric(db_factory, redis_client) -> None:
    metrics = Metrics()
    report = _job(db_factory, redis_client, metrics).run()
    assert (report.threshold_crossings, report.stale_config_rederived) == (0, 0)
    assert metrics.value("age_refresh_last_success_timestamp") > 0


def test_leap_day_birthdays_cross_on_march_first_of_common_years(db_factory, redis_client) -> None:
    leapling = _user(db_factory, date(2008, 2, 29), ordinal=1)  # cumple 18 el 2026-03-01 (2026 no es bisiesto)
    _job(db_factory, redis_client, today=date(2026, 3, 1)).run()
    assert _row(db_factory, leapling).max_age_ordinal == 2
