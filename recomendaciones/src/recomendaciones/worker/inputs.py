"""Insumos del perfil desde la base (T054, T027, FR-087): declaración propia, herencia derivada y señales.

La herencia se **deriva** en cada reconstrucción —tags declarados en el otro módulo ∩ compartidos según
`tag_modules`— y nunca se lee de una tabla (RD-97): si el vocabulario compartido cambia, el insumo lo
refleja en el siguiente recálculo sin escritura adicional. El perfil `general` agrega las declaraciones
y señales de ambos módulos. Las señales sobre ítems retirados siguen siendo insumo (FR-073).
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from recomendaciones.engine.profile import ProfileInputs, ProfileSignal, derive_inherited
from recomendaciones.shared.domain import Module, ProfileScope
from recomendaciones.storage.db.models import Item, TagModule, UserDeclaredTag, UserSignal


def _declared(s: Session, user_id: uuid.UUID, modules: tuple[str, ...]) -> frozenset[str]:
    return frozenset(
        s.scalars(
            sa.select(UserDeclaredTag.tag_name).where(
                UserDeclaredTag.user_id == user_id, UserDeclaredTag.module.in_(modules)
            )
        )
    )


def shared_tags(s: Session) -> frozenset[str]:
    return frozenset(
        s.scalars(sa.select(TagModule.tag_name).group_by(TagModule.tag_name).having(sa.func.count() > 1))
    )


def load_profile_inputs(s: Session, user_id: uuid.UUID, scope: ProfileScope) -> ProfileInputs:
    scope = ProfileScope(scope)
    if scope is ProfileScope.GENERAL:
        modules: tuple[str, ...] = (Module.PELICULAS.value, Module.JUEGOS.value)
        declared = _declared(s, user_id, modules)
        inherited: frozenset[str] = frozenset()
    else:
        module = Module(scope.value)
        modules = (module.value,)
        declared = _declared(s, user_id, modules)
        inherited = derive_inherited(_declared(s, user_id, (module.opposite.value,)), shared_tags(s)) - declared
    rows = s.execute(
        sa.select(UserSignal.id, UserSignal.item_id, UserSignal.signal_type, UserSignal.occurred_at)
        .join(Item, Item.id == UserSignal.item_id)
        .where(UserSignal.user_id == user_id, Item.module.in_(modules))
        .order_by(UserSignal.occurred_at, UserSignal.id)
    ).all()
    signals = tuple(ProfileSignal(r.item_id, r.signal_type, r.occurred_at, r.id) for r in rows)
    return ProfileInputs(declared, inherited, signals)
