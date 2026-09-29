"""T031 — freshness de la sincronización y métricas del lado del Data Transformer (FR-044, SC-014, §7.7, §7.12)."""

from __future__ import annotations

from datetime import date

from recomendaciones.observability.metrics import Metrics
from recomendaciones.transformer.freshness import refresh_sync_metrics
from tests.integration.test_sync_idempotent import Env


def test_failed_run_does_not_move_freshness_and_successful_does(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    env.double.add_item("peliculas", ["drama"])
    assert env.pipeline.run().status == "success"
    first = env.metrics.value("catalog_sync_last_success_timestamp")
    assert first > 0
    env.double.down = True
    assert env.pipeline.run().status == "failed"
    assert env.metrics.value("catalog_sync_last_success_timestamp") == first  # último éxito, no último intento
    env.double.down = False
    env.pipeline.run()
    assert env.metrics.value("catalog_sync_last_success_timestamp") >= first


def test_freshness_is_queryable_without_entering_the_db_from_any_long_running_process(db_factory, redis_client) -> None:  # noqa: ANN001
    """El Data Transformer es un proceso de una corrida: el worker re-expone la métrica en todo momento."""
    env = Env(db_factory, redis_client)
    env.double.add_item("peliculas", ["drama"])
    env.pipeline.run()
    other = Metrics()
    with db_factory() as s:
        refresh_sync_metrics(s, other)
    assert other.value("catalog_sync_last_success_timestamp") == env.metrics.value("catalog_sync_last_success_timestamp")


def test_catalog_and_ingest_metrics_are_emitted(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    user = env.double.add_user(birth_date=date(1990, 1, 1))
    rated = env.double.add_item("peliculas", ["drama"], rating="ATP")
    env.double.add_item("peliculas", ["horror"], rating=None)
    for i in range(8):
        env.double.add_item("juegos", [f"g{i}"])
    from datetime import UTC, datetime

    env.double.add_interaction(user, rated, "like", datetime(2026, 9, 1, tzinfo=UTC))
    env.pipeline.run()
    removed = env.double.items.pop()
    env.pipeline.run()
    assert env.metrics.value("catalog_unrated_ratio") == 1 / 9  # 1 de 9 vigentes, uno retirado por ausencia
    assert env.metrics.value("catalog_retired_total") == 1
    assert env.metrics.value("sync_volume_delta_ratio", entity="items") == 9 / 10
    assert env.metrics.value("sync_volume_delta_ratio", entity="users") == 1.0
    assert env.metrics.value("exclusion_resolve_lag_seconds") == 0.0
    assert env.metrics.value("signal_ingest_lag_seconds", source="sync") == 1  # una observación
    assert env.metrics.value("reco_sync_duration_seconds") == 2
    assert removed
