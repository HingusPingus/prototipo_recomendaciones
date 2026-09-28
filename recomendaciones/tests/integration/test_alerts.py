"""T042 — alertas operativas definidas **y probadas induciendo su condición** (Principio VII, §7).

Tres niveles de verificación:
1. `promtool test rules` (herramienta oficial de Prometheus) sobre series inducidas: cada alerta dispara
   con su condición —con las ventanas y `for` de producción— y se apaga al normalizarse.
2. Cadena viva: un Prometheus real raspa el registro del proceso mientras se inducen las tres condiciones
   que la tarea nombra (Redis caído → 503, sincronización congelada → frescura, mensajes inválidos → DLQ);
   cada alerta dispara y, al restablecer, se apaga. Esta variante acorta ventanas y `for` —la semántica
   temporal ya la verificó el nivel 1—: lo que prueba es que las expresiones funcionan sobre las métricas
   que el código emite de verdad.
3. Estructura: umbral justificado por escrito, entrada en el runbook y `exclusions_orphaned_permanent_total`
   sin alerta (FR-068d1).
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ALERTS = ROOT / "ops" / "alerts.yaml"
RUNBOOK = ROOT / "docs" / "runbook.md"
PROMETHEUS = "prom/prometheus:v2.53.1"


def _rules() -> list[dict]:
    return [rule for group in yaml.safe_load(ALERTS.read_text(encoding="utf-8"))["groups"] for rule in group["rules"]]


def _rule(name: str) -> dict:
    return next(r for r in _rules() if r["alert"] == name)


REQUIRED = {
    "CatalogSyncStale", "DeadLetterGrowth", "QueueDepthGrowth", "RedisUnavailable503", "HitRateDrop",
    "ConfigVersionInconsistent", "AgeRefreshStale", "AgeStaleConfigUsers", "ContractViolationBirthDate",
    "ContractViolationRegion", "ContractViolationInteractionId", "SuppressionsUnverified", "RetiredSetLarge",
    "PopularityStale", "CatalogUnrated", "TagProjectionAnomalies", "VectorRecomputeLag", "VocabTransitionStalled",
    "CatalogUnvectorized", "SignalIngestLag", "SignalsPurgeDeferred", "UserDeletionResidualKeys",
    "ExclusionResolveLag", "SyncVolumeDrop", "DeclarableTagsBelowMinimum",
}


def test_every_required_alert_exists() -> None:
    assert REQUIRED <= {r["alert"] for r in _rules()}


def test_every_alert_has_justified_threshold_owner_and_runbook_entry() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    for rule in _rules():
        annotations, labels = rule["annotations"], rule["labels"]
        assert len(annotations.get("justification", "")) > 40, f"umbral sin justificación: {rule['alert']}"
        assert labels.get("severity") in {"critical", "warning", "info"} and labels.get("owner"), rule["alert"]
        anchor = annotations["runbook"].split("#")[-1]
        assert f"### {rule['alert']}" in runbook and anchor == rule["alert"].lower(), rule["alert"]


def test_orphaned_exclusions_have_no_alert() -> None:
    """FR-068d1: medida informativa y sin umbral; configurarle una alerta contradiría el requisito."""
    assert not [r for r in _rules() if "exclusions_orphaned_permanent_total" in r["expr"]]


@pytest.mark.parametrize(
    ("alert", "needle"),
    [
        ("CatalogSyncStale", "93600"),  # > 26 h (§7.7)
        ("AgeRefreshStale", "93600"),  # > 26 h (§7.5.1)
        ("PopularityStale", "93600"),
        ("VectorRecomputeLag", "93600"),
        ("CatalogUnrated", "0.05"),  # > 5 % (§7.7)
        ("CatalogUnvectorized", "0.1"),  # > 10 % (§7.9)
        ("RetiredSetLarge", "10000"),  # > 10 000 (§4.4)
        ("SyncVolumeDrop", "0.9"),  # < 0,9 (§7.12)
        ("ExclusionResolveLag", "3600"),  # > 1 h (§7.12)
        ("SignalIngestLag", "3600"),  # p95 > 1 h en evento (§7.10)
        ("DeclarableTagsBelowMinimum", "5"),  # < declared_tags_min (DEP-10, RD-110)
    ],
)
def test_thresholds_come_from_the_data_model(alert: str, needle: str) -> None:
    assert needle in _rule(alert)["expr"]


# --- Nivel 1: promtool --------------------------------------------------------------------------------

# Por alerta: series inducidas (valores por minuto), minuto en que debe estar disparando, minuto en que
# debe haberse apagado, y etiquetas propias de la serie que la alerta conserva.
SCENARIOS: dict[str, dict] = {
    "CatalogSyncStale": {"series": {"catalog_sync_last_success_timestamp": "-100000x40 2400x40"}, "fire": "30m", "clear": "60m"},
    "DeadLetterGrowth": {"series": {'reco_dlq_messages_total{reason="invalid_payload"}': "0+1x60 60x120"}, "fire": "50m", "clear": "150m"},
    "QueueDepthGrowth": {"series": {'reco_queue_depth{queue="q"}': "5000x40 0x40"}, "fire": "30m", "clear": "60m", "labels": {"queue": "q"}},
    "RedisUnavailable503": {"series": {'reco_unavailable_responses_total{error="cache_unavailable"}': "0+60x30 1800x40"}, "fire": "20m", "clear": "60m"},
    "HitRateDrop": {
        "series": {
            'reco_cache_hits_total{result_type="personalized"}': "0+10x70 700+100x100",
            'reco_cache_hits_total{result_type="fallback"}': "0+90x70 6300x100",
        },
        "fire": "60m",
        "clear": "150m",
    },
    "ConfigVersionInconsistent": {
        "series": {
            'reco_active_config_version{config_version="a",component="api"}': "1x60",
            'reco_active_config_version{config_version="b",component="worker"}': "1x30 _x30",
        },
        "fire": "25m",
        "clear": "50m",
    },
    "AgeRefreshStale": {"series": {"age_refresh_last_success_timestamp": "-100000x40 2400x40"}, "fire": "30m", "clear": "60m"},
    "AgeStaleConfigUsers": {"series": {"age_stale_config_users_total": "10x100 0x60"}, "fire": "90m", "clear": "130m"},
    "ContractViolationBirthDate": {"series": {'contract_violations_total{field="birth_date"}': "0x5 3x100"}, "fire": "10m", "clear": "90m"},
    "ContractViolationRegion": {"series": {'contract_violations_total{field="region"}': "0x5 3x100"}, "fire": "10m", "clear": "90m"},
    "ContractViolationInteractionId": {"series": {'contract_violations_total{field="origin_interaction_id"}': "0x5 3x100"}, "fire": "10m", "clear": "90m"},
    "SuppressionsUnverified": {"series": {"suppressions_unverified_total": "1x60 0x30"}, "fire": "45m", "clear": "75m"},
    "RetiredSetLarge": {"series": {'retired_set_size{module="juegos"}': "20000x100 10x30"}, "fire": "80m", "clear": "120m", "labels": {"module": "juegos"}},
    "PopularityStale": {"series": {"catalog_popularity_last_success_timestamp": "-100000x40 2400x40"}, "fire": "30m", "clear": "60m"},
    "CatalogUnrated": {"series": {"catalog_unrated_ratio": "0.2x100 0x30"}, "fire": "80m", "clear": "120m"},
    "TagProjectionAnomalies": {"series": {'projection_field_anomalies_total{field="tag_name",reason="empty"}': "0x5 4x100"}, "fire": "10m", "clear": "90m"},
    "VectorRecomputeLag": {"series": {"vector_recompute_lag_seconds": "200000x40 0x40"}, "fire": "30m", "clear": "60m"},
    "VocabTransitionStalled": {"series": {"vocab_transition_progress": "0.5x200 1x30"}, "fire": "180m", "clear": "220m"},
    "CatalogUnvectorized": {"series": {"catalog_unvectorized_ratio": "0.5x100 0x30"}, "fire": "80m", "clear": "120m"},
    "SignalIngestLag": {
        "series": {
            'signal_ingest_lag_seconds_bucket{source="evento",le="60"}': "0x40 0+10x40",
            'signal_ingest_lag_seconds_bucket{source="evento",le="3600"}': "0x40 0+10x40",
            'signal_ingest_lag_seconds_bucket{source="evento",le="7200"}': "0+10x40 400+10x40",
            'signal_ingest_lag_seconds_bucket{source="evento",le="+Inf"}': "0+10x40 400+10x40",
        },
        "fire": "35m",
        "clear": "75m",
    },
    "SignalsPurgeDeferred": {"series": {"signals_purge_deferred_total": "0+1x3000 3000x3000"}, "fire": "2900m", "clear": "5900m"},
    "UserDeletionResidualKeys": {"series": {"user_deletion_residual_keys_total": "0x5 2x100"}, "fire": "10m", "clear": "90m"},
    "ExclusionResolveLag": {"series": {"exclusion_resolve_lag_seconds": "7200x30 0x30"}, "fire": "20m", "clear": "50m"},
    "SyncVolumeDrop": {"series": {'sync_volume_delta_ratio{entity="items"}': "0.5x20 1x20"}, "fire": "10m", "clear": "30m", "labels": {"entity": "items"}},
    "DeclarableTagsBelowMinimum": {"series": {'declarable_tags_total{module="peliculas"}': "3x40 8x40"}, "fire": "30m", "clear": "60m", "labels": {"module": "peliculas"}},
}


def _promtool_tests(tmp: Path) -> Path:
    tests = []
    for name, scenario in SCENARIOS.items():
        rule = _rule(name)
        labels = {**rule["labels"], **scenario.get("labels", {})}
        expected = [{"exp_labels": labels, "exp_annotations": rule["annotations"]}]
        tests.append(
            {
                "interval": "1m",
                "input_series": [{"series": s, "values": v} for s, v in scenario["series"].items()],
                "alert_rule_test": [
                    {"eval_time": scenario["fire"], "alertname": name, "exp_alerts": expected},
                    {"eval_time": scenario["clear"], "alertname": name, "exp_alerts": []},
                ],
            }
        )
    (tmp / "alerts.yaml").write_text(ALERTS.read_text(encoding="utf-8"), encoding="utf-8")
    path = tmp / "alerts.test.yaml"
    path.write_text(yaml.safe_dump({"rule_files": ["alerts.yaml"], "evaluation_interval": "1m", "tests": tests}), encoding="utf-8")
    return path


def test_promtool_every_alert_fires_on_its_condition_and_clears(tmp_path: Path) -> None:
    assert set(SCENARIOS) == {r["alert"] for r in _rules()}, "toda alerta necesita su escenario inducido"
    _promtool_tests(tmp_path)
    proc = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "promtool", "-v", f"{tmp_path}:/t", PROMETHEUS, "test", "rules", "/t/alerts.test.yaml"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_promtool_validates_the_rule_file(tmp_path: Path) -> None:
    (tmp_path / "alerts.yaml").write_text(ALERTS.read_text(encoding="utf-8"), encoding="utf-8")
    proc = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "promtool", "-v", f"{tmp_path}:/t", PROMETHEUS, "check", "rules", "/t/alerts.yaml"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --- Nivel 2: cadena viva -------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _live_rules(tmp: Path) -> Path:
    text = ALERTS.read_text(encoding="utf-8")
    text = re.sub(r"\[\d+[smhd]\]", "[20s]", text)
    text = re.sub(r"for: \d+[smhd]", "for: 0s", text)
    path = tmp / "rules.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _alerts(prom_port: int) -> set[str]:
    with urllib.request.urlopen(f"http://127.0.0.1:{prom_port}/api/v1/alerts", timeout=5) as response:
        data = json.loads(response.read())
    return {a["labels"]["alertname"] for a in data["data"]["alerts"] if a["state"] == "firing"}


def _wait(prom_port: int, predicate, timeout: float = 60) -> set[str]:  # noqa: ANN001
    deadline = time.monotonic() + timeout
    current: set[str] = set()
    while time.monotonic() < deadline:
        try:
            current = _alerts(prom_port)
        except OSError:
            current = set()
        if predicate(current):
            return current
        time.sleep(1)
    return current


async def test_live_chain_three_conditions_fire_and_clear(valid_env, db_factory, redis_client, amqp_url, tmp_path) -> None:  # noqa: ANN001
    from prometheus_client import start_http_server
    from fastapi.testclient import TestClient

    from recomendaciones.api.app import build_services, create_app
    from recomendaciones.config.settings import load_settings
    from recomendaciones.storage.cache.client import CacheClient
    from recomendaciones.transformer.freshness import refresh_sync_metrics
    from recomendaciones.worker.consumer import EventConsumer
    from tests.integration.test_retry_dlq import _body, _publish, _topology

    import sqlalchemy as sa

    settings = load_settings()
    closed = _free_port()
    broken = CacheClient.from_url(f"redis://127.0.0.1:{closed}/0", timeout_seconds=0.2)
    services = build_services(settings, db_factory=db_factory, cache=broken)
    metrics = services.metrics
    metrics_port, prom_port = _free_port(), _free_port()
    exporter = start_http_server(metrics_port, addr="127.0.0.1", registry=metrics.registry)
    (tmp_path / "prometheus.yml").write_text(
        yaml.safe_dump(
            {
                "global": {"scrape_interval": "1s", "evaluation_interval": "1s"},
                "rule_files": ["/etc/reco/rules.yaml"],
                "scrape_configs": [{"job_name": "reco", "static_configs": [{"targets": [f"127.0.0.1:{metrics_port}"]}]}],
            }
        )
    )
    _live_rules(tmp_path)
    container = subprocess.run(
        [
            "docker", "run", "-d", "--rm", "--network", "host", "-v", f"{tmp_path}:/etc/reco", PROMETHEUS,
            "--config.file=/etc/reco/prometheus.yml", f"--web.listen-address=127.0.0.1:{prom_port}",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    try:
        # Series de contador inicializadas en 0 y raspadas antes de inducir: sin muestra previa, Prometheus
        # no ve el incremento de una serie que aparece ya con su valor final.
        metrics.inc("reco_unavailable_responses_total", 0, error="cache_unavailable")
        metrics.inc("reco_dlq_messages_total", 0, reason="invalid_payload")
        _wait(prom_port, lambda current: True, timeout=5)
        time.sleep(3)
        headers = {"X-Internal-API-Key": valid_env["RECO_INTERNAL_API_KEY"]}
        # (1) Redis caído ⟹ 503
        with TestClient(create_app(settings, services)) as api:
            for _ in range(40):
                assert api.get(f"/internal/v1/recommendations/{uuid.uuid4()}", params={"module": "peliculas"}, headers=headers).status_code == 503
        # (2) sincronización congelada ⟹ frescura
        with db_factory.begin() as s:
            s.execute(
                sa.text("INSERT INTO sync_runs (started_at, finished_at, status) VALUES (:t, :t, 'success')"),
                {"t": datetime.now(UTC) - timedelta(days=3)},
            )
        with db_factory() as s:
            refresh_sync_metrics(s, metrics)
        # (3) mensajes inválidos ⟹ DLQ
        topology = _topology()
        consumer = EventConsumer(amqp_url, topology, lambda e: "ok", on_dead_letter=lambda r: metrics.inc("reco_dlq_messages_total", reason=r))
        await consumer.start()
        for _ in range(10):
            broken_event = _body()
            broken_event.pop("signal_type")
            await _publish(amqp_url, topology, broken_event)
        for _ in range(50):
            if metrics.value("reco_dlq_messages_total", reason="invalid_payload") >= 10:
                break
            time.sleep(0.1)
        await consumer.stop()

        wanted = {"RedisUnavailable503", "CatalogSyncStale", "DeadLetterGrowth"}
        firing = _wait(prom_port, lambda current: wanted <= current)
        assert wanted <= firing, firing

        # Restablecer: frescura al día, sin más 503 ni DLQ ⟹ las alertas se apagan (no quedan pegadas)
        with db_factory.begin() as s:
            s.execute(sa.text("INSERT INTO sync_runs (started_at, finished_at, status) VALUES (now(), now(), 'success')"))
        with db_factory() as s:
            refresh_sync_metrics(s, metrics)
        after = _wait(prom_port, lambda current: not (wanted & current), timeout=90)
        assert not (wanted & after), after
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        exporter[0].shutdown() if isinstance(exporter, tuple) else None
