"""T037 — la guarda del request path no importa `engine/` ni funciones de similitud (FR-033d, RD-8)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from recomendaciones.api.services import read_service


def test_read_service_imports_no_engine_nor_similarity() -> None:
    tree = ast.parse(Path(read_service.__file__).read_text(encoding="utf-8"))
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert not {m for m in imported if "engine" in m or "numpy" in m or "similarity" in m}


def test_guard_is_membership_and_comparison_only() -> None:
    source = inspect.getsource(read_service.ReadService._guard)
    for forbidden in ("cosine", "sort", "sorted", "score =", "mmr", "similarity"):
        assert forbidden not in source.lower(), forbidden
