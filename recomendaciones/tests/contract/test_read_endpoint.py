"""T033 — endpoint de lectura del top-N según el contrato de T049 (FR-001…FR-006a, RD-107)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from jsonschema import Draft202012Validator

from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry
from tests.contract.conftest import auth
from tests.integration import seed

URL = "/internal/v1/recommendations/{}"


def _response_validator(contract: dict) -> Draft202012Validator:
    schema = {"$ref": "#/components/schemas/RecommendationResponse", "components": contract["components"]}
    return Draft202012Validator(schema)


def _declared_user(db_factory) -> uuid.UUID:  # noqa: ANN001
    with db_factory.begin() as s:
        user = seed.user(s)
        seed.tags(s, ["horror"])
        seed.declare(s, user, "peliculas", ["horror"])
    return user


def _precompute(services, user: uuid.UUID, n: int = 30) -> None:  # noqa: ANN001
    services.repository.write_personalized(
        RecommendationEntry(
            user,
            Module.PELICULAS,
            services.engine_config.config_version,
            "vocab:x",
            2,
            datetime(2026, 9, 28, tzinfo=UTC),
            tuple(CachedItem(uuid.UUID(int=i + 1), i + 1, 1.0 - i / 100, 0) for i in range(n)),
        )
    )


def test_response_validates_against_the_published_contract(api, contract, valid_env, db_factory) -> None:  # noqa: ANN001
    client, services = api
    user = _declared_user(db_factory)
    _precompute(services, user)
    response = client.get(URL.format(user), params={"module": "peliculas", "top_n": 10}, headers=auth(valid_env))
    assert response.status_code == 200
    body = response.json()
    _response_validator(contract).validate(body)
    assert body["result_type"] == "personalized" and len(body["items"]) == 10
    assert [i["position"] for i in body["items"]] == list(range(1, 11))
    assert all(i["config_version"] == body["config_version"] for i in body["items"])  # FR-004
    assert "next_cursor" not in body


@pytest.mark.parametrize(("top_n", "status"), [(9, 422), (10, 200), (50, 200), (51, 422), (0, 422), ("x", 422)])
def test_top_n_domain_is_validated_on_both_ends(api, valid_env, db_factory, top_n, status) -> None:  # noqa: ANN001
    client, services = api
    user = _declared_user(db_factory)
    _precompute(services, user, n=50)
    response = client.get(URL.format(user), params={"module": "peliculas", "top_n": top_n}, headers=auth(valid_env))
    assert response.status_code == status
    if status == 200:
        assert len(response.json()["items"]) == top_n


def test_default_top_n_comes_from_configuration(api, valid_env, db_factory) -> None:  # noqa: ANN001
    client, services = api
    user = _declared_user(db_factory)
    _precompute(services, user, n=50)
    response = client.get(URL.format(user), params={"module": "peliculas"}, headers=auth(valid_env))
    assert len(response.json()["items"]) == services.engine_config.top_n_default == 20


@pytest.mark.parametrize("params", [{}, {"module": "musica"}, {"module": ""}])
def test_module_is_required_and_valid(api, valid_env, params) -> None:  # noqa: ANN001
    client, _ = api
    response = client.get(URL.format(uuid.uuid4()), params=params, headers=auth(valid_env))
    assert response.status_code == 422 and response.json()["error"] == "invalid_request"


@pytest.mark.parametrize("extra", [{"limit": 10}, {"cursor": "abc"}])
def test_pagination_parameters_are_rejected(api, valid_env, db_factory, extra) -> None:  # noqa: ANN001
    client, _ = api
    user = _declared_user(db_factory)
    response = client.get(URL.format(user), params={"module": "peliculas", **extra}, headers=auth(valid_env))
    assert response.status_code == 422


def test_invalid_user_id_is_422(api, valid_env) -> None:  # noqa: ANN001
    client, _ = api
    assert client.get(URL.format("no-es-uuid"), params={"module": "juegos"}, headers=auth(valid_env)).status_code == 422
