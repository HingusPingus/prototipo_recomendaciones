"""T002 — configuración por entorno y API key interna (FR-054, FR-059, FR-068, INV-4)."""

from __future__ import annotations

import pytest

from recomendaciones.config.errors import ConfigurationError
from recomendaciones.config.settings import Settings, load_settings
from tests.conftest import VALID_ENV


def test_valid_environment_loads(valid_env: dict[str, str]) -> None:
    settings = load_settings()
    assert settings.environment == "test"
    assert settings.ttl_filters_seconds < settings.ttl_fresh_seconds


def test_missing_api_key_fails_startup(valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RECO_INTERNAL_API_KEY")
    with pytest.raises(ConfigurationError) as exc:
        load_settings()
    assert "INTERNAL_API_KEY" in str(exc.value).upper()


@pytest.mark.parametrize(
    "operational",
    [k for k in VALID_ENV if k.startswith(("RECO_TTL_", "RECO_SIGNAL_", "RECO_EVENT_", "RECO_RETRY_"))],
)
def test_operational_parameters_have_no_default(
    operational: str, valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-068: ningún parámetro operativo queda como valor implícito en el código."""
    monkeypatch.delenv(operational)
    with pytest.raises(ConfigurationError):
        load_settings()


def test_api_key_of_other_environment_fails_startup(
    valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """La key incluye el identificador de entorno (FR-059)."""
    monkeypatch.setenv("RECO_INTERNAL_API_KEY", "prod.s3cr3t-0123456789abcdef")
    with pytest.raises(ConfigurationError):
        load_settings()


def test_presented_key_of_other_environment_is_rejected(valid_env: dict[str, str]) -> None:
    settings = load_settings()
    assert settings.verify_api_key("test.s3cr3t-0123456789abcdef") is True
    assert settings.verify_api_key("prod.s3cr3t-0123456789abcdef") is False
    assert settings.verify_api_key("test.otra-clave-cualquiera-xx") is False
    assert settings.verify_api_key("") is False
    assert settings.verify_api_key(None) is False


def test_repr_masks_secrets(valid_env: dict[str, str]) -> None:
    settings = load_settings()
    text = repr(settings) + str(settings) + str(settings.model_dump())
    assert "s3cr3t-0123456789abcdef" not in text
    assert "reco:reco@" not in text
    assert "guest:guest@" not in text


def test_redis_timeout_is_explicit(valid_env: dict[str, str]) -> None:
    """T021: el timeout hacia Redis es explícito y configurable."""
    assert load_settings().redis_timeout_seconds == pytest.approx(0.5)


def test_only_one_database_connection_string() -> None:
    """INV-4: no existe cadena de conexión a DB fuera de DB Recomendaciones."""
    dsn_fields = {
        name
        for name in Settings.model_fields
        if any(token in name for token in ("database", "dsn", "postgres", "cassandra", "db_"))
    }
    assert dsn_fields == {"database_url"}


def test_ttl_filters_must_be_shorter_than_fresh(
    valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """P4 del prototipo: `filters:` tiene TTL más corto que `reco:` (T018)."""
    monkeypatch.setenv("RECO_TTL_FILTERS_SECONDS", "86400")
    with pytest.raises(ConfigurationError):
        load_settings()
