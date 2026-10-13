"""T028 — cliente REST autenticado y de solo lectura hacia api-general (FR-015, FR-017, FR-040, INV-4)."""

from __future__ import annotations

import inspect

import httpx
import pytest

from recomendaciones.shared.errors import UpstreamError, UpstreamUnavailable
from recomendaciones.transformer.client import ApiGeneralClient
from tests.support.api_general_double import ApiGeneralDouble

KEY = "test.s3cr3t-0123456789abcdef"


def _client(double: ApiGeneralDouble, timeout: float = 5.0) -> ApiGeneralClient:
    return ApiGeneralClient("http://api-general.internal", KEY, timeout_seconds=timeout, transport=double.transport())


def test_public_surface_has_no_mutation_verbs() -> None:
    public = {name.lower() for name, _ in inspect.getmembers(ApiGeneralClient) if not name.startswith("_")}
    for verb in ("post", "put", "patch", "delete", "request", "send"):
        assert not any(verb == name or name.startswith(verb + "_") for name in public), (verb, public)


def test_sends_the_internal_api_key_and_uses_explicit_timeouts() -> None:
    double = ApiGeneralDouble(api_key=KEY)
    double.add_user()
    client = _client(double, timeout=3.5)
    assert len(list(client.list_users().rows)) == 1
    assert double.requests[0].headers["X-Internal-API-Key"] == KEY
    assert client.timeout_seconds == 3.5
    assert double.requests[0].extensions["timeout"]["read"] == 3.5


def test_pages_are_followed_and_completeness_is_reported() -> None:
    double = ApiGeneralDouble(api_key=KEY, page_size=2)
    for i in range(5):
        double.add_item("peliculas", [f"t{i}"])
    listing = _client(double).list_catalog()
    assert len(listing.rows) == 5 and listing.complete is True and listing.total == 5


def test_truncated_listing_is_reported_incomplete() -> None:
    double = ApiGeneralDouble(api_key=KEY, page_size=2, truncate_catalog_to=3)
    for i in range(6):
        double.add_item("juegos", [f"t{i}"])
    listing = _client(double).list_catalog()
    assert listing.complete is False  # CR-9: 3 recibidos frente a un total declarado de 6


@pytest.mark.parametrize(("status", "error"), [(500, UpstreamError), (401, UpstreamError), (503, UpstreamUnavailable)])
def test_http_errors_become_typed_errors(status: int, error: type) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={}))
    client = ApiGeneralClient("http://x", KEY, timeout_seconds=1, transport=transport)
    with pytest.raises(error):
        client.list_users()


@pytest.mark.parametrize("status", [500, 503])
def test_http_error_names_the_listing_that_failed(status: int) -> None:
    """`api-general` responde 503 a un listado entero por un solo dato (RD-119): la guardia lee `failure_reason`
    en `sync_runs` y necesita saber si fue usuarios, catálogo o actividad."""
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={}))
    client = ApiGeneralClient("http://x", KEY, timeout_seconds=1, transport=transport)
    with pytest.raises(UpstreamError) as caught:
        client.list_catalog()
    assert "/internal/v1/sync/catalog/items" in caught.value.message


def test_first_run_omits_since_instead_of_sending_it_empty_or_invented() -> None:
    """El contrato declara `since` opcional: sin marca de agua no se manda, ni vacío ni con una fecha inventada
    para esquivar el `500` de `api-general` con `since` nulo (RD-119)."""
    double = ApiGeneralDouble(api_key=KEY)
    _client(double).list_activity(None)
    assert "since" not in double.requests[0].url.params


def test_connection_failure_is_upstream_unavailable() -> None:
    double = ApiGeneralDouble(api_key=KEY, down=True)
    with pytest.raises(UpstreamUnavailable):
        _client(double).list_users()
