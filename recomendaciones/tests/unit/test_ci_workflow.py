"""T045 — el pipeline de CI tiene los gates exigidos y ninguno puede saltarse desde un PR."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"
GATES = {"lint", "config", "architecture", "unit-coverage", "mutation", "invariants", "contract", "critical", "integration"}


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _commands(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


def test_workflow_lives_at_the_git_root_and_runs_on_pull_requests() -> None:
    assert WORKFLOW.exists(), "GitHub Actions solo lee .github/workflows/ desde la raíz del repositorio"
    triggers = _workflow()[True]  # YAML 1.1 lee la clave `on` como booleano
    assert "pull_request" in triggers
    assert {"main", "dev"} <= set(triggers["push"]["branches"])  # dev integra; main recibe lo cerrado


def test_every_required_gate_exists_and_the_aggregate_needs_all_of_them() -> None:
    jobs = _workflow()["jobs"]
    assert set(jobs) == GATES | {"gates"}
    assert set(jobs["gates"]["needs"]) == GATES


def test_no_gate_can_be_skipped_or_softened() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "continue-on-error" not in text
    for name, job in _workflow()["jobs"].items():
        if name != "gates":
            assert "if" not in job, f"{name}: una condición en el job permitiría saltarlo"
        for step in job["steps"]:
            assert "if" not in step and "continue-on-error" not in step, name
            assert "|| true" not in step.get("run", ""), name


def test_the_aggregate_fails_unless_every_gate_succeeded() -> None:
    gates = _workflow()["jobs"]["gates"]
    assert gates["if"] == "${{ always() }}"  # un check requerido «skipped» cuenta como aprobado
    assert 'x == "success"' in _commands(gates)


def test_each_gate_runs_what_t045_requires() -> None:
    jobs = _workflow()["jobs"]
    assert "ruff check src tests" in _commands(jobs["lint"])  # T067: linters en CI (constitución)
    assert "load_engine_config" in _commands(jobs["config"])
    assert "tests/unit/test_architecture.py" in _commands(jobs["architecture"])
    assert "--cov=recomendaciones.engine" in _commands(jobs["unit-coverage"]) and "--cov-fail-under=" in _commands(jobs["unit-coverage"])
    assert "tools/mutation_postprocess.py" in _commands(jobs["mutation"])
    assert "tests/invariants" in _commands(jobs["invariants"])
    assert "tests/contract" in _commands(jobs["contract"])
    assert "tests/integration/test_critical_scenarios.py" in _commands(jobs["critical"])


def test_integration_runs_against_real_containers_not_service_mocks() -> None:
    for name, job in _workflow()["jobs"].items():
        assert "services" not in job, f"{name}: la infraestructura la levanta testcontainers, no services del runner"
