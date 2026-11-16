"""S5 del plan de pruebas — superficie interna: entradas raras nunca dan 500, ni filtran detalles, ni saltean la clave.

Complementa `tests/contract/test_auth.py` (matriz de claves y rutas protegidas) y `tests/contract/test_errors.py`
(códigos y formas de error): acá van las formas de clave, parámetros y cuerpos que esos tests no recorren.
"""

from __future__ import annotations

import uuid

import pytest

from tests.contract.conftest import auth
from tests.integration import seed

RECOS = "/internal/v1/recommendations/{}"
DECLARE = "/internal/v1/declarations/{}"
RECEIPT = "/internal/v1/deletion-receipts/{}"
LEAKS = ("Traceback", "sqlalchemy", "psycopg", "/home/", 'File "', "SELECT", "redis.exceptions", "pydantic")
UNAUTHORIZED = {"error": "unauthorized", "message": "credencial de servicio inválida"}


def _no_leaks(text: str) -> None:
    assert not [leak for leak in LEAKS if leak in text], text[:500]


def _error_shape(response, status: int, code: str | None = None) -> None:  # noqa: ANN001
    assert response.status_code == status, response.text[:500]
    body = response.json()
    assert set(body) == {"error", "message"}, body
    if code:
        assert body["error"] == code
    _no_leaks(response.text)


@pytest.mark.parametrize(
    "key",
    [
        "x" * 20_000,
        "clave-con-ñandú",
        "\t",
        "' OR '1'='1",
    ],
    ids=["20k-caracteres", "latin1", "tab", "inyeccion"],
)
def test_formas_raras_de_clave_dan_el_mismo_401(api, key) -> None:  # noqa: ANN001
    client, _ = api
    # Los encabezados viajan en latin-1: se mandan como bytes para que el cliente no los rechace antes de salir.
    headers = {"X-Internal-API-Key": key.encode("latin-1")}
    response = client.get(RECOS.format(uuid.uuid4()), params={"module": "peliculas"}, headers=headers)
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


def test_clave_valida_con_algo_de_mas_o_de_menos_no_entra(api, valid_env) -> None:  # noqa: ANN001
    client, _ = api
    valid = valid_env["RECO_INTERNAL_API_KEY"]
    for key in (valid + "x", valid[:-1], valid.upper() if valid.upper() != valid else valid.lower()):
        response = client.get(RECOS.format(uuid.uuid4()), params={"module": "peliculas"}, headers={"X-Internal-API-Key": key})
        assert response.json() == UNAUTHORIZED, key


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", RECOS.format("no-es-uuid"), {"params": {"module": "x"}}),
        ("post", DECLARE.format("no-es-uuid"), {"content": b"{no es json"}),
        ("post", DECLARE.format(uuid.uuid4()), {"json": {"module": "x", "tags": [], "extra": 1}}),
        ("get", RECEIPT.format("no-es-uuid"), {}),
    ],
    ids=["recos", "declaracion-no-json", "declaracion-invalida", "acuse"],
)
def test_sin_clave_responde_401_antes_de_validar_la_entrada(api, method, path, kwargs) -> None:  # noqa: ANN001
    """Validar antes que autenticar le contaría la forma del contrato a quien no tiene la clave."""
    client, _ = api
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"module": ""},
        {"module": "PELICULAS"},
        {"module": "peliculas", "top_n": "9"},
        {"module": "peliculas", "top_n": "51"},
        {"module": "peliculas", "top_n": "abc"},
        {"module": "peliculas", "top_n": "99999999999999999999999"},
        {"module": "peliculas", "prefer": "fresh"},
    ],
    ids=["sin-module", "module-vacio", "module-mayusculas", "top-9", "top-51", "top-texto", "top-enorme", "prefer-invalido"],
)
def test_parametros_invalidos_de_lectura_son_422_sin_rastros(api, valid_env, params) -> None:  # noqa: ANN001
    client, _ = api
    response = client.get(RECOS.format(uuid.uuid4()), params=params, headers=auth(valid_env))
    _error_shape(response, 422, "invalid_request")


@pytest.mark.parametrize("user_id", ["no-es-uuid", "1", "00000000-0000-0000-0000-00000000000g", "%00"])
def test_user_id_invalido_es_422_sin_rastros(api, valid_env, user_id) -> None:  # noqa: ANN001
    client, _ = api
    response = client.get(RECOS.format(user_id), params={"module": "peliculas"}, headers=auth(valid_env))
    _error_shape(response, 422, "invalid_request")


@pytest.mark.parametrize(
    "body",
    [
        b"{no es json",
        b"",
        b"[]",
        b'{"module": "peliculas"}',
        b'{"module": "peliculas", "tags": "drama"}',
        b'{"module": "peliculas", "tags": []}',
        b'{"module": "peliculas", "tags": [1, 2, 3, 4, 5]}',
        b'{"module": "peliculas", "tags": ["a","b","c","d","e"], "user_id": "otro"}',
    ],
    ids=["no-json", "vacio", "lista", "sin-tags", "tags-texto", "tags-vacios", "tags-numeros", "campo-extra"],
)
def test_cuerpos_invalidos_de_declaracion_son_422_sin_rastros(api, valid_env, db_factory, body) -> None:  # noqa: ANN001
    client, _ = api
    with db_factory.begin() as s:
        user = seed.user(s)
    response = client.post(
        DECLARE.format(user), content=body, headers={**auth(valid_env), "Content-Type": "application/json"}
    )
    _error_shape(response, 422, "invalid_request")


@pytest.mark.parametrize(
    "tags",
    [
        ["\x00", "a", "b", "c", "d"],
        ["<script>alert(1)</script>", "a", "b", "c", "d"],
        ["'; DROP TABLE users; --", "a", "b", "c", "d"],
    ],
    ids=["nul", "html", "sql"],
)
def test_tags_hostiles_se_rechazan_por_vocabulario_sin_tocar_la_base(api, valid_env, db_factory, tags) -> None:  # noqa: ANN001
    client, _ = api
    with db_factory.begin() as s:
        user = seed.user(s)
    response = client.post(DECLARE.format(user), json={"module": "peliculas", "tags": tags}, headers=auth(valid_env))
    _error_shape(response, 422, "invalid_request")


def test_el_error_por_tags_desconocidos_no_devuelve_la_entrada_completa(api, valid_env, db_factory) -> None:  # noqa: ANN001
    """Un rechazo no debe amplificar lo que llega: con tags enormes o miles de tags la respuesta queda acotada."""
    client, _ = api
    with db_factory.begin() as s:
        user = seed.user(s)
    huge = ["x" * 200_000] + [f"desconocido-{i}" for i in range(5_000)]
    response = client.post(DECLARE.format(user), json={"module": "peliculas", "tags": huge}, headers=auth(valid_env))
    _error_shape(response, 422, "invalid_request")
    assert len(response.content) < 4_096, len(response.content)
