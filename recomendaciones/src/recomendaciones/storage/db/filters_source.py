"""Repoblado de `filters:` y `retired:` ante miss de esa clave (INV-1: uno de los tres accesos a
Postgres que la API admite, T006). Lecturas acotadas por clave primaria o por índice."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from recomendaciones.shared.domain import ExclusionSet, Module
from recomendaciones.storage.cache.filters import UserFilters
from recomendaciones.storage.db.models import Item, User, UserDeclaredTag, UserExclusion


class DbFiltersSource:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def load_user_filters(self, user_id: uuid.UUID) -> UserFilters | None:
        with self._factory() as s:
            user = s.execute(
                sa.select(User.max_age_ordinal, User.age_config_version).where(User.id == user_id)
            ).one_or_none()
            if user is None:
                return None
            excluded = s.scalars(sa.select(UserExclusion.item_id).where(UserExclusion.user_id == user_id)).all()
            declared = s.scalars(
                sa.select(UserDeclaredTag.module).where(UserDeclaredTag.user_id == user_id).distinct()
            ).all()
        return UserFilters(
            user_id=user_id,
            max_age_ordinal=user.max_age_ordinal,
            age_config_version=user.age_config_version,
            exclusions=ExclusionSet(user_id, excluded),
            declared_modules=frozenset(Module(m) for m in declared),
        )

    def load_retired(self, module: Module, window_seconds: int) -> frozenset[uuid.UUID]:
        # §3.1 acota el set por `retired_at` (RD-39), aunque §2.2 lo declara forense: es la única
        # marca que permite la cota y es la consulta que el modelo especifica para esta familia.
        with self._factory() as s:
            rows = s.scalars(
                sa.select(Item.id).where(
                    Item.module == Module(module).value,
                    Item.status == "retired",
                    Item.retired_at > sa.func.now() - sa.func.make_interval(0, 0, 0, 0, 0, 0, window_seconds),
                )
            ).all()
        return frozenset(rows)
