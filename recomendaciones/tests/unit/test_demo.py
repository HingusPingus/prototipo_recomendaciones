"""Modo demo (`reco-demo`): el `api-general` simulado cumple el contrato de sync que consume el Transformer
real, sus datos pasan la ingesta sin violaciones y el evento que publica lo acepta el worker."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from recomendaciones.api.services.declaracion import validate_declaration
from recomendaciones.config.loader import load_engine_config
from recomendaciones.demo import datos
from recomendaciones.demo.api_general_simulada import create_app
from recomendaciones.shared.errors import UpstreamError
from recomendaciones.transformer.client import ApiGeneralClient
from recomendaciones.transformer.pipeline import SyncPipeline
from recomendaciones.worker.schemas import parse_actualizar

KEY = "demo.clave-de-test-0123456789"


@pytest.fixture
def app():  # noqa: ANN201
    return create_app(api_key=KEY, amqp_url="amqp://no-se-usa", recomendaciones_url="http://no-se-usa")


@pytest.fixture
def client(app) -> TestClient:  # noqa: ANN001
    return TestClient(app)  # sin `with`: el lifespan (RabbitMQ) no corre


def _sync_client(client: TestClient, key: str = KEY) -> ApiGeneralClient:
    return ApiGeneralClient("http://testserver", key, timeout_seconds=5, transport=client._transport)


def test_datos_son_deterministas_y_unicos() -> None:
    items, users = datos.catalogo(), datos.usuarios()
    assert [i.id for i in items] == [i.id for i in datos.catalogo()]
    assert len({i.id for i in items}) == len(items) and len({u.id for u in users}) == len(users)
    actividad = datos.actividad_inicial(items, users)
    assert actividad == datos.actividad_inicial(items, users)
    assert len({r["origin_interaction_id"] for r in actividad}) == len(actividad)


def test_cada_perfil_es_declarable_en_su_modulo() -> None:
    cfg = load_engine_config("v1.yaml")
    vocab = datos.tags_por_modulo(datos.catalogo())
    for perfil in datos.PERFILES.values():
        for module, tags in perfil.tags.items():
            validate_declaration(tags, declarable=frozenset(vocab[module]), minimum=cfg.declared_tags_min)


def test_el_transformer_real_recibe_pasadas_completas(client: TestClient) -> None:
    sync = _sync_client(client)
    users, catalog, activity = sync.list_users(), sync.list_catalog(), sync.list_activity(None)
    assert users.complete and catalog.complete and activity.complete
    assert len(catalog.rows) == len(datos.catalogo())
    since = sync.list_activity(datetime.now(UTC) - timedelta(days=5))
    assert since.complete and 0 < len(since.rows) < len(activity.rows)


def test_la_paginacion_recorre_todo_con_un_mismo_snapshot(client: TestClient) -> None:
    rows, snapshots, token = [], set(), None
    while True:
        params = {"page_size": 37, **({"page_token": token} if token else {})}
        page = client.get("/internal/v1/sync/activity", params=params, headers={"X-Internal-API-Key": KEY}).json()
        rows += page["items"]
        snapshots.add(page["snapshot_id"])
        token = page["next_page_token"]
        if not token:
            break
    assert len(rows) == page["total"] and len(snapshots) == 1


def test_una_api_key_ajena_se_rechaza(client: TestClient) -> None:
    with pytest.raises(UpstreamError):
        _sync_client(client, "demo.otra-clave-0123456789").list_users()


def test_los_datos_pasan_la_ingesta_sin_violaciones(client: TestClient) -> None:
    sync = _sync_client(client)
    pipeline = SyncPipeline.__new__(SyncPipeline)  # solo las validaciones, sin DB
    pipeline._metrics = mock.Mock()
    pipeline._cfg = load_engine_config("v1.yaml")
    frame, violations = pipeline._validate_users(sync.list_users().rows, run_id=0)
    assert violations == [] and len(frame) == len(datos.usuarios())
    items = pipeline._validate_items(sync.list_catalog().rows)
    assert len(items) == len(datos.catalogo())
    assert all(i["age_rating_source"] == "declared" for i in items)


def test_una_interaccion_publica_un_evento_que_el_worker_acepta(app, client: TestClient) -> None:  # noqa: ANN001
    published = []

    class Exchange:
        async def publish(self, message, routing_key) -> None:  # noqa: ANN001
            published.append(message)

    app.state.exchange = Exchange()
    response = client.post("/demo/usuarios/ana/interacciones", json={"item": "El conjuro", "signal_type": "dislike"})
    assert response.status_code == 200, response.text
    event = parse_actualizar(published[0].body)
    body = json.loads(published[0].body)
    # El mismo hecho por REST y por evento: mismo origin_interaction_id y occurred_at (CR-17, FR-061).
    assert any(
        r["origin_interaction_id"] == event.origin_interaction_id and r["occurred_at"] == body["occurred_at"]
        for r in app.state.demo.actividad
    )


@pytest.mark.parametrize(
    ("usuario", "item"), [("nadie", "El conjuro"), ("ana", "No existe")]
)
def test_usuario_o_item_desconocido_es_404(client: TestClient, usuario: str, item: str) -> None:
    response = client.post(f"/demo/usuarios/{usuario}/interacciones", json={"item": item, "signal_type": "like"})
    assert response.status_code == 404


def test_el_modo_demo_no_se_importa_desde_los_procesos_reales() -> None:
    from pathlib import Path

    import recomendaciones

    root = Path(recomendaciones.__file__).parent
    offenders = [
        p.relative_to(root).as_posix()
        for p in root.rglob("*.py")
        if "demo" not in p.relative_to(root).parts and "recomendaciones.demo" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
