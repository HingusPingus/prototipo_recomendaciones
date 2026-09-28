"""T027 — recálculo y propagación cross-module condicional (FR-010, FR-010a, FR-010c, FR-067, SC-005, SC-010, SC-016, SC-017)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa

from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module, SignalType
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.repository import RecommendationRepository
from recomendaciones.worker.handler import Recomputer
from recomendaciones.worker.schemas import ActualizarEvent
from tests.integration import seed

CFG = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")
T0 = datetime(2026, 9, 28, 10, tzinfo=UTC)


def _world(db_factory):  # noqa: ANN001, ANN202
    """Catálogo con un tag compartido (horror) y tags exclusivos por módulo; un usuario declarado en ambos."""
    with db_factory.begin() as s:
        movies = {name: seed.item(s, "peliculas", tags) for name, tags in {
            "conjuro": ["horror", "sobrenatural"], "hereditary": ["horror", "drama"], "musical": ["musical", "romance"],
            "western": ["western", "drama"], "adulto": ["drama", "belico"], "comedia": ["comedia", "familiar"],
        }.items()}
        s.execute(sa.text("UPDATE items SET min_age_ordinal = 2, age_rating = '+18' WHERE id = :i"), {"i": movies["adulto"]})
        games = {name: seed.item(s, "juegos", tags) for name, tags in {
            "re": ["horror", "survival"], "phasmo": ["horror", "cooperativo"], "rpg": ["rpg", "fantasia"],
            "deportes": ["deportes", "competitivo"],
        }.items()}
        user = seed.user(s, max_age_ordinal=1)
        seed.declare(s, user, "peliculas", ["horror", "drama", "musical", "western", "comedia"])
        seed.declare(s, user, "juegos", ["rpg", "fantasia", "deportes", "survival", "cooperativo"])
        seed.vectorize_all(s)
    return user, movies, games


def _recomputer(db_factory, redis_client, metrics: Metrics | None = None) -> tuple[Recomputer, RecommendationRepository]:  # noqa: ANN001
    repo = RecommendationRepository(CacheClient(redis_client), ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)
    return Recomputer(db_factory, repo, CFG, metrics or Metrics()), repo


def _event(user: uuid.UUID, item: uuid.UUID, module: Module, kind: str = "like") -> ActualizarEvent:
    return ActualizarEvent(uuid.uuid4(), f"int-{uuid.uuid4()}", user, module, item, SignalType(kind), T0)


def _signal(db_factory, user, item, kind: str) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        seed.signal(s, user, item, kind, source="evento")


def test_shared_tag_recomputes_both_modules_and_logs_the_reason(db_factory, redis_client, caplog) -> None:  # noqa: ANN001
    user, movies, _ = _world(db_factory)
    metrics = Metrics()
    recomputer, repo = _recomputer(db_factory, redis_client, metrics)
    _signal(db_factory, user, movies["conjuro"], "like")
    with caplog.at_level(logging.INFO, logger="recomendaciones.worker.handler"):
        result = recomputer.on_signal(_event(user, movies["conjuro"], Module.PELICULAS))
    assert result == "recomputed"
    assert repo.read_fresh(CFG.config_version, user, Module.PELICULAS) is not None
    assert repo.read_fresh(CFG.config_version, user, Module.JUEGOS) is not None
    decision = [r for r in caplog.records if getattr(r, "propagation_reason", None)]
    assert decision and decision[0].propagated is True and decision[0].propagation_reason == "shared_tag"
    assert metrics.value("reco_cross_module_propagation_total", propagated="true") == 1


def test_no_shared_tag_recomputes_only_its_module(db_factory, redis_client, caplog) -> None:  # noqa: ANN001
    user, movies, _ = _world(db_factory)
    metrics = Metrics()
    recomputer, repo = _recomputer(db_factory, redis_client, metrics)
    _signal(db_factory, user, movies["musical"], "like")
    with caplog.at_level(logging.INFO, logger="recomendaciones.worker.handler"):
        result = recomputer.on_signal(_event(user, movies["musical"], Module.PELICULAS))
    assert result == "skipped_no_shared_tag"
    assert repo.read_fresh(CFG.config_version, user, Module.PELICULAS) is not None
    assert repo.read_fresh(CFG.config_version, user, Module.JUEGOS) is None  # opuesto intacto
    decision = [r for r in caplog.records if getattr(r, "propagation_reason", None)]
    assert decision[0].propagated is False and decision[0].propagation_reason == "no_shared_tag"
    assert metrics.value("reco_cross_module_propagation_total", propagated="false") == 1


def test_result_went_through_the_full_pipeline(db_factory, redis_client) -> None:  # noqa: ANN001
    user, movies, _ = _world(db_factory)
    recomputer, repo = _recomputer(db_factory, redis_client)
    _signal(db_factory, user, movies["conjuro"], "consumo")
    with db_factory.begin() as s:
        s.execute(sa.text("INSERT INTO user_exclusions VALUES (:u, :i, 'consumo', now())"), {"u": user, "i": movies["conjuro"]})
    recomputer.recompute(user, Module.PELICULAS, "miss")
    entry = repo.read_fresh(CFG.config_version, user, Module.PELICULAS)
    ids = [i.item_id for i in entry.items]
    assert movies["conjuro"] not in ids  # exclusión
    assert movies["adulto"] not in ids  # edad (+18 para un usuario de ordinal 1)
    assert len(ids) == len(set(ids)) == min(CFG.top_n_max, len(movies) - 2)
    assert entry.max_age_ordinal == 1 and entry.config_version == CFG.config_version
    assert [i.rank for i in entry.items] == list(range(1, len(ids) + 1))


def test_persists_module_and_general_profiles(db_factory, redis_client) -> None:  # noqa: ANN001
    user, movies, _ = _world(db_factory)
    recomputer, _ = _recomputer(db_factory, redis_client)
    recomputer.recompute(user, Module.PELICULAS, "declaration")
    with db_factory() as s:
        scopes = set(s.execute(sa.text("SELECT scope::text FROM user_profiles WHERE user_id = :u"), {"u": user}).scalars())
    assert scopes == {"peliculas", "general"}  # el perfil de juegos no se toca: su contador (RD-104) no se reinicia


def test_reprocessing_produces_identical_top_n(db_factory, redis_client) -> None:  # noqa: ANN001
    """SC-005 / SC-021: misma entrada y misma configuración ⟹ mismos ítems, orden y scores."""
    user, movies, _ = _world(db_factory)
    recomputer, repo = _recomputer(db_factory, redis_client)
    _signal(db_factory, user, movies["hereditary"], "like")
    recomputer.recompute(user, Module.PELICULAS, "miss")
    first = repo.read_fresh(CFG.config_version, user, Module.PELICULAS)
    recomputer.recompute(user, Module.PELICULAS, "miss")
    second = repo.read_fresh(CFG.config_version, user, Module.PELICULAS)
    assert [(i.item_id, i.rank, i.score) for i in first.items] == [(i.item_id, i.rank, i.score) for i in second.items]


def test_cold_start_cross_module_gives_non_trivial_games(db_factory, redis_client) -> None:  # noqa: ANN001
    """SC-010: actividad solo en películas y declaración en juegos ⟹ top-N de juegos no vacío y afín."""
    user, movies, games = _world(db_factory)
    recomputer, repo = _recomputer(db_factory, redis_client)
    for name in ("conjuro", "hereditary"):
        _signal(db_factory, user, movies[name], "like")
    recomputer.recompute(user, Module.JUEGOS, "miss")
    entry = repo.read_fresh(CFG.config_version, user, Module.JUEGOS)
    assert entry is not None and entry.items
    ranked = [i.item_id for i in entry.items]
    assert ranked.index(games["re"]) < ranked.index(games["deportes"])


def test_suppressed_user_result_is_never_written(db_factory, redis_client) -> None:  # noqa: ANN001
    """FR-092a: la marca se consulta inmediatamente antes de escribir."""
    user, _, _ = _world(db_factory)
    with db_factory.begin() as s:
        s.execute(sa.text("INSERT INTO user_suppressions (user_id, requested_at, state) VALUES (:u, now(), 'in_progress')"), {"u": user})
    recomputer, repo = _recomputer(db_factory, redis_client)
    outcome = recomputer.recompute(user, Module.PELICULAS, "miss")
    assert outcome.status == "aborted_suppressed"
    assert repo.read_fresh(CFG.config_version, user, Module.PELICULAS) is None


def test_undeclared_module_is_not_computed(db_factory, redis_client) -> None:  # noqa: ANN001
    """FR-082: no existe un módulo activo para un usuario sin declaración."""
    with db_factory.begin() as s:
        seed.item(s, "juegos", ["rpg"])
        user = seed.user(s)
        seed.vectorize_all(s)
    recomputer, repo = _recomputer(db_factory, redis_client)
    assert recomputer.recompute(user, Module.JUEGOS, "miss").status == "skipped_undeclared"
    assert repo.read_fresh(CFG.config_version, user, Module.JUEGOS) is None


def test_modules_are_independent_units(db_factory, redis_client, monkeypatch) -> None:  # noqa: ANN001
    """FR-067: un fallo del opuesto no revierte el principal ya persistido."""
    user, movies, _ = _world(db_factory)
    recomputer, repo = _recomputer(db_factory, redis_client)
    original = recomputer.recompute

    def failing(user_id, module, reason):  # noqa: ANN001, ANN202
        if module is Module.JUEGOS:
            raise RuntimeError("fallo transitorio en el opuesto")
        return original(user_id, module, reason)

    monkeypatch.setattr(recomputer, "recompute", failing)
    _signal(db_factory, user, movies["conjuro"], "like")
    with pytest.raises(RuntimeError):
        recomputer.on_signal(_event(user, movies["conjuro"], Module.PELICULAS))
    assert repo.read_fresh(CFG.config_version, user, Module.PELICULAS) is not None


def test_recomputes_are_measured(db_factory, redis_client) -> None:  # noqa: ANN001
    user, _, _ = _world(db_factory)
    metrics = Metrics()
    recomputer, _ = _recomputer(db_factory, redis_client, metrics)
    recomputer.recompute(user, Module.PELICULAS, "miss")
    assert metrics.value("reco_recompute_total", status="written", module="peliculas") == 1
    assert metrics.value("reco_recompute_duration_seconds", module="peliculas") == 1
