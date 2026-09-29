"""T014 — resolutor de exclusiones: escritor único, aditivo, invalida `filters:` antes de escribir."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.orm import Session, sessionmaker

from recomendaciones.storage.db.exclusions import ExclusionResolver, load_exclusion_set
from tests.integration.conftest import alembic_config

T0 = datetime(2026, 9, 1, tzinfo=UTC)


@pytest.fixture
def db(pg_url: str) -> Iterator[sessionmaker[Session]]:
    admin = sa.create_engine(pg_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text("DROP DATABASE IF EXISTS excltest"))
        conn.execute(sa.text("CREATE DATABASE excltest"))
    admin.dispose()
    url = pg_url.rsplit("/", 1)[0] + "/excltest"
    command.upgrade(alembic_config(url), "head")
    eng = sa.create_engine(url)
    with eng.begin() as conn:
        conn.execute(sa.text("INSERT INTO engine_config_versions VALUES ('cfg', '{}', now(), NULL)"))
    yield sessionmaker(bind=eng, expire_on_commit=False)
    eng.dispose()


def _user(s: Session) -> uuid.UUID:
    uid = uuid.uuid4()
    s.execute(
        sa.text("INSERT INTO users VALUES (:u, '1990-01-01', 2, 'cfg', now(), 'AR', now())"), {"u": uid}
    )
    return uid


def _item(s: Session) -> uuid.UUID:
    iid = uuid.uuid4()
    s.execute(
        sa.text("INSERT INTO items (id, module, age_config_version, age_rating_source, synced_at) "
                "VALUES (:i, 'peliculas', 'cfg', 'declared', now())"),
        {"i": iid},
    )
    return iid


def _signal(s: Session, user: uuid.UUID, item: uuid.UUID, kind: str, minutes: int) -> None:
    s.execute(
        sa.text(
            "INSERT INTO user_signals (origin_interaction_id, user_id, item_id, signal_type, occurred_at, source) "
            "VALUES (:o, :u, :i, :k, :t, 'sync')"
        ),
        {"o": str(uuid.uuid4()), "u": user, "i": item, "k": kind, "t": T0 + timedelta(minutes=minutes)},
    )


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, uuid.UUID]] = []

    def __call__(self, user_id: uuid.UUID) -> None:
        self.events.append(("invalidate", user_id))


def _origins(s: Session, user: uuid.UUID) -> dict[uuid.UUID, str]:
    rows = s.execute(sa.text("SELECT item_id, origin::text FROM user_exclusions WHERE user_id = :u"), {"u": user})
    return dict(rows.all())


def test_resolves_the_four_origins_with_latest_wins(db: sessionmaker[Session]) -> None:
    rec = Recorder()
    resolver = ExclusionResolver(rec)
    with db.begin() as s:
        user = _user(s)
        liked, disliked, consumed, reverted = (_item(s) for _ in range(4))
        _signal(s, user, liked, "like", 0)
        _signal(s, user, disliked, "dislike", 0)
        _signal(s, user, consumed, "consumo", 0)
        _signal(s, user, consumed, "like", 5)
        _signal(s, user, reverted, "dislike", 0)
        _signal(s, user, reverted, "like", 5)
        result = resolver.resolve(s, {user})
    assert result.affected_users == {user}
    with db.begin() as s:
        assert _origins(s, user) == {liked: "like", disliked: "dislike", consumed: "consumo", reverted: "like"}
        assert load_exclusion_set(s, user).item_ids == {liked, disliked, consumed, reverted}


def test_invalidates_filters_before_writing(db: sessionmaker[Session]) -> None:
    order: list[str] = []

    def invalidate(user_id: uuid.UUID) -> None:
        with db() as probe:  # otra conexión: todavía no ve la escritura
            order.append(f"invalidate:{len(_origins(probe, user_id))}")

    resolver = ExclusionResolver(invalidate)
    with db.begin() as s:
        user, item = _user(s), _item(s)
    with db.begin() as s:
        _signal(s, user, item, "dislike", 0)
        resolver.resolve(s, {user})
        order.append("write")
    assert order[0] == "invalidate:0"


def test_consumo_exclusion_survives_purge_of_its_signal(db: sessionmaker[Session]) -> None:
    """DI-20: reconstruir tras purgar la señal de un consumo conserva la exclusión (FR-029b1)."""
    resolver = ExclusionResolver(Recorder())
    with db.begin() as s:
        user, item = _user(s), _item(s)
        _signal(s, user, item, "consumo", 0)
        resolver.resolve(s, {user})
    with db.begin() as s:
        s.execute(sa.text("DELETE FROM user_signals WHERE user_id = :u"), {"u": user})  # purga simulada
        resolver.resolve(s, {user})
    with db.begin() as s:
        assert _origins(s, user) == {item: "consumo"}


def test_consumo_is_never_downgraded_by_later_like(db: sessionmaker[Session]) -> None:
    resolver = ExclusionResolver(Recorder())
    with db.begin() as s:
        user, item = _user(s), _item(s)
        _signal(s, user, item, "consumo", 0)
        resolver.resolve(s, {user})
    with db.begin() as s:
        _signal(s, user, item, "like", 10)
        resolver.resolve(s, {user})
    with db.begin() as s:
        assert _origins(s, user) == {item: "consumo"}


def test_resolved_at_written_and_idempotent(db: sessionmaker[Session]) -> None:
    rec = Recorder()
    resolver = ExclusionResolver(rec)
    with db.begin() as s:
        user, item = _user(s), _item(s)
        _signal(s, user, item, "like", 0)
        resolver.resolve(s, {user})
    with db.begin() as s:
        first = s.execute(sa.text("SELECT resolved_at FROM user_exclusions")).scalar_one()
        again = resolver.resolve(s, {user})
    assert first is not None
    assert again.affected_users == set()  # sin cambios: ni escritura ni invalidación


def test_same_timestamp_tie_breaks_by_id(db: sessionmaker[Session]) -> None:
    resolver = ExclusionResolver(Recorder())
    with db.begin() as s:
        user, item = _user(s), _item(s)
        _signal(s, user, item, "like", 0)
        _signal(s, user, item, "dislike", 0)  # mismo occurred_at, id mayor
        resolver.resolve(s, {user})
    with db.begin() as s:
        assert _origins(s, user) == {item: "dislike"}
