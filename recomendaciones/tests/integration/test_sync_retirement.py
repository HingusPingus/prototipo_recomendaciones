"""T052 — retiro por sincronización: desaparición = retiro (FR-074, RD-91) y aborto sin retiros (CR-9)."""

from __future__ import annotations

import sqlalchemy as sa

from recomendaciones.config.loader import load_engine_config
from recomendaciones.observability.metrics import Metrics
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.db.filters_source import DbFiltersSource
from recomendaciones.transformer.client import ApiGeneralClient
from recomendaciones.transformer.pipeline import SyncPipeline
from tests.support.api_general_double import ApiGeneralDouble

CFG = load_engine_config("v1.yaml")
KEY = "test.s3cr3t-0123456789abcdef"


def _sync(db_factory, redis_client, double: ApiGeneralDouble):
    cache = CacheClient(redis_client)
    client = ApiGeneralClient("http://api-general.internal", KEY, timeout_seconds=5, transport=double.transport())
    filters = FiltersCache(cache, DbFiltersSource(db_factory), 3600)
    return SyncPipeline(db_factory, client, filters, cache, CFG, Metrics(), volume_delta_ratio=0.9, redelivery_window_hours=48).run()


def _catalog(n: int = 10) -> tuple[ApiGeneralDouble, list]:
    double = ApiGeneralDouble(api_key=KEY, page_size=4)
    double.add_user()
    return double, [double.add_item("peliculas", [f"t{i % 3}"]) for i in range(n)]


def _retired(db_factory) -> set:
    with db_factory() as s:
        return set(s.execute(sa.text("SELECT id FROM items WHERE status = 'retired'")).scalars())


def test_item_absent_from_a_complete_listing_without_explicit_signal_is_retired(db_factory, redis_client) -> None:
    double, items = _catalog()
    assert _sync(db_factory, redis_client, double).status == "success"
    double.items = [r for r in double.items if r["id"] != str(items[0])]
    report = _sync(db_factory, redis_client, double)
    assert report.status == "success" and report.retired == 1
    assert _retired(db_factory) == {items[0]}
    with db_factory() as s:
        retired_at = s.execute(sa.text("SELECT retired_at FROM items WHERE id = :i"), {"i": items[0]}).scalar_one()
    assert retired_at is not None  # retiro lógico: la fila existe, con su marca


def test_listing_truncated_to_half_aborts_and_retires_nothing(db_factory, redis_client) -> None:
    """Test obligatorio de T052: listado truncado al 50 % → cero retirados y corrida abortada con causa."""
    double, _items = _catalog()
    assert _sync(db_factory, redis_client, double).status == "success"
    double.truncate_catalog_to = 5
    report = _sync(db_factory, redis_client, double)
    assert report.status == "failed" and "CR-9" in (report.failure_reason or "")
    assert _retired(db_factory) == set()
    with db_factory() as s:
        reason = s.execute(sa.text("SELECT failure_reason FROM sync_runs WHERE id = :r"), {"r": report.run_id}).scalar_one()
    assert reason and "CR-9" in reason


def test_complete_listing_with_anomalous_volume_drop_aborts_and_retires_nothing(db_factory, redis_client) -> None:
    double, _items = _catalog()
    assert _sync(db_factory, redis_client, double).status == "success"
    double.items = double.items[:5]  # completo según el origen, pero la mitad: ratio 0,5 < 0,9
    report = _sync(db_factory, redis_client, double)
    assert report.status == "failed" and "volumen" in (report.failure_reason or "")
    assert _retired(db_factory) == set()
