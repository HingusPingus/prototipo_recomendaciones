"""T030 — transición de vocabulario: vectores completos antes de activar, activación atómica (FR-010f, FR-010g, RD-22)."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

import recomendaciones.transformer.vocabulary_sync as vocab_module
from recomendaciones.observability.metrics import Metrics
from recomendaciones.transformer.vocabulary_sync import VocabularySync
from tests.integration import seed


def _q(db_factory, sql: str, **p: object) -> list[tuple]:  # noqa: ANN001
    with db_factory() as s:
        return [tuple(r) for r in s.execute(sa.text(sql), p).all()]


def _active(db_factory) -> str:  # noqa: ANN001
    return _q(db_factory, "SELECT version FROM vocab_versions WHERE activated_at IS NOT NULL AND deactivated_at IS NULL")[0][0]


def test_new_vocabulary_is_fully_vectorized_before_activation(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        items = [seed.item(s, "peliculas", ["horror"]), seed.item(s, "peliculas", ["drama"])]
    sync = VocabularySync(db_factory, Metrics())
    sync.run()
    old = _active(db_factory)
    with db_factory.begin() as s:
        items.append(seed.item(s, "juegos", ["rpg"]))  # tag nuevo ⟹ versión nueva
    sync.run()
    new = _active(db_factory)
    assert new != old
    under_new = {r[0] for r in _q(db_factory, "SELECT item_id FROM item_vectors WHERE vocab_version = :v", v=new)}
    assert under_new == set(items)  # no existe instante con la versión activa a medio vectorizar
    dims = _q(db_factory, "SELECT tag_count FROM vocab_versions WHERE version = :v", v=new)[0][0]
    lengths = {r[0] for r in _q(db_factory, "SELECT vector_dims(vector) FROM item_vectors WHERE vocab_version = :v", v=new)}
    assert lengths == {dims} == {3}  # DI-17


def test_interrupted_transition_does_not_activate(db_factory, monkeypatch) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        seed.item(s, "peliculas", ["horror"])
    sync = VocabularySync(db_factory, Metrics())
    sync.run()
    old = _active(db_factory)
    with db_factory.begin() as s:
        seed.item(s, "juegos", ["rpg"])

    def crash(*a: object, **k: object) -> None:
        raise RuntimeError("interrupción a mitad de la transición")

    monkeypatch.setattr(vocab_module, "vectorize_catalog", crash)
    with pytest.raises(RuntimeError):
        sync.run()
    assert _active(db_factory) == old


def test_versions_are_identified_by_content(db_factory) -> None:  # noqa: ANN001
    """DI-14: mismo conjunto de tags ⟹ mismo identificador."""
    with db_factory.begin() as s:
        seed.item(s, "peliculas", ["horror", "drama"])
    VocabularySync(db_factory, Metrics()).run()
    first = _active(db_factory)
    VocabularySync(db_factory, Metrics()).run()
    assert _active(db_factory) == first
