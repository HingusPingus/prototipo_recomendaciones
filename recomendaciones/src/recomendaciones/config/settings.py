"""Configuración por entorno (T002).

Todo valor viene del entorno (`RECO_*`), nunca del repo. Los parámetros operativos de FR-068 son
obligatorios y **sin default**: ninguno queda como valor implícito en el código. Las credenciales
son `SecretStr`, de modo que `repr()`, logs y `/health` nunca las exponen.

La API key interna tiene la forma `<entorno>.<secreto>`: incluye el identificador de entorno, y una
key de otro entorno se rechaza igual que una inválida (FR-059).
"""

from __future__ import annotations

import hmac

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from recomendaciones.config.errors import ConfigurationError

_MIN_SECRET_LENGTH = 16


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RECO_", extra="ignore", frozen=True)

    # --- Identidad y credenciales ---------------------------------------------------------------
    environment: str = Field(min_length=1)
    internal_api_key: SecretStr

    # --- Conexiones. INV-4: la única base de datos es DB Recomendaciones ------------------------
    database_url: SecretStr
    redis_url: SecretStr
    amqp_url: SecretStr
    api_general_base_url: str

    # --- Configuración versionada del motor activa en este entorno (FR-025b) -------------------
    engine_config_file: str

    # --- Parámetros operativos obligatorios (FR-068, RD-46), sin default -----------------------
    ttl_fresh_seconds: int = Field(gt=0)
    ttl_stale_seconds: int = Field(gt=0)
    ttl_filters_seconds: int = Field(gt=0)
    ttl_fallback_seconds: int = Field(gt=0)
    ttl_suppress_seconds: int = Field(gt=0)
    ttl_dedupe_seconds: int = Field(gt=0)
    idempotency_retention_hours: int = Field(gt=0)
    signal_retention_days: int = Field(gt=0)
    sync_volume_delta_ratio: float = Field(gt=0, le=1)
    interaction_recalc_threshold: int = Field(gt=0)
    recompute_requests_maxlen: int = Field(gt=0)
    recompute_requests_max_deliveries: int = Field(gt=0)
    event_redelivery_window_hours: int = Field(gt=0)
    retry_max_attempts: int = Field(gt=0)
    retry_backoff_base_seconds: float = Field(gt=0)
    redis_timeout_seconds: float = Field(gt=0)
    api_general_timeout_seconds: float = Field(gt=0)
    warmup_rate_per_second: float = Field(gt=0)

    # --- Proceso (no son parámetros de FR-068) -----------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    metrics_port: int = 9100

    @model_validator(mode="after")
    def _check_consistency(self) -> Settings:
        key = self.internal_api_key.get_secret_value()
        prefix, _, secret = key.partition(".")
        if prefix != self.environment:
            raise ValueError(
                "RECO_INTERNAL_API_KEY debe llevar el identificador del entorno como prefijo "
                f"('{self.environment}.<secreto>'): la credencial es válida en un único entorno (FR-059)"
            )
        if len(secret) < _MIN_SECRET_LENGTH:
            raise ValueError(f"RECO_INTERNAL_API_KEY: el secreto debe tener al menos {_MIN_SECRET_LENGTH} caracteres")
        if self.ttl_filters_seconds >= self.ttl_fresh_seconds:
            raise ValueError("RECO_TTL_FILTERS_SECONDS debe ser estrictamente menor que RECO_TTL_FRESH_SECONDS")
        if self.ttl_fresh_seconds > self.ttl_stale_seconds:
            raise ValueError("RECO_TTL_STALE_SECONDS no puede ser menor que RECO_TTL_FRESH_SECONDS")
        return self

    def verify_api_key(self, presented: str | None) -> bool:
        """Compara en tiempo constante. Ausente, inválida o de otro entorno: siempre `False`."""
        if not presented:
            return False
        expected = self.internal_api_key.get_secret_value().encode()
        return hmac.compare_digest(expected, presented.encode())

    # Ventanas derivadas -------------------------------------------------------------------------
    @property
    def retired_window_seconds(self) -> int:
        """Ventana del set `retired:{module}` = `TTL_STALE` + 1 día (RD-39). Derivada, no constante (DI-25)."""
        return self.ttl_stale_seconds + 86_400


def load_settings() -> Settings:
    """Carga la configuración del entorno. Cualquier ausencia o inconsistencia impide el arranque."""
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        problems = "; ".join(
            f"RECO_{'.'.join(str(p) for p in err['loc']).upper()}: {err['msg']}" if err["loc"] else err["msg"]
            for err in exc.errors()
        )
        raise ConfigurationError(f"configuración inválida o incompleta — {problems}") from None
