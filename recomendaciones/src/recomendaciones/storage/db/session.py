"""Motor y sesiones de SQLAlchemy sobre DB Recomendaciones (la única base, INV-4)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker


def create_db_engine(url: str) -> sa.Engine:
    return sa.create_engine(url, pool_pre_ping=True, future=True)


def session_factory(engine: sa.Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory.begin() as session:
        yield session


SessionFactory = sessionmaker[Session]
