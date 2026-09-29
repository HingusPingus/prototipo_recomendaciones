"""T011 — señal cross-module (FR-024, SC-010)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from recomendaciones.engine.content import CatalogItem, vectorize_catalog
from recomendaciones.engine.cross_module import cross_module_scores
from recomendaciones.engine.profile import ProfileInputs, ProfileSignal, SignalWeights, build_profile
from recomendaciones.engine.vocabulary import Vocabulary

T0 = datetime(2026, 9, 1, tzinfo=UTC)
MOVIES = [
    CatalogItem(uuid.UUID(int=1), "peliculas", frozenset({"horror", "sobrenatural"})),
    CatalogItem(uuid.UUID(int=2), "peliculas", frozenset({"horror", "thriller"})),
    CatalogItem(uuid.UUID(int=3), "peliculas", frozenset({"comedia"})),
]
GAMES = [
    CatalogItem(uuid.UUID(int=11), "juegos", frozenset({"horror", "survival"})),
    CatalogItem(uuid.UUID(int=12), "juegos", frozenset({"deportes", "competitivo"})),
    CatalogItem(uuid.UUID(int=13), "juegos", frozenset({"plataformas", "familiar"})),
]


def _general_profile_from_movie_likes():  # noqa: ANN202
    items = MOVIES + GAMES
    vocab = Vocabulary.from_tags({t for i in items for t in i.tags})
    vectors = vectorize_catalog(items, vocab)
    signals = (ProfileSignal(MOVIES[0].item_id, "like", T0, 1), ProfileSignal(MOVIES[1].item_id, "like", T0, 2))
    general = build_profile(
        ProfileInputs(frozenset(), frozenset(), signals),
        vectors,
        {i.item_id: i.tags for i in items},
        vocab,
        SignalWeights(1.0, -1.0),
    )
    return general, vectors


def test_horror_movies_boost_horror_games() -> None:
    general, vectors = _general_profile_from_movie_likes()
    games = {g.item_id: vectors[g.item_id] for g in GAMES}
    boost = cross_module_scores(general.vector, games, has_opposite_activity=True)
    assert boost[GAMES[0].item_id] > boost[GAMES[1].item_id]
    assert boost[GAMES[0].item_id] > boost[GAMES[2].item_id]
    assert boost[GAMES[0].item_id] > 0  # resultado no trivial en el módulo sin actividad (SC-010)


def test_no_activity_in_opposite_module_gives_zero() -> None:
    general, vectors = _general_profile_from_movie_likes()
    games = {g.item_id: vectors[g.item_id] for g in GAMES}
    assert set(cross_module_scores(general.vector, games, has_opposite_activity=False).values()) == {0.0}
    assert set(cross_module_scores(None, games, has_opposite_activity=True).values()) == {0.0}


def test_boost_is_bounded() -> None:
    general, vectors = _general_profile_from_movie_likes()
    boost = cross_module_scores(general.vector, dict(vectors), has_opposite_activity=True)
    assert all(-1.0 <= b <= 1.0 for b in boost.values())
