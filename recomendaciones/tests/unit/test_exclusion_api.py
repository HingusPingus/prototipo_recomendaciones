"""T014 — deuda del prototipo: el conjunto de exclusión expone una interfaz pública de consulta."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import recomendaciones
from recomendaciones.shared.domain import ExclusionSet

SRC = Path(recomendaciones.__file__).parent


def test_public_query_interface() -> None:
    a, b = uuid.UUID(int=1), uuid.UUID(int=2)
    ex = ExclusionSet(uuid.UUID(int=9), [a])
    assert ex.contains(a) and a in ex and not ex.contains(b)
    assert ex.item_ids == frozenset({a}) and len(ex) == 1


def test_internal_state_is_not_assignable() -> None:
    ex = ExclusionSet(uuid.UUID(int=9), [])
    try:
        ex.nuevo_atributo = 1  # type: ignore[attr-defined]
    except AttributeError:
        pass
    else:
        raise AssertionError("ExclusionSet debe ser cerrado (__slots__)")


def test_no_caller_reaches_into_private_attributes() -> None:
    """El prototipo accedía a `exclusion._ids` desde el batch (`orchestration.py`)."""
    pattern = re.compile(r"\.(_ids|_items|_item_ids)\b")
    offenders = [
        str(p.relative_to(SRC))
        for p in SRC.rglob("*.py")
        if p.name != "domain.py" and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []
