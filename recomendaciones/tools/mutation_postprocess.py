"""Test de mutación del post-proceso (T045): si una mutación del filtro de edad o de exclusión sobrevive, falla.

Es la verificación de que los tests de T017 tienen poder de detección real y no solo cobertura de líneas.
Cada mutante se aplica sobre una **copia** del paquete en un directorio temporal —el árbol de trabajo no se
toca nunca— y se corre la batería de invariantes con esa copia primera en `PYTHONPATH`. Un mutante
«muerto» es uno que hace fallar la batería; uno «sobreviviente» hace fallar este script.

Uso: `python tools/mutation_postprocess.py` (desde `recomendaciones/`). Sale con 0 solo si mueren todos.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = Path("recomendaciones/engine/postprocess.py")
SUITE = ["tests/invariants/test_age_filter.py", "tests/invariants/test_exclusion.py", "tests/invariants/test_pipeline_order.py"]

# (nombre, texto original, texto mutado): cada original debe aparecer exactamente una vez.
MUTANTS = [
    ("edad: <= pasa a <", "if s.candidate.min_age_ordinal <= user_max_age_ordinal]", "if s.candidate.min_age_ordinal < user_max_age_ordinal]"),
    ("edad: un nivel de más", "if s.candidate.min_age_ordinal <= user_max_age_ordinal]", "if s.candidate.min_age_ordinal <= user_max_age_ordinal + 1]"),
    ("edad: filtro anulado", "if s.candidate.min_age_ordinal <= user_max_age_ordinal]", "if True]"),
    ("edad: etapa salteada", "kept = _age_stage(scoring.ranked, req.user_max_age_ordinal)", "kept = list(scoring.ranked)"),
    ("exclusión: filtro anulado", "if not exclusions.contains(s.candidate.item_id)]", "if True]"),
    ("exclusión: fail-open sin conjunto", "    if exclusions is None:\n        raise ExclusionSetUnavailable()", "    if exclusions is None:\n        return list(scored)"),
    ("exclusión: etapa salteada", "kept = _exclusion_stage(stage.items, req.exclusions)", "kept = list(stage.items)"),
]


def _run_suite(pythonpath: Path) -> int:
    env = {**os.environ, "PYTHONPATH": f"{pythonpath}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"}
    cmd = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-p", "no:warnings", *SUITE]
    return subprocess.run(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode


def main() -> int:
    original = (ROOT / "src" / TARGET).read_text(encoding="utf-8")
    survivors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="mutantes-") as tmp:
        copy = Path(tmp) / "src"
        shutil.copytree(ROOT / "src", copy)
        if _run_suite(copy) != 0:
            print("la batería falla sin mutar: no se puede evaluar")
            return 2
        for name, before, after in MUTANTS:
            if original.count(before) != 1:
                print(f"ERROR: el mutante «{name}» ya no aplica (el código cambió): actualizar MUTANTS")
                return 2
            (copy / TARGET).write_text(original.replace(before, after), encoding="utf-8")
            killed = _run_suite(copy) != 0
            print(f"{'muerto      ' if killed else 'SOBREVIVE   '} {name}")
            if not killed:
                survivors.append(name)
        (copy / TARGET).write_text(original, encoding="utf-8")
    if survivors:
        print(f"\n{len(survivors)} mutante(s) sobreviven: los tests de invariantes no detectan {survivors}")
        return 1
    print(f"\n{len(MUTANTS)}/{len(MUTANTS)} mutantes muertos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
