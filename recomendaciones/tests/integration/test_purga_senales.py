"""T057 — purga de señales con guarda de exclusión (FR-068…FR-068d1, FR-068e, DI-20, `data-model.md` §7.10)."""

from __future__ import annotations

import inspect
import logging
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from recomendaciones.batch.purga_senales import SignalPurgeJob

from recomendaciones.config.errors import ConfigurationError
from recomendaciones.config.loader import load_engine_config
from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.db.exclusions import ExclusionResolver
from tests.integration import seed

CFG = load_engine_config("v1.yaml")
NOW = seed.T0 + timedelta(days=400)
OLD = 0  # minutos desde T0: 400 días antes de NOW, fuera de la retención
RECENT = 60 * 24 * 390  # 10 días antes de NOW


def _windows(retention_days: int = 365, **overrides: int) -> SimpleNamespace:
    base = {
        "signal_retention_days": retention_days,
        "idempotency_retention_hours": 72,
        "ttl_dedupe_seconds": 3600,
        "event_redelivery_window_hours": 48,
    }
    return SimpleNamespace(**(base | overrides))


def _job(db_factory, metrics: Metrics | None = None, **windows: int) -> SignalPurgeJob:
    return SignalPurgeJob(db_factory, CFG, _windows(**windows), metrics or Metrics(), now=lambda: NOW)


def _world(db_factory, n_items: int = 3):
    with db_factory.begin() as s:
        user = seed.user(s)
        items = [seed.item(s, "peliculas", [f"t{i}"]) for i in range(n_items)]
    return user, items


def _signals(db_factory, user: uuid.UUID) -> set[tuple[uuid.UUID, str]]:
    with db_factory() as s:
        rows = s.execute(sa.text("SELECT item_id, signal_type::text FROM user_signals WHERE user_id = :u"), {"u": user})
        return {(r[0], r[1]) for r in rows}


def _exclusions(db_factory, user: uuid.UUID) -> dict[uuid.UUID, str]:
    with db_factory() as s:
        rows = s.execute(sa.text("SELECT item_id, origin::text FROM user_exclusions WHERE user_id = :u"), {"u": user})
        return {r[0]: r[1] for r in rows}


def test_signals_older_than_retention_are_purged_and_recent_ones_kept(db_factory) -> None:
    user, (a, b, _) = _world(db_factory)
    with db_factory.begin() as s:
        seed.signal(s, user, a, "like", minutes=OLD)
        seed.signal(s, user, a, "dislike", minutes=OLD + 1)
        seed.signal(s, user, b, "like", minutes=RECENT)
    report = _job(db_factory).run()
    assert _signals(db_factory, user) == {(b, "like")}
    assert report.purged == 2


def test_exclusion_survives_the_purge_of_its_origin_signal(db_factory) -> None:
    """DI-20: consumo → purga de la señal → reconstrucción de derivados → la exclusión sigue presente."""
    user, (a, _, _) = _world(db_factory)
    with db_factory.begin() as s:
        seed.signal(s, user, a, "consumo", minutes=OLD)
        seed.exclusion(s, user, a, "consumo")
    _job(db_factory).run()
    assert _signals(db_factory, user) == set()
    with db_factory.begin() as s:
        ExclusionResolver(lambda _u: None).resolve(s, [user])  # la reconstrucción es aditiva
    assert _exclusions(db_factory, user) == {a: "consumo"}


def test_consumo_without_materialized_exclusion_is_deferred_not_purged(db_factory) -> None:
    """FR-068c: purgarlo convertiría un ítem ya consumido en recomendable."""
    user, (a, b, c) = _world(db_factory)
    with db_factory.begin() as s:
        seed.signal(s, user, a, "consumo", minutes=OLD)  # sin exclusión
        seed.signal(s, user, b, "consumo", minutes=OLD)
        seed.exclusion(s, user, b, "like")  # exclusión de otro origen: no es la materialización del consumo
        seed.signal(s, user, c, "like", minutes=OLD)  # la guarda solo alcanza al consumo
    metrics = Metrics()
    report = _job(db_factory, metrics).run()
    assert _signals(db_factory, user) == {(a, "consumo"), (b, "consumo")}
    assert report.deferred == 2
    assert metrics.value("signals_purge_deferred_total") == 2


def test_guard_is_evaluated_on_every_run_so_a_deferred_signal_is_purged_once_materialized(db_factory) -> None:
    user, (a, _, _) = _world(db_factory)
    with db_factory.begin() as s:
        seed.signal(s, user, a, "consumo", minutes=OLD)
    assert _job(db_factory).run().deferred == 1
    with db_factory.begin() as s:
        ExclusionResolver(lambda _u: None).resolve(s, [user])
    second = _job(db_factory).run()
    assert second.deferred == 0 and second.purged == 1
    assert _exclusions(db_factory, user) == {a: "consumo"}


def test_orphaned_permanent_exclusions_are_measured_without_threshold(db_factory) -> None:
    user, (a, b, _) = _world(db_factory)
    with db_factory.begin() as s:
        seed.signal(s, user, a, "consumo", minutes=OLD)
        seed.exclusion(s, user, a, "consumo")
        seed.signal(s, user, b, "consumo", minutes=RECENT)
        seed.exclusion(s, user, b, "consumo")
    metrics = Metrics()
    report = _job(db_factory, metrics).run()
    assert report.orphaned_permanent == 1  # solo la de `a` perdió su señal de origen
    assert metrics.value("exclusions_orphaned_permanent_total") == 1


def test_retention_that_does_not_exceed_every_window_refuses_to_start(db_factory) -> None:
    with pytest.raises(ConfigurationError, match="popularity_window_days"):
        _job(db_factory, retention_days=CFG.popularity_window_days)
    with pytest.raises(ConfigurationError, match="event_redelivery_window_hours"):
        _job(db_factory, retention_days=365, event_redelivery_window_hours=365 * 24)


def test_retention_and_windows_are_mandatory_without_hidden_default() -> None:
    params = inspect.signature(SignalPurgeJob).parameters
    assert params["windows"].default is inspect.Parameter.empty
    assert params["config"].default is inspect.Parameter.empty


def test_each_run_records_the_retention_value_in_force(db_factory, caplog) -> None:
    """RD-54: una reducción no aprobada debe ser detectable después."""
    _world(db_factory)
    with caplog.at_level(logging.INFO, logger="recomendaciones.batch.purga_senales"):
        report = _job(db_factory, retention_days=400).run()
    assert report.retention_days == 400
    assert any(getattr(r, "reco_signal_retention_days", None) == 400 for r in caplog.records)


def test_expired_processed_events_are_purged(db_factory) -> None:
    expired, live = uuid.uuid4(), uuid.uuid4()
    with db_factory.begin() as s:
        for event_id, expires in ((expired, NOW - timedelta(hours=1)), (live, NOW + timedelta(hours=1))):
            s.execute(
                sa.text("INSERT INTO processed_events VALUES (:e, :p, 'recomputed', :x)"),
                {"e": event_id, "p": NOW - timedelta(days=3), "x": expires},
            )
    report = _job(db_factory).run()
    with db_factory() as s:
        remaining = set(s.execute(sa.text("SELECT event_id FROM processed_events")).scalars())
    assert remaining == {live} and report.processed_events_purged == 1


def test_purge_is_idempotent(db_factory) -> None:
    user, (a, _, _) = _world(db_factory)
    with db_factory.begin() as s:
        seed.signal(s, user, a, "like", minutes=OLD)
    assert _job(db_factory).run().purged == 1
    assert _job(db_factory).run().purged == 0


def test_purge_never_touches_exclusions_or_declarations(db_factory) -> None:
    user, (a, _, _) = _world(db_factory)
    with db_factory.begin() as s:
        seed.declare(s, user, "peliculas", ["t0", "t1", "t2"])
        seed.signal(s, user, a, "dislike", minutes=OLD)
        seed.exclusion(s, user, a, "dislike")
    _job(db_factory).run()
    with db_factory() as s:
        declared = s.execute(sa.text("SELECT count(*) FROM user_declared_tags WHERE user_id = :u"), {"u": user}).scalar_one()
    assert declared == 3 and _exclusions(db_factory, user) == {a: "dislike"}
