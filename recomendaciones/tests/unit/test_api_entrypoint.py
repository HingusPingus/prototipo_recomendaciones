"""`reco-api-con-migraciones`: migra y arranca la API con un comando de una sola palabra (RD-124).

Es el Run Command de la Application `reco-api` en Dokploy, que separa ese campo por espacios sin respetar comillas:
`sh -c "alembic upgrade head && reco-api"` le llega partido y falla.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from recomendaciones.api import main

ROOT = Path(__file__).resolve().parents[2]


def test_the_command_is_published_by_the_image() -> None:
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    assert scripts["reco-api-con-migraciones"] == "recomendaciones.api.main:run_with_migrations"


def test_it_migrates_to_head_before_starting_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr("alembic.config.main", lambda argv: calls.append(list(argv)))
    monkeypatch.setattr(main, "run", lambda: calls.append("api"))

    main.run_with_migrations()

    assert calls == [["upgrade", "head"], "api"]


def test_a_failed_migration_never_starts_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[bool] = []

    def failing_migration(argv: list[str]) -> None:
        raise SystemExit(1)  # alembic termina así ante un error de migración

    monkeypatch.setattr("alembic.config.main", failing_migration)
    monkeypatch.setattr(main, "run", lambda: started.append(True))

    with pytest.raises(SystemExit):
        main.run_with_migrations()
    assert started == []
