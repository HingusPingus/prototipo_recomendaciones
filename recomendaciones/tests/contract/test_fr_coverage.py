"""T048 — integridad del recorrido FR → tarea (ítem de la Definition of Done).

Falla si un requisito funcional de `spec.md` no aparece en `docs/validation/fr-coverage.md`, si el documento
cita una tarea que `tasks.md` no define, o una evidencia que no existe. Automatiza la **integridad**; que la
tarea cumpla el requisito lo sostienen sus propios tests.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "specs" / "001-recomendaciones-precomputadas"
COVERAGE = ROOT / "docs" / "validation" / "fr-coverage.md"
EVIDENCE = re.compile(r"`((?:tests|src|docs|ops|specs|tools|migrations)/[\w./-]+?)(?:::(\w+))?`")


def _spec_requirements() -> set[str]:
    text = (SPEC_DIR / "spec.md").read_text(encoding="utf-8")
    return set(re.findall(r"^- \*\*(FR-\d{3}[a-z0-9]*)\*\*:", text, flags=re.MULTILINE))


def _defined_tasks() -> set[str]:
    text = (SPEC_DIR / "tasks.md").read_text(encoding="utf-8")
    return set(re.findall(r"^### (T\d{3})\b", text, flags=re.MULTILINE))


def _rows() -> dict[str, list[str]]:
    """FR → celdas, para toda fila de tabla del documento."""
    rows: dict[str, list[str]] = {}
    for line in COVERAGE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| FR-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert cells[0] not in rows, f"fila duplicada: {cells[0]}"
        rows[cells[0]] = cells
    return rows


def test_every_requirement_of_the_spec_has_a_row_with_a_task() -> None:
    requirements, rows = _spec_requirements(), _rows()
    assert len(requirements) == 168, f"se esperaban 168 FR en spec.md, hay {len(requirements)}"  # FR-095b (RD-115)
    assert not sorted(requirements - set(rows)), f"FR sin fila: {sorted(requirements - set(rows))}"
    assert not sorted(set(rows) - requirements), f"filas de FR inexistentes: {sorted(set(rows) - requirements)}"
    assert all(re.search(r"T\d{3}", cells[1]) for cells in rows.values()), "fila sin tarea"


def test_every_cited_task_is_defined_in_tasks_md() -> None:
    defined = _defined_tasks()
    unknown = {t for cells in _rows().values() for t in re.findall(r"T\d{3}", cells[1])} - defined
    assert not unknown, f"tareas inexistentes: {sorted(unknown)}"


def test_every_referenced_evidence_exists() -> None:
    broken = []
    for key, cells in _rows().items():
        for match in EVIDENCE.finditer(" ".join(cells[2:])):
            path, test = match.group(1), match.group(2)
            target = ROOT / path
            if not target.exists():
                broken.append(f"{key}: {path} no existe")
            elif test and not re.search(rf"^(async )?def {test}\(", target.read_text(encoding="utf-8"), flags=re.MULTILINE):
                broken.append(f"{key}: {path}::{test} no existe")
    assert not broken, "\n".join(broken)
