"""T004 — configuración versionada del motor y loader validante (FR-025, FR-027, FR-053, FR-054)."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from recomendaciones.config.errors import ConfigurationError
from recomendaciones.config.loader import (
    ENGINE_CONFIG_DIR,
    InMemoryConfigRegistry,
    load_engine_config,
    parse_engine_config,
    register_active_version,
    validate_operational_windows,
)
from recomendaciones.config.settings import load_settings

V1 = ENGINE_CONFIG_DIR / "v1.yaml"


def _v1() -> dict:
    return yaml.safe_load(V1.read_text(encoding="utf-8"))


def _write(tmp_path: Path, data: dict, name: str = "vX.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_v1_loads_with_decided_values() -> None:
    cfg = load_engine_config(V1)
    assert (cfg.alpha, cfg.beta, cfg.gamma) == (0.5, 0.3, 0.2)
    assert cfg.k == 20 and cfg.lambda_mmr == 0.7
    assert (cfg.top_n_min, cfg.top_n_default, cfg.top_n_max) == (10, 20, 50)
    assert (cfg.peso_like, cfg.peso_dislike) == (1.0, -1.0)
    assert cfg.popularity_window_days == 90 and cfg.popularity_confidence_z == 1.96
    assert cfg.fallback_new_item_quota_ratio == 0.20 and cfg.fallback_stored_size == 100
    assert cfg.diversity_max_cluster_share == 0.4 and cfg.declared_tags_min == 5
    assert cfg.region_weight_factor == 0.1 and cfg.collab_min_neighbors == 10
    assert cfg.emergent_evidence_threshold == 20
    assert [r.rating for r in cfg.age_rating_catalog] == ["ATP", "+13", "+18"]
    assert cfg.config_version.startswith("sha256:")


def _mutate(path: str, value: object):
    def apply(data: dict) -> dict:
        data = copy.deepcopy(data)
        if value is _DELETE:
            data.pop(path)
        else:
            data[path] = value
        return data

    return apply


_DELETE = object()

INVALID = {
    "suma-distinta-de-1": (_mutate("gamma", 0.3), "alpha+beta+gamma"),
    "alpha-fuera-de-rango": (lambda d: {**d, "alpha": 1.2, "beta": -0.4, "gamma": 0.2}, "alpha"),
    "lambda-fuera-de-rango": (_mutate("lambda_mmr", 1.5), "lambda_mmr"),
    "peso-like-no-positivo": (_mutate("peso_like", 0.0), "peso_like"),
    "peso-dislike-no-negativo": (_mutate("peso_dislike", 0.0), "peso_dislike"),
    "z-cero": (_mutate("popularity_confidence_z", 0), "popularity_confidence_z"),
    "catalogo-ordinal-repetido": (
        _mutate(
            "age_rating_catalog",
            [
                {"rating": "ATP", "ordinal": 0, "min_age": 0},
                {"rating": "+13", "ordinal": 0, "min_age": 13},
                {"rating": "+18", "ordinal": 2, "min_age": 18},
            ],
        ),
        "ordinal",
    ),
    "catalogo-ordinal-salteado": (
        _mutate(
            "age_rating_catalog",
            [
                {"rating": "ATP", "ordinal": 0, "min_age": 0},
                {"rating": "+18", "ordinal": 2, "min_age": 18},
            ],
        ),
        "ordinal",
    ),
    "catalogo-no-creciente": (
        _mutate(
            "age_rating_catalog",
            [
                {"rating": "ATP", "ordinal": 0, "min_age": 13},
                {"rating": "+13", "ordinal": 1, "min_age": 0},
            ],
        ),
        "min_age",
    ),
    "filtro-edad-desactivado": (_mutate("disable_age_filter", True), "FR-054"),
    "filtro-exclusion-desactivado": (_mutate("exclusion_filter_enabled", False), "FR-054"),
    "tiebreak-criteria-presente": (_mutate("tiebreak_criteria", ["popularity"]), "tiebreak_criteria"),
    "peso-consumo-presente": (_mutate("peso_consumo", 0.3), "RD-99"),
    "region-factor-uno": (_mutate("region_weight_factor", 1.0), "region_weight_factor"),
    "region-factor-negativo": (_mutate("region_weight_factor", -0.1), "region_weight_factor"),
    "ratio-cuota-cero": (_mutate("fallback_new_item_quota_ratio", 0.0), "fallback_new_item_quota_ratio"),
    "ratio-cuota-uno": (_mutate("fallback_new_item_quota_ratio", 1.0), "fallback_new_item_quota_ratio"),
    "top-n-min-bajo": (_mutate("top_n_min", 5), "top_n_min"),
    "top-n-desordenado": (_mutate("top_n_default", 60), "top_n_default"),
    "declared-min-ausente": (_mutate("declared_tags_min", _DELETE), "declared_tags_min"),
    "collab-min-no-positivo": (_mutate("collab_min_neighbors", 0), "collab_min_neighbors"),
    "umbral-emergente-ausente": (_mutate("emergent_evidence_threshold", _DELETE), "emergent_evidence_threshold"),
    "umbral-emergente-fraccion": (_mutate("emergent_evidence_threshold", 2.5), "emergent_evidence_threshold"),
    "cluster-share-cero": (_mutate("diversity_max_cluster_share", 0), "diversity_max_cluster_share"),
    "cluster-share-mayor-1": (_mutate("diversity_max_cluster_share", 1.1), "diversity_max_cluster_share"),
    "stored-size-menor-que-max": (_mutate("fallback_stored_size", 40), "fallback_stored_size"),
    "version-label-ausente": (_mutate("version_label", _DELETE), "version_label"),
}


@pytest.mark.parametrize("case", sorted(INVALID))
def test_invalid_configurations_fail_naming_the_field(case: str, tmp_path: Path) -> None:
    mutate, needle = INVALID[case]
    path = _write(tmp_path, mutate(_v1()))
    with pytest.raises(ConfigurationError) as exc:
        load_engine_config(path)
    assert needle in str(exc.value)


def test_region_weight_factor_zero_is_representable(tmp_path: Path) -> None:
    """RD-76: el límite inferior es inclusivo (0 es el neutro de FR-090)."""
    assert load_engine_config(_write(tmp_path, {**_v1(), "region_weight_factor": 0.0})).region_weight_factor == 0


def test_rating_outside_catalog_is_not_a_valid_rating() -> None:
    cfg = load_engine_config(V1)
    assert cfg.ordinal_for_rating("+18") == 2
    for garbage in (None, "", "XYZ", 123, "NC-17", "+16", "atp"):
        assert cfg.ordinal_for_rating(garbage) is None  # type: ignore[arg-type]


def test_hash_is_reproducible_and_content_based(tmp_path: Path) -> None:
    a = load_engine_config(V1).config_version
    b = load_engine_config(V1).config_version
    assert a == b
    # mismo contenido con otro formato (orden de claves, comentarios) ⟹ mismo identificador
    data = _v1()
    reordered = dict(reversed(list(data.items())))
    path = tmp_path / "reordenado.yaml"
    path.write_text("# comentario\n" + yaml.safe_dump(reordered, sort_keys=True), encoding="utf-8")
    assert load_engine_config(path).config_version == a
    changed = _write(tmp_path, {**data, "version_label": "otra"}, "otra.yaml")
    assert load_engine_config(changed).config_version != a


def test_parse_rejects_malformed_yaml(tmp_path: Path) -> None:
    path = tmp_path / "roto.yaml"
    path.write_text("alpha: [0.5\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_engine_config(path)
    with pytest.raises(ConfigurationError):
        parse_engine_config("no es un mapeo")


def test_missing_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_engine_config(tmp_path / "inexistente.yaml")


# --- FR-068b: ventanas en lista cerrada (RD-110) ---------------------------------------------------


def test_operational_windows_valid(valid_env: dict[str, str]) -> None:
    validate_operational_windows(load_engine_config(V1), load_settings())


@pytest.mark.parametrize(
    ("env_key", "value", "needle"),
    [
        ("RECO_SIGNAL_RETENTION_DAYS", "90", "popularity_window_days"),
        ("RECO_SIGNAL_RETENTION_DAYS", "7", "idempotencia"),
        ("RECO_EVENT_REDELIVERY_WINDOW_HOURS", str(24 * 800), "event_redelivery_window_hours"),
    ],
)
def test_retention_must_exceed_all_three_windows(
    env_key: str, value: str, needle: str, valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(env_key, value)
    with pytest.raises(ConfigurationError) as exc:
        validate_operational_windows(load_engine_config(V1), load_settings())
    assert needle in str(exc.value)


# --- DI-24 / RD-94: rollback hacia adelante -----------------------------------------------------


def test_registration_activates_and_deactivates_previous(tmp_path: Path) -> None:
    registry = InMemoryConfigRegistry()
    v1 = load_engine_config(V1)
    v2 = load_engine_config(_write(tmp_path, {**_v1(), "version_label": "v2", "k": 25}))
    now = datetime(2026, 9, 28, tzinfo=UTC)
    register_active_version(registry, v1, now)
    register_active_version(registry, v1, now)  # idempotente: misma versión activa
    register_active_version(registry, v2, now)
    assert registry.active() == v2.config_version
    assert registry.rows[v1.config_version].deactivated_at == now


def test_reactivating_a_deactivated_version_fails_with_rollback_forward_message(tmp_path: Path) -> None:
    registry = InMemoryConfigRegistry()
    v1 = load_engine_config(V1)
    v2 = load_engine_config(_write(tmp_path, {**_v1(), "version_label": "v2", "k": 25}))
    now = datetime(2026, 9, 28, tzinfo=UTC)
    register_active_version(registry, v1, now)
    register_active_version(registry, v2, now)
    with pytest.raises(ConfigurationError) as exc:
        register_active_version(registry, v1, now)
    assert "hacia adelante" in str(exc.value)


def test_loader_module_has_no_engine_constants() -> None:
    """Deuda del prototipo resuelta: ninguna constante del motor en código (FR-025)."""
    from recomendaciones.config import loader

    source = Path(loader.__file__).read_text(encoding="utf-8")
    for literal in ("0.5", "0.3", "0.2", "0.7", "1.96", "0.20", "0.4", "\"ATP\"", "'ATP'", "+13", "+18"):
        assert literal not in source, f"constante del motor en loader.py: {literal}"
