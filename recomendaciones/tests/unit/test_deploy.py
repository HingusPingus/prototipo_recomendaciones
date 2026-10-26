"""Despliegue continuo a Dokploy (docs/despliegue.md): solo lo que pasó los gates de `main` llega al servidor.

El flujo es CI → imagen en ghcr.io → Dokploy. Estos tests fijan las garantías que no se ven en un deploy que sale
bien: que nada se publica sin el CI en verde (Principio VI: un contract test roto bloquea el deploy) y que solo
despliega `main` (Principio V: la configuración del motor llega a producción con aprobación). El servidor corre
Applications de Dokploy que descargan esa imagen (RD-124): su configuración vive en Dokploy, no en el repositorio.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT.parent / ".github" / "workflows" / "deploy.yml"
IMAGE = "ghcr.io/hinguspingus/recomendaciones"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


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
    assert "/api/application.deploy" in command and "x-api-key" in command
    env = {k: v for s in _steps(dokploy) for k, v in (s.get("env") or {}).items()}
    assert env == {
        "DOKPLOY_URL": "${{ secrets.DOKPLOY_URL }}",
        "DOKPLOY_API_KEY": "${{ secrets.DOKPLOY_API_KEY }}",
        "DOKPLOY_API_APPLICATION_ID": "${{ secrets.DOKPLOY_API_APPLICATION_ID }}",
        "DOKPLOY_WORKER_APPLICATION_ID": "${{ secrets.DOKPLOY_WORKER_APPLICATION_ID }}",
    }


def test_the_api_is_redeployed_before_the_worker() -> None:
    # La Application de la API aplica las migraciones al arrancar; el worker falla si las tablas no existen.
    command = "\n".join(s.get("run", "") for s in _steps(_workflow()["jobs"]["dokploy"]))
    assert command.index("DOKPLOY_API_APPLICATION_ID") < command.index("DOKPLOY_WORKER_APPLICATION_ID")


def test_deploys_never_overlap_or_cancel_each_other() -> None:
    concurrency = _workflow()["concurrency"]
    assert concurrency["cancel-in-progress"] is False  # un deploy a medias es peor que uno demorado


# --- Servidor -------------------------------------------------------------------------------------------


def test_the_server_compose_is_gone_because_dokploy_runs_applications() -> None:
    assert not (ROOT / "docker-compose.dokploy.yml").exists(), "el servidor corre Applications de Dokploy (RD-124)"
