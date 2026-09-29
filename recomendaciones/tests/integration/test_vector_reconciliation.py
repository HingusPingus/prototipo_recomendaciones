"""T030 — reconciliación de vectores tras cada sincronización (FR-010e…FR-010g, RD-22, RD-24, RD-25)."""

from __future__ import annotations

import sqlalchemy as sa

from recomendaciones.observability.metrics import Metrics
from recomendaciones.transformer.vocabulary_sync import VocabularySync
from tests.integration import seed


def _q(db_factory, sql: str, **p: object) -> list[tuple]:  # noqa: ANN001
    with db_factory() as s:
        return [tuple(r) for r in s.execute(sa.text(sql), p).all()]


def _active(db_factory) -> str | None:  # noqa: ANN001
    rows = _q(db_factory, "SELECT version FROM vocab_versions WHERE activated_at IS NOT NULL AND deactivated_at IS NULL")
    return rows[0][0] if rows else None


def test_startup_from_empty_vectorizes_every_live_item_with_tags(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        live = [seed.item(s, "peliculas", ["horror", "drama"]), seed.item(s, "juegos", ["rpg"])]
        seed.item(s, "juegos", ["rpg", "raro"], status="retired")  # retirado sin señales: sin vector
    metrics = Metrics()
    report = VocabularySync(db_factory, metrics).run()
    active = _active(db_factory)
    assert active is not None and report.activated == active
    vectors = {r[0] for r in _q(db_factory, "SELECT item_id FROM item_vectors WHERE vocab_version = :v", v=active)}
    assert vectors == set(live)
    assert metrics.value("catalog_unvectorized_ratio") == 0.0
    tags = {r[0] for r in _q(db_factory, "SELECT tag_name FROM vocab_version_tags WHERE version = :v", v=active)}
    assert tags == {"horror", "drama", "rpg"}  # el vocabulario se deriva solo de vigentes


def test_new_item_with_existing_tags_gets_a_vector(db_factory) -> None:  # noqa: ANN001
    """El caso que el disparador por hash no veía: el conjunto de tags no cambia."""
    with db_factory.begin() as s:
        seed.item(s, "peliculas", ["horror"])
        seed.item(s, "peliculas", ["drama"])
    sync = VocabularySync(db_factory, Metrics())
    sync.run()
    version = _active(db_factory)
    with db_factory.begin() as s:
        newcomer = seed.item(s, "peliculas", ["horror", "drama"])
    sync.run()
    assert _active(db_factory) == version  # mismo vocabulario
    assert _q(db_factory, "SELECT count(*) FROM item_vectors WHERE item_id = :i AND vocab_version = :v", i=newcomer, v=version) == [(1,)]


def test_second_run_without_changes_rewrites_nothing(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        for tags in (["horror"], ["drama", "horror"], ["comedia"]):
            seed.item(s, "peliculas", tags)
    sync = VocabularySync(db_factory, Metrics())
    sync.run()
    before = _q(db_factory, "SELECT item_id, computed_at FROM item_vectors ORDER BY 1")
    report = sync.run()
    assert report.vectors_written == 0
    assert _q(db_factory, "SELECT item_id, computed_at FROM item_vectors ORDER BY 1") == before


def test_retired_item_with_signals_keeps_feeding_profiles_across_versions(db_factory) -> None:  # noqa: ANN001
    """FR-073: tras cambiar el vocabulario, el retirado con señales recibe vector bajo la versión nueva."""
    with db_factory.begin() as s:
        user = seed.user(s)
        item = seed.item(s, "juegos", ["rpg", "fantasia"])
        seed.item(s, "juegos", ["rpg"])
        seed.signal(s, user, item, "like")
    sync = VocabularySync(db_factory, Metrics())
    sync.run()
    with db_factory.begin() as s:
        s.execute(sa.text("UPDATE items SET status = 'retired', retired_at = now() WHERE id = :i"), {"i": item})
        seed.item(s, "juegos", ["rpg", "fantasia", "nuevo"])  # cambia el vocabulario
    sync.run()
    assert _q(db_factory, "SELECT count(*) FROM item_vectors WHERE item_id = :i AND vocab_version = :v", i=item, v=_active(db_factory)) == [(1,)]


def test_metrics_are_emitted(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        for tags in (["a1", "shared"], ["a2"], ["a3"], ["a4"], ["a5"]):
            seed.item(s, "peliculas", tags)
        seed.item(s, "juegos", ["shared", "g1"])
    metrics = Metrics()
    VocabularySync(db_factory, metrics).run()
    assert metrics.value("declarable_tags_total", module="peliculas") == 6
    assert metrics.value("declarable_tags_total", module="juegos") == 2
    assert metrics.value("vocab_transition_progress") == 1.0
    assert metrics.value("vector_recompute_lag_seconds") >= 0.0
