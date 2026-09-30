"""T052 — ciclo de vida del ítem (FR-072…FR-075, DI-10, DI-11, RD-87, RD-88, RD-91).

El retiro lo produce el Data Transformer real contra el doble de `api-general`; los tres caminos por los que
un ítem podría servirse se verifican por separado porque son tres mecanismos distintos (§4.4).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
import sqlalchemy as sa

from recomendaciones.batch.fallback import FallbackJob
from recomendaciones.config.loader import load_engine_config
from recomendaciones.engine.profile import SignalWeights, build_profile
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module, ProfileScope
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.transformer.client import ApiGeneralClient
from recomendaciones.transformer.pipeline import SyncPipeline
from recomendaciones.worker.catalog import load_snapshot
from recomendaciones.worker.handler import Recomputer
from recomendaciones.worker.inputs import load_profile_inputs
from tests.integration import seed
from tests.support.api_general_double import ApiGeneralDouble

CFG = load_engine_config("v1.yaml")
KEY = "test.s3cr3t-0123456789abcdef"
TAGS = ["accion", "drama", "terror", "comedia", "suspenso", "aventura"]
T0 = datetime(2026, 9, 20, tzinfo=UTC)


class World:
    def __init__(self, db_factory, redis_client, n_items: int = 12) -> None:
        self.db, self.redis = db_factory, redis_client
        self.cache = CacheClient(redis_client)
        self.repo = RecommendationRepository(self.cache, ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)
        self.double = ApiGeneralDouble(api_key=KEY, page_size=100)
        self.user = self.double.add_user()
        self.items = [self.double.add_item("peliculas", [TAGS[i % 6], TAGS[(i + 1) % 6]]) for i in range(n_items)]
        self.double.add_interaction(self.user, self.items[0], "like", T0)
        self.double.add_interaction(self.user, self.items[1], "like", T0 + timedelta(minutes=1))
        self.double.add_interaction(self.user, self.items[2], "dislike", T0 + timedelta(minutes=2))
        assert self.sync().status == "success"
        with db_factory.begin() as s:
            seed.declare(s, self.user, "peliculas", TAGS[:5])
            seed.vectorize_all(s)

    def sync(self):
        client = ApiGeneralClient("http://api-general.internal", KEY, timeout_seconds=5, transport=self.double.transport())
        filters = FiltersCache(self.cache, DbFiltersSource(self.db), 3600)
        pipeline = SyncPipeline(self.db, client, filters, self.cache, CFG, Metrics(), volume_delta_ratio=0.9, redelivery_window_hours=48)
        return pipeline.run()

    def _record(self, item_id: uuid.UUID) -> dict:
        return next(r for r in self.double.items if r["id"] == str(item_id))

    def retire_explicitly(self, *item_ids: uuid.UUID) -> None:  # CR-7
        for item_id in item_ids:
            self._record(item_id)["status"] = "retired"
        assert self.sync().status == "success"

    def remove_from_origin(self, item_id: uuid.UUID) -> None:  # CR-8
        self.double.items.remove(self._record(item_id))
        assert self.sync().status == "success"

    def reinstate(self, item_id: uuid.UUID, record: dict | None = None) -> None:
        if record is not None:
            self.double.items.append(record)
        self._record(item_id).pop("status", None)
        assert self.sync().status == "success"

    def status(self, item_id: uuid.UUID) -> str:
        with self.db() as s:
            return s.execute(sa.text("SELECT status::text FROM items WHERE id = :i"), {"i": item_id}).scalar_one()

    def signals(self) -> list[tuple]:
        with self.db() as s:
            return [tuple(r) for r in s.execute(sa.text("SELECT id, item_id, signal_type::text, occurred_at FROM user_signals ORDER BY id"))]

    def profile(self, scope: ProfileScope = ProfileScope.PELICULAS) -> np.ndarray:
        modules = ("peliculas",) if scope is ProfileScope.PELICULAS else ("peliculas", "juegos")
        with self.db() as s:
            snapshot = load_snapshot(s, CFG.config_version)
            inputs = load_profile_inputs(s, self.user, scope)
        profile = build_profile(inputs, snapshot.vectors, snapshot.seed_items(modules), snapshot.vocab, SignalWeights(CFG.peso_like, CFG.peso_dislike))
        return profile.vector.values

    def recompute(self) -> set[uuid.UUID]:
        outcome = Recomputer(self.db, self.repo, CFG, Metrics()).recompute(self.user, Module.PELICULAS, "signal")
        assert outcome.status == "written", outcome
        entry = self.repo.read_fresh(CFG.config_version, self.user, Module.PELICULAS)
        return {i.item_id for i in entry.items}

    def fallback(self) -> set[uuid.UUID]:
        FallbackJob(self.db, self.repo, CFG, Metrics()).run()
        entry = self.repo.read_fallback(CFG.config_version, Module.PELICULAS)
        return {i.item_id for i in entry.items}


# --- FR-073, DI-11 --------------------------------------------------------------------------------


def test_logical_retirement_preserves_signals_and_leaves_every_profile_unchanged(db_factory, redis_client) -> None:
    world = World(db_factory, redis_client)
    signals, module_profile, general_profile = world.signals(), world.profile(), world.profile(ProfileScope.GENERAL)
    world.retire_explicitly(world.items[0])  # el ítem con like
    world.remove_from_origin(world.items[2])  # el ítem con dislike, por desaparición
    assert (world.status(world.items[0]), world.status(world.items[2])) == ("retired", "retired")
    assert world.signals() == signals
    np.testing.assert_array_equal(world.profile(), module_profile)  # conservar y dejar de usar sería lo mismo que borrar
    np.testing.assert_array_equal(world.profile(ProfileScope.GENERAL), general_profile)


# --- FR-072, DI-10: tres caminos, tres tests ---------------------------------------------------------


def test_retired_item_is_not_selected_as_a_candidate(db_factory, redis_client) -> None:
    world = World(db_factory, redis_client)
    target = world.items[3]
    assert target in world.recompute()  # control: vigente, sí es candidato
    world.retire_explicitly(target)
    assert target not in world.recompute()


def test_retired_item_is_not_in_the_fallback(db_factory, redis_client) -> None:
    world = World(db_factory, redis_client)
    target = world.items[3]
    assert target in world.fallback()
    world.retire_explicitly(target)
    assert target not in world.fallback()


def test_item_retired_after_its_result_was_precomputed_is_not_served(api, db_factory, redis_client) -> None:
    """El caso crítico: los dos primeros filtros ya pasaron; solo la guarda del request path lo detiene."""
    _client, services = api
    world = World(db_factory, redis_client)
    target = world.items[3]
    assert target in world.recompute()
    world.retire_explicitly(target)
    cached = world.repo.read_fresh(CFG.config_version, world.user, Module.PELICULAS)
    assert target in {i.item_id for i in cached.items}  # la entrada viva todavía lo contiene
    result = services.read_service.read(world.user, Module.PELICULAS, top_n=50, prefer_stale=False)
    assert result.result_type.value == "personalized"
    assert target not in {i.item_id for i in result.items}


# --- FR-075 ------------------------------------------------------------------------------------------


def test_reduced_list_is_served_without_padding(api, db_factory, redis_client) -> None:
    _client, services = api
    world = World(db_factory, redis_client, n_items=24)
    listed = world.items[4:24]  # 20 ítems sin interacción, todos aptos
    world.repo.write_personalized(
        RecommendationEntry(
            user_id=world.user,
            module=Module.PELICULAS,
            config_version=CFG.config_version,
            vocab_version="forense",
            max_age_ordinal=2,
            computed_at=datetime.now(UTC),
            items=tuple(CachedItem(item_id, rank, 1.0 - rank / 100, 0) for rank, item_id in enumerate(listed, start=1)),
        )
    )
    world.fallback()  # hay respaldo disponible: aun así no se usa para rellenar
    world.retire_explicitly(*listed[:13])
    result = services.read_service.read(world.user, Module.PELICULAS, top_n=20, prefer_stale=False)
    assert [i.item_id for i in result.items] == listed[13:]  # 7 de 20, en su orden
    assert result.result_type.value == "personalized"  # el estado lo determina la frescura, no el tamaño


def test_list_emptied_by_retirement_is_empty_no_candidates(api, db_factory, redis_client) -> None:
    _client, services = api
    world = World(db_factory, redis_client)
    listed = world.items[4:8]
    world.repo.write_personalized(
        RecommendationEntry(
            world.user, Module.PELICULAS, CFG.config_version, "forense", 2, datetime.now(UTC),
            tuple(CachedItem(item_id, rank, 0.5, 0) for rank, item_id in enumerate(listed, start=1)),
        )
    )
    world.retire_explicitly(*listed)
    result = services.read_service.read(world.user, Module.PELICULAS, top_n=10, prefer_stale=False)
    assert len(result.items) == 0
    assert result.result_type.value == "empty_no_candidates"  # solo la lista vacía (FR-056, RD-42)


# --- FR-074 revocable -----------------------------------------------------------------------------------


def test_retired_and_reinstated_item_is_recommendable_again_and_previous_signals_still_apply(db_factory, redis_client) -> None:
    world = World(db_factory, redis_client)
    profile_before, signals = world.profile(), world.signals()
    liked, neutral = world.items[0], world.items[3]
    removed = world._record(liked)
    world.remove_from_origin(liked)
    world.retire_explicitly(neutral)
    assert neutral not in world.recompute()
    world.reinstate(liked, record=removed)
    world.reinstate(neutral)
    assert (world.status(liked), world.status(neutral)) == ("available", "available")
    recommended = world.recompute()
    assert neutral in recommended  # vuelve a ser recomendable
    assert liked not in recommended  # su like sigue excluyéndolo (señal previa vigente)
    assert world.signals() == signals
    np.testing.assert_array_equal(world.profile(), profile_before)


# --- FR-072, DI-10 con `retired:` ya poblado (T068) ----------------------------------------------------


def test_retirement_by_sync_invalidates_a_warm_retired_set(api, db_factory, redis_client) -> None:
    """El caso real: `retired:{module}` ya está en caché cuando llega el retiro. La lectura siguiente no lo sirve.

    Un set vacío no se guarda en Redis, así que primero se retira otro ítem y se lee: el set queda poblado.
    """
    _client, services = api
    world = World(db_factory, redis_client)
    earlier, target = world.items[5], world.items[3]
    assert target in world.recompute()
    world.retire_explicitly(earlier)
    services.read_service.read(world.user, Module.PELICULAS, top_n=50, prefer_stale=False)
    assert redis_client.exists("retired:peliculas")  # set poblado antes del retiro
    world.retire_explicitly(target)
    result = services.read_service.read(world.user, Module.PELICULAS, top_n=50, prefer_stale=False)
    assert target not in {i.item_id for i in result.items}


class _RetiredDeleteFails(CacheClient):
    """Redis cae justo al invalidar `retired:` (T068)."""

    def delete(self, *keys: str) -> int:
        from recomendaciones.shared.errors import CacheUnavailable

        if any(k.startswith("retired:") for k in keys):
            raise CacheUnavailable()
        return super().delete(*keys)


def test_retirement_is_not_applied_silently_when_the_retired_set_cannot_be_invalidated(db_factory, redis_client) -> None:
    world = World(db_factory, redis_client)
    target = world.items[3]
    world._record(target)["status"] = "retired"
    cache = _RetiredDeleteFails(redis_client)
    client = ApiGeneralClient("http://api-general.internal", KEY, timeout_seconds=5, transport=world.double.transport())
    pipeline = SyncPipeline(
        db_factory, client, FiltersCache(cache, DbFiltersSource(db_factory), 3600), cache, CFG, Metrics(),
        volume_delta_ratio=0.9, redelivery_window_hours=48,
    )
    report = pipeline.run()
    assert report.status == "failed" and "Redis" in (report.reason or "")
    assert world.status(target) == "available"  # la transacción se revirtió: la próxima corrida lo retira
    with db_factory() as s:
        last = s.execute(sa.text("SELECT status::text, failure_reason FROM sync_runs ORDER BY id DESC LIMIT 1")).one()
    assert last[0] == "failed" and "Redis" in (last[1] or "")
