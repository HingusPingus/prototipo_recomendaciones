"""T077 — consulta de la recepción de una baja para el checkpoint de `api-general` (FR-095c, RD-117).

`api-general` consulta por `event_id`: `200` con `event_id` y `received_at` si la recepción está registrada (T074),
`404` mientras no lo esté. Excepción de lectura del Principio III (constitución v1.2.0): una fila por clave, sin
datos del usuario y sin Redis.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from tests.conftest import VALID_ENV

HEADERS = {"X-Internal-API-Key": VALID_ENV["RECO_INTERNAL_API_KEY"]}
RECEIVED = datetime(2026, 10, 5, 12, 0, 30, tzinfo=UTC)


def _receipt(db_factory, *, state: str = "completed") -> tuple[uuid.UUID, uuid.UUID]:  # noqa: ANN001
    user, event = uuid.uuid4(), uuid.uuid4()
    with db_factory.begin() as s:
        s.execute(
            sa.text(
                "INSERT INTO user_suppressions (user_id, requested_at, state, attempts, verified_at, event_id, received_at) "
                "VALUES (:u, :r, CAST(:st AS suppression_state), 1, :v, :e, :rx)"
            ),
            {"u": user, "r": RECEIVED, "st": state, "v": RECEIVED if state == "completed" else None, "e": event, "rx": RECEIVED},
        )
    return user, event


def test_recorded_receipt_returns_event_id_received_at_and_state(api, db_factory) -> None:  # noqa: ANN001
    client, _ = api
    user, event = _receipt(db_factory)
    response = client.get(f"/internal/v1/deletion-receipts/{event}", headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"event_id": str(event), "received_at": body["received_at"], "suppression_state": "completed"}
    assert datetime.fromisoformat(body["received_at"]) == RECEIVED
    assert str(user) not in response.text  # ningún dato del usuario (FR-095)


def test_receipt_in_progress_is_reported_as_such(api, db_factory) -> None:  # noqa: ANN001
    client, _ = api
    _user, event = _receipt(db_factory, state="in_progress")
    assert client.get(f"/internal/v1/deletion-receipts/{event}", headers=HEADERS).json()["suppression_state"] == "in_progress"


def test_unrecorded_event_is_404_receipt_not_found(api) -> None:  # noqa: ANN001
    client, _ = api
    response = client.get(f"/internal/v1/deletion-receipts/{uuid.uuid4()}", headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["error"] == "receipt_not_found"


def test_requires_the_internal_api_key_and_a_uuid(api) -> None:  # noqa: ANN001
    client, _ = api
    assert client.get(f"/internal/v1/deletion-receipts/{uuid.uuid4()}").status_code == 401
    assert client.get("/internal/v1/deletion-receipts/no-es-uuid", headers=HEADERS).status_code == 422


def test_database_unavailable_is_a_retryable_503(api, monkeypatch) -> None:  # noqa: ANN001
    client, services = api

    def caida(*_args: object) -> None:
        raise OperationalError("SELECT", {}, Exception("conexión rechazada"))

    monkeypatch.setattr(services.receipt_service, "_lookup", caida)
    response = client.get(f"/internal/v1/deletion-receipts/{uuid.uuid4()}", headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["error"] == "receipts_unavailable"
    assert response.headers.get("Retry-After")


def test_does_not_touch_redis(api, db_factory, monkeypatch) -> None:  # noqa: ANN001
    """La consulta no depende de Redis: con la caché caída, responde igual."""
    client, services = api
    _user, event = _receipt(db_factory)

    def redis_caido(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("la consulta de recepción no debe tocar Redis")

    monkeypatch.setattr(services.cache, "call", redis_caido)
    assert client.get(f"/internal/v1/deletion-receipts/{event}", headers=HEADERS).status_code == 200
