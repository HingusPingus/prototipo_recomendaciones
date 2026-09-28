"""T030 — `tag_modules` solo sobre ítems vigentes (DI-15, RD-20)."""

from __future__ import annotations

import sqlalchemy as sa

from recomendaciones.observability.metrics import Metrics
from recomendaciones.transformer.vocabulary_sync import VocabularySync
from tests.integration import seed


def _modules(db_factory, tag: str) -> set[str]:  # noqa: ANN001
    with db_factory() as s:
        return set(s.execute(sa.text("SELECT module::text FROM tag_modules WHERE tag_name = :t"), {"t": tag}).scalars())


def test_retiring_the_last_item_of_a_module_removes_the_tag_from_it(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        seed.item(s, "peliculas", ["horror"])
        game = seed.item(s, "juegos", ["horror"])
    sync = VocabularySync(db_factory, Metrics())
    sync.run()
    assert _modules(db_factory, "horror") == {"peliculas", "juegos"}  # compartido
    with db_factory.begin() as s:
        s.execute(sa.text("UPDATE items SET status = 'retired', retired_at = now() WHERE id = :i"), {"i": game})
    sync.run()
    assert _modules(db_factory, "horror") == {"peliculas"}  # deja de ser compartido: deja de propagar
