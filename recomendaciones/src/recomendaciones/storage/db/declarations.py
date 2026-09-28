"""Escritura de la declaración de gustos (T053): uno de los tres accesos a Postgres de la API (INV-1).

`user_declared_tags` solo recibe `INSERT` de este repositorio y `DELETE` por el `CASCADE` de la
supresión (RD-109, FR-086a): no hay operación de edición ni de retiro.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from recomendaciones.shared.domain import Module
from recomendaciones.storage.db.models import TagModule, User, UserDeclaredTag


class DeclarationRepository:
    def lock_user(self, s: Session, user_id: uuid.UUID) -> bool:
        """Serializa las declaraciones concurrentes del mismo usuario. `False` si no existe."""
        return s.execute(sa.select(User.id).where(User.id == user_id).with_for_update()).first() is not None

    def declared_tags(self, s: Session, user_id: uuid.UUID, module: Module) -> frozenset[str]:
        rows = s.scalars(
            sa.select(UserDeclaredTag.tag_name).where(
                UserDeclaredTag.user_id == user_id, UserDeclaredTag.module == Module(module).value
            )
        ).all()
        return frozenset(rows)

    def declarable_tags(self, s: Session, module: Module) -> frozenset[str]:
        """Vocabulario vigente del módulo según `tag_modules` (DEP-10)."""
        return frozenset(s.scalars(sa.select(TagModule.tag_name).where(TagModule.module == Module(module).value)))

    def shared_tags(self, s: Session) -> frozenset[str]:
        """Tags compartidos: pertenecen a más de un módulo (§2.12)."""
        rows = s.scalars(
            sa.select(TagModule.tag_name).group_by(TagModule.tag_name).having(sa.func.count() > 1)
        ).all()
        return frozenset(rows)

    def insert(self, s: Session, user_id: uuid.UUID, module: Module, tags: Iterable[str]) -> None:
        rows = [
            {"user_id": user_id, "module": Module(module).value, "tag_name": t, "declared_at": sa.func.now()}
            for t in tags
        ]
        s.execute(sa.insert(UserDeclaredTag).values(rows))
