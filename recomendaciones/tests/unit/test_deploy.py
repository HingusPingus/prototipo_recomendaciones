"""Despliegue continuo a Dokploy (docs/despliegue.md): solo lo que pasó los gates de `main` llega al servidor.

El flujo es CI → imagen en ghcr.io → Dokploy. Estos tests fijan las garantías que no se ven en un deploy que sale
bien: que nada se publica sin el CI en verde (Principio VI: un contract test roto bloquea el deploy), que solo
despliega `main` (Principio V: la configuración del motor llega a producción con aprobación) y que el compose del
servidor no versiona credenciales ni expone servicios a la red (Principio IV, FR-008).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT.parent / ".github" / "workflows" / "deploy.yml"
COMPOSE = ROOT / "docker-compose.dokploy.yml"
LOCAL_COMPOSE = ROOT / "docker-compose.yml"
IMAGE = "ghcr.io/hinguspingus/recomendaciones"
APP_SERVICES = {"migraciones", "api-general-simulada", "preparacion", "api", "worker", "semilla-declaraciones"}
DATA_SERVICES = {"postgres", "redis", "rabbitmq"}


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _steps(job: dict) -> list[dict]:
    return job["steps"]


# --- Workflow ---------------------------------------------------------------------------------------


def test_deploy_runs_only_after_ci_finishes_on_main() -> None:
    triggers = _workflow()[True]  # YAML 1.1 lee la clave `on` como booleano
    assert set(triggers) == {"workflow_run"}, "ni push ni pull_request: el único disparador es el CI terminado"
    run = triggers["workflow_run"]
    assert run["workflows"] == ["ci"] and run["types"] == ["completed"] and run["branches"] == ["main"]


def test_nothing_is_built_unless_the_ci_gates_passed_on_a_push() -> None:
    image = _workflow()["jobs"]["image"]
    condition = image["if"]
    assert "github.event.workflow_run.conclusion == 'success'" in condition
    assert "github.event.workflow_run.event == 'push'" in condition  # nunca el código de un PR


def test_the_image_is_built_from_the_commit_that_passed_ci() -> None:
    checkout = next(s for s in _steps(_workflow()["jobs"]["image"]) if s.get("uses", "").startswith("actions/checkout"))
    assert checkout["with"]["ref"] == "${{ github.event.workflow_run.head_sha }}"


def test_the_image_goes_to_ghcr_with_the_branch_and_commit_tags() -> None:
    workflow = _workflow()
    assert workflow["env"]["IMAGE"] == IMAGE
    build = next(s for s in _steps(workflow["jobs"]["image"]) if s.get("uses", "").startswith("docker/build-push-action"))
    assert build["with"]["context"] == "recomendaciones" and build["with"]["push"] is True
    tags = build["with"]["tags"]
    assert "${{ env.IMAGE }}:main" in tags and "${{ env.IMAGE }}:sha-${{ github.event.workflow_run.head_sha }}" in tags


def test_permissions_are_the_minimum_to_publish_the_image() -> None:
    assert _workflow()["permissions"] == {"contents": "read", "packages": "write"}


def test_dokploy_deploys_after_the_image_and_only_with_secrets() -> None:
    dokploy = _workflow()["jobs"]["dokploy"]
    assert dokploy["needs"] == "image"
    command = "\n".join(s.get("run", "") for s in _steps(dokploy))
    assert "/api/compose.deploy" in command and "x-api-key" in command
    env = {k: v for s in _steps(dokploy) for k, v in (s.get("env") or {}).items()}
    assert env == {
        "DOKPLOY_URL": "${{ secrets.DOKPLOY_URL }}",
        "DOKPLOY_API_KEY": "${{ secrets.DOKPLOY_API_KEY }}",
        "DOKPLOY_COMPOSE_ID": "${{ secrets.DOKPLOY_COMPOSE_ID }}",
        "SHA": "${{ github.event.workflow_run.head_sha }}",
    }


def test_deploys_never_overlap_or_cancel_each_other() -> None:
    concurrency = _workflow()["concurrency"]
    assert concurrency["cancel-in-progress"] is False  # un deploy a medias es peor que uno demorado


# --- Compose del servidor -----------------------------------------------------------------------------


def test_the_server_runs_the_same_services_as_the_local_stack() -> None:
    local = set(yaml.safe_load(LOCAL_COMPOSE.read_text(encoding="utf-8"))["services"])
    assert set(_compose()["services"]) == local == APP_SERVICES | DATA_SERVICES


def test_app_services_pull_the_published_image_instead_of_building() -> None:
    for name in APP_SERVICES:
        service = _compose()["services"][name]
        assert "build" not in service, name
        assert service["image"] == f"{IMAGE}:${{RECO_IMAGE_TAG:-main}}", name
        assert service["pull_policy"] == "always", f"{name}: con un tag fijo, sin esto se reusa la imagen vieja"


def test_no_credential_is_versioned() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    for variable in ("RECO_INTERNAL_API_KEY", "POSTGRES_PASSWORD", "RABBITMQ_PASSWORD", "RECO_ENVIRONMENT"):
        assert re.search(rf"\$\{{{variable}:\?[^}}]+\}}", text), f"{variable} tiene que ser obligatoria y venir del entorno"
    assert "demo.clave-local-solo-para-la-demo" not in text
    assert not re.search(r"(PASSWORD|_PASS|API_KEY):\s+(?!\$\{)", text), "una credencial literal en el compose"


def test_nothing_is_published_beyond_the_server_loopback() -> None:
    for name, service in _compose()["services"].items():
        for port in service.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name}: {port} quedaría expuesto a la red (FR-008)"


def test_data_survives_a_redeploy() -> None:
    services = _compose()["services"]
    for name in DATA_SERVICES - {"redis"}:  # Redis es caché: se reconstruye desde Postgres (INV-2)
        assert services[name].get("volumes"), f"{name}: sin volumen, cada deploy borraría los datos"
