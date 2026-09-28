"""T001 — cada paquete es importable y `engine/` no importa `storage/`, `api/` ni librerías de I/O."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

import recomendaciones

PACKAGES = [
    "api",
    "engine",
    "config",
    "worker",
    "transformer",
    "batch",
    "storage",
    "storage.db",
    "storage.cache",
    "observability",
    "shared",
]

ENGINE_FORBIDDEN_PREFIXES = (
    "recomendaciones.storage",
    "recomendaciones.api",
    "recomendaciones.worker",
    "recomendaciones.transformer",
    "recomendaciones.batch",
    "recomendaciones.observability",
    "sqlalchemy",
    "redis",
    "httpx",
    "aio_pika",
    "psycopg",
    "requests",
    "socket",
    "urllib",
    "http",
    "asyncio",
    "time",
    "random",
)

# `datetime` se admite como tipo (las señales traen `occurred_at`); lo prohibido es leer el reloj.
CLOCK_CALLS = ("datetime.now(", "datetime.utcnow(", "date.today(", "time.time(", "time.monotonic(")

PACKAGE_ROOT = Path(recomendaciones.__file__).parent


@pytest.mark.parametrize("name", PACKAGES)
def test_package_importable(name: str) -> None:
    importlib.import_module(f"recomendaciones.{name}")


def _imports_of(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # import relativo: se resuelve dentro de engine/
                base = "recomendaciones.engine"
                found.append(f"{base}.{node.module}" if node.module else base)
            elif node.module:
                found.append(node.module)
    return found


def test_engine_is_pure_library() -> None:
    """`engine/` no declara dependencias de red, DB ni reloj (T001, verificable por inspección)."""
    offenders = []
    for path in sorted((PACKAGE_ROOT / "engine").rglob("*.py")):
        for imported in _imports_of(path):
            if any(imported == p or imported.startswith(p + ".") for p in ENGINE_FORBIDDEN_PREFIXES):
                offenders.append(f"{path.name}: {imported}")
        source = path.read_text(encoding="utf-8")
        offenders.extend(f"{path.name}: {call}" for call in CLOCK_CALLS if call in source)
    assert not offenders, f"engine/ debe ser puro (FR-003): {offenders}"


def test_three_entrypoints_and_batch_are_declared() -> None:
    for module in ("api.main", "worker.main", "transformer.main", "batch.main"):
        mod = importlib.import_module(f"recomendaciones.{module}")
        assert callable(getattr(mod, "run"))


@pytest.mark.parametrize("script", ["reco-api", "reco-worker", "reco-transformer", "reco-batch"])
def test_entrypoint_fails_explicitly_without_configuration(script: str) -> None:
    """Los entrypoints arrancan de forma independiente y fallan con error explícito si falta config."""
    import os
    import subprocess
    import sys

    exe = Path(sys.executable).parent / script
    env = {k: v for k, v in os.environ.items() if not k.startswith("RECO_")}
    proc = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2
    assert "no arranca" in proc.stderr and "RECO_" in proc.stderr
    assert "Traceback" not in proc.stderr
