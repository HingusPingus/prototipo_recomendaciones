"""T055 — rechazo por módulo sin declaración como precondición, sin sexto estado (FR-088, SC-029, DEP-6)."""

from __future__ import annotations

import inspect

from recomendaciones.api.services import precondiciones, read_service
from recomendaciones.shared.domain import ResultType
from tests.contract.conftest import auth
from tests.integration import seed

URL = "/internal/v1/recommendations/{}"


def test_the_set_of_result_states_still_has_five_members(contract) -> None:  # noqa: ANN001
    assert len(ResultType) == 5
    assert len(contract["components"]["schemas"]["ResultType"]["enum"]) == 5


def test_rejection_is_per_module(api, valid_env, db_factory) -> None:  # noqa: ANN001
    client, _ = api
    with db_factory.begin() as s:
        user = seed.user(s)
        seed.tags(s, ["horror"])
        seed.declare(s, user, "peliculas", ["horror"])
    declared = client.get(URL.format(user), params={"module": "peliculas"}, headers=auth(valid_env))
    undeclared = client.get(URL.format(user), params={"module": "juegos"}, headers=auth(valid_env))
    assert declared.status_code == 200 and declared.json()["result_type"] in {r.value for r in ResultType}
    assert undeclared.status_code == 412
    body = undeclared.json()
    assert body["error"] == "declaration_required" and "declar" in body["message"]
    assert "result_type" not in body  # no es un estado de resultado


def test_precondition_runs_before_result_resolution() -> None:
    source = inspect.getsource(read_service.ReadService.read)
    check = source.index("check_preconditions")
    assert check < source.index("_resolve(") and check < source.index("read_fallback")
    assert "DeclarationRequired" in inspect.getsource(precondiciones)
