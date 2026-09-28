"""Cliente REST hacia `api-general`, autenticado y de **solo lectura** (T028, FR-015, FR-017, FR-040).

El cliente no expone verbos de mutación: la restricción es estructural (el `httpx.Client` es privado y
solo existen operaciones de listado), no una convención. Envía la API key interna del entorno y usa
timeouts explícitos. Los errores HTTP se traducen a errores tipados. No hay conexión directa a la DB de
`api-general` (INV-4): todo pasa por REST.

Consume el contrato **propuesto** `contracts/api-general-sync.openapi.yaml`. La completitud de un listado
(CR-9) se informa: todas las páginas de un mismo `snapshot_id`, la última sin `next_page_token` y la
cantidad recibida igual al `total` declarado.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from recomendaciones.shared.errors import UpstreamError, UpstreamUnavailable

_PAGE_SIZE = 500


@dataclass(frozen=True)
class Listing:
    rows: list[dict[str, Any]]
    total: int
    complete: bool


class ApiGeneralClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.__http = httpx.Client(
            base_url=base_url,
            headers={"X-Internal-API-Key": api_key},
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    def close(self) -> None:
        self.__http.close()

    def __get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.__http.get(path, params={k: v for k, v in params.items() if v is not None})
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise UpstreamUnavailable(f"api-general no respondió: {exc.__class__.__name__}") from None
        if response.status_code in (502, 503, 504):
            raise UpstreamUnavailable(f"api-general respondió {response.status_code}")
        if response.status_code >= 400:
            raise UpstreamError(f"api-general respondió {response.status_code} en {path}")
        try:
            return response.json()
        except ValueError:
            raise UpstreamError(f"respuesta no JSON en {path}") from None

    def __pages(self, path: str, extra: dict[str, Any]) -> Iterator[dict[str, Any]]:
        token: str | None = None
        while True:
            page = self.__get(path, {**extra, "page_token": token, "page_size": _PAGE_SIZE})
            yield page
            token = page.get("next_page_token")
            if not token:
                return

    def __listing(self, path: str, extra: dict[str, Any] | None = None) -> Listing:
        rows: list[dict[str, Any]] = []
        snapshots: set[str] = set()
        total = -1
        last_had_no_token = False
        for page in self.__pages(path, extra or {}):
            rows.extend(page.get("items", []))
            snapshots.add(str(page.get("snapshot_id")))
            total = int(page.get("total", -1))
            last_had_no_token = page.get("next_page_token") is None
        complete = last_had_no_token and len(snapshots) == 1 and total == len(rows)
        return Listing(rows, total, complete)

    def list_users(self) -> Listing:
        return self.__listing("/internal/v1/sync/users")

    def list_catalog(self) -> Listing:
        return self.__listing("/internal/v1/sync/catalog/items")

    def list_activity(self, since: datetime | None) -> Listing:
        return self.__listing("/internal/v1/sync/activity", {"since": since.isoformat() if since else None})
