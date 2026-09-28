"""Loader validante de la configuración versionada del motor (T004).

Reglas (data-model.md §4, FR-025…FR-027, FR-053, FR-054):

- Toda clave desconocida impide el arranque; algunas con mensaje propio porque son decisiones
  revertidas que suelen volver por la puerta de la configuración: `tiebreak_criteria` (RD-10), un peso
  de consumo (RD-99) y cualquier intento de desactivar un filtro obligatorio (FR-054).
- `config_version` = SHA-256 del contenido canónico: mismo contenido ⟹ mismo identificador en
  cualquier máquina, independiente de comentarios, orden de claves o fin de línea.
- Una versión desactivada no se reactiva: el rollback es hacia adelante (DI-24, RD-94).

Este módulo no contiene valores del motor: viven en `engine_config/vN.yaml`.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from recomendaciones.config.errors import ConfigurationError

ENGINE_CONFIG_DIR = Path(__file__).parent / "engine_config"
_SUM_TOLERANCE = 1e-9


class AgeRatingLevel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rating: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    min_age: int = Field(ge=0)


class VocabRegenerationPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trigger: Literal["tag_set_hash_change"]
    transition: Literal["recompute_all_before_activate"]


class EngineConfig(BaseModel):
    """Contenido validado de un `vN.yaml`. Inmutable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version_label: str = Field(min_length=1)
    alpha: float
    beta: float
    gamma: float
    k: int = Field(gt=0)
    collab_min_neighbors: int = Field(gt=0, strict=True)
    lambda_mmr: float
    diversity_max_cluster_share: float
    top_n_min: int
    top_n_default: int
    top_n_max: int
    peso_like: float
    peso_dislike: float
    popularity_window_days: int = Field(gt=0)
    popularity_confidence_z: float
    fallback_stored_size: int = Field(gt=0)
    fallback_new_item_quota_ratio: float
    emergent_evidence_threshold: int = Field(gt=0, strict=True)
    declared_tags_min: int = Field(gt=0, strict=True)
    region_weight_factor: float
    vocab_regeneration_policy: VocabRegenerationPolicy
    age_rating_catalog: tuple[AgeRatingLevel, ...] = Field(min_length=1)

    # Derivados del archivo (no son claves del YAML)
    config_version: str = Field(default="", exclude=True)

    @field_validator("alpha", "beta", "gamma", "lambda_mmr")
    @classmethod
    def _unit_interval(cls, value: float, info: Any) -> float:
        if not 0 <= value <= 1:
            raise ValueError(f"{info.field_name} debe estar en [0,1] (FR-027)")
        return value

    @model_validator(mode="after")
    def _cross_field(self) -> EngineConfig:
        errors: list[str] = []
        if not math.isclose(self.alpha + self.beta + self.gamma, 1.0, abs_tol=_SUM_TOLERANCE):
            errors.append("alpha+beta+gamma debe sumar 1.0 (FR-027)")
        if not self.peso_like > 0:
            errors.append("peso_like debe ser > 0: el like refuerza (FR-022a)")
        if not self.peso_dislike < 0:
            errors.append("peso_dislike debe ser < 0: el dislike penaliza (FR-022a)")
        if not self.popularity_confidence_z > 0:
            errors.append("popularity_confidence_z debe ser > 0 estricto: 0 degenera Wilson (FR-033a3, RD-44)")
        if not 0 <= self.region_weight_factor < 1:
            errors.append("region_weight_factor debe cumplir 0 <= x < 1 (FR-081b, RD-76)")
        if not 0 < self.fallback_new_item_quota_ratio < 1:
            errors.append("fallback_new_item_quota_ratio debe cumplir 0 < x < 1 (FR-033a6b)")
        if not self.top_n_min >= 10:
            errors.append("top_n_min debe ser >= 10 (FR-006a)")
        if not self.top_n_min <= self.top_n_default <= self.top_n_max:
            errors.append("top_n_default debe cumplir top_n_min <= top_n_default <= top_n_max (FR-033a6b)")
        if not 0 < self.diversity_max_cluster_share <= 1:
            errors.append("diversity_max_cluster_share debe cumplir 0 < x <= 1 (FR-071)")
        if not self.fallback_stored_size >= self.top_n_max:
            errors.append("fallback_stored_size debe ser >= top_n_max (FR-033f, RD-111)")
        errors.extend(_catalog_errors(self.age_rating_catalog))
        if errors:
            raise ValueError("; ".join(errors))
        return self

    # --- Escala etaria (§4.1): única fuente del mapeo ------------------------------------------
    def ordinal_for_rating(self, rating: object) -> int | None:
        """Ordinal de una etiqueta del catálogo; `None` si está fuera de él (el llamador cierra)."""
        if not isinstance(rating, str):
            return None
        for level in self.age_rating_catalog:
            if level.rating == rating:
                return level.ordinal
        return None

    @property
    def max_ordinal(self) -> int:
        return self.age_rating_catalog[-1].ordinal

    @property
    def most_restrictive_rating(self) -> str:
        return self.age_rating_catalog[-1].rating

    def max_age_ordinal_for_age(self, age_years: int) -> int:
        """El ordinal más alto cuyo `min_age` ≤ edad (§4.1). El catálogo arranca en `min_age` 0."""
        allowed = [level.ordinal for level in self.age_rating_catalog if level.min_age <= age_years]
        return max(allowed) if allowed else -1

    @property
    def age_thresholds(self) -> tuple[int, ...]:
        """Edades que cruzan un umbral del catálogo (§7.5 causa A)."""
        return tuple(level.min_age for level in self.age_rating_catalog if level.min_age > 0)

    def age_catalog_fingerprint(self) -> str:
        """Identidad del catálogo etario: dos versiones legibles entre sí la comparten (RD-103)."""
        return _canonical_hash([level.model_dump() for level in self.age_rating_catalog])

    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _catalog_errors(catalog: tuple[AgeRatingLevel, ...]) -> list[str]:
    errors: list[str] = []
    ordinals = [level.ordinal for level in catalog]
    if sorted(ordinals) != list(range(len(catalog))):
        errors.append("age_rating_catalog: ordinal debe ser único y contiguo desde 0 (§4.1)")
    if len({level.rating for level in catalog}) != len(catalog):
        errors.append("age_rating_catalog: rating repetido (§4.1)")
    ordered = sorted(catalog, key=lambda level: level.ordinal)
    if any(a.min_age >= b.min_age for a, b in zip(ordered, ordered[1:])):
        errors.append("age_rating_catalog: min_age debe crecer estrictamente con el ordinal (§4.1)")
    if ordered and ordered[0].min_age != 0:
        errors.append("age_rating_catalog: el ordinal 0 debe tener min_age 0 (§4.1)")
    return errors


_KNOWN_KEYS = set(EngineConfig.model_fields) - {"config_version"}


def _forbidden_key_errors(data: dict[str, Any]) -> list[str]:
    errors = []
    for key in data:
        lowered = key.lower()
        if key == "tiebreak_criteria":
            errors.append("tiebreak_criteria: eliminado del esquema, el desempate es fijo (RD-10)")
        elif "consumo" in lowered or "consumption" in lowered:
            errors.append(f"{key}: el consumo no modifica el perfil, no existe peso de consumo (RD-99, FR-022b)")
        elif any(t in lowered for t in ("filter", "filtro")) or lowered.startswith(("disable", "enable", "skip")):
            errors.append(f"{key}: los filtros de edad y exclusión no son desactivables (FR-054, FR-029)")
        elif key not in _KNOWN_KEYS:
            errors.append(f"{key}: clave desconocida en la configuración del motor (FR-027)")
    return errors


def _canonical_hash(data: Any) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_engine_config(data: Any, *, source: str = "<config>") -> EngineConfig:
    if not isinstance(data, dict):
        raise ConfigurationError(f"{source}: la configuración del motor debe ser un mapeo")
    errors = _forbidden_key_errors(data)
    if errors:
        raise ConfigurationError(f"{source}: " + "; ".join(errors))
    try:
        cfg = EngineConfig.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" if err["loc"] else err["msg"]
            for err in exc.errors()
        )
        raise ConfigurationError(f"{source}: configuración del motor inválida — {problems}") from None
    return cfg.model_copy(update={"config_version": _canonical_hash(data)})


def load_engine_config(path: Path | str) -> EngineConfig:
    path = Path(path)
    if not path.is_absolute() and not path.exists():
        path = ENGINE_CONFIG_DIR / path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"{path}: no se puede leer la configuración del motor ({exc})") from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"{path}: YAML malformado ({exc})") from None
    return parse_engine_config(data, source=str(path.name))


class OperationalWindows(Protocol):
    signal_retention_days: int
    idempotency_retention_hours: int
    ttl_dedupe_seconds: int
    event_redelivery_window_hours: int


def validate_operational_windows(cfg: EngineConfig, settings: OperationalWindows) -> None:
    """FR-068b: la retención supera estrictamente las tres ventanas de la lista cerrada (RD-110)."""
    retention_h = settings.signal_retention_days * 24
    windows = {
        "popularity_window_days": cfg.popularity_window_days * 24,
        "idempotencia (TTL_DEDUPE / processed_events)": max(
            settings.idempotency_retention_hours, settings.ttl_dedupe_seconds / 3600
        ),
        "event_redelivery_window_hours": settings.event_redelivery_window_hours,
    }
    failing = [name for name, hours in windows.items() if not retention_h > hours]
    if failing:
        raise ConfigurationError(
            "signal_retention_days debe superar estrictamente a toda ventana operativa (FR-068b); "
            f"no supera: {', '.join(failing)}"
        )


# --- Registro de versiones activas (engine_config_versions, §2.8) ---------------------------------


@dataclass
class ConfigRow:
    config_version: str
    payload: dict[str, Any]
    activated_at: datetime
    deactivated_at: datetime | None = None


class ConfigRegistry(Protocol):
    def get(self, config_version: str) -> ConfigRow | None: ...
    def active(self) -> str | None: ...
    def deactivate(self, config_version: str, at: datetime) -> None: ...
    def insert(self, row: ConfigRow) -> None: ...


class InMemoryConfigRegistry:
    """Registro en memoria para tests unitarios; el real es `storage.db.config_registry`."""

    def __init__(self) -> None:
        self.rows: dict[str, ConfigRow] = {}

    def get(self, config_version: str) -> ConfigRow | None:
        return self.rows.get(config_version)

    def active(self) -> str | None:
        return next((v for v, r in self.rows.items() if r.deactivated_at is None), None)

    def deactivate(self, config_version: str, at: datetime) -> None:
        self.rows[config_version].deactivated_at = at

    def insert(self, row: ConfigRow) -> None:
        self.rows[row.config_version] = row


def register_active_version(registry: ConfigRegistry, cfg: EngineConfig, now: datetime) -> None:
    """Deja `cfg` como única versión activa. Idempotente si ya lo es (FR-025b, DI-7, DI-24)."""
    existing = registry.get(cfg.config_version)
    if existing is not None:
        if existing.deactivated_at is None:
            return
        raise ConfigurationError(
            f"la configuración {cfg.config_version} ({cfg.version_label}) coincide con una versión "
            "desactivada, que no se reactiva: el rollback se hace hacia adelante con una versión nueva "
            "y otro version_label (RD-94, DI-24)"
        )
    current = registry.active()
    if current is not None:
        registry.deactivate(current, now)
    registry.insert(ConfigRow(cfg.config_version, cfg.payload(), now))


# --- Versiones desplegadas (RD-103: «desde los archivos de configuración desplegados») --------------


def _file_order(path: Path) -> tuple[int, str]:
    stem = path.stem
    digits = stem[1:] if stem[:1] == "v" and stem[1:].isdigit() else ""
    return (int(digits) if digits else -1, stem)


def load_deployed_configs(directory: Path = ENGINE_CONFIG_DIR) -> list[EngineConfig]:
    """Todas las `vN.yaml` desplegadas, de la más nueva a la más vieja (por N)."""
    paths = sorted(directory.glob("v*.yaml"), key=_file_order, reverse=True)
    return [load_engine_config(p) for p in paths]


def age_compatible_versions(active: EngineConfig, deployed: list[EngineConfig]) -> frozenset[str]:
    """Versiones cuyo catálogo etario es idéntico al activo: sus ordinales son comparables (§3.1.1).

    Comparar por identidad de versión —el hash de todo el archivo— volvería incomparable a todo usuario
    ante cualquier cambio de pesos, con `503` generalizado hasta rederivar (DI-23 leído literalmente).
    """
    fingerprint = active.age_catalog_fingerprint()
    return frozenset({active.config_version}) | {
        c.config_version for c in deployed if c.age_catalog_fingerprint() == fingerprint
    }


def readable_versions_from_files(active: EngineConfig, deployed: list[EngineConfig]) -> tuple[str, ...]:
    """Versiones anteriores legibles (RD-103), de la más nueva a la más vieja, sin tocar Postgres.

    La cota «desactivadas hace menos de `TTL_STALE`» es redundante con los TTL: las claves de una versión
    más vieja ya expiraron, y consultarlas solo cuesta un miss.
    """
    compatible = age_compatible_versions(active, deployed)
    ordered: list[str] = []
    for cfg in deployed:
        if cfg.config_version != active.config_version and cfg.config_version in compatible:
            if cfg.config_version not in ordered:
                ordered.append(cfg.config_version)
    return tuple(ordered)
