"""T059 — verificación ejecutable de supresión, observador y escalamiento (FR-094, FR-095, FR-095a, SC-030)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.worker.suppression import SuppressionProcedure, SuppressionSweep, refresh_suppression_metrics
from tests.integration import seed
from tests.integration.test_supresion_aborta_recalculo import FIVE_TABLES, REQUESTED, _populated, _rows

ATTEMPTS = 3


def _procedure(db_factory, redis_client, metrics: Metrics, sleep=lambda _s: None) -> SuppressionProcedure:
    return SuppressionProcedure(
        db_factory, CacheClient(redis_client), metrics, max_attempts=ATTEMPTS, backoff_base_seconds=0.5, sleep=sleep
    )


def _row(db_factory, user: uuid.UUID):
    with db_factory() as s:
        return s.execute(sa.text("SELECT * FROM user_suppressions WHERE user_id = :u"), {"u": user}).mappings().one()


def test_clean_suppression_is_verified_and_the_row_keeps_only_identifier_and_timestamps(db_factory, redis_client) -> None:
    user, _ = _populated(db_factory, redis_client)
    metrics = Metrics()
    outcome = _procedure(db_factory, redis_client, metrics).run(user, REQUESTED)
    row = _row(db_factory, user)
    assert outcome.state == row["state"] == "completed" and row["verified_at"] is not None
    assert row["requested_at"] == REQUESTED and row["attempts"] == 1
    assert set(row) == {"user_id", "requested_at", "state", "attempts", "verified_at"}  # sin datos personales
    assert metrics.value("user_deletion_residual_keys_total") == 0
    assert metrics.value("suppressions_unverified_total") == 0


def test_persistent_residue_in_redis_ends_in_visible_failure_and_increments_the_alert_metric(db_factory, redis_client) -> None:
    """Una verificación que solo mirara Postgres daría por exitosa esta supresión."""
    user, _ = _populated(db_factory, redis_client)
    metrics = Metrics()
    delays: list[float] = []
    procedure = _procedure(db_factory, redis_client, metrics, sleep=delays.append)
    original = procedure.residue

    def residue_with_concurrent_writer(user_id):
        redis_client.set(keys.reco_key("sha256:otra", user_id, Module.JUEGOS), "{}")
        return original(user_id)

    procedure.residue = residue_with_concurrent_writer  # type: ignore[method-assign]
    outcome = procedure.run(user, REQUESTED)
    row = _row(db_factory, user)
    assert outcome.state == row["state"] == "failed" and row["verified_at"] is None
    assert row["attempts"] == ATTEMPTS
    assert delays == [0.5, 1.0]  # backoff exponencial entre verificaciones
    assert metrics.value("user_deletion_residual_keys_total") >= 1
    assert metrics.value("suppressions_unverified_total") == 1
    assert _rows(db_factory, user) == dict.fromkeys(FIVE_TABLES, 0)  # Postgres quedó limpio: el residuo es de Redis


def test_transient_residue_is_removed_on_retry_without_alerting(db_factory, redis_client) -> None:
    user, _ = _populated(db_factory, redis_client)
    metrics = Metrics()
    procedure = _procedure(db_factory, redis_client, metrics)
    original = procedure.residue
    calls = []

    def residue_after_late_write(user_id):
        calls.append(1)
        if len(calls) == 1:  # un recálculo en vuelo escribió tras la limpieza
            redis_client.set(keys.stale_key("sha256:x", user_id, Module.PELICULAS), "{}")
        return original(user_id)

    procedure.residue = residue_after_late_write  # type: ignore[method-assign]
    outcome = procedure.run(user, REQUESTED)
    assert outcome.state == "completed" and _row(db_factory, user)["attempts"] == 2
    assert metrics.value("user_deletion_residual_keys_total") == 0
    assert [k for k in redis_client.scan_iter(match=f"*{user}*")] == []


def test_residue_detects_rows_in_every_table_and_pending_stream_entries(db_factory, redis_client) -> None:
    user, _ = _populated(db_factory, redis_client)
    residue = _procedure(db_factory, redis_client, Metrics()).residue(user)
    assert set(residue.tables) == set(FIVE_TABLES) and all(n > 0 for n in residue.tables.values())
    assert residue.keys and residue.stream_entries == 2
    assert not residue.empty


def test_sweep_resumes_stuck_and_failed_suppressions(db_factory, redis_client) -> None:
    stuck, failed, recent = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    old = datetime.now(UTC) - timedelta(hours=2)
    with db_factory.begin() as s:
        seed.user(s, user_id=stuck)
        for uid, state, when in ((stuck, "in_progress", old), (failed, "failed", old), (recent, "in_progress", datetime.now(UTC))):
            s.execute(
                sa.text("INSERT INTO user_suppressions (user_id, requested_at, state, attempts) VALUES (:u, :r, :s, 1)"),
                {"u": uid, "r": when, "s": state},
            )
    metrics = Metrics()
    sweep = SuppressionSweep(db_factory, _procedure(db_factory, redis_client, metrics), metrics, stale_after=timedelta(minutes=30))
    assert sweep.run() == 2  # la reciente puede estar en curso en otro worker: no se toca
    assert (_row(db_factory, stuck)["state"], _row(db_factory, failed)["state"], _row(db_factory, recent)["state"]) == (
        "completed", "completed", "in_progress",
    )
    assert _rows(db_factory, stuck)["users"] == 0
    assert metrics.value("suppressions_unverified_total") == 1


def test_unverified_gauge_counts_open_suppressions(db_factory) -> None:
    with db_factory.begin() as s:
        for state in ("in_progress", "failed"):
            s.execute(
                sa.text("INSERT INTO user_suppressions (user_id, requested_at, state, attempts) VALUES (:u, now(), :s, 0)"),
                {"u": uuid.uuid4(), "s": state},
            )
    metrics = Metrics()
    with db_factory() as s:
        refresh_suppression_metrics(s, metrics)
    assert metrics.value("suppressions_unverified_total") == 2
