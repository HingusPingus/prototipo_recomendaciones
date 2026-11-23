"""RD-128 — el lazo de `reco-sync-usuarios`: una vuelta por intervalo, sobrevive a las fallas y no inunda el log."""

from __future__ import annotations

import logging
import threading

import pytest

from recomendaciones.transformer.pipeline import NewUsersReport
from recomendaciones.transformer.usuarios_continuo import NewUsersLoop

LOGGER = "recomendaciones.transformer.usuarios_continuo"
NONE = NewUsersReport("none")
FAILED = NewUsersReport("failed", reason="api-general no respondió: ConnectError")


class ScriptedMaterializer:
    """Devuelve (o lanza) los resultados en orden y pide parar al llegar a `stop_after` vueltas."""

    def __init__(self, outcomes: list[NewUsersReport | Exception], stop: threading.Event, stop_after: int) -> None:
        self.outcomes, self.stop, self.stop_after, self.calls = outcomes, stop, stop_after, 0

    def run_once(self) -> NewUsersReport:
        self.calls += 1
        if self.calls >= self.stop_after:
            self.stop.set()
        outcome = self.outcomes[min(self.calls, len(self.outcomes)) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _run(outcomes: list[NewUsersReport | Exception], stop_after: int) -> ScriptedMaterializer:
    stop = threading.Event()
    materializer = ScriptedMaterializer(outcomes, stop, stop_after)
    NewUsersLoop(materializer, interval_seconds=0.01, stop=stop).run()
    return materializer


def test_runs_one_tick_then_stops_when_stop_is_set() -> None:
    assert _run([NONE], stop_after=1).calls == 1


def test_unexpected_exception_does_not_stop_loop() -> None:
    assert _run([RuntimeError("la base no responde"), NONE], stop_after=2).calls == 2


def test_failure_logged_once_and_recovery_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    _run([FAILED, FAILED, FAILED, NONE], stop_after=4)
    records = [r for r in caplog.records if r.name == LOGGER]
    assert len([r for r in records if r.levelno == logging.WARNING]) == 1
    assert len([r for r in records if "recuperada" in r.getMessage()]) == 1


def test_exception_streak_logged_once_with_traceback(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    _run([RuntimeError("uno"), RuntimeError("dos"), NONE], stop_after=3)
    warnings = [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].exc_info is not None


def test_inserted_users_are_logged_and_quiet_ticks_are_not(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    _run([NewUsersReport("inserted", 2), NONE, NewUsersReport("busy")], stop_after=3)
    records = [r for r in caplog.records if r.name == LOGGER]
    assert len(records) == 1
    assert getattr(records[0], "inserted", None) == 2


def test_entrypoint_is_a_single_word_console_script() -> None:
    """Dokploy parte el Run Command por espacios (docs/despliegue.md §2): el proceso tiene su propio comando."""
    import tomllib
    from pathlib import Path

    from recomendaciones.transformer import main

    pyproject = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["scripts"]["reco-sync-usuarios"] == "recomendaciones.transformer.main:run_usuarios"
    assert callable(main.run_usuarios)
