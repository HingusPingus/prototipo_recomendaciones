"""T018 — esquema de claves Redis (data-model.md §3.1, DI-5, RD-36, RD-39, RD-103)."""

from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from recomendaciones.config.loader import ConfigRow
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.ttl import CacheTTLs
from recomendaciones.storage.cache.versions import readable_versions

U1, U2 = uuid.UUID(int=1), uuid.UUID(int=2)
CATALOG = [{"rating": "ATP", "ordinal": 0, "min_age": 0}, {"rating": "+18", "ordinal": 1, "min_age": 18}]
OTHER_CATALOG = [{"rating": "ATP", "ordinal": 0, "min_age": 0}, {"rating": "+16", "ordinal": 1, "min_age": 16}]


def test_no_collision_between_modules_versions_and_freshness() -> None:
    generated = set()
    for cfg, user, module in itertools.product(["sha256:a", "sha256:b"], [U1, U2], list(Module)):
        fresh, stale = keys.reco_key(cfg, user, module), keys.stale_key(cfg, user, module)
        assert fresh != stale
        generated.update({fresh, stale})
    assert len(generated) == 2 * 2 * 2 * 2


def test_config_version_is_in_both_fresh_and_stale_keys() -> None:
    """Hallazgo F3: un resultado de otra versión nunca se sirve rotulado con la vigente."""
    assert "sha256:a" in keys.reco_key("sha256:a", U1, Module.JUEGOS)
    assert "sha256:a" in keys.stale_key("sha256:a", U1, Module.JUEGOS)
    assert "sha256:a" in keys.fallback_key("sha256:a", Module.JUEGOS)


def test_keys_cannot_be_built_without_a_valid_module() -> None:
    """DI-5: no existe forma de generar una clave de recomendación sin módulo."""
    with pytest.raises((ValueError, TypeError)):
        keys.reco_key("sha256:a", U1, "musica")  # type: ignore[arg-type]
    with pytest.raises((ValueError, TypeError)):
        keys.reco_key("sha256:a", U1, None)  # type: ignore[arg-type]
    assert keys.reco_key("sha256:a", U1, "peliculas") == keys.reco_key("sha256:a", U1, Module.PELICULAS)


def test_other_families() -> None:
    assert keys.filters_key(U1) == f"filters:{U1}"
    assert keys.retired_key(Module.PELICULAS) == "retired:peliculas"
    assert keys.lock_key(U1, Module.JUEGOS) == f"recompute:lock:{U1}:juegos"
    assert keys.dedupe_key(U2) == f"dedupe:event:{U2}"
    assert keys.RECOMPUTE_STREAM == "recompute:requests"
    assert len(keys.FAMILIES) == 8


def test_ttls_come_from_settings_and_retired_window_derives_from_stale(valid_env: dict[str, str]) -> None:
    from recomendaciones.config.settings import load_settings

    ttl = CacheTTLs.from_settings(load_settings())
    assert ttl.filters < ttl.fresh <= ttl.stale
    assert ttl.retired_window == ttl.stale + 86_400  # DI-25: ventana ≥ TTL_STALE, derivada


def _row(version: str, catalog: list[dict], deactivated: datetime | None) -> ConfigRow:
    return ConfigRow(version, {"age_rating_catalog": catalog}, datetime(2026, 1, 1, tzinfo=UTC), deactivated)


def test_readable_versions_share_age_catalog_and_are_recent() -> None:
    now = datetime(2026, 9, 28, tzinfo=UTC)
    rows = [
        _row("sha256:v3", CATALOG, None),  # activa
        _row("sha256:v2", CATALOG, now - timedelta(days=1)),
        _row("sha256:v1", CATALOG, now - timedelta(days=3)),
        _row("sha256:v0", CATALOG, now - timedelta(days=30)),  # desactivada hace más que TTL_STALE
        _row("sha256:vx", OTHER_CATALOG, now - timedelta(hours=2)),  # catálogo etario distinto
    ]
    assert readable_versions("sha256:v3", rows, ttl_stale_seconds=7 * 86_400, now=now) == ("sha256:v2", "sha256:v1")


def test_version_with_different_age_catalog_is_never_readable() -> None:
    now = datetime(2026, 9, 28, tzinfo=UTC)
    rows = [_row("sha256:new", OTHER_CATALOG, None), _row("sha256:old", CATALOG, now - timedelta(minutes=1))]
    assert readable_versions("sha256:new", rows, ttl_stale_seconds=7 * 86_400, now=now) == ()
