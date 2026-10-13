"""T043 — contract testing contra `api-general` como gate de CI (Principio VI, SC-013).

Tres frentes, cada uno con su caso negativo:

1. **Eventos consumidos** (`recomendacion.actualizar`, baja de cuenta): todo campo que el worker necesita es
   requerido por el schema oficial, y lo que el productor emite valida contra él.
2. **REST consumido por el Data Transformer**: todo campo que la sincronización lee es requerido por el
   contrato de sincronización, y lo que sirve el doble valida contra él.
3. **Respuestas propias**: cada respuesta real de la API —los cinco `result_type` y cada error— valida contra
   el OpenAPI publicado.

Las copias de `specs/.../contracts/` son las derivadas del contrato que custodia `api-general` (T049); cuando
allá se publique, esta suite se apunta a la versión publicada y el gate sigue siendo el mismo.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import re
import socket
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository
from recomendaciones.worker.schemas import ActualizarEvent, EliminadoEvent, parse_actualizar, parse_eliminado
from tests.conftest import VALID_ENV
from tests.integration import seed
from tests.support.api_general_double import ApiGeneralDouble

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "specs" / "001-recomendaciones-precomputadas" / "contracts"
WORKER_COPIES = ROOT / "src" / "recomendaciones" / "worker" / "contracts"
HEADERS = {"X-Internal-API-Key": VALID_ENV["RECO_INTERNAL_API_KEY"]}


class ContractGap(AssertionError):
    """El contrato dejó de exigir un campo que este repositorio consume."""


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _yaml(name: str) -> dict[str, Any]:
    return yaml.safe_load((CONTRACTS / name).read_text(encoding="utf-8"))


def _required_by_consumer(event_type: type) -> set[str]:
    """Derivado del tipo de dominio que produce el parser: los campos sin default son los que el worker usa."""
    return {f.name for f in dataclasses.fields(event_type) if f.default is dataclasses.MISSING}


# Lo que `transformer/pipeline.py` lee de cada registro de sincronización (`_validate_users`, `_validate_items`,
# `_write_activity`). `status` del ítem es deseable no bloqueante (CR-7): su ausencia no rompe la ingesta.
SYNC_CONSUMER = {
    "User": {"id", "birth_date", "region"},
    "CatalogItem": {"id", "module", "age_rating", "tags"},
    "Interaction": {"origin_interaction_id", "user_id", "item_id", "signal_type", "occurred_at"},
}
EVENTS = {
    "recomendacion-actualizar-v3.schema.json": (ActualizarEvent, parse_actualizar),
    "usuario-eliminado.schema.json": (EliminadoEvent, parse_eliminado),
}


def check_required(schema: dict[str, Any], consumed: set[str], *, where: str) -> None:
    missing = consumed - set(schema.get("required", []))
    if missing:
        raise ContractGap(f"{where}: el contrato ya no exige {sorted(missing)}, que este repositorio consume")


def _validator(schema: dict[str, Any], root: dict[str, Any] | None = None) -> Draft202012Validator:
    document = {**(root or {}), **schema}
    return Draft202012Validator(document, format_checker=FormatChecker())


# --- 1. Eventos consumidos --------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EVENTS))
def test_every_field_the_worker_consumes_is_required_by_the_official_event_schema(name: str) -> None:
    event_type, _parser = EVENTS[name]
    check_required(_json(CONTRACTS / name), _required_by_consumer(event_type), where=name)


def _producer_samples() -> dict[str, dict[str, Any]]:
    return {
        "recomendacion-actualizar-v3.schema.json": {
            "event_id": str(uuid.uuid4()), "origin_interaction_id": f"int-{uuid.uuid4()}", "user_id": str(uuid.uuid4()),
            "module": "juegos", "item_id": str(uuid.uuid4()), "signal_type": "consumo",
            "occurred_at": datetime(2026, 9, 28, tzinfo=UTC).isoformat(), "correlation_id": "c-1",
        },
        "usuario-eliminado.schema.json": {
            "event_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4()), "occurred_at": datetime(2026, 9, 28, tzinfo=UTC).isoformat(),
        },
    }


@pytest.mark.parametrize("name", sorted(EVENTS))
def test_producer_payload_validates_against_the_official_schema_and_the_worker_accepts_it(name: str) -> None:
    sample = _producer_samples()[name]
    _validator(_json(CONTRACTS / name)).validate(sample)
    event_type, parser = EVENTS[name]
    assert isinstance(parser(json.dumps(sample).encode()), event_type)


@pytest.mark.parametrize("name", sorted(EVENTS))
def test_worker_copies_are_identical_to_the_contracts(name: str) -> None:
    assert _json(WORKER_COPIES / name) == _json(CONTRACTS / name)


def test_v3_transport_of_the_contract_is_the_one_the_worker_consumes() -> None:
    """RD-116: el exchange y los headers AMQP que declara el contrato v3 (`x-amqp-transport`) son los que usa la
    topología del worker. Si `api-general` cambia el destino o los headers, este gate falla antes del despliegue."""
    from recomendaciones.worker.topology import actualizar_topology

    transport = _json(CONTRACTS / "recomendacion-actualizar-v3.schema.json")["x-amqp-transport"]
    topology = actualizar_topology()
    assert topology.exchange == transport["exchange"]["name"]
    assert transport["exchange"]["type"] == "fanout"
    required = {name: spec["value"] for name, spec in transport["headers"].items() if spec.get("required")}
    assert required == {"event_type": "recomendacion.actualizar.v3", "event_version": "3.0.0"}
    assert dict(topology.required_headers or {}) == required


def test_gate_fails_if_signal_type_disappears_from_the_contract() -> None:
    """Verificación de T043: eliminar `signal_type` del schema del doble debe hacer fallar el gate."""
    mutated = copy.deepcopy(_json(CONTRACTS / "recomendacion-actualizar-v3.schema.json"))
    mutated["required"].remove("signal_type")
    mutated["properties"].pop("signal_type")
    with pytest.raises(ContractGap, match="signal_type"):
        check_required(mutated, _required_by_consumer(ActualizarEvent), where="doble")


# --- 2. REST consumido por el Data Transformer --------------------------------------------------------------


@pytest.mark.parametrize("schema_name", sorted(SYNC_CONSUMER))
def test_every_field_the_transformer_reads_is_required_by_the_sync_contract(schema_name: str) -> None:
    spec = _yaml("api-general-sync.openapi.yaml")
    check_required(spec["components"]["schemas"][schema_name], SYNC_CONSUMER[schema_name], where=schema_name)


def test_gate_fails_if_region_disappears_from_the_sync_contract() -> None:
    mutated = copy.deepcopy(_yaml("api-general-sync.openapi.yaml")["components"]["schemas"]["User"])
    mutated["required"].remove("region")
    with pytest.raises(ContractGap, match="region"):
        check_required(mutated, SYNC_CONSUMER["User"], where="User")


def test_the_double_serves_what_the_sync_contract_declares() -> None:
    spec = _yaml("api-general-sync.openapi.yaml")
    schemas = spec["components"]["schemas"]
    double = ApiGeneralDouble(api_key="k")
    user = double.add_user()
    item = double.add_item("peliculas", ["horror"], status="available")
    double.add_interaction(user, item, "like", datetime(2026, 9, 28, tzinfo=UTC))
    for records, name in ((double.users, "User"), (double.items, "CatalogItem"), (double.activity, "Interaction")):
        validator = _validator(schemas[name], spec)
        for record in records:
            validator.validate(record)


# --- 3. Respuestas propias contra el OpenAPI publicado ---------------------------------------------------------


def _response_validator(spec: dict[str, Any], path: str, method: str, status: int) -> Draft202012Validator:
    response = spec["paths"][path][method]["responses"][str(status)]
    if "$ref" in response:
        response = spec["components"]["responses"][response["$ref"].rsplit("/", 1)[-1]]
    return _validator(response["content"]["application/json"]["schema"], spec)


READ = "/internal/v1/recommendations/{user_id}"
DECLARE = "/internal/v1/declarations/{user_id}"
RECEIPT = "/internal/v1/deletion-receipts/{event_id}"  # T077


def _declared(db_factory, modules=("peliculas", "juegos"), ordinal: int = 2) -> uuid.UUID:
    with db_factory.begin() as s:
        user = seed.user(s, max_age_ordinal=ordinal)
        for module in modules:
            names = [f"{module}-t{i}" for i in range(5)]
            seed.tags(s, names)
            seed.declare(s, user, module, names)
    return user


def test_every_read_response_validates_against_the_published_openapi(api, db_factory, redis_client) -> None:
    client, services = api
    spec = _yaml("recomendaciones-api.openapi.yaml")
    cfg = services.engine_config.config_version
    with db_factory.begin() as s:
        movies = [seed.item(s, "peliculas", [f"peliculas-t{i}"]) for i in range(4)]
        adult = seed.item(s, "peliculas", ["peliculas-t0"], rating="+18", ordinal=2)
        games = [seed.item(s, "juegos", [f"juegos-t{i}"]) for i in range(3)]
    repo = RecommendationRepository(CacheClient(redis_client), ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)

    def entry(user, module, items, ordinals=None, snapshot=2):
        ordinals = ordinals or [0] * len(items)
        return RecommendationEntry(
            user, module, cfg, "v", snapshot if user else None, datetime.now(UTC),
            tuple(CachedItem(i, n, 0.5, o) for n, (i, o) in enumerate(zip(items, ordinals, strict=True), start=1)),
        )

    users = {kind: _declared(db_factory) for kind in ("personalized", "personalized_stale", "fallback", "empty_pending", "empty_no_candidates")}
    minor = _declared(db_factory, ordinal=0)
    repo.write_personalized(entry(users["personalized"], Module.PELICULAS, movies))
    repo.write_fallback(entry(None, Module.PELICULAS, movies))
    repo.write_personalized(entry(users["personalized_stale"], Module.JUEGOS, games))
    redis_client.delete(f"reco:v{cfg}:{users['personalized_stale']}:juegos")
    repo.write_personalized(entry(minor, Module.PELICULAS, [adult], [2], snapshot=0))  # instantáneo del menor (§3.2)
    cases = [
        (users["personalized"], "peliculas", "personalized"),
        (users["personalized_stale"], "juegos", "personalized_stale"),
        (users["fallback"], "peliculas", "fallback"),
        (users["empty_pending"], "juegos", "empty_pending"),
        (minor, "peliculas", "empty_no_candidates"),
    ]
    ok = _response_validator(spec, READ, "get", 200)
    for user, module, expected in cases:
        response = client.get(f"/internal/v1/recommendations/{user}", params={"module": module}, headers=HEADERS)
        assert response.status_code == 200 and response.json()["result_type"] == expected
        ok.validate(response.json())
    undeclared = _declared(db_factory, modules=("juegos",))
    errors = [
        (client.get(f"/internal/v1/recommendations/{undeclared}", params={"module": "peliculas"}), 401),
        (client.get(f"/internal/v1/recommendations/{undeclared}", params={"module": "peliculas"}, headers=HEADERS), 412),
        (client.get(f"/internal/v1/recommendations/{undeclared}", params={"module": "juegos", "top_n": 5}, headers=HEADERS), 422),
        (client.get(f"/internal/v1/recommendations/{undeclared}", params={"module": "musica"}, headers=HEADERS), 422),
        (client.get(f"/internal/v1/recommendations/{uuid.uuid4()}", params={"module": "juegos"}, headers=HEADERS), 404),
    ]
    for response, status in errors:
        assert response.status_code == status, (status, response.text)
        _response_validator(spec, READ, "get", status).validate(response.json())


def test_503_response_validates_against_the_published_openapi(valid_env, db_factory) -> None:
    from recomendaciones.api.app import build_services, create_app
    from recomendaciones.config.settings import load_settings

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    settings = load_settings()
    dead = CacheClient.from_url(f"redis://127.0.0.1:{port}/0", timeout_seconds=0.3)
    with TestClient(create_app(settings, build_services(settings, db_factory=db_factory, cache=dead))) as client:
        response = client.get(f"/internal/v1/recommendations/{uuid.uuid4()}", params={"module": "juegos"}, headers=HEADERS)
    assert response.status_code == 503 and re.fullmatch(r"\d+", response.headers["Retry-After"])
    _response_validator(_yaml("recomendaciones-api.openapi.yaml"), READ, "get", 503).validate(response.json())


def test_every_declaration_response_validates_against_the_published_openapi(api, db_factory) -> None:
    client, _ = api
    spec = _yaml("recomendaciones-api.openapi.yaml")
    with db_factory.begin() as s:
        user = seed.user(s)
        for i in range(6):
            seed.item(s, "peliculas", [f"peliculas-t{i}"])
        seed.vectorize_all(s)
    tags = [f"peliculas-t{i}" for i in range(5)]
    cases = [
        (client.post(f"/internal/v1/declarations/{user}", json={"module": "peliculas", "tags": tags[:4]}, headers=HEADERS), 422),
        (client.post(f"/internal/v1/declarations/{user}", json={"module": "peliculas", "tags": tags}, headers=HEADERS), 201),
        (client.post(f"/internal/v1/declarations/{user}", json={"module": "peliculas", "tags": tags}, headers=HEADERS), 409),
    ]
    for response, status in cases:
        assert response.status_code == status, (status, response.text)
        _response_validator(spec, DECLARE, "post", status).validate(response.json())


def test_every_receipt_response_validates_against_the_published_openapi(api, db_factory) -> None:
    client, _ = api
    spec = _yaml("recomendaciones-api.openapi.yaml")
    event = uuid.uuid4()
    with db_factory.begin() as s:
        s.execute(
            sa.text(
                "INSERT INTO user_suppressions (user_id, requested_at, state, attempts, event_id, received_at) "
                "VALUES (:u, now(), 'in_progress', 0, :e, now())"
            ),
            {"u": uuid.uuid4(), "e": event},
        )
    cases = [
        (client.get(f"/internal/v1/deletion-receipts/{event}", headers=HEADERS), 200),
        (client.get(f"/internal/v1/deletion-receipts/{uuid.uuid4()}", headers=HEADERS), 404),
    ]
    for response, status in cases:
        assert response.status_code == status, (status, response.text)
        _response_validator(spec, RECEIPT, "get", status).validate(response.json())


def test_every_exposed_operation_is_exercised_by_this_gate() -> None:
    """SC-013: el 100 % de los endpoints expuestos pasa la validación; ninguno queda fuera de la suite."""
    spec = _yaml("recomendaciones-api.openapi.yaml")
    exposed = {(path, method) for path, ops in spec["paths"].items() for method in ops if method in ("get", "post", "put", "delete", "patch")}
    health = {(p, m) for p, m in exposed if p.startswith("/health")}
    assert exposed - health == {(READ, "get"), (DECLARE, "post"), (RECEIPT, "get")}  # salud la cubre T041 contra el mismo schema


# --- Dependencias externas vigentes ---------------------------------------------------------------------------


def _sync_schema(name: str) -> dict[str, Any]:
    return _yaml("api-general-sync.openapi.yaml")["components"]["schemas"][name]


DEP_CHECKS = {
    "DEP-1": lambda: {"signal_type"} <= set(_json(CONTRACTS / "recomendacion-actualizar-v3.schema.json")["required"])
    and "signal_type" in _sync_schema("Interaction")["required"],
    "DEP-2": lambda: "occurred_at" in _json(CONTRACTS / "recomendacion-actualizar-v3.schema.json")["required"]
    and "occurred_at" in _sync_schema("Interaction")["required"],
    "DEP-5": lambda: "birth_date" in _sync_schema("User")["required"],
    "DEP-6": lambda: len(_yaml("recomendaciones-api.openapi.yaml")["components"]["schemas"]["ResultType"]["enum"]) == 5,
    "DEP-7": lambda: _sync_schema("CatalogItem")["properties"]["tags"].get("minItems", 0) >= 1,
    "DEP-8": lambda: "origin_interaction_id" in _json(CONTRACTS / "recomendacion-actualizar-v3.schema.json")["required"]
    and "origin_interaction_id" in _sync_schema("Interaction")["required"],
    "DEP-9": lambda: {"event_id", "origin_interaction_id"} <= set(_json(CONTRACTS / "recomendacion-actualizar-v3.schema.json")["required"]),
    "DEP-10": lambda: _sync_schema("CatalogItem")["properties"]["tags"]["items"]["type"] == "string",
    "DEP-11": lambda: "region" in _sync_schema("User")["required"] and _sync_schema("User")["properties"]["region"]["pattern"] == "^[A-Z]{2}$",
    "DEP-12": lambda: {"event_id", "user_id", "occurred_at"} <= set(_json(CONTRACTS / "usuario-eliminado.schema.json")["required"]),
}


def _active_dependencies() -> set[str]:
    table = (ROOT / "specs" / "001-recomendaciones-precomputadas" / "spec.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (DEP-\d+) \| (.*)$", table, flags=re.MULTILINE)
    return {dep for dep, rest in rows if not rest.startswith("~~")}  # DEP-4 resuelta; DEP-3 vacante no figura


def test_every_active_external_dependency_is_covered_by_the_gate() -> None:
    active = _active_dependencies()
    assert active == set(DEP_CHECKS), f"sin cobertura: {sorted(active - set(DEP_CHECKS))}; sobrantes: {sorted(set(DEP_CHECKS) - active)}"


@pytest.mark.parametrize("dep", sorted(DEP_CHECKS))
def test_dependency_is_declared_in_the_contract(dep: str) -> None:
    assert DEP_CHECKS[dep](), dep
