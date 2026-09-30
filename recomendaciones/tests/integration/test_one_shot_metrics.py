"""T066 — métricas de los procesos de una corrida (`reco-transformer`, `reco-batch`) observables desde el worker.

Esos procesos terminan al final de la corrida y no exponen un servidor de métricas: lo que fijan se perdía y
las alertas que dependen de ello no podían dispararse (`docs/validation/alert-threshold-review.md` §2). Cada
corrida deja su resultado en `process_runs` y el worker lo re-expone (Constitución VII, FR-044, FR-068d1).

Cada test **corre el proceso real** por su entrypoint (`run_once`, `run_job`) sobre el estado que induce la
condición, y verifica sobre lo que el worker expone —sin inyectar la serie a mano— que la condición de la
alerta se cumple. La lógica de cada regla (umbral, `for`, `increase`) la sigue verificando promtool en
`tests/integration/test_alerts.py`. `VectorRecomputeLag` se redefine en T070 y su caso vive allí.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa

from recomendaciones.batch.runtime import run_job
from recomendaciones.config.settings import load_settings
from recomendaciones.observability.metrics import Metrics
from recomendaciones.transformer.runtime import run_once
from recomendaciones.transformer.vocabulary_sync import VocabularySync
from recomendaciones.worker.process_metrics import ProcessMetricsState, refresh_process_metrics
from tests.integration import seed
from tests.support.api_general_double import ApiGeneralDouble

TAGS = ["accion", "drama", "terror", "comedia", "suspenso", "aventura"]


@pytest.fixture
def env(valid_env, monkeypatch, db_factory, redis_url) -> dict[str, str]:  # noqa: ANN001
    monkeypatch.setenv("RECO_DATABASE_URL", db_factory.url)
    monkeypatch.setenv("RECO_REDIS_URL", redis_url)
    monkeypatch.setenv("RECO_RETRY_MAX_ATTEMPTS", "1")  # un api-general caído falla sin esperar backoff
    return valid_env


def _double(env: dict[str, str], n_items: int = 12, tags: list[str] = TAGS) -> ApiGeneralDouble:
    double = ApiGeneralDouble(api_key=env["RECO_INTERNAL_API_KEY"], page_size=100)
    double.add_user(birth_date=date(1990, 1, 1), region="AR")
    for i in range(n_items):
        double.add_item("peliculas", [tags[i % len(tags)], tags[(i + 1) % len(tags)]])
    return double


def _exposed(db_factory, state: ProcessMetricsState | None = None) -> Metrics:  # noqa: ANN001
    """Lo que el worker expone tras un refresco, en un registro nuevo como el de un worker recién arrancado."""
    metrics = Metrics()
    with db_factory() as s:
        refresh_process_metrics(s, metrics, state or ProcessMetricsState())
    return metrics


def _runs(db_factory) -> list[tuple]:  # noqa: ANN001
    with db_factory() as s:
        return [tuple(r) for r in s.execute(sa.text("SELECT component, status, failure_reason, details FROM process_runs ORDER BY id"))]


# --- Registro de cada corrida (FR-044: éxito/falla por corrida) -------------------------------------------


def test_every_one_shot_run_is_recorded_even_when_it_fails(env, db_factory) -> None:  # noqa: ANN001
    settings = load_settings()
    down = _double(env)
    down.down = True
    assert run_once(settings, transport=down.transport()) == 1
    assert run_job(settings, ["popularity"]) == 0
    runs = _runs(db_factory)
    assert [(c, st) for c, st, _r, _d in runs] == [("transformer", "failed"), ("batch:popularity", "success")]
    assert runs[0][2]  # la falla deja su motivo


def test_transformer_duration_is_exposed(env, db_factory) -> None:  # noqa: ANN001
    assert run_once(load_settings(), transport=_double(env).transport()) == 0
    assert _exposed(db_factory).value("reco_sync_duration_seconds") >= 1  # _count del histograma (FR-044)


def test_purge_run_persists_the_retention_in_force(env, db_factory) -> None:  # noqa: ANN001
    """RD-54: la constancia de la retención vigente deja de depender de la retención de los logs."""
    assert run_job(load_settings(), ["purge-signals"]) == 0
    (_c, status, _r, details), = _runs(db_factory)
    assert status == "success" and details["signal_retention_days"] == 730
    exposed = _exposed(db_factory)
    assert exposed.value("exclusions_orphaned_permanent_total") >= 0  # FR-068d1: expuesta, no NaN


# --- Las alertas de §2 disparan sobre lo que el worker expone ----------------------------------------------


def test_contract_violation_birth_date(env, db_factory) -> None:  # noqa: ANN001
    double = _double(env)
    double.add_user(birth_date=None)
    run_once(load_settings(), transport=double.transport())
    assert _exposed(db_factory).value("contract_violations_total", field="birth_date") >= 1  # increase(…) > 0


def test_contract_violation_region(env, db_factory) -> None:  # noqa: ANN001
    double = _double(env)
    double.add_user(region=None)
    run_once(load_settings(), transport=double.transport())
    assert _exposed(db_factory).value("contract_violations_total", field="region") >= 1


def test_tag_projection_anomalies(env, db_factory) -> None:  # noqa: ANN001
    double = _double(env)
    double.add_item("peliculas", ["drama", ""])  # nombre de tag vacío (§7.8)
    run_once(load_settings(), transport=double.transport())
    assert _exposed(db_factory).value("projection_field_anomalies_total", field="tag_name", reason="empty") >= 1


def test_sync_volume_drop(env, db_factory) -> None:  # noqa: ANN001
    double = _double(env, n_items=20)
    settings = load_settings()
    assert run_once(settings, transport=double.transport()) == 0
    del double.items[:5]  # el catálogo cae al 75 %
    assert run_once(settings, transport=double.transport()) == 1  # aborta sin marcar retiros
    assert _exposed(db_factory).value("sync_volume_delta_ratio", entity="items") < 0.9


def test_declarable_tags_below_minimum(env, db_factory) -> None:  # noqa: ANN001
    run_once(load_settings(), transport=_double(env, tags=TAGS[:3]).transport())
    assert _exposed(db_factory).value("declarable_tags_total", module="peliculas") < 5


def test_catalog_unvectorized(env, db_factory, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(VocabularySync, "_write_vectors", lambda self, s, version, vectors, only_changed: 0)
    run_once(load_settings(), transport=_double(env).transport())
    assert _exposed(db_factory).value("catalog_unvectorized_ratio") > 0.1


def test_vocab_transition_stalled(env, db_factory, monkeypatch) -> None:  # noqa: ANN001
    def crash(self, s, version, vectors, only_changed):  # noqa: ANN001, ANN202
        raise RuntimeError("vectorización interrumpida")

    monkeypatch.setattr(VocabularySync, "_write_vectors", crash)
    with pytest.raises(RuntimeError):
        run_once(load_settings(), transport=_double(env).transport())
    assert _runs(db_factory)[-1][1] == "failed"
    assert _exposed(db_factory).value("vocab_transition_progress") < 1


def test_popularity_stale(env, db_factory) -> None:  # noqa: ANN001
    before = time.time()
    assert run_job(load_settings(), ["popularity"]) == 0
    stamp = _exposed(db_factory).value("catalog_popularity_last_success_timestamp")
    assert before - 5 <= stamp <= time.time() + 5  # sin corridas nuevas, `time() - stamp` supera 26 h y dispara


def test_age_refresh_stale(env, db_factory) -> None:  # noqa: ANN001
    before = time.time()
    assert run_job(load_settings(), ["age-refresh"]) == 0
    stamp = _exposed(db_factory).value("age_refresh_last_success_timestamp")
    assert before - 5 <= stamp <= time.time() + 5


def test_signals_purge_deferred(env, db_factory) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        user, item = seed.user(s), seed.item(s, "peliculas", ["drama"])
        seed.signal(s, user, item, "consumo", minutes=-800 * 24 * 60)  # más vieja que la retención, sin exclusión
    assert run_job(load_settings(), ["purge-signals"]) == 0
    assert _exposed(db_factory).value("signals_purge_deferred_total") >= 1


# --- Semántica de la re-exposición -------------------------------------------------------------------------


def test_refreshing_again_does_not_count_the_same_run_twice(env, db_factory) -> None:  # noqa: ANN001
    double = _double(env)
    double.add_user(birth_date=None)
    run_once(load_settings(), transport=double.transport())
    metrics, state = Metrics(), ProcessMetricsState()
    for _ in range(3):
        with db_factory() as s:
            refresh_process_metrics(s, metrics, state)
    assert metrics.value("contract_violations_total", field="birth_date") == 1


def test_a_restarted_worker_only_replays_runs_within_the_lookback(env, db_factory) -> None:  # noqa: ANN001
    double = _double(env)
    double.add_user(birth_date=None)
    run_once(load_settings(), transport=double.transport())
    with db_factory.begin() as s:
        s.execute(sa.text("UPDATE process_runs SET finished_at = finished_at - interval '2 hours'"))
    assert _exposed(db_factory).value("contract_violations_total", field="birth_date") == 0  # ya expuesto antes del reinicio
    assert _exposed(db_factory).value("reco_sync_duration_seconds") == 0
    assert run_job(load_settings(), ["popularity"]) == 0
    assert _exposed(db_factory).value("catalog_popularity_last_success_timestamp") > 0  # los gauges no dependen de la ventana


def test_old_runs_are_pruned_but_the_latest_of_each_outcome_survives(env, db_factory) -> None:  # noqa: ANN001
    settings = load_settings()
    assert run_job(settings, ["popularity"]) == 0
    with db_factory.begin() as s:
        s.execute(sa.text("UPDATE process_runs SET started_at = started_at - interval '40 days', finished_at = finished_at - interval '40 days'"))
        s.execute(
            sa.text(
                "INSERT INTO process_runs (component, started_at, finished_at, status, metrics) "
                "SELECT component, started_at - interval '1 day', finished_at - interval '1 day', 'success', '{}'::jsonb FROM process_runs"
            )
        )
    assert run_job(settings, ["popularity"]) == 0
    runs = _runs(db_factory)
    assert len(runs) == 1  # la corrida vieja más reciente también cae: hay una exitosa más nueva
    assert _exposed(db_factory).value("catalog_popularity_last_success_timestamp") > datetime.now(UTC).timestamp() - 60


def test_the_worker_loop_refreshes_process_metrics() -> None:
    """El refresco corre en el mismo ciclo de 30 s que ya re-expone la frescura del catálogo (SC-014)."""
    import inspect

    from recomendaciones.worker import runtime

    assert "refresh_process_metrics" in inspect.getsource(runtime)


def test_process_runs_uses_no_user_data() -> None:
    """La tabla guarda métricas agregadas: ninguna etiqueta de usuario (mismo criterio que el registro)."""
    from recomendaciones.storage.db.models import ProcessRun

    columns = {c.name for c in ProcessRun.__table__.columns}
    assert columns == {"id", "component", "started_at", "finished_at", "status", "failure_reason", "metrics", "details"}
    assert not {"user_id", "item_id"} & columns
