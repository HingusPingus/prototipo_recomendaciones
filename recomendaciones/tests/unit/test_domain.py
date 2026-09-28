"""T005 — dominio compartido y errores tipados (FR-056, FR-057, FR-062)."""

from __future__ import annotations

import ast
import inspect
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

import recomendaciones.shared.domain as domain
import recomendaciones.shared.errors as errors
from recomendaciones.shared.domain import Module, ResultType, Signal, SignalType


def test_result_type_has_exactly_the_five_states_of_fr056() -> None:
    assert {r.value for r in ResultType} == {
        "empty_pending",
        "empty_no_candidates",
        "fallback",
        "personalized_stale",
        "personalized",
    }


def test_result_type_is_closed() -> None:
    with pytest.raises(TypeError):

        class Sexto(ResultType):  # type: ignore[misc]
            DECLARATION_REQUIRED = "declaration_required"


def test_precedence_order_is_fr056() -> None:
    assert ResultType.precedence() == (
        ResultType.EMPTY_PENDING,
        ResultType.EMPTY_NO_CANDIDATES,
        ResultType.FALLBACK,
        ResultType.PERSONALIZED_STALE,
        ResultType.PERSONALIZED,
    )


def test_signal_type_distinguishes_three_kinds() -> None:
    assert {s.value for s in SignalType} == {"like", "dislike", "consumo"}
    assert {m.value for m in Module} == {"peliculas", "juegos"}


def test_signal_without_type_cannot_be_built() -> None:
    with pytest.raises(TypeError):
        Signal(  # type: ignore[call-arg]
            origin_interaction_id="int-1",
            user_id=uuid.uuid4(),
            item_id=uuid.uuid4(),
            occurred_at=datetime.now(UTC),
        )
    with pytest.raises(ValueError):
        Signal(
            origin_interaction_id="int-1",
            user_id=uuid.uuid4(),
            item_id=uuid.uuid4(),
            signal_type="visto",  # type: ignore[arg-type]
            occurred_at=datetime.now(UTC),
        )


def test_signal_accepts_string_type_and_normalizes() -> None:
    s = Signal(
        origin_interaction_id="int-1",
        user_id=uuid.uuid4(),
        item_id=uuid.uuid4(),
        signal_type="like",  # type: ignore[arg-type]
        occurred_at=datetime.now(UTC),
    )
    assert s.signal_type is SignalType.LIKE


def test_every_error_declares_its_http_status() -> None:
    classes = [
        obj
        for _, obj in inspect.getmembers(errors, inspect.isclass)
        if issubclass(obj, errors.RecoError) and obj.__module__ == errors.__name__
    ]
    assert len(classes) >= 6
    for cls in classes:
        assert isinstance(cls.http_status, int) and 400 <= cls.http_status <= 599, cls
        assert cls.code and cls.code.islower(), cls


def test_unavailability_errors_carry_retry_after() -> None:
    err = errors.CacheUnavailable()
    assert err.http_status == 503 and err.retry_after_seconds > 0
    assert errors.ExclusionSetUnavailable().http_status == 503


def test_declaration_required_is_an_error_not_a_result_type() -> None:
    """FR-088: el rechazo por falta de declaración es precondición incumplida, no un sexto estado."""
    assert errors.DeclarationRequired.code not in {r.value for r in ResultType}


@pytest.mark.parametrize("module", [domain, errors])
def test_shared_types_do_not_depend_on_storage(module: object) -> None:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))  # type: ignore[attr-defined]
    imported = {
        (node.module or "") if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [None])  # type: ignore[list-item]
    }
    assert not {m for m in imported if m.split(".")[0] in {"sqlalchemy", "redis", "psycopg"}}
