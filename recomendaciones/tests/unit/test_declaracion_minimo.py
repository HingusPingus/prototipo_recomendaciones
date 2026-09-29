"""T053 — validación de la declaración: mínimo de tags propios, sin máximo, solo vocabulario vigente."""

from __future__ import annotations

import pytest

from recomendaciones.api.services.declaracion import validate_declaration
from recomendaciones.shared.errors import InvalidRequest

VOCAB = frozenset(f"tag{i}" for i in range(60))


@pytest.mark.parametrize(("n", "ok"), [(4, False), (5, True), (40, True)])
def test_minimum_without_maximum(n: int, ok: bool) -> None:
    tags = [f"tag{i}" for i in range(n)]
    if ok:
        assert validate_declaration(tags, declarable=VOCAB, minimum=5) == tuple(sorted(tags))
    else:
        with pytest.raises(InvalidRequest):
            validate_declaration(tags, declarable=VOCAB, minimum=5)


def test_only_current_vocabulary_is_acceptable() -> None:
    with pytest.raises(InvalidRequest) as exc:
        validate_declaration(["tag1", "tag2", "tag3", "tag4", "inventado"], declarable=VOCAB, minimum=5)
    assert "inventado" in str(exc.value)


def test_duplicates_count_once() -> None:
    with pytest.raises(InvalidRequest):
        validate_declaration(["tag1", "tag1", "tag2", "tag3", "tag4"], declarable=VOCAB, minimum=5)
