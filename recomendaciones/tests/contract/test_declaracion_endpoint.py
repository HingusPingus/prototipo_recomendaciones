"""T053 — endpoint de declaración de gustos: la única excepción de escritura (FR-082…FR-089b, SC-029)."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from jsonschema import Draft202012Validator

from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from tests.contract.conftest import auth
from tests.integration import seed

URL = "/internal/v1/declarations/{}"
MOVIE_TAGS = ["horror", "drama", "comedia", "thriller", "scifi", "misterio"]


def _vocab(db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        for tag in MOVIE_TAGS:
            seed.item(s, "peliculas", [tag])
        seed.item(s, "juegos", ["horror", "rpg"])
        s.execute(sa.text("INSERT INTO tag_modules SELECT DISTINCT it.tag_name, i.module, now() FROM item_tags it JOIN items i ON i.id = it.item_id"))


def _rows(db_factory, user: uuid.UUID) -> list[tuple[str, str]]:  # noqa: ANN001
    with db_factory() as s:
        return sorted(s.execute(sa.text("SELECT module::text, tag_name FROM user_declared_tags WHERE user_id = :u"), {"u": user}).all())


def test_valid_declaration_is_confirmed_synchronously(api, contract, valid_env, db_factory, redis_client) -> None:  # noqa: ANN001
    client, _ = api
    _vocab(db_factory)
    with db_factory.begin() as s:
        user = seed.user(s)
    response = client.post(URL.format(user), json={"module": "peliculas", "tags": MOVIE_TAGS[:5]}, headers=auth(valid_env))
    assert response.status_code == 201
    schema = {"$ref": "#/components/schemas/DeclarationResponse", "components": contract["components"]}
    Draft202012Validator(schema).validate(response.json())
    assert _rows(db_factory, user) == sorted(("peliculas", t) for t in MOVIE_TAGS[:5])  # persistido antes de responder
    requests = [e[1] for e in redis_client.xrange(keys.RECOMPUTE_STREAM)]
    assert requests == [{"user_id": str(user), "module": "peliculas", "reason": "declaration"}]


def test_second_declaration_is_409_and_leaves_rows_intact(api, valid_env, db_factory) -> None:  # noqa: ANN001
    client, _ = api
    _vocab(db_factory)
    with db_factory.begin() as s:
        user = seed.user(s)
    assert client.post(URL.format(user), json={"module": "peliculas", "tags": MOVIE_TAGS[:5]}, headers=auth(valid_env)).status_code == 201
    before = _rows(db_factory, user)
    second = client.post(URL.format(user), json={"module": "peliculas", "tags": MOVIE_TAGS[1:6]}, headers=auth(valid_env))
    assert second.status_code == 409 and second.json()["error"] == "declaration_already_exists"
    assert _rows(db_factory, user) == before


@pytest.mark.parametrize(
    ("tags", "status"),
    [(MOVIE_TAGS[:4], 422), (MOVIE_TAGS[:5], 201), (["horror", "drama", "comedia", "thriller", "inexistente"], 422)],
    ids=["4-tags", "5-tags", "tag-fuera-de-vocabulario"],
)
def test_minimum_and_vocabulary(api, valid_env, db_factory, tags, status) -> None:  # noqa: ANN001
    client, _ = api
    _vocab(db_factory)
    with db_factory.begin() as s:
        user = seed.user(s)
    assert client.post(URL.format(user), json={"module": "peliculas", "tags": tags}, headers=auth(valid_env)).status_code == status


def test_no_maximum(api, valid_env, db_factory) -> None:  # noqa: ANN001
    client, _ = api
    many = [f"t{i:02d}" for i in range(40)]
    with db_factory.begin() as s:
        for tag in many:
            seed.item(s, "juegos", [tag])
        s.execute(sa.text("INSERT INTO tag_modules SELECT DISTINCT it.tag_name, i.module, now() FROM item_tags it JOIN items i ON i.id = it.item_id"))
        user = seed.user(s)
    assert client.post(URL.format(user), json={"module": "juegos", "tags": many}, headers=auth(valid_env)).status_code == 201


def test_declaring_one_module_does_not_require_the_other(api, valid_env, db_factory) -> None:  # noqa: ANN001
    """FR-084: se declara al primer ingreso al módulo, uno por llamada."""
    client, _ = api
    _vocab(db_factory)
    with db_factory.begin() as s:
        user = seed.user(s)
    assert client.post(URL.format(user), json={"module": "peliculas", "tags": MOVIE_TAGS[:5]}, headers=auth(valid_env)).status_code == 201
    assert {m for m, _ in _rows(db_factory, user)} == {"peliculas"}


def test_invalidates_filters_before_writing(api, valid_env, db_factory, redis_client) -> None:  # noqa: ANN001
    """Sin esto, un `filters:` previo sin el módulo rechazaría por FR-088 a quien acaba de declarar."""
    client, services = api
    _vocab(db_factory)
    with db_factory.begin() as s:
        user = seed.user(s)
    seen: list[bool] = []
    original = services.filters.invalidate

    def spy(user_id: uuid.UUID) -> None:
        seen.append(bool(_rows(db_factory, user_id)))  # ¿ya estaba escrito al invalidar?
        original(user_id)

    services.filters.invalidate = spy
    services.filters.get(user)  # filters: poblado sin el módulo
    assert client.post(URL.format(user), json={"module": "peliculas", "tags": MOVIE_TAGS[:5]}, headers=auth(valid_env)).status_code == 201
    assert seen[0] is False  # Redis primero (FR-080c)
    assert Module.PELICULAS in services.filters.get(user).declared_modules


def test_unknown_user_is_404(api, valid_env, db_factory) -> None:  # noqa: ANN001
    client, _ = api
    _vocab(db_factory)
    response = client.post(URL.format(uuid.uuid4()), json={"module": "peliculas", "tags": MOVIE_TAGS[:5]}, headers=auth(valid_env))
    assert response.status_code == 404


def test_the_engine_is_never_invoked(api, valid_env, db_factory, monkeypatch) -> None:  # noqa: ANN001
    """FR-089b: se verifica por ausencia de llamada, no por tiempo de respuesta."""
    import recomendaciones.engine.postprocess as pp
    import recomendaciones.engine.profile as profile
    import recomendaciones.engine.scoring as scoring

    def boom(*a: object, **k: object) -> None:
        raise AssertionError("el endpoint de declaración ejecutó el motor")

    for module, name in ((pp, "postprocess"), (scoring, "combine"), (profile, "build_profile")):
        monkeypatch.setattr(module, name, boom)
    client, _ = api
    _vocab(db_factory)
    with db_factory.begin() as s:
        user = seed.user(s)
    assert client.post(URL.format(user), json={"module": "peliculas", "tags": MOVIE_TAGS[:5]}, headers=auth(valid_env)).status_code == 201
