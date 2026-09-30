"""T069 — la auditoría periódica de DI-28 corre como job de `reco-batch` y se observa.

DI-28 (todo módulo declarado tiene al menos `declared_tags_min` filas **propias**) es el único invariante que el
esquema no sostiene, y `data-model.md` §6 manda que «lo audita una consulta periódica». La consulta existía
(`batch/audits.py`) pero solo la llamaba un test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from recomendaciones.batch.runtime import JOBS, run_job
from recomendaciones.config.settings import load_settings
from recomendaciones.observability.metrics import Metrics
from recomendaciones.worker.process_metrics import ProcessMetricsState, refresh_process_metrics
from tests.integration import seed

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def env(valid_env, monkeypatch, db_factory, redis_url) -> dict[str, str]:  # noqa: ANN001
    monkeypatch.setenv("RECO_DATABASE_URL", db_factory.url)
    monkeypatch.setenv("RECO_REDIS_URL", redis_url)
    return valid_env


def _exposed(db_factory) -> Metrics:  # noqa: ANN001
    metrics = Metrics()
    with db_factory() as s:
        refresh_process_metrics(s, metrics, ProcessMetricsState())
    return metrics


def test_audits_is_a_batch_job() -> None:
    assert "audits" in JOBS


def test_a_declaration_below_the_minimum_is_reported_and_exposed(env, db_factory, caplog) -> None:  # noqa: ANN001
    with db_factory.begin() as s:
        seed.tags(s, ["a", "b", "c", "d", "e"])
        compliant, bypass = seed.user(s), seed.user(s)
        seed.declare(s, compliant, "peliculas", ["a", "b", "c", "d", "e"])
        seed.declare(s, bypass, "juegos", ["a", "b", "c"])  # escrita saltando la transacción del endpoint
    with caplog.at_level("WARNING"):
        assert run_job(load_settings(), ["audits"]) == 0
    assert _exposed(db_factory).value("declared_minimum_violations_total") == 1
    logged = [r for r in caplog.records if getattr(r, "reco_user_id", None) == str(bypass)]
    assert logged and logged[0].reco_module == "juegos"  # user_id y módulo, sin los tags declarados


def test_without_violations_the_metric_is_zero(env, db_factory) -> None:  # noqa: ANN001
    assert run_job(load_settings(), ["audits"]) == 0
    exposed = _exposed(db_factory)
    assert exposed.registry.get_sample_value("declared_minimum_violations_total") == 0.0  # expuesta en 0, no ausente


def test_the_violation_has_an_alert_and_a_runbook_entry() -> None:
    rules = [r for g in yaml.safe_load((ROOT / "ops" / "alerts.yaml").read_text(encoding="utf-8"))["groups"] for r in g["rules"]]
    rule = next(r for r in rules if "declared_minimum_violations_total" in r["expr"])
    assert "> 0" in rule["expr"]
    assert f"### {rule['alert']}" in (ROOT / "docs" / "runbook.md").read_text(encoding="utf-8")
