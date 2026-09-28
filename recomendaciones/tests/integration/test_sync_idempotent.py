"""T029 — materialización idempotente de usuarios, catálogo y actividad (FR-015…FR-021b, FR-072…FR-074, FR-079, FR-091b)."""

from __future__ import annotations

import ast
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

import recomendaciones.transformer.pipeline as pipeline_module
from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.transformer.client import ApiGeneralClient
from recomendaciones.transformer.pipeline import SyncPipeline
from tests.support.api_general_double import ApiGeneralDouble

KEY = "test.s3cr3t-0123456789abcdef"
CFG = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")
TODAY = date(2026, 9, 28)
T0 = datetime(2026, 9, 1, 12, tzinfo=UTC)


class Env:
    def __init__(self, db_factory, redis_client, double: ApiGeneralDouble | None = None) -> None:  # noqa: ANN001
        self.double = double or ApiGeneralDouble(api_key=KEY, page_size=3)
        self.metrics = Metrics()
        self.cache = CacheClient(redis_client)
        self.db = db_factory
        self.pipeline = SyncPipeline(
            db_factory,
            ApiGeneralClient("http://api-general.internal", KEY, timeout_seconds=5, transport=self.double.transport()),
            FiltersCache(self.cache, DbFiltersSource(db_factory), 3_600),
            self.cache,
            CFG,
            self.metrics,
            volume_delta_ratio=0.9,
            redelivery_window_hours=48,
            today=lambda: TODAY,
        )

    def q(self, sql: str, **params: object) -> list[tuple]:
        with self.db() as s:
            return [tuple(r) for r in s.execute(sa.text(sql), params).all()]


FUNCTIONAL = {
    "users": "SELECT id, birth_date, max_age_ordinal, age_config_version, region FROM users ORDER BY id",
    "items": "SELECT id, module::text, status::text, min_age_ordinal, age_rating::text, age_rating_source::text FROM items ORDER BY id",
    "tags": "SELECT name FROM tags ORDER BY name",
    "item_tags": "SELECT item_id, tag_name FROM item_tags ORDER BY 1, 2",
    "signals": "SELECT origin_interaction_id, user_id, item_id, signal_type::text, occurred_at, source::text FROM user_signals ORDER BY 1",
    "exclusions": "SELECT user_id, item_id, origin::text FROM user_exclusions ORDER BY 1, 2",
}


def _state(env: Env) -> dict[str, list[tuple]]:
    return {name: env.q(sql) for name, sql in FUNCTIONAL.items()}


def _populate(double: ApiGeneralDouble) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user = double.add_user(birth_date=date(1990, 5, 1), region="AR")
    minor = double.add_user(birth_date=date(2014, 1, 1), region="UY")
    movie = double.add_item("peliculas", ["horror", "sobrenatural"], rating="+13")
    double.add_item("juegos", ["horror", "survival"], rating="+18")
    double.add_item("peliculas", ["comedia"], rating="ATP")
    double.add_interaction(user, movie, "like", T0)
    double.add_interaction(minor, movie, "consumo", T0)
    return user, minor, movie


def test_double_execution_leaves_identical_state(db_factory, redis_client) -> None:  # noqa: ANN001
    """SC-006."""
    env = Env(db_factory, redis_client)
    _populate(env.double)
    first = env.pipeline.run()
    state = _state(env)
    second = env.pipeline.run()
    assert first.status == second.status == "success"
    assert _state(env) == state
    assert len(state["users"]) == 2 and len(state["items"]) == 3 and len(state["signals"]) == 2
    assert env.q("SELECT source::text FROM user_signals") == [("sync",), ("sync",)]
    assert env.q("SELECT count(*) FROM sync_runs WHERE status = 'success'") == [(2,)]


def test_item_without_rating_or_with_unknown_rating_gets_most_restrictive(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    missing = env.double.add_item("peliculas", ["drama"], rating=None)
    garbage = env.double.add_item("peliculas", ["drama"], rating="NC-17")
    env.pipeline.run()
    rows = dict((r[0], r[1:]) for r in env.q("SELECT id, age_rating::text, min_age_ordinal, age_rating_source::text FROM items"))
    assert rows[missing] == rows[garbage] == ("+18", CFG.max_ordinal, "unknown_defaulted")


def test_activity_keeps_signal_type_and_origin_timestamp(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    user, minor, movie = _populate(env.double)
    env.pipeline.run()
    assert (str(user), "like", T0) in [(str(u), k, t) for u, k, t in env.q("SELECT user_id, signal_type::text, occurred_at FROM user_signals")]


def test_interruption_leaves_consistent_state(db_factory, redis_client) -> None:  # noqa: ANN001
    double = ApiGeneralDouble(api_key=KEY, page_size=1, fail_catalog_after_pages=2)
    env = Env(db_factory, redis_client, double)
    _populate(double)
    report = env.pipeline.run()
    assert report.status == "failed"
    assert _state(env) == {name: [] for name in FUNCTIONAL}  # nada a medias
    assert env.q("SELECT status::text, failure_reason IS NOT NULL FROM sync_runs") == [("failed", True)]


def test_user_without_region_is_rejected_and_counted_separately(db_factory, redis_client) -> None:  # noqa: ANN001
    """SC-028: 100 % rechazados y contados; 0 materializados con valor por defecto."""
    env = Env(db_factory, redis_client)
    no_region = env.double.add_user(region=None)
    bad_region = env.double.add_user(region="ar")
    no_birth = env.double.add_user(birth_date=None)
    ok = env.double.add_user()
    report = env.pipeline.run()
    assert {r[0] for r in env.q("SELECT id FROM users")} == {ok}
    assert env.metrics.value("contract_violations_total", field="region") == 2
    assert env.metrics.value("contract_violations_total", field="birth_date") == 1
    assert report.status == "failed" and "contrato" in report.failure_reason
    assert no_region and bad_region and no_birth


def test_item_without_tags_is_rejected_without_aborting(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    untagged = env.double.add_item("peliculas", [])
    only_empty = env.double.add_item("juegos", ["   ", ""])
    kept = env.double.add_item("peliculas", ["drama", "", " padded "])
    env.pipeline.run()
    items = {r[0] for r in env.q("SELECT id FROM items")}
    assert items == {kept} and untagged not in items and only_empty not in items
    assert env.q("SELECT tag_name FROM item_tags") == [("drama",)]  # tal cual; los mal formados se descartan
    assert env.metrics.value("projection_field_anomalies_total", field="tag_name", reason="empty") == 3
    assert env.metrics.value("projection_field_anomalies_total", field="tag_name", reason="malformed") == 1
    assert env.metrics.value("projection_field_anomalies_total", field="tags", reason="missing") == 2


def test_tags_are_not_normalized(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    env.double.add_item("peliculas", ["Horror", "horror"])
    env.pipeline.run()
    assert env.q("SELECT name FROM tags ORDER BY name") == [("Horror",), ("horror",)]


def test_reused_interaction_with_other_type_is_a_contract_violation(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    user, _, movie = _populate(env.double)
    env.pipeline.run()
    env.double.activity[0]["signal_type"] = "dislike"  # mismo origin_interaction_id, otro hecho
    env.pipeline.run()
    assert env.metrics.value("contract_violations_total", field="origin_interaction_id") == 1
    assert env.q("SELECT signal_type::text FROM user_signals WHERE user_id = :u", u=user) == [("like",)]


def test_identical_reentry_counts_as_duplicate(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    _populate(env.double)
    env.pipeline.run()
    env.pipeline.run()
    assert env.metrics.value("signal_duplicate_rejections_total", source="sync") == 2


def test_ingested_signals_materialize_exclusions_and_invalidate_filters(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    user, minor, movie = _populate(env.double)
    env.pipeline.run()
    assert (minor, movie, "consumo") in env.q("SELECT user_id, item_id, origin::text FROM user_exclusions")
    redis_client.set(keys.filters_key(user), "{}")
    new_item = env.double.add_item("peliculas", ["drama"])
    env.double.add_interaction(user, new_item, "dislike", T0)
    env.pipeline.run()
    assert not redis_client.exists(keys.filters_key(user))


def test_suppressed_user_is_never_rematerialized(db_factory, redis_client) -> None:  # noqa: ANN001
    """DI-29 / FR-091b: la lápida gana aunque el origen lo siga listando."""
    env = Env(db_factory, redis_client)
    ghost = env.double.add_user()
    item = env.double.add_item("peliculas", ["drama"])
    env.double.add_interaction(ghost, item, "like", T0)
    with db_factory.begin() as s:
        s.execute(sa.text("INSERT INTO user_suppressions (user_id, requested_at, state, verified_at) VALUES (:u, now(), 'completed', now())"), {"u": ghost})
    env.pipeline.run()
    assert env.q("SELECT count(*) FROM users") == [(0,)] and env.q("SELECT count(*) FROM user_signals") == [(0,)]


def test_absent_user_does_not_trigger_suppression(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    user = env.double.add_user()
    env.pipeline.run()
    env.double.users.clear()
    env.pipeline.run()
    assert env.q("SELECT count(*) FROM users") == [(1,)] and env.q("SELECT count(*) FROM user_suppressions") == [(0,)]
    assert user


def test_absence_from_a_complete_listing_retires_logically_and_reappearance_restores(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    keep = [env.double.add_item("peliculas", [f"t{i}"]) for i in range(10)]
    env.pipeline.run()
    gone = keep[0]
    removed = env.double.items.pop(0)
    env.pipeline.run()  # 9 de 10: ratio 0,9, no aborta
    assert env.q("SELECT status::text, retired_at IS NOT NULL FROM items WHERE id = :i", i=gone) == [("retired", True)]
    env.double.items.append(removed)
    env.pipeline.run()
    assert env.q("SELECT status::text, retired_at IS NULL FROM items WHERE id = :i", i=gone) == [("available", True)]


def test_explicit_retirement_signal_uses_the_same_branch(db_factory, redis_client) -> None:  # noqa: ANN001
    env = Env(db_factory, redis_client)
    item = env.double.add_item("juegos", ["rpg"])
    env.pipeline.run()
    env.double.items[0]["status"] = "retired"
    env.pipeline.run()
    assert env.q("SELECT status::text FROM items WHERE id = :i", i=item) == [("retired",)]


@pytest.mark.parametrize("scenario", ["truncated", "volume_drop"])
def test_incomplete_listing_aborts_without_marking_any_retirement(db_factory, redis_client, scenario: str) -> None:  # noqa: ANN001
    """CR-9, FR-074: listado truncado al 50 % ⟹ cero retirados y corrida abortada con causa."""
    env = Env(db_factory, redis_client)
    for i in range(10):
        env.double.add_item("peliculas", [f"t{i}"])
    env.pipeline.run()
    if scenario == "truncated":
        env.double.truncate_catalog_to = 5
    else:
        del env.double.items[5:]  # listado «completo» pero con la mitad del volumen: ratio 0,5 < 0,9
    report = env.pipeline.run()
    assert report.status == "failed" and report.failure_reason
    assert env.q("SELECT count(*) FROM items WHERE status = 'retired'") == [(0,)]


def test_birth_date_correction_rederives_and_invalidates_in_the_same_act(db_factory, redis_client) -> None:  # noqa: ANN001
    """DI-2c, CR-4: una corrección que restringe el permiso invalida los resultados del usuario."""
    env = Env(db_factory, redis_client)
    user = env.double.add_user(birth_date=date(1990, 1, 1))
    env.pipeline.run()
    assert env.q("SELECT max_age_ordinal FROM users") == [(2,)]
    for key in (keys.reco_key(CFG.config_version, user, Module.PELICULAS), keys.stale_key(CFG.config_version, user, Module.JUEGOS), keys.filters_key(user)):
        redis_client.set(key, "{}")
    env.double.users[0]["birth_date"] = date(2015, 1, 1).isoformat()
    env.pipeline.run()
    assert env.q("SELECT max_age_ordinal FROM users") == [(0,)]
    assert redis_client.keys(f"*{user}*") == []


def test_pipeline_never_writes_derived_tables() -> None:
    """DI-13: el Data Transformer no escribe item_popularity, tag_modules ni vocab_*; ni vectores ni perfiles."""
    tree = ast.parse(Path(pipeline_module.__file__).read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        alias.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for alias in n.names
    }
    modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    forbidden = {"ItemPopularity", "TagModule", "VocabVersion", "VocabVersionTag", "ItemVector", "UserProfile", "ItemPromotion"}
    assert not names & forbidden
    assert not {m for m in modules if m.endswith(("vocabulary_sync", "batch.popularidad", "engine.content"))}
    source = Path(pipeline_module.__file__).read_text(encoding="utf-8")
    for table in ("item_popularity", "tag_modules", "vocab_versions", "vocab_version_tags", "item_vectors", "user_profiles"):
        assert table not in source
