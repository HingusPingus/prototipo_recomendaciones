"""Stack para la integración local con el `api-general` real (docs/integracion-local.md, spec 007 de `api-general`).

Fija lo que hace que la prueba sea de verdad contra el real y no contamine nada: sin el simulado, con la clave del
entorno de prueba tomada del `.env`, con una red compartida que no expone las bases y sin puertos hacia la red.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.integracion.yml"
SHARED = "recome-integracion"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _networks(service: dict) -> set[str]:
    return set(service.get("networks", []))


def test_the_real_api_general_replaces_the_simulated_one() -> None:
    services = _compose()["services"]
    assert "api-general-simulada" not in services and "semilla-declaraciones" not in services
    assert set(services) == {"postgres", "redis", "rabbitmq", "migraciones", "api", "worker", "sincronizacion"}
    text = COMPOSE.read_text(encoding="utf-8")
    assert "http://api-general:8080/api/v1" in text  # servicio `api-general`, context-path `/api/v1` de su compose
    assert "api-general-simulada" not in text


def test_the_service_key_and_broker_credentials_come_from_the_environment() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    for variable in ("RECO_ENVIRONMENT", "RECO_INTERNAL_API_KEY", "RABBITMQ_USER", "RABBITMQ_PASSWORD"):
        assert re.search(rf"\$\{{{variable}:\?[^}}]+\}}", text), f"{variable} tiene que ser obligatoria y venir del .env"
    assert "demo.clave-local-solo-para-la-demo" not in text


def test_only_the_services_api_general_talks_to_share_its_network() -> None:
    compose = _compose()
    assert compose["networks"]["integracion"]["name"] == SHARED  # nombre fijo: su compose lo declara externo
    services = compose["services"]
    for name in ("rabbitmq", "api", "worker", "sincronizacion"):
        assert "integracion" in _networks(services[name]), name
    for name in ("postgres", "redis", "migraciones"):
        # api-general también tiene un servicio `postgres`: en una red compartida el nombre sería ambiguo.
        assert _networks(services[name]) == {"interna"}, name


def test_nothing_is_published_beyond_loopback_and_amqp_stays_inside_docker() -> None:
    for name, service in _compose()["services"].items():
        for port in service.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name}: {port}"
            assert not str(port).endswith(":5672"), "api-general llega a RabbitMQ por la red compartida, no por el host"


def test_the_worker_reports_ready_so_api_general_can_wait_for_it() -> None:
    worker = _compose()["services"]["worker"]
    assert "8081/health/ready" in " ".join(worker["healthcheck"]["test"])


def test_the_sync_runs_only_when_asked_after_api_general_has_data() -> None:
    sync = _compose()["services"]["sincronizacion"]
    assert sync["profiles"] == ["manual"]  # `up` no la arranca: el api-general real todavía no tiene datos
    assert "reco-transformer" in " ".join(sync["command"])
