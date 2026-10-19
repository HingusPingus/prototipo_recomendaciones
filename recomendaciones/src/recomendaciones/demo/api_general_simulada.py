"""`api-general` simulado (`reco-demo api-general`). NO reemplaza al repo `api-general`: es un doble para la demo.

Cumple los dos papeles que `api-general` tiene frente a este servicio:

1. **Proveedor de sync**: sirve `/internal/v1/sync/{users,catalog/items,activity}` según el contrato propuesto
   `contracts/api-general-sync.openapi.yaml`. Lo consume el Data Transformer real, sin cambios.
2. **Puerta de entrada**: los endpoints `/demo/...` hacen lo que haría `api-general`: reenvían la declaración
   de gustos y la lectura a la API de recomendaciones con la API key interna, agregan títulos a los
   `item_id` y, al registrar una interacción, publican `recomendacion.actualizar` en RabbitMQ.

Tiene Swagger en `/docs` para recorrer el flujo sin escribir comandos. La API de recomendaciones sigue sin
Swagger (FR-060).
"""

from __future__ import annotations

import asyncio
import hmac
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

import aio_pika
import httpx
from fastapi import APIRouter, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from recomendaciones.demo import datos
from recomendaciones.worker.topology import actualizar_topology

_MAX_PAGE_SIZE = 500
_SYNC = "Sync (lo consume el Data Transformer)"
_DATOS = "1. Datos de la demo"
_FLUJO = "2. Flujo de recomendación"

Modulo = Literal["peliculas", "juegos"]


@dataclass
class EstadoDemo:
    api_key: str
    catalogo: list[datos.Item] = field(default_factory=datos.catalogo)
    usuarios: list[datos.Usuario] = field(default_factory=datos.usuarios)
    actividad: list[dict] = field(default_factory=list)
    snapshot: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.actividad:
            self.actividad = datos.actividad_inicial(self.catalogo, self.usuarios)
        self.items = {item.id: item for item in self.catalogo}
        self.por_alias = {u.alias: u for u in self.usuarios}
        self.por_id = {u.id: u for u in self.usuarios}


def create_app(*, api_key: str, amqp_url: str, recomendaciones_url: str) -> FastAPI:
    exchange_name = actualizar_topology().exchange

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ANN202
        connection = await _conectar(amqp_url)
        channel = await connection.channel(publisher_confirms=True)
        # Misma declaración que hace el worker (fanout, durable): es idempotente.
        app.state.exchange = await channel.declare_exchange(exchange_name, aio_pika.ExchangeType.FANOUT, durable=True)
        app.state.http = httpx.AsyncClient(
            base_url=recomendaciones_url, headers={"X-Internal-API-Key": api_key}, timeout=httpx.Timeout(10)
        )
        try:
            yield
        finally:
            await app.state.http.aclose()
            await connection.close()

    app = FastAPI(
        title="api-general SIMULADA (demo)",
        version="demo",
        description=(
            "Reemplaza a `api-general` mientras su integración no está disponible. Los endpoints **/demo** "
            "muestran el flujo de punta a punta; los de **sync** los consume el Data Transformer."
        ),
        lifespan=lifespan,
    )
    app.state.demo = EstadoDemo(api_key=api_key)
    app.include_router(router)
    return app


router = APIRouter()


async def _conectar(amqp_url: str, *, intentos: int = 30) -> aio_pika.abc.AbstractRobustConnection:
    """El broker puede tardar unos segundos en aceptar conexiones aunque el contenedor ya figure arriba."""
    for intento in range(1, intentos + 1):
        try:
            return await aio_pika.connect_robust(amqp_url)
        except (ConnectionError, aio_pika.exceptions.AMQPConnectionError):
            if intento == intentos:
                raise
            await asyncio.sleep(1)
    raise AssertionError("inalcanzable")


def _estado(request: Request) -> EstadoDemo:
    return request.app.state.demo


# --- Sincronización (contrato api-general-sync) --------------------------------------------------


def _autorizado(request: Request, key: str | None) -> EstadoDemo:
    estado = _estado(request)
    if not key or not hmac.compare_digest(key.encode(), estado.api_key.encode()):
        raise HTTPException(status_code=401, detail="API key interna inválida")
    return estado


def _pagina(estado: EstadoDemo, rows: list[dict], page_token: str | None, page_size: int) -> dict:
    start = _inicio(page_token, len(rows))
    nxt = start + min(page_size, _MAX_PAGE_SIZE)
    return {
        "snapshot_id": estado.snapshot,
        "total": len(rows),
        "next_page_token": str(nxt) if nxt < len(rows) else None,
        "items": rows[start:nxt],
    }


def _inicio(page_token: str | None, total: int) -> int:
    """Posición del token. Uno que este simulado no emitió es un error del cliente: 400, no 500 ni otra página."""
    if not page_token:
        return 0
    try:
        start = int(page_token)
    except ValueError:
        start = -1
    if not 0 <= start < total:
        raise HTTPException(status_code=400, detail=f"page_token inválido: {page_token}")
    return start


@router.get("/internal/v1/sync/users", tags=[_SYNC])
def sync_users(
    request: Request,
    page_token: str | None = None,
    page_size: int = Query(100, ge=1),
    x_internal_api_key: str | None = Header(default=None),
) -> dict:
    estado = _autorizado(request, x_internal_api_key)
    rows = [{"id": str(u.id), "birth_date": u.birth_date.isoformat(), "region": u.region} for u in estado.usuarios]
    return _pagina(estado, rows, page_token, page_size)


@router.get("/internal/v1/sync/catalog/items", tags=[_SYNC])
def sync_catalog(
    request: Request,
    page_token: str | None = None,
    page_size: int = Query(100, ge=1),
    x_internal_api_key: str | None = Header(default=None),
) -> dict:
    estado = _autorizado(request, x_internal_api_key)
    rows = [
        {"id": str(i.id), "module": i.module, "tags": list(i.tags), "age_rating": i.age_rating, "status": "available"}
        for i in estado.catalogo
    ]
    return _pagina(estado, rows, page_token, page_size)


@router.get("/internal/v1/sync/activity", tags=[_SYNC])
def sync_activity(
    request: Request,
    since: datetime | None = None,
    page_token: str | None = None,
    page_size: int = Query(100, ge=1),
    x_internal_api_key: str | None = Header(default=None),
) -> dict:
    estado = _autorizado(request, x_internal_api_key)
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)  # `occurred_at` lleva zona: un `since` sin zona se toma en UTC
    rows = [r for r in estado.actividad if since is None or datetime.fromisoformat(r["occurred_at"]) >= since]
    return _pagina(estado, rows, page_token, page_size)


# --- Puerta de entrada simulada -------------------------------------------------------------------


def _usuario(estado: EstadoDemo, alias_o_id: str) -> datos.Usuario:
    user = estado.por_alias.get(alias_o_id.lower())
    if user is None:
        try:
            user = estado.por_id.get(uuid.UUID(alias_o_id))
        except ValueError:
            user = None
    if user is None:
        raise HTTPException(status_code=404, detail=f"usuario desconocido: {alias_o_id} (ver GET /demo/usuarios)")
    return user


def _item(estado: EstadoDemo, texto: str) -> datos.Item:
    try:
        found = estado.items.get(uuid.UUID(texto))
    except ValueError:
        found = next((i for i in estado.catalogo if i.titulo.lower() == texto.strip().lower()), None)
    if found is None:
        raise HTTPException(status_code=404, detail=f"ítem desconocido: {texto} (ver GET /demo/catalogo)")
    return found


def _item_json(item: datos.Item) -> dict:
    return {"item_id": str(item.id), "titulo": item.titulo, "tags": list(item.tags), "age_rating": item.age_rating}


def _reenviar(response: httpx.Response, **extra: object) -> JSONResponse:
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}
    return JSONResponse(status_code=response.status_code, content={**extra, "respuesta_recomendaciones": body})


@router.get("/health", include_in_schema=False)
def health() -> dict:
    return {"status": "ok"}


@router.get("/demo/usuarios", tags=[_DATOS])
def listar_usuarios(request: Request, incluir_fondo: bool = False) -> list[dict]:
    """Personas de la demo. Los usuarios de fondo solo aportan actividad y perfiles vecinos."""
    return [
        {
            "alias": u.alias,
            "user_id": str(u.id),
            "nombre": u.nombre,
            "birth_date": u.birth_date.isoformat(),
            "region": u.region,
            "descripcion": u.descripcion,
        }
        for u in _estado(request).usuarios
        if incluir_fondo or u.perfil is None
    ]


@router.get("/demo/catalogo", tags=[_DATOS])
def listar_catalogo(request: Request, module: Modulo) -> list[dict]:
    return [_item_json(i) for i in _estado(request).catalogo if i.module == module]


@router.get("/demo/tags", tags=[_DATOS])
def listar_tags(request: Request, module: Modulo) -> list[str]:
    """Vocabulario del módulo: los tags que se pueden declarar."""
    return datos.tags_por_modulo(_estado(request).catalogo)[module]


class Declaracion(BaseModel):
    module: Modulo
    tags: list[str] = Field(
        min_length=1,
        examples=[["terror", "sobrenatural", "suspenso", "misterio", "drama"]],
        description="Al menos 5 tags del vocabulario del módulo (GET /demo/tags).",
    )


@router.post("/demo/usuarios/{usuario}/declaracion", tags=[_FLUJO])
async def declarar(usuario: str, body: Declaracion, request: Request) -> JSONResponse:
    """Reenvía la declaración de gustos a `POST /internal/v1/declarations/{user_id}` de recomendaciones."""
    user = _usuario(_estado(request), usuario)
    response = await request.app.state.http.post(f"/internal/v1/declarations/{user.id}", json=body.model_dump())
    return _reenviar(response, usuario=user.alias)


@router.get("/demo/usuarios/{usuario}/recomendaciones", tags=[_FLUJO])
async def recomendaciones(
    usuario: str,
    request: Request,
    module: Modulo,
    top_n: int | None = Query(default=None, ge=10, le=50),
) -> JSONResponse:
    """Lee `GET /internal/v1/recommendations/{user_id}` y agrega título, tags y clasificación de cada ítem."""
    estado = _estado(request)
    user = _usuario(estado, usuario)
    params: dict[str, object] = {"module": module}
    if top_n is not None:
        params["top_n"] = top_n
    response = await request.app.state.http.get(f"/internal/v1/recommendations/{user.id}", params=params)
    if response.status_code != 200:
        return _reenviar(response, usuario=user.alias)
    body = response.json()
    items = []
    for entry in body.get("items", []):
        item = estado.items.get(uuid.UUID(entry["item_id"]))
        detalle = _item_json(item) if item else {"item_id": entry["item_id"]}
        items.append({"position": entry["position"], "score": entry["score"], **detalle})
    return JSONResponse(
        {
            "usuario": user.alias,
            "module": module,
            "result_type": body["result_type"],
            "computed_at": body.get("computed_at"),
            "config_version": body.get("config_version"),
            "items": items,
        }
    )


class Interaccion(BaseModel):
    item: str = Field(description="UUID o título exacto del ítem (GET /demo/catalogo).", examples=["El conjuro"])
    signal_type: Literal["like", "dislike", "consumo"]


@router.post("/demo/usuarios/{usuario}/interacciones", tags=[_FLUJO])
async def interactuar(usuario: str, body: Interaccion, request: Request) -> dict:
    """Registra la interacción (queda en la actividad de sync) y publica `recomendacion.actualizar` en RabbitMQ."""
    estado = _estado(request)
    user = _usuario(estado, usuario)
    item = _item(estado, body.item)
    occurred_at = datetime.now(UTC).isoformat()
    origin_interaction_id = f"demo-{uuid.uuid4()}"
    # El mismo hecho, con el mismo origin_interaction_id y occurred_at, por REST y por evento (CR-17, FR-061).
    estado.actividad.append(
        {
            "origin_interaction_id": origin_interaction_id,
            "user_id": str(user.id),
            "item_id": str(item.id),
            "module": item.module,
            "signal_type": body.signal_type,
            "occurred_at": occurred_at,
        }
    )
    event = {
        "event_id": str(uuid.uuid4()),
        "origin_interaction_id": origin_interaction_id,
        "user_id": str(user.id),
        "module": item.module,
        "item_id": str(item.id),
        "signal_type": body.signal_type,
        "occurred_at": occurred_at,
        "correlation_id": str(uuid.uuid4()),
    }
    await request.app.state.exchange.publish(
        aio_pika.Message(
            json.dumps(event).encode(),
            content_type="application/json",
            message_id=event["event_id"],
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers={"event_type": "recomendacion.actualizar.v3", "event_version": "3.0.0"},
        ),
        routing_key="",
    )
    return {"usuario": user.alias, "item": _item_json(item), "evento_publicado": event}
