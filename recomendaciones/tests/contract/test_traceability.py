"""T048 — integridad de la matriz de trazabilidad ítem → evidencia.

Falla si la matriz referencia un test o archivo que no existe, si un ítem de los checklists no aparece, o si
un ítem marcado no tiene evidencia. Automatiza la **integridad**; la suficiencia de la evidencia es revisión
humana y así se declara en el PR de cierre.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GIT_ROOT = ROOT.parent
MATRIX = ROOT / "docs" / "validation" / "traceability-matrix.md"
CHECKLISTS = ROOT / "specs" / "001-recomendaciones-precomputadas" / "checklists"
EVIDENCE = re.compile(r"`((?:tests|src|docs|ops|specs|tools|migrations|\.github)/[\w./-]+?)(?:::(\w+))?`")


def _rows() -> dict[str, list[str]]:
    """Primera columna → celdas, para toda fila de tabla de la matriz."""
    rows: dict[str, list[str]] = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        key = cells[0]
        assert key not in rows or key.startswith(("Ítem", "Invariante", "SC", "Deuda")), f"fila duplicada: {key}"
        rows[key] = cells
    return rows


def _checklist_ids() -> set[str]:
    ids: set[str] = set()
    for path in CHECKLISTS.glob("*.md"):
        ids |= set(re.findall(r"^- \[[ xX]\] \**(CHK\d{3})", path.read_text(encoding="utf-8"), flags=re.MULTILINE))
    return ids


def _evidence(cells: list[str]) -> list[tuple[str, str | None]]:
    return [(m.group(1), m.group(2)) for cell in cells[1:] for m in EVIDENCE.finditer(cell)]


def _resolve(path: str) -> Path:
    return (GIT_ROOT if path.startswith(".github/") else ROOT) / path


def test_every_checklist_item_appears_in_the_matrix() -> None:
    ids = _checklist_ids()
    assert len(ids) == 76, f"se esperaban 76 ítems en los dos checklists, hay {len(ids)}"
    missing = sorted(ids - set(_rows()))
    assert not missing, f"ítems del checklist ausentes de la matriz: {missing}"


def test_every_marked_row_has_concrete_evidence_and_unmarked_rows_say_why() -> None:
    for key, cells in _rows().items():
        if len(cells) < 3 or cells[1] not in ("[x]", "[ ]"):
            continue
        if cells[1] == "[x]":
            assert _evidence(cells) or "Historial" in " ".join(cells), f"{key}: marcado sin evidencia concreta"
        else:
            assert len(" ".join(cells[2:])) > 20, f"{key}: sin marcar y sin motivo"


@pytest.mark.parametrize("key", ["INV-1", "INV-2", "INV-3", "INV-4"])
def test_each_cross_cutting_invariant_names_its_test(key: str) -> None:
    assert any(test for _path, test in _evidence(_rows()[key])), f"{key} sin test identificado por nombre"


def test_every_success_criterion_is_traced() -> None:
    rows = _rows()
    for n in range(1, 32):
        key = f"SC-{n:03d}"
        assert key in rows and rows[key][1] == "[x]" and _evidence(rows[key]), key


def test_every_referenced_evidence_exists() -> None:
    broken = []
    for key, cells in _rows().items():
        for path, test in _evidence(cells):
            target = _resolve(path)
            if not target.exists():
                broken.append(f"{key}: {path} no existe")
            elif test and not re.search(rf"^(async )?def {test}\(", target.read_text(encoding="utf-8"), flags=re.MULTILINE):
                broken.append(f"{key}: {path}::{test} no existe")
    assert not broken, "\n".join(broken)


def test_integrity_check_detects_a_broken_reference(tmp_path: Path) -> None:
    """Poder de detección: una evidencia inexistente se reporta."""
    fake = "| CHK999 | [x] | `tests/unit/test_domain.py::test_que_no_existe` | |"
    match = EVIDENCE.search(fake)
    assert match and match.group(2) == "test_que_no_existe"
    source = _resolve(match.group(1)).read_text(encoding="utf-8")
    assert not re.search(rf"^(async )?def {match.group(2)}\(", source, flags=re.MULTILINE)
