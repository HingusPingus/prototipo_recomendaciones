"""T063 — popularidad por ventana: límite inferior de Wilson y promoción definitiva (FR-033a1…FR-033a5, FR-033a6e, DI-26, DI-27)."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from recomendaciones.batch.popularidad import PopularityJob, wilson_lower_bound
from recomendaciones.config.errors import ConfigurationError
from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
from recomendaciones.observability.metrics import Metrics
from tests.integration import seed

CFG = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")
NOW = datetime(2026, 9, 28, tzinfo=UTC)


def _job(db_factory, *, retention_days: int = 730, threshold: int | None = None) -> PopularityJob:  # noqa: ANN001
    cfg = CFG if threshold is None else CFG.model_copy(update={"emergent_evidence_threshold": threshold})
    return PopularityJob(db_factory, cfg, Metrics(), signal_retention_days=retention_days, now=lambda: NOW)


def _engage(s, item, *, likes: int, others: int, days_ago: int = 1) -> None:  # noqa: ANN001
    when = NOW - timedelta(days=days_ago)
    for i in range(likes + others):
        user = seed.user(s)
        kind = "like" if i < likes else "consumo"
        s.execute(
            sa.text("INSERT INTO user_signals (origin_interaction_id, user_id, item_id, signal_type, occurred_at, source) "
                    "VALUES (:o, :u, :i, :k, :t, 'sync')"),
            {"o": f"int-{item}-{i}-{days_ago}", "u": user, "i": item, "k": kind, "t": when},
        )


def _pop(db_factory, item) -> tuple:  # noqa: ANN001
    with db_factory() as s:
        return tuple(s.execute(sa.text("SELECT like_count, engaged_user_count, popularity_score FROM item_popularity WHERE item_id = :i AND config_version = :c"), {"i": item, "c": CFG.config_version}).one())


def test_wilson_formula() -> None:
    assert wilson_lower_bound(0, 0, 1.96) == 0.0
    p, n, z = 0.8, 100, 1.96
    expected = (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    assert wilson_lower_bound(80, 100, 1.96) == pytest.approx(expected)
    assert 0.0 <= wilson_lower_bound(1, 1, 1.96) <= 1.0


def test_window_greater_than_retention_does_not_start(db_factory) -> None:  # noqa: ANN001
    with pytest.raises(ConfigurationError):
        _job(db_factory, retention_days=CFG.popularity_window_days)


def test_one_like_of_one_does_not_beat_eighty_of_one_hundred(db_factory) -> None:  # noqa: ANN001
    """El caso que distingue a Wilson del conteo bruto y de la proporción cruda."""
    with db_factory.begin() as s:
        lucky = seed.item(s, "peliculas", ["a"])
        solid = seed.item(s, "peliculas", ["b"])
        _engage(s, lucky, likes=1, others=0)
        _engage(s, solid, likes=80, others=20)
    _job(db_factory).run()
    assert _pop(db_factory, solid)[2] > _pop(db_factory, lucky)[2]
    assert _pop(db_factory, solid)[:2] == (80, 100)


def test_denominator_counts_distinct_users_and_consumption_only_in_denominator(db_factory) -> None:  # noqa: ANN001
    """RD-45: quien consumió y además likeó cuenta una vez."""
    with db_factory.begin() as s:
        item = seed.item(s, "peliculas", ["a"])
        users = [seed.user(s) for _ in range(3)]
        for n, u in enumerate(users):
            seed.signal(s, u, item, "consumo", minutes=n)
            seed.signal(s, u, item, "like", minutes=n + 10)
    _job(db_factory).run()
    like_count, engaged, _score = _pop(db_factory, item)
    assert (like_count, engaged) == (3, 3)


def test_only_signals_inside_the_window_count(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        item = seed.item(s, "peliculas", ["a"])
        _engage(s, item, likes=5, others=0, days_ago=CFG.popularity_window_days + 5)
        _engage(s, item, likes=1, others=1, days_ago=2)
    _job(db_factory).run()
    assert _pop(db_factory, item)[:2] == (1, 2)


def test_item_without_signals_has_score_zero_and_is_representable(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        item = seed.item(s, "juegos", ["rpg"])
    _job(db_factory).run()
    assert _pop(db_factory, item) == (0, 0, 0.0)


def test_results_are_written_per_config_version_and_computed_at_per_row(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        item = seed.item(s, "juegos", ["rpg"])
        s.execute(sa.text("INSERT INTO engine_config_versions VALUES ('sha256:vieja', '{}', now(), now())"))
        s.execute(sa.text("INSERT INTO item_popularity VALUES (:i, 'sha256:vieja', 1, 2, 0.1, now() - interval '9 days')"), {"i": item})
    _job(db_factory).run()
    with db_factory() as s:
        rows = dict(s.execute(sa.text("SELECT config_version, computed_at FROM item_popularity WHERE item_id = :i"), {"i": item}).all())
    assert set(rows) == {"sha256:vieja", CFG.config_version}  # cambiar de versión no pisa la anterior
    assert rows[CFG.config_version] > rows["sha256:vieja"]


def test_retired_items_are_not_recomputed(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        retired = seed.item(s, "juegos", ["rpg"], status="retired")
    _job(db_factory).run()
    with db_factory() as s:
        assert s.execute(sa.text("SELECT count(*) FROM item_popularity WHERE item_id = :i"), {"i": retired}).scalar_one() == 0


def test_promotion_is_recorded_once_and_never_revoked(db_factory) -> None:  # noqa: ANN001
    """FR-033a6e, DI-27: la evidencia puede bajar; la promoción, no."""
    with db_factory.begin() as s:
        item = seed.item(s, "peliculas", ["a"])
        _engage(s, item, likes=2, others=1, days_ago=10)
    job = _job(db_factory, threshold=3)
    job.run()
    with db_factory() as s:
        first = s.execute(sa.text("SELECT promoted_at, config_version FROM item_promotions WHERE item_id = :i"), {"i": item}).one()
    assert first.config_version == CFG.config_version
    with db_factory.begin() as s:
        s.execute(sa.text("UPDATE user_signals SET occurred_at = occurred_at - interval '400 days' WHERE item_id = :i"), {"i": item})
    job.run()
    assert _pop(db_factory, item)[1] == 0  # la evidencia cayó por debajo del umbral…
    with db_factory() as s:
        again = s.execute(sa.text("SELECT promoted_at FROM item_promotions WHERE item_id = :i"), {"i": item}).one()
    assert again.promoted_at == first.promoted_at  # …y la fila sigue, intacta


def test_liveness_metric_is_emitted(db_factory) -> None:  # noqa: ANN001
    job = _job(db_factory)
    job.run()
    assert job.metrics.value("catalog_popularity_last_success_timestamp") == NOW.timestamp()


def test_interrupted_batch_leaves_old_computed_at_on_unprocessed_rows(db_factory, monkeypatch) -> None:  # noqa: ANN001
    """RD-13: `computed_at` por fila hace detectable un batch parcialmente fallido."""
    with db_factory.begin() as s:
        movie = seed.item(s, "peliculas", ["a"])
        game = seed.item(s, "juegos", ["b"])
    job = _job(db_factory)
    job.run()
    with db_factory() as s:
        before = dict(s.execute(sa.text("SELECT item_id, computed_at FROM item_popularity")).all())
    later = NOW + timedelta(hours=1)
    job._now = lambda: later  # noqa: SLF001
    original = job._write_chunk  # noqa: SLF001
    calls = {"n": 0}

    def flaky(s, rows):  # noqa: ANN001, ANN202
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("interrupción del batch")
        return original(s, rows)

    monkeypatch.setattr(job, "_write_chunk", flaky)
    with pytest.raises(RuntimeError):
        job.run()
    with db_factory() as s:
        after = dict(s.execute(sa.text("SELECT item_id, computed_at FROM item_popularity")).all())
    updated = [i for i in (movie, game) if after[i] != before[i]]
    stale = [i for i in (movie, game) if after[i] == before[i]]
    assert len(updated) == 1 and len(stale) == 1
