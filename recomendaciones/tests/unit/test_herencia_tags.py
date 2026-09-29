"""T054 — herencia de tags entre módulos: derivada, no persistida y fuera del mínimo (FR-085, RD-97)."""

from __future__ import annotations

import pytest

from recomendaciones.api.services.declaracion import validate_declaration
from recomendaciones.engine.profile import derive_inherited
from recomendaciones.shared.errors import InvalidRequest


def test_inherited_are_other_module_declared_intersect_shared() -> None:
    assert derive_inherited(frozenset({"horror", "drama", "rpg"}), frozenset({"horror", "drama", "comedia"})) == {"horror", "drama"}


def test_five_inherited_and_zero_own_is_rejected() -> None:
    inherited = {"a", "b", "c", "d", "e"}
    with pytest.raises(InvalidRequest):
        validate_declaration([], declarable=frozenset(inherited), minimum=5)  # el mínimo cuenta solo propios
