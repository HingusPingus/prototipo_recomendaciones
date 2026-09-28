"""T017 — batería exhaustiva de invariantes: los 34 de data-model.md §6, cada uno con su evidencia.

Estructura:
- `EVIDENCE` asigna cada invariante al test que lo verifica. Un meta-test falla si §6 declara un
  invariante sin evidencia o si la evidencia referenciada no existe: la cobertura no se supone.
- Los invariantes que no tenían test propio se verifican acá.
- `test_every_result_type_respects_age_and_exclusion` recorre los cinco `result_type` (FR-055).

Poder de detección: mutar el filtro de edad (`engine/postprocess._age_stage` o la guarda del request
path) hace fallar esta suite; ver el mensaje de commit de T017.
"""

from __future__ import annotations

import ast
import json
import re
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pytest
import sqlalchemy as sa
from hypothesis import given
from hypothesis import strategies as st

import recomendaciones
from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
from recomendaciones.engine.age import age_on, derive_max_age_ordinal
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module, ResultType
from recomendaciones.shared.errors import StaleAgeScale
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository

ROOT = Path(__file__).resolve().parents[2]
CFG = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")
SRC = Path(recomendaciones.__file__).parent

EVIDENCE: dict[str, str] = {
    "DI-1": "tests/integration/test_migrations.py::test_item_without_age_rating_gets_most_restrictive_default",
    "DI-2": "tests/integration/test_migrations.py::test_user_ingest_constraints",
    "DI-2a'": "tests/invariants/test_data_invariants.py::test_di_2a_ordinal_matches_birth_date",
    "DI-2b": "tests/invariants/test_data_invariants.py::test_di_2b_no_stored_or_served_result_exceeds_permission",
    "DI-2c": "tests/integration/test_sync_idempotent.py::test_birth_date_correction_rederives_and_invalidates_in_the_same_act",
    "DI-2d": "tests/invariants/test_age_filter.py::test_filter_has_no_parameter_to_disable_it",
    "DI-2e": "tests/invariants/test_data_invariants.py::test_di_2e_user_with_incompatible_scale_is_not_evaluated",
    "DI-3": "tests/integration/test_propagation.py::test_result_went_through_the_full_pipeline",
    "DI-4": "tests/invariants/test_data_invariants.py::test_di_4_stored_config_versions_exist",
    "DI-5": "tests/unit/test_cache_keys.py::test_keys_cannot_be_built_without_a_valid_module",
    "DI-6": "tests/integration/test_idempotency.py::test_same_event_ten_times_processes_once",
    "DI-7": "tests/integration/test_migrations.py::test_at_most_one_active_config",
    "DI-8": "tests/unit/test_vocabulary.py::test_comparing_vectors_of_different_versions_raises",
    "DI-9": "tests/invariants/test_data_invariants.py::test_di_9_request_path_never_calls_api_general",
    "DI-10": "tests/invariants/test_data_invariants.py::test_di_10_retired_item_is_unreachable_by_all_three_paths",
    "DI-11": "tests/invariants/test_data_invariants.py::test_di_11_retirement_keeps_signals_and_profiles",
    "DI-12": "tests/integration/test_fallback_batch.py::test_only_live_items_and_only_active_config_counts",
    "DI-13": "tests/invariants/test_data_invariants.py::test_di_13_single_writer_per_table",
    "DI-14": "tests/integration/test_vocab_transition.py::test_versions_are_identified_by_content",
    "DI-15": "tests/integration/test_tag_modules.py::test_retiring_the_last_item_of_a_module_removes_the_tag_from_it",
    "DI-16": "tests/invariants/test_data_invariants.py::test_di_16_tag_with_assignments_cannot_be_deleted",
    "DI-17": "tests/integration/test_vocab_transition.py::test_new_vocabulary_is_fully_vectorized_before_activation",
    "DI-18": "tests/invariants/test_data_invariants.py::test_di_18_vector_must_reference_existing_version",
    "DI-19": "tests/invariants/test_data_invariants.py::test_di_19_persisted_vectors_are_l2_normalized",
    "DI-20": "tests/integration/test_exclusion_resolver.py::test_consumo_exclusion_survives_purge_of_its_signal",
    "DI-21": "tests/integration/test_event_signals.py::test_interaction_that_arrived_first_by_sync_is_not_duplicated",
    "DI-22": "tests/integration/test_exclusion_resolver.py::test_same_timestamp_tie_breaks_by_id",
    "DI-23": "tests/invariants/test_data_invariants.py::test_di_23_incomparable_scale_is_503_never_200",
    "DI-24": "tests/integration/test_migrations.py::test_config_immutability_trigger",
    "DI-25": "tests/unit/test_cache_keys.py::test_ttls_come_from_settings_and_retired_window_derives_from_stale",
    "DI-26": "tests/integration/test_migrations.py::test_item_popularity_composite_pk_and_checks",
    "DI-27": "tests/integration/test_popularidad.py::test_promotion_is_recorded_once_and_never_revoked",
    "DI-28": "tests/invariants/test_data_invariants.py::test_di_28_declared_minimum_audit",
    "DI-29": "tests/integration/test_sync_idempotent.py::test_suppressed_user_is_never_rematerialized",
}


def _declared_invariants() -> set[str]:
    text = (ROOT / "specs" / "001-recomendaciones-precomputadas" / "data-model.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| \*\*(DI-[0-9a-z']+)\*\*", text, re.MULTILINE))


def _test_exists(node_id: str) -> bool:
    path, _, name = node_id.partition("::")
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name for n in ast.walk(tree))


def test_every_invariant_of_section_6_has_existing_evidence() -> None:
    declared = _declared_invariants()
    assert len(declared) == 34
    assert declared == set(EVIDENCE), f"sin evidencia: {declared - set(EVIDENCE)}; sobrantes: {set(EVIDENCE) - declared}"
    missing = [f"{di} → {node}" for di, node in EVIDENCE.items() if not _test_exists(node)]
    assert not missing, missing


# --- DI-2a' ---------------------------------------------------------------------------------------


@given(st.dates(min_value=date(1920, 1, 1), max_value=date(2026, 9, 28)))
def test_di_2a_ordinal_matches_birth_date(birth: date) -> None:
    today = date(2026, 9, 28)
    ordinal = derive_max_age_ordinal(birth, today, CFG)
    age = age_on(birth, today)
    allowed = [lvl.ordinal for lvl in CFG.age_rating_catalog if lvl.min_age <= age]
    assert ordinal == max(allowed)
    # valores límite: exactamente la edad mínima, un día antes y un día después
    for level in CFG.age_rating_catalog:
        if level.min_age == 0:
            continue
        exact = date(today.year - level.min_age, today.month, today.day)
        assert derive_max_age_ordinal(exact, today, CFG) >= level.ordinal
        assert derive_max_age_ordinal(date.fromordinal(exact.toordinal() + 1), today, CFG) < level.ordinal


# --- mundo compartido para los invariantes de extremo a extremo ----------------------------------


def _world(db_factory):  # noqa: ANN001, ANN202
    from tests.integration import seed

    with db_factory.begin() as s:
        items = {
            "atp": seed.item(s, "peliculas", ["horror", "drama"]),
            "trece": seed.item(s, "peliculas", ["horror", "misterio"], rating="+13", ordinal=1),
            "adulto": seed.item(s, "peliculas", ["horror", "thriller"], rating="+18", ordinal=2),
            "comedia": seed.item(s, "peliculas", ["comedia", "familiar"]),
            "drama": seed.item(s, "peliculas", ["drama", "romance"]),
            "juego": seed.item(s, "juegos", ["horror", "survival"]),
        }
        minor = seed.user(s, birth_date=date(2014, 1, 1), max_age_ordinal=0)
        adult = seed.user(s)
        for user in (minor, adult):
            seed.declare(s, user, "peliculas", ["horror", "drama", "misterio", "comedia", "romance"])
        seed.vectorize_all(s)
    return items, minor, adult


def _recomputer(db_factory, redis_client):  # noqa: ANN001, ANN202
    from recomendaciones.worker.handler import Recomputer

    repo = RecommendationRepository(CacheClient(redis_client), ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)
    return Recomputer(db_factory, repo, CFG, Metrics()), repo


def _read_service(db_factory, redis_client, compatible: frozenset[str] | None = None):  # noqa: ANN001, ANN202
    from recomendaciones.api.services.read_service import ReadService
    from recomendaciones.storage.cache.filters import FiltersCache, RetiredCache
    from recomendaciones.storage.cache.recompute import RecomputeStream
    from recomendaciones.storage.db.filters_source import DbFiltersSource

    cache = CacheClient(redis_client)
    source = DbFiltersSource(db_factory)
    return ReadService(
        repository=RecommendationRepository(cache, ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600),
        filters=FiltersCache(cache, source, 3_600),
        retired=RetiredCache(cache, source, 3_600, 8 * 86_400),
        signaler=RecomputeStream(cache, maxlen=1_000, ttl_suppress=300),
        active_version=CFG.config_version,
        readable_versions=(),
        age_compatible_versions=compatible or frozenset({CFG.config_version}),
    )


def _ordinals(db_factory) -> dict[uuid.UUID, int]:  # noqa: ANN001
    with db_factory() as s:
        return dict(s.execute(sa.text("SELECT id, min_age_ordinal FROM items")).all())


def test_di_2b_no_stored_or_served_result_exceeds_permission(db_factory, redis_client) -> None:  # noqa: ANN001
    items, minor, _ = _world(db_factory)
    recomputer, repo = _recomputer(db_factory, redis_client)
    recomputer.recompute(minor, Module.PELICULAS, "miss")
    stored = repo.read_fresh(CFG.config_version, minor, Module.PELICULAS)
    ordinals = _ordinals(db_factory)
    assert stored.items and all(ordinals[i.item_id] <= 0 for i in stored.items)  # almacenado
    served = _read_service(db_factory, redis_client).read(minor, Module.PELICULAS, top_n=10)
    assert all(ordinals[i.item_id] <= 0 for i in served.items)  # servido


def test_di_2e_user_with_incompatible_scale_is_not_evaluated(db_factory, redis_client) -> None:  # noqa: ANN001
    items, minor, _ = _world(db_factory)
    with db_factory.begin() as s:
        s.execute(sa.text("INSERT INTO engine_config_versions VALUES ('sha256:otra-escala', CAST(:p AS jsonb), now(), now())"),
                  {"p": '{"age_rating_catalog": [{"rating": "ATP", "ordinal": 0, "min_age": 0}]}'})
        s.execute(sa.text("UPDATE users SET age_config_version = 'sha256:otra-escala' WHERE id = :u"), {"u": minor})
    recomputer, repo = _recomputer(db_factory, redis_client)
    assert recomputer.recompute(minor, Module.PELICULAS, "miss").status == "skipped_incompatible_age"
    assert repo.read_fresh(CFG.config_version, minor, Module.PELICULAS) is None


def test_di_4_stored_config_versions_exist(db_factory, redis_client) -> None:  # noqa: ANN001
    items, minor, adult = _world(db_factory)
    recomputer, _ = _recomputer(db_factory, redis_client)
    for user in (minor, adult):
        recomputer.recompute(user, Module.PELICULAS, "miss")
    stored = {json.loads(redis_client.get(k))["config_version"] for k in redis_client.keys("reco:*")}
    with db_factory() as s:
        known = set(s.execute(sa.text("SELECT config_version FROM engine_config_versions")).scalars())
    assert stored and stored <= known


def test_di_9_request_path_never_calls_api_general() -> None:
    """Edad y exclusión se resuelven solo con datos locales: la API no alcanza clientes HTTP salientes."""
    from tests.unit.test_architecture import PKG, Tree

    tree = Tree.scan(SRC, PKG)
    for module in [m for m in tree.imports if m.startswith(f"{PKG}.api")]:
        reach = tree.reachable(module)
        assert not [t for t in reach if t.startswith(f"{PKG}.transformer")], module
        assert not [i for t in reach for i in tree.imports.get(t, ()) if i.split(".")[0] in ("httpx", "aio_pika")], module


def test_di_10_retired_item_is_unreachable_by_all_three_paths(db_factory, redis_client) -> None:  # noqa: ANN001
    """FR-072: selección, respaldo y guarda del request path. Retirar un ítem presente en `reco:*` y en `fallback:*`."""
    from recomendaciones.batch.fallback import FallbackJob

    items, _, adult = _world(db_factory)
    recomputer, repo = _recomputer(db_factory, redis_client)
    recomputer.recompute(adult, Module.PELICULAS, "miss")
    FallbackJob(db_factory, repo, CFG, Metrics()).run()
    victim = items["comedia"]
    assert victim in {i.item_id for i in repo.read_fresh(CFG.config_version, adult, Module.PELICULAS).items}
    assert victim in {i.item_id for i in repo.read_fallback(CFG.config_version, Module.PELICULAS).items}
    with db_factory.begin() as s:
        s.execute(sa.text("UPDATE items SET status = 'retired', retired_at = now() WHERE id = :i"), {"i": victim})
    # 3) guarda del request path sobre el resultado ya precomputado
    served = _read_service(db_factory, redis_client).read(adult, Module.PELICULAS, top_n=10)
    assert victim not in {i.item_id for i in served.items}
    # 1) selección de candidatos en el recálculo
    recomputer.recompute(adult, Module.PELICULAS, "miss")
    assert victim not in {i.item_id for i in repo.read_fresh(CFG.config_version, adult, Module.PELICULAS).items}
    # 2) construcción del respaldo
    FallbackJob(db_factory, repo, CFG, Metrics()).run()
    assert victim not in {i.item_id for i in repo.read_fallback(CFG.config_version, Module.PELICULAS).items}


def test_di_11_retirement_keeps_signals_and_profiles(db_factory, redis_client) -> None:  # noqa: ANN001
    """FR-073: retirar un ítem con señales conserva las filas y no altera el perfil."""
    from tests.integration import seed

    items, _, adult = _world(db_factory)
    with db_factory.begin() as s:
        seed.signal(s, adult, items["drama"], "like")
        seed.vectorize_all(s)  # el ítem con señal tiene vector
    recomputer, _ = _recomputer(db_factory, redis_client)
    recomputer.recompute(adult, Module.PELICULAS, "miss")

    def profile() -> tuple[np.ndarray, int]:
        with db_factory() as s:
            row = s.execute(sa.text("SELECT vector::text, signal_count FROM user_profiles WHERE user_id = :u AND scope = 'peliculas'"), {"u": adult}).one()
        return np.asarray(json.loads(row[0]), dtype=float), row[1]

    before_vec, before_count = profile()
    with db_factory.begin() as s:
        s.execute(sa.text("UPDATE items SET status = 'retired', retired_at = now() WHERE id = :i"), {"i": items["drama"]})
    recomputer.recompute(adult, Module.PELICULAS, "miss")
    after_vec, after_count = profile()
    with db_factory() as s:
        kept = s.execute(sa.text("SELECT count(*) FROM user_signals WHERE item_id = :i"), {"i": items["drama"]}).scalar_one()
    assert kept == 1 and after_count == before_count
    np.testing.assert_allclose(after_vec, before_vec, atol=1e-6)


# Escritor único por tabla (§1.1): módulo(s) de src/ autorizados a escribirla.
WRITERS: dict[str, set[str]] = {
    "User": {"transformer/pipeline.py"},
    "Item": {"transformer/pipeline.py"},
    "Tag": {"transformer/pipeline.py"},
    "ItemTag": {"transformer/pipeline.py"},
    "UserSignal": {"transformer/pipeline.py", "worker/signals.py"},
    "UserExclusion": {"storage/db/exclusions.py"},
    "UserProfile": {"worker/handler.py", "transformer/vocabulary_sync.py"},
    "ItemVector": {"transformer/vocabulary_sync.py"},
    "TagModule": {"transformer/vocabulary_sync.py"},
    "VocabVersion": {"transformer/vocabulary_sync.py"},
    "VocabVersionTag": {"transformer/vocabulary_sync.py"},
    "ItemPopularity": {"batch/popularidad.py"},
    "ItemPromotion": {"batch/popularidad.py"},
    "UserDeclaredTag": {"storage/db/declarations.py"},
    "EngineConfigVersion": {"storage/db/config_registry.py"},
    "ProcessedEvent": {"worker/idempotency.py"},
    "SyncRun": {"transformer/pipeline.py"},
}


def test_di_13_single_writer_per_table() -> None:
    """Cada tabla tiene un único proceso escritor (la purga de perfiles/vectores es del job de vocabulario)."""
    pattern = re.compile(r"\b(?:insert|update)\((\w+)\)|s\.add\((\w+)\(")
    offenders = []
    for path in SRC.rglob("*.py"):
        rel = str(path.relative_to(SRC))
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            model = match.group(1) or match.group(2)
            if model in WRITERS and rel not in WRITERS[model]:
                offenders.append(f"{rel} escribe {model}")
    assert not offenders, offenders


def test_di_16_tag_with_assignments_cannot_be_deleted(db_factory) -> None:  # noqa: ANN001
    from sqlalchemy.exc import IntegrityError

    from tests.integration import seed

    with db_factory.begin() as s:
        seed.item(s, "peliculas", ["horror"])
    with pytest.raises(IntegrityError), db_factory.begin() as s:
        s.execute(sa.text("DELETE FROM tags WHERE name = 'horror'"))


def test_di_18_vector_must_reference_existing_version(db_factory) -> None:  # noqa: ANN001
    from sqlalchemy.exc import IntegrityError

    from tests.integration import seed

    with db_factory.begin() as s:
        item = seed.item(s, "peliculas", ["horror"])
    with pytest.raises(IntegrityError), db_factory.begin() as s:
        s.execute(sa.text("INSERT INTO item_vectors VALUES (:i, 'vocab:inexistente', '[1]', now())"), {"i": item})


def test_di_19_persisted_vectors_are_l2_normalized(db_factory, redis_client) -> None:  # noqa: ANN001
    items, minor, adult = _world(db_factory)
    recomputer, _ = _recomputer(db_factory, redis_client)
    recomputer.recompute(adult, Module.PELICULAS, "miss")
    with db_factory() as s:
        norms = [float(n) for n in s.execute(sa.text("SELECT vector_norm(vector) FROM item_vectors UNION ALL SELECT vector_norm(vector) FROM user_profiles")).scalars()]
    assert norms and all(abs(n - 1.0) < 1e-6 for n in norms)


def test_di_23_incomparable_scale_is_503_never_200(db_factory, redis_client) -> None:  # noqa: ANN001
    items, minor, _ = _world(db_factory)
    with db_factory.begin() as s:
        s.execute(sa.text("INSERT INTO engine_config_versions VALUES ('sha256:otra-escala', '{}', now(), now())"))
        s.execute(sa.text("UPDATE users SET age_config_version = 'sha256:otra-escala' WHERE id = :u"), {"u": minor})
    with pytest.raises(StaleAgeScale) as exc:
        _read_service(db_factory, redis_client).read(minor, Module.PELICULAS, top_n=10)
    assert exc.value.http_status == 503


def test_di_28_declared_minimum_audit(db_factory) -> None:  # noqa: ANN001
    """El único invariante que el esquema no sostiene: lo audita una consulta periódica."""
    from recomendaciones.batch.audits import declared_minimum_violations
    from tests.integration import seed

    with db_factory.begin() as s:
        seed.tags(s, ["a", "b", "c", "d", "e"])
        compliant = seed.user(s)
        seed.declare(s, compliant, "peliculas", ["a", "b", "c", "d", "e"])
        bypass = seed.user(s)
        seed.declare(s, bypass, "juegos", ["a", "b", "c"])  # escrita por fuera de la transacción de declaración
    with db_factory() as s:
        violations = declared_minimum_violations(s, CFG.declared_tags_min)
    assert violations == [(bypass, "juegos", 3)]


def test_every_result_type_respects_age_and_exclusion(db_factory, redis_client) -> None:  # noqa: ANN001
    """FR-055: cada uno de los cinco estados, con un menor y una exclusión, nunca expone lo prohibido."""
    items, minor, _ = _world(db_factory)
    service = _read_service(db_factory, redis_client)
    repo = RecommendationRepository(CacheClient(redis_client), ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)
    with db_factory.begin() as s:
        s.execute(sa.text("INSERT INTO user_exclusions VALUES (:u, :i, 'dislike', now())"), {"u": minor, "i": items["atp"]})
    forbidden = {items["adulto"], items["trece"], items["atp"]}
    everything = tuple(CachedItem(i, n + 1, 1.0, o) for n, (i, o) in enumerate(_ordinals(db_factory).items()))
    now = datetime.now(UTC)
    seen: set[ResultType] = set()

    def check() -> None:
        result = service.read(minor, Module.PELICULAS, top_n=10)
        seen.add(result.result_type)
        assert not {i.item_id for i in result.items} & forbidden

    check()  # empty_pending
    repo.write_fallback(RecommendationEntry(None, Module.PELICULAS, CFG.config_version, "v", None, now, everything))
    check()  # fallback
    repo.write_fallback(RecommendationEntry(None, Module.PELICULAS, CFG.config_version, "v", None, now, tuple(i for i in everything if i.item_id in forbidden)))
    check()  # empty_no_candidates
    redis_client.delete(*redis_client.keys("fallback:*"))
    repo.write_personalized(RecommendationEntry(minor, Module.PELICULAS, CFG.config_version, "v", 0, now, everything))
    check()  # personalized
    redis_client.delete(*redis_client.keys("reco:v*"))
    check()  # personalized_stale
    assert seen == set(ResultType)
