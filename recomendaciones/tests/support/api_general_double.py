"""Doble de `api-general` para el Data Transformer (Principio VI): sirve el contrato propuesto
`contracts/api-general-sync.openapi.yaml` desde memoria y registra cada solicitud recibida."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx


@dataclass
class ApiGeneralDouble:
    api_key: str
    users: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    activity: list[dict] = field(default_factory=list)
    page_size: int = 2
    requests: list[httpx.Request] = field(default_factory=list)
    down: bool = False
    truncate_catalog_to: int | None = None  # simula un listado incompleto (CR-9)
    fail_catalog_after_pages: int | None = None
    snapshot: str = "snap-1"

    # --- construcción de datos ---------------------------------------------------------------
    def add_user(self, *, birth_date: date | None = date(1990, 1, 1), region: str | None = "AR", user_id: uuid.UUID | None = None) -> uuid.UUID:
        uid = user_id or uuid.uuid4()
        record: dict = {"id": str(uid)}
        if birth_date is not None:
            record["birth_date"] = birth_date.isoformat()
        if region is not None:
            record["region"] = region
        self.users.append(record)
        return uid

    def add_item(self, module: str, tags: list[str], *, rating: str | None = "ATP", status: str | None = None, item_id: uuid.UUID | None = None) -> uuid.UUID:
        iid = item_id or uuid.uuid4()
        record: dict = {"id": str(iid), "module": module, "tags": tags}
        if rating is not None:
            record["age_rating"] = rating
        if status is not None:
            record["status"] = status
        self.items.append(record)
        return iid

    def add_interaction(self, user_id: uuid.UUID, item_id: uuid.UUID, kind: str, occurred_at: datetime, oid: str | None = None) -> str:
        oid = oid or f"int-{uuid.uuid4()}"
        self.activity.append(
            {"origin_interaction_id": oid, "user_id": str(user_id), "item_id": str(item_id), "signal_type": kind, "occurred_at": occurred_at.isoformat()}
        )
        return oid

    # --- servidor ----------------------------------------------------------------------------
    def _page(self, rows: list[dict], request: httpx.Request, total: int) -> httpx.Response:
        token = request.url.params.get("page_token")
        start = int(token) if token else 0
        size = int(request.url.params.get("page_size", self.page_size))
        size = min(size, self.page_size)
        chunk = rows[start : start + size]
        nxt = start + size
        body = {"snapshot_id": self.snapshot, "total": total, "next_page_token": str(nxt) if nxt < len(rows) else None, "items": chunk}
        return httpx.Response(200, json=body)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("api-general no disponible", request=request)
        if request.headers.get("X-Internal-API-Key") != self.api_key:
            return httpx.Response(401, json={"error": "unauthorized"})
        path = request.url.path
        if path == "/internal/v1/sync/users":
            return self._page(self.users, request, len(self.users))
        if path == "/internal/v1/sync/catalog/items":
            token = int(request.url.params.get("page_token") or 0)
            if self.fail_catalog_after_pages is not None and token >= self.fail_catalog_after_pages * self.page_size:
                return httpx.Response(503, json={"error": "unavailable"})
            rows = self.items if self.truncate_catalog_to is None else self.items[: self.truncate_catalog_to]
            return self._page(rows, request, len(self.items))
        if path == "/internal/v1/sync/activity":
            since = request.url.params.get("since")
            rows = [r for r in self.activity if since is None or r["occurred_at"] >= since]
            return self._page(rows, request, len(rows))
        return httpx.Response(404, json={"error": "not_found"})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def methods(self) -> set[str]:
        return {r.method for r in self.requests}


def dumps(value: object) -> str:
    return json.dumps(value)
