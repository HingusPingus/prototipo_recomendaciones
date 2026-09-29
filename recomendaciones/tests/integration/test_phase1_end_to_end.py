"""Gate de salida de Fase 1 (plan.md §4): un usuario declarado obtiene un top-N materializado de punta a
punta, y el ciclo de recálculo se cierra (US1, US2, US5). También arranca los tres procesos (T001)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, date, datetime

import aio_pika
import pytest
from fastapi.testclient import TestClient

from recomendaciones.api.app import create_app
from recomendaciones.batch.runtime import run_job
from recomendaciones.bootstrap import build_runtime
from recomendaciones.config.settings import load_settings
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.transformer.runtime import run_once
from recomendaciones.worker.runtime import build_worker
from recomendaciones.worker.topology import actualizar_topology
from tests.support.api_general_double import ApiGeneralDouble

MOVIE_TAGS = ["horror", "sobrenatural", "drama", "comedia", "thriller", "misterio", "romance", "scifi"]


@pytest.fixture
def stack_env(valid_env, monkeypatch, db_factory, redis_url, amqp_url) -> dict[str, str]:  # noqa: ANN001
    monkeypatch.setenv("RECO_DATABASE_URL", db_factory.url)
    monkeypatch.setenv("RECO_REDIS_URL", redis_url)
    monkeypatch.setenv("RECO_AMQP_URL", amqp_url)
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        monkeypatch.setenv("RECO_METRICS_PORT", str(sock.getsockname()[1]))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        monkeypatch.setenv("RECO_HEALTH_PORT", str(sock.getsockname()[1]))
    return valid_env


def _catalog(double: ApiGeneralDouble) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    user = double.add_user(birth_date=date(1995, 6, 15), region="AR")
    for _ in range(3):
        double.add_user()
    items = {}
    for i, tag in enumerate(MOVIE_TAGS):
        items[tag] = double.add_item("peliculas", [tag, MOVIE_TAGS[(i + 1) % len(MOVIE_TAGS)]], rating="ATP")
    items["adulto"] = double.add_item("peliculas", ["horror", "drama"], rating="+18")
    items["juego"] = double.add_item("juegos", ["horror", "survival"], rating="ATP")
    return user, items


async def _publish(amqp_url: str, body: dict) -> None:
    connection = await aio_pika.connect_robust(amqp_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.get_exchange(actualizar_topology().exchange)
        await exchange.publish(aio_pika.Message(json.dumps(body).encode()), routing_key="")


async def test_declared_user_gets_a_materialized_top_n_end_to_end(stack_env, db_factory, redis_client, amqp_url) -> None:  # noqa: ANN001
    settings = load_settings()
    double = ApiGeneralDouble(api_key=stack_env["RECO_INTERNAL_API_KEY"], page_size=4)
    user, items = _catalog(double)

    # Data Transformer: sincroniza y reconcilia vocabulario (T029, T030)
    assert run_once(settings, transport=double.transport()) == 0
    # Jobs: popularidad y respaldo (T063, T038)
    assert run_job(settings, ["popularity"]) == 0
    assert run_job(settings, ["fallback"]) == 0
    assert run_job(settings, ["age-refresh"]) == 0  # T051
    assert run_job(settings, ["purge-signals"]) == 0  # T057
    assert run_job(settings, ["suppressions"]) == 0  # T059: barrido
    assert run_job(settings, ["desconocido"]) == 2

    headers = {"X-Internal-API-Key": stack_env["RECO_INTERNAL_API_KEY"]}
    with TestClient(create_app(settings)) as api:
        url = f"/internal/v1/recommendations/{user}"
        assert api.get(url, params={"module": "peliculas"}, headers=headers).status_code == 412  # FR-088
        declared = api.post(f"/internal/v1/declarations/{user}", json={"module": "peliculas", "tags": MOVIE_TAGS[:5]}, headers=headers)
        assert declared.status_code == 201
        first = api.get(url, params={"module": "peliculas"}, headers=headers).json()
        assert first["result_type"] == "fallback" and first["items"]  # respaldo no personalizado mientras recalcula

        # Worker: procesa la solicitud de recálculo de la declaración (T027)
        runtime = build_runtime(settings, "worker", cache=CacheClient(redis_client))
        events, requests = build_worker(runtime)
        await events.start()
        try:
            while await asyncio.to_thread(requests.poll_once):
                pass
            personalized = api.get(url, params={"module": "peliculas", "top_n": 10}, headers=headers).json()
            assert personalized["result_type"] == "personalized"  # US4-5: deja de marcarse como respaldo
            served = [uuid.UUID(i["item_id"]) for i in personalized["items"]]
            victim = served[0]

            # US2: un dislike por evento se persiste, excluye y recalcula (T023, T064, T027)
            await _publish(
                amqp_url,
                {
                    "event_id": str(uuid.uuid4()),
                    "origin_interaction_id": f"int-{uuid.uuid4()}",
                    "user_id": str(user),
                    "module": "peliculas",
                    "item_id": str(victim),
                    "signal_type": "dislike",
                    "occurred_at": datetime.now(UTC).isoformat(),
                },
            )
            for _ in range(100):
                after = api.get(url, params={"module": "peliculas", "top_n": 10}, headers=headers).json()
                if victim not in {uuid.UUID(i["item_id"]) for i in after["items"]}:
                    break
                await asyncio.sleep(0.1)
            else:
                pytest.fail("el ítem dislikeado siguió apareciendo")
            assert after["result_type"] == "personalized"
        finally:
            await events.stop()


async def test_worker_process_starts_and_stops(stack_env) -> None:  # noqa: ANN001
    from recomendaciones.worker.runtime import serve

    stop = asyncio.Event()
    task = asyncio.create_task(serve(load_settings(), stop=stop))
    await asyncio.sleep(1.5)
    assert not task.done(), task.exception() if task.done() else None
    stop.set()
    await asyncio.wait_for(task, timeout=10)
