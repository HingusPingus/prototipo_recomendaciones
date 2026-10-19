"""T006 — test de arquitectura: INV-1, FR-003, FR-068e y SC-012 como fallas de CI.

Es la única defensa automatizable contra que alguien «resuelva» una latencia calculando en línea.
El poder de detección se demuestra con paquetes sintéticos que violan cada regla (caso negativo).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import recomendaciones

SRC_ROOT = Path(recomendaciones.__file__).parent
PKG = "recomendaciones"

# INV-1: la API solo toca Postgres por los caminos admitidos (repoblado de `filters:` y de `retired:` ante miss
# de esa clave, escritura de la declaración, T053, y consulta de la recepción de una baja, T077, excepción de
# lectura de la constitución v1.2.0). Estos son sus módulos.
API_ALLOWED_DB_MODULES = {
    f"{PKG}.storage.db.filters_source",  # repoblado de filters: y retired: ante miss
    f"{PKG}.storage.db.declarations",  # escritura de la declaración (T053)
    f"{PKG}.storage.db.receipts",  # consulta de la recepción de una baja (T077, Principio III v1.2.0)
    f"{PKG}.storage.db.session",
    f"{PKG}.storage.db.models",
}
ENGINE_FORBIDDEN = ("storage", "httpx", "redis", "sqlalchemy", "psycopg", "aio_pika")

# FR-068e: únicas rutinas autorizadas a borrar datos no recuperables.
PROTECTED_TABLES = ("user_signals", "user_declared_tags", "user_exclusions", "user_suppressions", "item_promotions")
PROTECTED_MODELS = ("UserSignal", "UserDeclaredTag", "UserExclusion", "UserSuppression", "ItemPromotion")
DELETE_ALLOWED = {f"{PKG}.batch.purga_senales", f"{PKG}.worker.suppression"}

# SC-012: ningún driver ni cadena de conexión hacia bases de otros repos.
FOREIGN_DB_DRIVERS = ("cassandra", "pymongo", "mysql", "cx_Oracle")


@dataclass
class Tree:
    root: Path
    package: str
    imports: dict[str, set[str]] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)

    @classmethod
    def scan(cls, root: Path, package: str) -> Tree:
        tree = cls(root, package)
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(root).with_suffix("")
            parts = [package, *rel.parts]
            if parts[-1] == "__init__":
                parts = parts[:-1]
            name = ".".join(parts)
            source = path.read_text(encoding="utf-8")
            tree.sources[name] = source
            tree.imports[name] = _imports(ast.parse(source), name, path.name == "__init__.py")
        return tree

    def reachable(self, start: str) -> dict[str, str]:
        """Módulos internos alcanzables desde `start`, con el primer importador que los trajo."""
        seen: dict[str, str] = {start: start}
        stack = [start]
        while stack:
            current = stack.pop()
            for imported in self.imports.get(current, ()):
                target = self._resolve(imported)
                if target and target not in seen:
                    seen[target] = current
                    stack.append(target)
        return seen

    def _resolve(self, imported: str) -> str | None:
        candidate = imported
        while candidate:
            if candidate in self.imports:
                return candidate
            candidate = candidate.rpartition(".")[0]
        return None


def _imports(tree: ast.AST, module: str, is_package: bool) -> set[str]:
    found: set[str] = set()
    base_parts = module.split(".") if is_package else module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parent = base_parts[: len(base_parts) - (node.level - 1)]
                prefix = ".".join(parent)
                mod = f"{prefix}.{node.module}" if node.module else prefix
            else:
                mod = node.module or ""
            found.add(mod)
            found.update(f"{mod}.{alias.name}" for alias in node.names)
    return found


def violations(tree: Tree) -> list[str]:
    pkg = tree.package
    out: list[str] = []
    api_modules = [m for m in tree.imports if m == f"{pkg}.api" or m.startswith(f"{pkg}.api.")]

    # 1. api/ no importa engine/, ni directa ni transitivamente (FR-003, INV-1)
    for module in api_modules:
        reach = tree.reachable(module)
        for target, via in reach.items():
            if target == f"{pkg}.engine" or target.startswith(f"{pkg}.engine."):
                out.append(f"FR-003: {module} alcanza {target} (importado desde {via})")
                break

    # 2. engine/ no importa storage/ ni librerías de red o base de datos
    for module, imported in tree.imports.items():
        if not (module == f"{pkg}.engine" or module.startswith(f"{pkg}.engine.")):
            continue
        for name in imported:
            head = name.removeprefix(f"{pkg}.").split(".")[0]
            if head in ENGINE_FORBIDDEN:
                out.append(f"FR-003: {module} importa {name}")

    # 3. la API accede a Postgres solo por los repositorios admitidos por INV-1
    for module in api_modules:
        for name in tree.imports[module]:
            if name.split(".")[0] in ("sqlalchemy", "psycopg"):
                out.append(f"FR-003/INV-1: {module} importa {name} directamente")
        for target, via in tree.reachable(module).items():
            if target.startswith(f"{pkg}.storage.db.") and target not in {
                m.replace(PKG, pkg, 1) for m in API_ALLOWED_DB_MODULES
            }:
                out.append(f"FR-003/INV-1: {module} alcanza {target} (desde {via}), fuera de los repositorios admitidos")

    # 4. FR-068e: DELETE/TRUNCATE sobre tablas no recuperables solo en purga y supresión
    table_re = re.compile(
        r"(DELETE\s+FROM|TRUNCATE(\s+TABLE)?)\s+(" + "|".join(PROTECTED_TABLES) + r")\b", re.IGNORECASE
    )
    orm_re = re.compile(r"\bdelete\(\s*(" + "|".join(PROTECTED_MODELS) + r")\b")
    allowed = {m.replace(PKG, pkg, 1) for m in DELETE_ALLOWED}
    for module, source in tree.sources.items():
        if module in allowed:
            continue
        for match in list(table_re.finditer(source)) + list(orm_re.finditer(source)):
            out.append(f"FR-068e: {module} borra {match.group(0)!r} fuera de la purga (T057) y la supresión (T058)")

    # 6. SC-012: sin drivers de bases ajenas
    for module, imported in tree.imports.items():
        for name in imported:
            if name.split(".")[0] in FOREIGN_DB_DRIVERS:
                out.append(f"SC-012: {module} importa el driver ajeno {name}")
    return out


def test_repository_respects_architecture() -> None:
    found = violations(Tree.scan(SRC_ROOT, PKG))
    assert not found, "Violaciones de arquitectura (FR-003, INV-1, FR-068e, SC-012):\n" + "\n".join(found)


# --- Poder de detección: cada regla falla ante su caso negativo --------------------------------


def _synthetic(tmp_path: Path, files: dict[str, str]) -> Tree:
    root = tmp_path / "pkg"
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for directory in [root, *[p for p in root.rglob("*") if p.is_dir()]]:
        (directory / "__init__.py").touch()
    return Tree.scan(root, "pkg")


NEGATIVE_CASES = {
    "api-importa-engine-directo": ({"api/routes.py": "from pkg.engine import scoring\n", "engine/scoring.py": ""}, "FR-003"),
    "api-importa-engine-transitivo": (
        {
            "api/routes.py": "from pkg.shared import helpers\n",
            "shared/helpers.py": "from pkg.engine.scoring import score\n",
            "engine/scoring.py": "def score(): ...\n",
        },
        "pkg.engine.scoring",
    ),
    "api-importa-engine-relativo": ({"api/routes.py": "from ..engine import scoring\n", "engine/scoring.py": ""}, "FR-003"),
    "engine-importa-redis": ({"engine/content.py": "import redis\n"}, "FR-003"),
    "engine-importa-storage": ({"engine/content.py": "from pkg.storage.db import models\n", "storage/db/models.py": ""}, "FR-003"),
    "api-usa-sqlalchemy": ({"api/services/read.py": "import sqlalchemy as sa\n"}, "INV-1"),
    "api-lee-resultados-de-postgres": (
        {"api/services/read.py": "from pkg.storage.db import signals_repo\n", "storage/db/signals_repo.py": ""},
        "INV-1",
    ),
    "delete-de-senales-fuera-de-purga": ({"batch/fallback.py": 'SQL = "DELETE FROM user_signals WHERE 1=1"\n'}, "FR-068e"),
    "truncate-de-exclusiones": ({"worker/handler.py": 'SQL = "TRUNCATE TABLE user_exclusions"\n'}, "FR-068e"),
    "orm-delete-de-declaraciones": ({"api/services/declaracion.py": "stmt = delete(UserDeclaredTag)\n"}, "FR-068e"),
    "driver-de-base-ajena": ({"transformer/client.py": "import cassandra.cluster\n"}, "SC-012"),
}


@pytest.mark.parametrize("case", sorted(NEGATIVE_CASES))
def test_detection_power(case: str, tmp_path: Path) -> None:
    files, needle = NEGATIVE_CASES[case]
    found = violations(_synthetic(tmp_path, files))
    assert found, f"el caso negativo {case} no fue detectado"
    assert any(needle in v for v in found), found


def test_allowed_paths_are_not_flagged(tmp_path: Path) -> None:
    tree = _synthetic(
        tmp_path,
        {
            "api/services/read.py": "from pkg.storage.db import filters_source\n",
            "storage/db/filters_source.py": "import sqlalchemy\n",
            "batch/purga_senales.py": 'SQL = "DELETE FROM user_signals WHERE received_at < :c"\n',
            "worker/suppression.py": 'SQL = "DELETE FROM users WHERE id = :u"\n',
        },
    )
    assert violations(tree) == []


def test_failure_message_names_the_offender_and_cites_fr003(tmp_path: Path) -> None:
    found = violations(_synthetic(tmp_path, {"api/routes.py": "from pkg.engine import scoring\n", "engine/scoring.py": ""}))
    assert any("pkg.api.routes" in v and "FR-003" in v for v in found)
