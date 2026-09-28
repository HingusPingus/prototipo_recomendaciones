"""Logging estructurado en JSON con identificador de correlación (T040, FR-046, Principio VII).

Campos estables por línea: `timestamp`, `level`, `logger`, `message`, `component`, `correlation_id`, y los
`extra` de dominio (`event_id`, `user_id`, `reco_module`, `config_version`, `reason`…). El identificador
sobrevive al salto asíncrono: la API lo toma de `X-Correlation-ID` (o lo genera), lo escribe en la entrada
de `recompute:requests`, y el worker lo restituye al procesarla; en los eventos del broker viaja en el
campo opcional `correlation_id` del contrato. Ningún secreto aparece en una línea: los valores registrados
como secretos se enmascaran aunque alguien los loguee por error.
"""

from __future__ import annotations

import contextvars
import json
import logging
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

_correlation: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)

_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}
_MASK = "***"


def current_correlation_id() -> str | None:
    return _correlation.get()


def new_correlation_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def correlation_scope(value: str | None) -> Iterator[str]:
    token = _correlation.set(value or new_correlation_id())
    try:
        yield _correlation.get()  # type: ignore[misc]
    finally:
        _correlation.reset(token)


class JsonFormatter(logging.Formatter):
    def __init__(self, *, component: str, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self._component = component
        self._secrets = tuple(s for s in secrets if s)

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, _MASK)
        return text

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "component": self._component,
            "correlation_id": current_correlation_id(),
        }
        for key, value in vars(record).items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return self._redact(json.dumps(payload, default=str, ensure_ascii=False))


def configure_logging(component: str, *, secrets: Iterable[str] = (), level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(component=component, secrets=secrets))
    root = logging.getLogger("recomendaciones")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = True
