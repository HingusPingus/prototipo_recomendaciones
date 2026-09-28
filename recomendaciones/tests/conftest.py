"""Fixtures compartidas."""

from __future__ import annotations

import pytest

# Entorno mínimo válido. Los parámetros operativos de FR-068 son obligatorios y sin default:
# cada test que los necesite parte de este diccionario completo.
VALID_ENV: dict[str, str] = {
    "RECO_ENVIRONMENT": "test",
    "RECO_INTERNAL_API_KEY": "test.s3cr3t-0123456789abcdef",
    "RECO_DATABASE_URL": "postgresql+psycopg://reco:reco@localhost:5432/recomendaciones",
    "RECO_REDIS_URL": "redis://localhost:6379/0",
    "RECO_AMQP_URL": "amqp://guest:guest@localhost:5672/",
    "RECO_API_GENERAL_BASE_URL": "http://api-general.internal",
    "RECO_ENGINE_CONFIG_FILE": "v1.yaml",
    "RECO_TTL_FRESH_SECONDS": "86400",
    "RECO_TTL_STALE_SECONDS": "604800",
    "RECO_TTL_FILTERS_SECONDS": "3600",
    "RECO_TTL_FALLBACK_SECONDS": "21600",
    "RECO_TTL_SUPPRESS_SECONDS": "300",
    "RECO_TTL_DEDUPE_SECONDS": "86400",
    "RECO_IDEMPOTENCY_RETENTION_HOURS": "168",
    "RECO_SIGNAL_RETENTION_DAYS": "730",
    "RECO_SYNC_VOLUME_DELTA_RATIO": "0.9",
    "RECO_INTERACTION_RECALC_THRESHOLD": "10",
    "RECO_RECOMPUTE_REQUESTS_MAXLEN": "100000",
    "RECO_RECOMPUTE_REQUESTS_MAX_DELIVERIES": "5",
    "RECO_EVENT_REDELIVERY_WINDOW_HOURS": "48",
    "RECO_RETRY_MAX_ATTEMPTS": "5",
    "RECO_RETRY_BACKOFF_BASE_SECONDS": "1",
    "RECO_REDIS_TIMEOUT_SECONDS": "0.5",
    "RECO_API_GENERAL_TIMEOUT_SECONDS": "10",
    "RECO_WARMUP_RATE_PER_SECOND": "50",
}


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    return dict(VALID_ENV)
