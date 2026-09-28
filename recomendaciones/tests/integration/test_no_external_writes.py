"""T028 — contra un doble de api-general, el cliente emite cero solicitudes que no sean GET (FR-017)."""

from __future__ import annotations

from datetime import UTC, datetime

from recomendaciones.transformer.client import ApiGeneralClient
from tests.support.api_general_double import ApiGeneralDouble

KEY = "test.s3cr3t-0123456789abcdef"


def test_only_get_requests_are_ever_sent() -> None:
    double = ApiGeneralDouble(api_key=KEY)
    user = double.add_user()
    item = double.add_item("peliculas", ["horror"])
    double.add_interaction(user, item, "like", datetime(2026, 9, 1, tzinfo=UTC))
    client = ApiGeneralClient("http://api-general.internal", KEY, timeout_seconds=5, transport=double.transport())
    client.list_users()
    client.list_catalog()
    client.list_activity(since=None)
    assert double.requests and double.methods() == {"GET"}
