"""Siembra de datos materializados para tests de integración (atajos sobre la proyección local)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

T0 = datetime(2026, 9, 1, tzinfo=UTC)


def active_config(s: Session) -> str:
    return s.execute(
        sa.text("SELECT config_version FROM engine_config_versions WHERE deactivated_at IS NULL")
    ).scalar_one()


def user(
    s: Session,
    *,
    birth_date: date = date(1990, 1, 1),
    max_age_ordinal: int = 2,
    region: str = "AR",
    user_id: uuid.UUID | None = None,
    config_version: str | None = None,
) -> uuid.UUID:
    uid = user_id or uuid.uuid4()
    s.execute(
        sa.text(
            "INSERT INTO users (id, birth_date, max_age_ordinal, age_config_version, age_derived_at, region, synced_at) "
            "VALUES (:u, :b, :o, :c, now(), :r, now())"
        ),
        {"u": uid, "b": birth_date, "o": max_age_ordinal, "c": config_version or active_config(s), "r": region},
    )
    return uid


def tags(s: Session, names: Iterable[str]) -> None:
    for name in names:
        s.execute(
            sa.text("INSERT INTO tags (name, synced_at) VALUES (:n, now()) ON CONFLICT DO NOTHING"), {"n": name}
        )


def item(
    s: Session,
    module: str,
    tag_names: Iterable[str],
    *,
    rating: str = "ATP",
    ordinal: int = 0,
    item_id: uuid.UUID | None = None,
    status: str = "available",
    retired_at: datetime | None = None,
) -> uuid.UUID:
    iid = item_id or uuid.uuid4()
    tag_list = list(tag_names)
    tags(s, tag_list)
    if status == "retired" and retired_at is None:
        retired_at = datetime.now(UTC)
    s.execute(
        sa.text(
            "INSERT INTO items (id, module, status, retired_at, min_age_ordinal, age_config_version, age_rating, "
            "age_rating_source, synced_at) VALUES (:i, :m, :st, :ra, :o, :c, :r, 'declared', now())"
        ),
        {"i": iid, "m": module, "st": status, "ra": retired_at, "o": ordinal, "c": active_config(s), "r": rating},
    )
    for tag in tag_list:
        s.execute(sa.text("INSERT INTO item_tags VALUES (:i, :t)"), {"i": iid, "t": tag})
    return iid


def signal(
    s: Session,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    kind: str,
    *,
    minutes: int = 0,
    source: str = "sync",
    origin_interaction_id: str | None = None,
    received_at: datetime | None = None,
) -> str:
    oid = origin_interaction_id or f"int-{uuid.uuid4()}"
    s.execute(
        sa.text(
            "INSERT INTO user_signals (origin_interaction_id, user_id, item_id, signal_type, occurred_at, source, received_at) "
            "VALUES (:o, :u, :i, :k, :t, :src, COALESCE(:rcv, now()))"
        ),
        {
            "o": oid,
            "u": user_id,
            "i": item_id,
            "k": kind,
            "t": T0 + timedelta(minutes=minutes),
            "src": source,
            "rcv": received_at,
        },
    )
    return oid


def declare(s: Session, user_id: uuid.UUID, module: str, tag_names: Iterable[str]) -> None:
    for tag in tag_names:
        s.execute(
            sa.text("INSERT INTO user_declared_tags VALUES (:u, :m, :t, now())"), {"u": user_id, "m": module, "t": tag}
        )


def exclusion(s: Session, user_id: uuid.UUID, item_id: uuid.UUID, origin: str = "dislike") -> None:
    s.execute(
        sa.text("INSERT INTO user_exclusions VALUES (:u, :i, :o, now())"), {"u": user_id, "i": item_id, "o": origin}
    )
