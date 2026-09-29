"""T044 — casos críticos obligatorios (plan.md §5 y los de la declaración de gustos).

Un test por escenario, identificable por nombre en el reporte de CI, contra la pila real: API HTTP, Postgres,
Redis y RabbitMQ. Los resultados precomputados se escriben por el repositorio —como lo haría el worker— para
poder fijar cada `result_type`, y los que dependen del motor se calculan con el `Recomputer` real.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import uuid
from datetime import UTC, date, datetime

import aio_pika
import sqlalchemy as sa
from fastapi.testclient import TestClient

from recomendaciones.batch.fallback import FallbackJob
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module, SignalType
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository
from recomendaciones.storage.db.exclusions import ExclusionResolver
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.transformer.client import ApiGeneralClient
from recomendaciones.transformer.pipeline import SyncPipeline
from recomendaciones.worker.consumer import EventConsumer, RetryPolicy
from recomendaciones.worker.handler import ActualizarHandler
from recomendaciones.worker.idempotency import EventIdempotency
from recomendaciones.worker.schemas import ActualizarEvent
from recomendaciones.worker.signals import SignalIngestor
from recomendaciones.worker.topology import Topology
from tests.conftest import VALID_ENV
from tests.integration import seed
from tests.integration.test_propagation import CFG, _recomputer, _world
from tests.support.api_general_double import ApiGeneralDouble

HEADERS = {"X-Internal-API-Key": VALID_ENV["RECO_INTERNAL_API_KEY"]}
MINOR_BIRTH = date(2016, 1, 1)
RESULT_TYPES = {"personalized", "personalized_stale", "fallback", "empty_pending", "empty_no_candidates"}


def _get(client: TestClient, user: uuid.UUID, module: str, **params: object):
    return client.get(f"/internal/v1/recommendations/{user}", params={"module": module, **params}, headers=HEADERS)


def _repo(redis_client) -> RecommendationRepository:
    return RecommendationRepository(CacheClient(redis_client), ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)


def _entry(user: uuid.UUID | None, module: Module, items: list[tuple[uuid.UUID, int]], ordinal: int | None = 0) -> RecommendationEntry:
    return RecommendationEntry(
        user, module, CFG.config_version, "forense", ordinal if user else None, datetime.now(UTC),
        tuple(CachedItem(item_id, rank, 1.0 - rank / 100, age) for rank, (item_id, age) in enumerate(items, start=1)),
    )


def _write_stale_only(redis_client, entry: RecommendationEntry) -> None:
    _repo(redis_client).write_personalized(entry)
    redis_client.delete(keys.reco_key(entry.config_version, entry.user_id, entry.module))


def _ordinals(db_factory, item_ids) -> dict[uuid.UUID, int]:
    with db_factory() as s:
        rows = s.execute(sa.text("SELECT id, min_age_ordinal FROM items WHERE id = ANY(:i)"), {"i": list(item_ids)})
        return dict(rows.all())


def _catalog(db_factory):
    """Por módulo: cinco aptos para todo público y tres para adultos."""
    with db_factory.begin() as s:
        out = {}
        for module in ("peliculas", "juegos"):
            apt = [(seed.item(s, module, [f"{module}-t{i}", f"{module}-t{(i + 1) % 6}"]), 0) for i in range(5)]
            adult = [(seed.item(s, module, [f"{module}-t{i}"], rating="+18", ordinal=2), 2) for i in range(3)]
            out[module] = (apt, adult)
    return out


def _declared_user(db_factory, *, birth: date = date(1990, 1, 1), ordinal: int = 2, modules=("peliculas", "juegos")) -> uuid.UUID:
    with db_factory.begin() as s:
        user = seed.user(s, birth_date=birth, max_age_ordinal=ordinal)
        for module in modules:
            names = [f"{module}-t{i}" for i in range(5)]
            seed.tags(s, names)
            seed.declare(s, user, module, names)
    return user


# --- 1. Menor de edad --------------------------------------------------------------------------------


def test_minor_receives_zero_unsuitable_content_in_all_five_result_types(api, db_factory, redis_client) -> None:
    client, _ = api
    catalog = _catalog(db_factory)
    (m_apt, m_adult), (j_apt, j_adult) = catalog["peliculas"], catalog["juegos"]
    minors = {kind: _declared_user(db_factory, birth=MINOR_BIRTH, ordinal=0) for kind in RESULT_TYPES}
    repo = _repo(redis_client)
    mixed_m, mixed_j = m_adult[:2] + m_apt[:3] + m_adult[2:], j_adult[:2] + j_apt[:3] + j_adult[2:]
    repo.write_personalized(_entry(minors["personalized"], Module.PELICULAS, mixed_m))
    repo.write_fallback(_entry(None, Module.PELICULAS, mixed_m))  # el de películas; juegos queda sin respaldo
    _write_stale_only(redis_client, _entry(minors["personalized_stale"], Module.JUEGOS, mixed_j))
    repo.write_personalized(_entry(minors["empty_no_candidates"], Module.PELICULAS, m_adult))
    module_of = {"personalized": "peliculas", "fallback": "peliculas", "empty_no_candidates": "peliculas",
                 "personalized_stale": "juegos", "empty_pending": "juegos"}
    adult_ids = {i for i, _ in m_adult + j_adult}
    for kind, user in minors.items():
        response = _get(client, user, module_of[kind], top_n=10)
        assert response.status_code == 200, (kind, response.text)
        body = response.json()
        assert body["result_type"] == kind
        served = {uuid.UUID(i["item_id"]) for i in body["items"]}
        assert not served & adult_ids, kind
        assert all(o <= 0 for o in _ordinals(db_factory, served).values()), kind


# --- 2. Exclusión estricta ---------------------------------------------------------------------------


def test_strict_exclusion_zero_excluded_items_in_any_response(api, db_factory, redis_client) -> None:
    client, _ = api
    apt = _catalog(db_factory)["peliculas"][0]
    excluded = [apt[0][0], apt[2][0]]
    users = [_declared_user(db_factory) for _ in range(3)]
    with db_factory.begin() as s:
        for user in users:
            for item_id in excluded:
                seed.exclusion(s, user, item_id, "consumo")
    games = _catalog_juegos_with(db_factory, excluded_user=users[1])  # antes de toda lectura: sin pasar por el resolutor
    repo = _repo(redis_client)
    repo.write_personalized(_entry(users[0], Module.PELICULAS, apt, ordinal=2))
    repo.write_fallback(_entry(None, Module.PELICULAS, apt))
    for user in users:  # users[1] y users[2] reciben el respaldo
        body = _get(client, user, "peliculas", top_n=10).json()
        served = {uuid.UUID(i["item_id"]) for i in body["items"]}
        assert served and not served & set(excluded), body["result_type"]
    _write_stale_only(redis_client, _entry(users[1], Module.JUEGOS, games))
    body = _get(client, users[1], "juegos", top_n=10).json()
    assert body["result_type"] == "personalized_stale" and body["items"]
    with db_factory() as s:
        excl = set(s.execute(sa.text("SELECT item_id FROM user_exclusions WHERE user_id = :u"), {"u": users[1]}).scalars())
    assert not {uuid.UUID(i["item_id"]) for i in body["items"]} & excl


def _catalog_juegos_with(db_factory, *, excluded_user: uuid.UUID) -> list[tuple[uuid.UUID, int]]:
    with db_factory.begin() as s:
        games = [seed.item(s, "juegos", [f"juegos-t{i}"]) for i in range(4)]
        seed.exclusion(s, excluded_user, games[1], "dislike")
    return [(g, 0) for g in games]


# --- 3. Sin declaración en el módulo -------------------------------------------------------------------


def test_user_without_declaration_is_rejected_as_precondition_without_a_sixth_state(api, db_factory) -> None:
    client, _ = api
    user = _declared_user(db_factory, modules=("juegos",))
    response = _get(client, user, "peliculas")
    assert response.status_code == 412
    assert "result_type" not in response.json()
    assert _get(client, user, "juegos").status_code == 200  # el rechazo es por módulo


# --- 4. Recién declarado, sin top-N calculado ------------------------------------------------------------


def test_newly_declared_user_gets_non_personalized_fallback_then_personalized_after_recompute(api, db_factory, redis_client) -> None:
    client, _ = api
    _world(db_factory)
    newcomer = uuid.uuid4()
    with db_factory.begin() as s:
        seed.user(s, user_id=newcomer)
    FallbackJob(db_factory, _repo(redis_client), CFG, Metrics()).run()
    declared = client.post(
        f"/internal/v1/declarations/{newcomer}", json={"module": "peliculas", "tags": ["horror", "drama", "musical", "western", "comedia"]},
        headers=HEADERS,
    )
    assert declared.status_code in (200, 201), declared.text
    first = _get(client, newcomer, "peliculas").json()
    assert first["result_type"] == "fallback" and first["items"]  # marcado como no personalizado (US4-2)
    recomputer, _ = _recomputer(db_factory, redis_client)
    assert recomputer.recompute(newcomer, Module.PELICULAS, "declaration").status == "written"
    assert _get(client, newcomer, "peliculas").json()["result_type"] == "personalized"  # US4-5


def test_newly_declared_minor_with_only_unsuitable_catalog_gets_empty_no_candidates(api, db_factory, redis_client) -> None:
    client, _ = api
    with db_factory.begin() as s:
        for i in range(6):
            seed.item(s, "peliculas", [f"peliculas-t{i}"], rating="+18", ordinal=2)
    minor = _declared_user(db_factory, birth=MINOR_BIRTH, ordinal=0, modules=("peliculas",))
    FallbackJob(db_factory, _repo(redis_client), CFG, Metrics()).run()
    assert _get(client, minor, "peliculas").json()["result_type"] == "empty_no_candidates"


# --- 5. Cold start cruzado (SC-010) -------------------------------------------------------------------------


def test_cross_cold_start_movie_activity_and_game_declaration_produce_non_trivial_games(db_factory, redis_client) -> None:
    user, movies, games = _world(db_factory)
    with db_factory.begin() as s:
        baseline = seed.user(s, max_age_ordinal=1)
        seed.declare(s, baseline, "juegos", ["rpg", "fantasia", "deportes", "survival", "cooperativo"])
        seed.declare(s, baseline, "peliculas", ["horror", "drama", "musical", "western", "comedia"])
        for name in ("conjuro", "hereditary"):
            seed.signal(s, user, movies[name], "like")  # actividad solo en películas
    recomputer, repo = _recomputer(db_factory, redis_client)
    for who in (user, baseline):
        assert recomputer.recompute(who, Module.JUEGOS, "miss").status == "written"
    scores = {
        who: {i.item_id: i.score for i in repo.read_fresh(CFG.config_version, who, Module.JUEGOS).items} for who in (user, baseline)
    }
    assert scores[user]  # no vacío
    for horror_game in (games["re"], games["phasmo"]):  # el tag compartido sube por la actividad del otro módulo
        assert scores[user][horror_game] > scores[baseline][horror_game]


# --- 6. Cache miss -------------------------------------------------------------------------------------------


def test_cache_miss_returns_the_state_by_precedence_and_a_single_recompute_signal(api, db_factory, redis_client) -> None:
    client, _ = api
    user = _declared_user(db_factory)
    for _ in range(5):  # ráfaga de misses
        assert _get(client, user, "juegos").json()["result_type"] == "empty_pending"
    requests = [f for _i, f in redis_client.xrange(keys.RECOMPUTE_STREAM)]
    assert [(r["user_id"], r["module"], r["reason"]) for r in requests] == [(str(user), "juegos", "miss")]


# --- 7. Evento duplicado ---------------------------------------------------------------------------------------


def test_duplicate_event_triggers_a_single_recompute_even_when_delivered_concurrently(db_factory, redis_client) -> None:
    user, movies, _ = _world(db_factory)
    cache = CacheClient(redis_client)
    recomputes: list[uuid.UUID] = []
    lock = threading.Lock()

    class CountingRecompute:
        def on_signal(self, event: ActualizarEvent) -> str:
            with lock:
                recomputes.append(event.event_id)
            return "recomputed"

    handler = ActualizarHandler(
        idempotency=EventIdempotency(cache, db_factory, ttl_dedupe_seconds=60, retention_hours=24),
        ingestor=SignalIngestor(db_factory, ExclusionResolver(FiltersCache(cache, DbFiltersSource(db_factory), 60).invalidate), Metrics()),
        should_recompute=lambda _e: True,
        recompute=CountingRecompute(),
    )
    sequential = ActualizarEvent(uuid.uuid4(), f"int-{uuid.uuid4()}", user, Module.PELICULAS, movies["musical"], SignalType.LIKE, seed.T0)
    assert [handler(sequential) for _ in range(3)] == ["recomputed", "duplicate", "duplicate"]
    # El consumidor procesa en paralelo (prefetch): la misma entrega puede llegar a varios hilos a la vez.
    concurrent_ids = []
    for item in (movies["western"], movies["comedia"], movies["hereditary"], movies["adulto"], movies["conjuro"]):
        concurrent = ActualizarEvent(uuid.uuid4(), f"int-{uuid.uuid4()}", user, Module.PELICULAS, item, SignalType.LIKE, seed.T0)
        concurrent_ids.append(concurrent.event_id)
        barrier = threading.Barrier(6)
        results: list[str] = []

        def deliver(event: ActualizarEvent = concurrent, gate: threading.Barrier = barrier, out: list[str] = results) -> None:
            gate.wait()
            outcome = handler(event)
            with lock:
                out.append(outcome)

        threads = [threading.Thread(target=deliver) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(results) == ["duplicate"] * 5 + ["recomputed"]
    assert recomputes == [sequential.event_id, *concurrent_ids]


# --- 8. Payload inválido --------------------------------------------------------------------------------------


async def test_invalid_payload_goes_to_dlq_without_blocking_the_queue(amqp_url) -> None:
    suffix = uuid.uuid4().hex[:8]
    topology = Topology(f"x.crit.{suffix}", f"q.crit.{suffix}", f"q.crit.{suffix}.dlq", f"q.crit.{suffix}.retry")
    handled: list[uuid.UUID] = []
    consumer = EventConsumer(amqp_url, topology, lambda e: handled.append(e.event_id) or "recomputed", prefetch=1,
                             retry=RetryPolicy(max_attempts=5, backoff_base_seconds=0.05))
    valid_id = uuid.uuid4()
    valid = {"event_id": str(valid_id), "origin_interaction_id": "int-x", "user_id": str(uuid.uuid4()), "module": "peliculas",
             "item_id": str(uuid.uuid4()), "signal_type": "like", "occurred_at": seed.T0.isoformat()}
    await consumer.start()
    try:
        connection = await aio_pika.connect_robust(amqp_url)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.get_exchange(topology.exchange)
            await exchange.publish(aio_pika.Message(b'{"event_id": "no-es-uuid"'), routing_key="")  # primero, el inválido
            await exchange.publish(aio_pika.Message(json.dumps(valid).encode()), routing_key="")
        for _ in range(100):
            if handled:
                break
            await asyncio.sleep(0.1)
    finally:
        await consumer.stop()
    assert handled == [valid_id]  # el siguiente se procesó: la cola no quedó bloqueada
    connection = await aio_pika.connect_robust(amqp_url)
    async with connection:
        channel = await connection.channel()
        dlq = await channel.get_queue(topology.dead_letter_queue, ensure=True)
        message = await dlq.get(fail=False)
        assert message is not None and message.headers["x-dlq-reason"] == "invalid_payload"
        await message.ack()


# --- 9. Catálogo sin candidatos ------------------------------------------------------------------------------


def test_catalog_without_candidates_is_explicit_empty_never_padded_with_unsuitable_items(api, db_factory, redis_client) -> None:
    client, _ = api
    with db_factory.begin() as s:
        for i in range(6):
            seed.item(s, "peliculas", [f"peliculas-t{i}", f"peliculas-t{(i + 1) % 6}"], rating="+18", ordinal=2)
        minor = seed.user(s, birth_date=MINOR_BIRTH, max_age_ordinal=0)
        seed.declare(s, minor, "peliculas", [f"peliculas-t{i}" for i in range(5)])
        seed.vectorize_all(s)
    recomputer, repo = _recomputer(db_factory, redis_client)
    assert recomputer.recompute(minor, Module.PELICULAS, "miss").status == "written"
    assert repo.read_fresh(CFG.config_version, minor, Module.PELICULAS).items == ()  # vacío, sin relleno
    FallbackJob(db_factory, _repo(redis_client), CFG, Metrics()).run()
    body = _get(client, minor, "peliculas").json()
    assert body["result_type"] == "empty_no_candidates" and body["items"] == []


# --- 10. Dependencia externa caída ------------------------------------------------------------------------------


def _closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_redis_down_is_503_with_retry_after_and_no_database_fallback(valid_env, db_factory) -> None:
    from recomendaciones.api.app import build_services, create_app
    from recomendaciones.config.settings import load_settings

    user = _declared_user(db_factory)
    settings = load_settings()
    dead = CacheClient.from_url(f"redis://127.0.0.1:{_closed_port()}/0", timeout_seconds=0.3)
    with TestClient(create_app(settings, build_services(settings, db_factory=db_factory, cache=dead))) as client:
        response = _get(client, user, "peliculas")
    assert response.status_code == 503 and int(response.headers["Retry-After"]) > 0
    assert "items" not in response.json()


def test_broker_down_does_not_affect_reads(api, db_factory, redis_client) -> None:
    client, _ = api
    amqp = VALID_ENV["RECO_AMQP_URL"]
    host, port = "localhost", int(amqp.rsplit(":", 1)[1].split("/")[0])
    with socket.socket() as sock:
        assert sock.connect_ex((host, port)) != 0  # nadie escucha en el broker configurado
    user = _declared_user(db_factory)
    _repo(redis_client).write_personalized(_entry(user, Module.PELICULAS, _catalog(db_factory)["peliculas"][0], ordinal=2))
    assert _get(client, user, "peliculas").json()["result_type"] == "personalized"


def test_api_general_down_degrades_freshness_not_availability(api, db_factory, redis_client) -> None:
    client, _ = api
    user = _declared_user(db_factory)
    _repo(redis_client).write_personalized(_entry(user, Module.PELICULAS, _catalog(db_factory)["peliculas"][0], ordinal=2))
    double = ApiGeneralDouble(api_key=VALID_ENV["RECO_INTERNAL_API_KEY"], down=True)
    cache = CacheClient(redis_client)
    report = SyncPipeline(
        db_factory,
        ApiGeneralClient("http://api-general.internal", VALID_ENV["RECO_INTERNAL_API_KEY"], timeout_seconds=1, transport=double.transport()),
        FiltersCache(cache, DbFiltersSource(db_factory), 3600), cache, CFG, Metrics(), volume_delta_ratio=0.9, redelivery_window_hours=48,
    ).run()
    assert report.status == "failed" and "api-general" in (report.failure_reason or "")
    assert _get(client, user, "peliculas").json()["result_type"] == "personalized"


# --- 11. SC-019 y SC-020 ----------------------------------------------------------------------------------------


def test_dislike_measurably_lowers_items_sharing_its_tags_and_a_later_like_reverts_it(db_factory, redis_client) -> None:
    user, movies, _ = _world(db_factory)
    recomputer, repo = _recomputer(db_factory, redis_client)

    def score_of(item: uuid.UUID) -> float:
        assert recomputer.recompute(user, Module.PELICULAS, "signal").status == "written"
        return {i.item_id: i.score for i in repo.read_fresh(CFG.config_version, user, Module.PELICULAS).items}[item]

    sibling = movies["hereditary"]  # comparte `horror` con `conjuro`
    before = score_of(sibling)
    with db_factory.begin() as s:
        seed.signal(s, user, movies["conjuro"], "dislike", minutes=1)
    after_dislike = score_of(sibling)
    with db_factory.begin() as s:
        seed.signal(s, user, movies["conjuro"], "like", minutes=2)  # posterior: gana por occurred_at (FR-029d)
    after_like = score_of(sibling)
    assert after_dislike < before  # SC-019
    assert after_like > after_dislike  # SC-020
