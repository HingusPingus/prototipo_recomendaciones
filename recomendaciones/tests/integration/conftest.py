"""Marcador de integración; las fixtures de contenedores viven en `tests/conftest.py`."""

from __future__ import annotations

import pytest

from tests.conftest import alembic_config, fresh_database  # noqa: F401 — reexportados para los tests


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/integration" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.integration)
