"""T062 — señal de resultado obsoleto como campo aparte, no como sexto estado (FR-056a, RD-107)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from recomendaciones.shared.domain import Module, ResultType
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry
from tests.contract.conftest import auth
from tests.integration import seed


def _setup(api, db_factory):  # noqa: ANN001, ANN202
    client, services = api
    with db_factory.begin() as s:
        user = seed.user(s, max_age_ordinal=0)
        seed.tags(s, ["horror"])
        seed.declare(s, user, "peliculas", ["horror"])
    cfg = services.engine_config.config_version
    now = datetime.now(UTC)
    stale_items = (CachedItem(uuid.UUID(int=1), 1, 0.9, 0), CachedItem(uuid.UUID(int=2), 2, 0.8, 2))  # el segundo, +18
    services.repository.write_personalized(RecommendationEntry(user, Module.PELICULAS, cfg, "v", 0, now, stale_items))
    services.cache.delete(keys.reco_key(cfg, user, Module.PELICULAS))  # vence el vigente: queda el obsoleto
    services.repository.write_fallback(RecommendationEntry(None, Module.PELICULAS, cfg, "v", None, now, (CachedItem(uuid.UUID(int=9), 1, 0.3, 0),)))
    return client, services, user


def test_enum_keeps_five_members(contract) -> None:  # noqa: ANN001
    assert len(ResultType) == 5 and "stale_available" not in contract["components"]["schemas"]["ResultType"]["enum"]
    assert contract["components"]["schemas"]["RecommendationResponse"]["properties"]["stale_available"]["type"] == "boolean"


def test_fallback_with_stale_signals_it(api, valid_env, db_factory) -> None:  # noqa: ANN001
    client, _, user = _setup(api, db_factory)
    body = client.get(f"/internal/v1/recommendations/{user}", params={"module": "peliculas"}, headers=auth(valid_env)).json()
    assert body["result_type"] == "fallback" and body["stale_available"] is True


def test_prefer_stale_serves_it_filtered(api, valid_env, db_factory) -> None:  # noqa: ANN001
    client, _, user = _setup(api, db_factory)
    body = client.get(f"/internal/v1/recommendations/{user}", params={"module": "peliculas", "prefer": "stale"}, headers=auth(valid_env)).json()
    assert body["result_type"] == "personalized_stale"
    assert [i["item_id"] for i in body["items"]] == [str(uuid.UUID(int=1))]  # el +18 cae por la guarda etaria


def test_prefer_stale_without_stale_is_identical_to_no_parameter(api, valid_env, db_factory) -> None:  # noqa: ANN001
    client, services = api
    with db_factory.begin() as s:
        user = seed.user(s)
        seed.tags(s, ["horror"])
        seed.declare(s, user, "peliculas", ["horror"])
    cfg = services.engine_config.config_version
    services.repository.write_fallback(RecommendationEntry(None, Module.PELICULAS, cfg, "v", None, datetime.now(UTC), (CachedItem(uuid.UUID(int=9), 1, 0.3, 0),)))
    url = f"/internal/v1/recommendations/{user}"
    plain = client.get(url, params={"module": "peliculas"}, headers=auth(valid_env)).json()
    preferred = client.get(url, params={"module": "peliculas", "prefer": "stale"}, headers=auth(valid_env)).json()
    assert plain == preferred and plain["stale_available"] is False


def test_precedence_applies_only_after_preconditions(api, valid_env, db_factory) -> None:  # noqa: ANN001
    client, _ = api
    with db_factory.begin() as s:
        user = seed.user(s)
    response = client.get(f"/internal/v1/recommendations/{user}", params={"module": "peliculas", "prefer": "stale"}, headers=auth(valid_env))
    assert response.status_code == 412
