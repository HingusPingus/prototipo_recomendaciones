"""T003 — esquema DB Recomendaciones + Alembic (data-model.md §2).

Ciclo upgrade/downgrade/upgrade sobre base vacía y poblada, y las restricciones que el esquema
—no el código— debe hacer cumplir.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.integration.conftest import alembic_config

EXPECTED_TABLES = {
    "users",
    "items",
    "tags",
    "item_tags",
    "item_vectors",
    "user_profiles",
    "user_signals",
    "user_exclusions",
    "engine_config_versions",
    "sync_runs",
    "processed_events",
    "item_popularity",
    "tag_modules",
    "vocab_versions",
    "vocab_version_tags",
    "user_declared_tags",
    "user_suppressions",
    "item_promotions",
}


@pytest.fixture(scope="module")
def mig_url(pg_url: str) -> str:
    """Base propia del módulo, para no interferir con otros tests de integración."""
    admin = sa.create_engine(pg_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text("DROP DATABASE IF EXISTS migtest"))
        conn.execute(sa.text("CREATE DATABASE migtest"))
    admin.dispose()
    return pg_url.rsplit("/", 1)[0] + "/migtest"


@pytest.fixture
def engine(mig_url: str) -> Iterator[sa.Engine]:
    cfg = alembic_config(mig_url)
    command.upgrade(cfg, "head")
    eng = sa.create_engine(mig_url)
    yield eng
    eng.dispose()
    command.downgrade(cfg, "base")


def _tables(eng: sa.Engine) -> set[str]:
    return set(sa.inspect(eng).get_table_names()) - {"alembic_version"}


def _seed_config(conn: sa.Connection, version: str = "sha256:test") -> str:
    conn.execute(
        sa.text(
            "INSERT INTO engine_config_versions (config_version, payload, activated_at) "
            "VALUES (:v, '{}'::jsonb, now())"
        ),
        {"v": version},
    )
    return version


def _seed_user(conn: sa.Connection, cfg: str, **overrides: object) -> uuid.UUID:
    uid = uuid.uuid4()
    values = {
        "id": uid,
        "birth_date": "2000-01-01",
        "max_age_ordinal": 2,
        "age_config_version": cfg,
        "age_derived_at": "2026-09-28T00:00:00Z",
        "region": "AR",
        "synced_at": "2026-09-28T00:00:00Z",
    }
    values.update(overrides)
    cols = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    conn.execute(sa.text(f"INSERT INTO users ({cols}) VALUES ({params})"), values)
    return uid


def _seed_item(conn: sa.Connection, cfg: str) -> uuid.UUID:
    iid = uuid.uuid4()
    conn.execute(
        sa.text(
            "INSERT INTO items (id, module, age_config_version, age_rating_source, synced_at) "
            "VALUES (:id, 'peliculas', :cfg, 'unknown_defaulted', now())"
        ),
        {"id": iid, "cfg": cfg},
    )
    return iid


def test_upgrade_downgrade_upgrade_on_empty_database(mig_url: str) -> None:
    cfg = alembic_config(mig_url)
    command.upgrade(cfg, "head")
    eng = sa.create_engine(mig_url)
    assert _tables(eng) == EXPECTED_TABLES
    command.downgrade(cfg, "base")
    assert _tables(eng) == set()
    command.upgrade(cfg, "head")
    assert _tables(eng) == EXPECTED_TABLES
    command.downgrade(cfg, "base")
    eng.dispose()


def test_downgrade_on_populated_database(mig_url: str) -> None:
    cfg = alembic_config(mig_url)
    command.upgrade(cfg, "head")
    eng = sa.create_engine(mig_url)
    with eng.begin() as conn:
        version = _seed_config(conn)
        user = _seed_user(conn, version)
        item = _seed_item(conn, version)
        conn.execute(sa.text("INSERT INTO tags (name, synced_at) VALUES ('horror', now())"))
        conn.execute(sa.text("INSERT INTO item_tags VALUES (:i, 'horror')"), {"i": item})
        conn.execute(
            sa.text(
                "INSERT INTO user_signals (origin_interaction_id, user_id, item_id, signal_type, "
                "occurred_at, source) VALUES ('int-1', :u, :i, 'like', now(), 'sync')"
            ),
            {"u": user, "i": item},
        )
    command.downgrade(cfg, "base")
    assert _tables(eng) == set()
    command.upgrade(cfg, "head")
    assert _tables(eng) == EXPECTED_TABLES
    command.downgrade(cfg, "base")
    eng.dispose()


def test_item_without_age_rating_gets_most_restrictive_default(engine: sa.Engine) -> None:
    with engine.begin() as conn:
        item = _seed_item(conn, _seed_config(conn))
        rating, ordinal, status = conn.execute(
            sa.text("SELECT age_rating::text, min_age_ordinal, status::text FROM items WHERE id = :i"),
            {"i": item},
        ).one()
    assert (rating, ordinal, status) == ("+18", 2, "available")


def test_item_with_null_age_rating_violates_constraint(engine: sa.Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        cfg = _seed_config(conn)
        conn.execute(
            sa.text(
                "INSERT INTO items (id, module, age_rating, age_config_version, age_rating_source, "
                "synced_at) VALUES (:id, 'juegos', NULL, :cfg, 'declared', now())"
            ),
            {"id": uuid.uuid4(), "cfg": cfg},
        )


def test_retired_at_iff_retired(engine: sa.Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        item = _seed_item(conn, _seed_config(conn))
        conn.execute(sa.text("UPDATE items SET status = 'retired' WHERE id = :i"), {"i": item})


def test_profile_with_invalid_scope_violates_constraint(engine: sa.Engine) -> None:
    with pytest.raises(DBAPIError), engine.begin() as conn:
        user = _seed_user(conn, _seed_config(conn))
        conn.execute(
            sa.text("INSERT INTO vocab_versions (version, tag_count, created_at) VALUES ('v1', 1, now())")
        )
        conn.execute(
            sa.text(
                "INSERT INTO user_profiles (user_id, scope, vocab_version, vector, signal_count, computed_at) "
                "VALUES (:u, 'musica', 'v1', '[1]', 0, now())"
            ),
            {"u": user},
        )


@pytest.mark.parametrize(
    "overrides",
    [{"birth_date": None}, {"region": None}, {"region": "ar"}, {"region": "ARG"}],
    ids=["sin-birth_date", "sin-region", "region-minuscula", "region-3-letras"],
)
def test_user_ingest_constraints(engine: sa.Engine, overrides: dict[str, object]) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _seed_user(conn, _seed_config(conn), **overrides)


def test_users_have_no_max_age_rating_nor_age_resolution(engine: sa.Engine) -> None:
    cols = {c["name"] for c in sa.inspect(engine).get_columns("users")}
    assert "max_age_rating" not in cols and "age_resolution" not in cols
    assert {"birth_date", "max_age_ordinal", "age_derived_at", "age_config_version", "region"} <= cols


def test_item_vectors_is_pgvector_with_vocab_version_in_pk(engine: sa.Engine) -> None:
    insp = sa.inspect(engine)
    assert insp.get_pk_constraint("item_vectors")["constrained_columns"] == ["item_id", "vocab_version"]
    with engine.connect() as conn:
        udt = conn.execute(
            sa.text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_name = 'item_vectors' AND column_name = 'vector'"
            )
        ).scalar_one()
    assert udt == "vector"


def test_item_popularity_composite_pk_and_checks(engine: sa.Engine) -> None:
    assert sa.inspect(engine).get_pk_constraint("item_popularity")["constrained_columns"] == [
        "item_id",
        "config_version",
    ]
    with pytest.raises(IntegrityError), engine.begin() as conn:
        cfg = _seed_config(conn)
        item = _seed_item(conn, cfg)
        conn.execute(
            sa.text(
                "INSERT INTO item_popularity VALUES (:i, :c, 10, 5, 0.5, now())"
            ),
            {"i": item, "c": cfg},
        )


def test_user_exclusions_has_no_is_permanent(engine: sa.Engine) -> None:
    cols = {c["name"] for c in sa.inspect(engine).get_columns("user_exclusions")}
    assert cols == {"user_id", "item_id", "origin", "resolved_at"}


def test_config_immutability_trigger(engine: sa.Engine) -> None:
    with engine.begin() as conn:
        _seed_config(conn, "sha256:a")
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(sa.text("UPDATE engine_config_versions SET payload = '{\"x\":1}'::jsonb"))
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE engine_config_versions SET deactivated_at = now()"))
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(sa.text("UPDATE engine_config_versions SET deactivated_at = NULL"))


def test_at_most_one_active_config(engine: sa.Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _seed_config(conn, "sha256:a")
        _seed_config(conn, "sha256:b")


def test_declared_tags_asymmetric_fks(engine: sa.Engine) -> None:
    with engine.begin() as conn:
        user = _seed_user(conn, _seed_config(conn))
        conn.execute(sa.text("INSERT INTO tags (name, synced_at) VALUES ('horror', now())"))
        conn.execute(
            sa.text("INSERT INTO user_declared_tags VALUES (:u, 'peliculas', 'horror', now())"), {"u": user}
        )
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM tags WHERE name = 'horror'"))
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": user})
        left = conn.execute(sa.text("SELECT count(*) FROM user_declared_tags")).scalar_one()
    assert left == 0


def test_processed_events_and_signal_uniqueness(engine: sa.Engine) -> None:
    eid = uuid.uuid4()
    with pytest.raises(IntegrityError), engine.begin() as conn:
        for _ in range(2):
            conn.execute(
                sa.text(
                    "INSERT INTO processed_events VALUES (:e, now(), 'recomputed', now() + interval '1 day')"
                ),
                {"e": eid},
            )
    with pytest.raises(IntegrityError), engine.begin() as conn:
        cfg = _seed_config(conn)
        user, item = _seed_user(conn, cfg), _seed_item(conn, cfg)
        for kind in ("like", "dislike"):
            conn.execute(
                sa.text(
                    "INSERT INTO user_signals (origin_interaction_id, user_id, item_id, signal_type, "
                    "occurred_at, source) VALUES ('int-dup', :u, :i, :k, now(), 'evento')"
                ),
                {"u": user, "i": item, "k": kind},
            )


def test_signal_without_origin_interaction_id_is_rejected(engine: sa.Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        cfg = _seed_config(conn)
        user, item = _seed_user(conn, cfg), _seed_item(conn, cfg)
        conn.execute(
            sa.text(
                "INSERT INTO user_signals (origin_interaction_id, user_id, item_id, signal_type, "
                "occurred_at, source) VALUES (NULL, :u, :i, 'like', now(), 'sync')"
            ),
            {"u": user, "i": item},
        )


def test_user_suppressions_survive_cascade_and_check_state(engine: sa.Engine) -> None:
    with engine.begin() as conn:
        user = _seed_user(conn, _seed_config(conn))
        conn.execute(
            sa.text("INSERT INTO user_suppressions (user_id, requested_at, state) VALUES (:u, now(), 'in_progress')"),
            {"u": user},
        )
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": user})
        assert conn.execute(sa.text("SELECT count(*) FROM user_suppressions")).scalar_one() == 1
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(sa.text("UPDATE user_suppressions SET state = 'completed'"))  # sin verified_at


def test_item_promotions_restrict(engine: sa.Engine) -> None:
    with engine.begin() as conn:
        cfg = _seed_config(conn)
        item = _seed_item(conn, cfg)
        conn.execute(sa.text("INSERT INTO item_promotions VALUES (:i, now(), :c)"), {"i": item, "c": cfg})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM items WHERE id = :i"), {"i": item})


def test_required_indexes_exist(engine: sa.Engine) -> None:
    with engine.connect() as conn:
        names = set(conn.execute(sa.text("SELECT indexname FROM pg_indexes WHERE schemaname='public'")).scalars())
    assert {
        "idx_signals_user_received",
        "idx_signals_vigente",
        "idx_items_candidates",
        "idx_users_birth_date",
        "idx_popularity_ranking",
        "idx_suppressions_open",
        "idx_sync_runs_success",
        "idx_processed_expires",
        "idx_declared_user_module",
        "idx_item_tags_tag",
        "idx_tag_modules_module",
    } <= names


def test_every_foreign_key_declares_on_delete_policy(engine: sa.Engine) -> None:
    """Cuatro omisiones históricas (RD-19, RD-31, RD-35, RD-43): toda FK es CASCADE o RESTRICT."""
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT conrelid::regclass::text, conname, confdeltype FROM pg_constraint "
                "WHERE contype = 'f' AND connamespace = 'public'::regnamespace"
            )
        ).all()
    assert rows, "no hay FKs"
    undeclared = [(t, n) for t, n, policy in rows if policy not in ("c", "r")]
    assert not undeclared, f"FK sin política ON DELETE explícita: {undeclared}"


def test_user_suppressions_has_no_foreign_key(engine: sa.Engine) -> None:
    assert sa.inspect(engine).get_foreign_keys("user_suppressions") == []
