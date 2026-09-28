"""T013 — filtro de edad fail-closed (FR-049…FR-055, DI-1, DI-2b, SC-002). Test-first: es la spec.

La regla es y solo es `item.min_age_ordinal <= user.max_age_ordinal` (§4.2). Un rating ausente,
vacío, basura o fuera del catálogo se mapea al ordinal más restrictivo (FR-051, CR-15): nunca al
permisivo, que es el `.get(rating, 0)` del prototipo (P2).
"""

from __future__ import annotations

import inspect
import uuid
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

import recomendaciones.engine.postprocess as postprocess
from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
from recomendaciones.engine.age import derive_max_age_ordinal, min_age_ordinal_for_rating
from recomendaciones.engine.postprocess import _age_stage
from recomendaciones.engine.scoring import Candidate, ScoredCandidate

CFG = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")
TODAY = date(2026, 9, 28)
GARBAGE = [None, "", "XYZ", 123, "NC-17", "+16", "atp", " +18", "PG-13", "M"]


def _scored(rating: object, n: int = 0) -> ScoredCandidate:
    cand = Candidate(
        item_id=uuid.UUID(int=n + 1),
        module="peliculas",
        available=True,
        min_age_ordinal=min_age_ordinal_for_rating(rating, CFG),
        vector=None,
        popularity=0.0,
        tags=frozenset(),
    )
    return ScoredCandidate(cand, 0.5)


def _age_band_birthdates() -> dict[str, date]:
    return {
        "niño-8": date(2018, 1, 1),
        "12-y-364d": date(2013, 9, 29),
        "13-exacto": date(2013, 9, 28),
        "17": date(2009, 1, 1),
        "17-y-364d": date(2008, 9, 29),
        "18-exacto": date(2008, 9, 28),
        "adulto-40": date(1986, 5, 5),
    }


@pytest.mark.parametrize("band", sorted(_age_band_birthdates()))
@pytest.mark.parametrize("rating", ["ATP", "+13", "+18"])
def test_cartesian_product_rating_by_age_band(band: str, rating: str) -> None:
    birth = _age_band_birthdates()[band]
    user_ordinal = derive_max_age_ordinal(birth, TODAY, CFG)
    age = TODAY.year - birth.year - ((TODAY.month, TODAY.day) < (birth.month, birth.day))
    min_age = next(level.min_age for level in CFG.age_rating_catalog if level.rating == rating)
    survivors = _age_stage([_scored(rating)], user_ordinal)
    assert (len(survivors) == 1) == (age >= min_age)


@pytest.mark.parametrize("garbage", GARBAGE, ids=repr)
def test_garbage_ratings_map_to_most_restrictive(garbage: object) -> None:
    assert min_age_ordinal_for_rating(garbage, CFG) == CFG.max_ordinal
    for band, birth in _age_band_birthdates().items():
        user_ordinal = derive_max_age_ordinal(birth, TODAY, CFG)
        if user_ordinal < CFG.max_ordinal:  # todo menor
            assert _age_stage([_scored(garbage)], user_ordinal) == [], band


@given(
    birth=st.dates(min_value=date(1920, 1, 1), max_value=TODAY),
    ratings=st.lists(st.sampled_from(["ATP", "+13", "+18", None, "", "NC-17", 7]), min_size=1, max_size=30),
)
def test_no_minor_ever_receives_adult_content(birth: date, ratings: list[object]) -> None:
    user_ordinal = derive_max_age_ordinal(birth, TODAY, CFG)
    survivors = _age_stage([_scored(r, n) for n, r in enumerate(ratings)], user_ordinal)
    assert all(s.candidate.min_age_ordinal <= user_ordinal for s in survivors)
    if user_ordinal < CFG.max_ordinal:
        assert all(s.candidate.min_age_ordinal < CFG.max_ordinal for s in survivors)


def test_filter_has_no_parameter_to_disable_it() -> None:
    params = set(inspect.signature(_age_stage).parameters)
    assert params == {"scored", "user_max_age_ordinal"}


def test_no_hardcoded_rating_dict_in_engine() -> None:
    for path in (Path(postprocess.__file__), Path(postprocess.__file__).with_name("age.py")):
        source = path.read_text(encoding="utf-8")
        for literal in ('"ATP"', "'ATP'", '"+13"', '"+18"', "PG-13", ".get(rating, 0)"):
            assert literal not in source, f"{path.name}: {literal}"
