"""T050 — latencia de lectura y SC-001: p95 ≤ 50 ms medido en el servicio, con el catálogo a 10× (RD-105).

Bajo demanda y antes de release, **no** es gate de CI (`-m performance`; `addopts` lo excluye):

    pytest -m performance tests/performance -s

La aserción clave es la **independencia respecto del tamaño del catálogo**: si la latencia creciera con él,
habría cómputo en el request path (INV-1). El valor absoluto depende del hardware y se reporta con él en
`docs/validation/performance-report.md`. La latencia se mide alrededor de la llamada HTTP del `TestClient`,
en el mismo proceso que la aplicación: incluye el enrutamiento y la serialización, no la red.

- **Caché poblada**: `reco:`, `filters:` y `retired:` presentes (el camino normal).
- **Caché fría**: `filters:{user}` y `retired:{module}` borrados antes de cada solicitud, que así repuebla
  desde Postgres —el único acceso a la base que INV-1 admite en la lectura—. El top-N sigue presente: sin
  él no hay nada que medir más que el `empty_pending`.
"""

from __future__ import annotations

import json
import os
import platform
import random
import statistics
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry
from tests.conftest import VALID_ENV
from tests.performance.fixtures.catalog_10x import MODULES, Population, declare_sample, grow, item_id, user_id

pytestmark = pytest.mark.performance

HEADERS = {"X-Internal-API-Key": VALID_ENV["RECO_INTERNAL_API_KEY"]}
SAMPLE_USERS = 300
REQUESTS = 1_500
SC_001_P95_MS = 50.0
RESULTS = Path(os.environ.get("RECO_PERF_RESULTS", Path(__file__).with_name("results.json")))


def _percentiles(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    q = statistics.quantiles(ordered, n=100, method="inclusive")
    return {"p50": round(q[49], 2), "p95": round(q[94], 2), "p99": round(q[98], 2), "max": round(ordered[-1], 2), "n": len(ordered)}


def _write_entries(services, sample: list[uuid.UUID], items_per_module: int, rng: random.Random) -> None:
    repo = services.read_service._repository
    cfg = services.engine_config.config_version
    for user in sample:
        for module in MODULES:
            chosen = rng.sample(range(items_per_module), 50)
            repo.write_personalized(
                RecommendationEntry(
                    user, Module(module), cfg, "perf", 2, datetime.now(UTC),
                    tuple(CachedItem(item_id(module, n), rank, 1.0 - rank / 100, 0) for rank, n in enumerate(chosen, start=1)),
                )
            )


def _measure(client, redis_client, sample: list[uuid.UUID], *, cold: bool) -> list[float]:
    latencies = []
    for i in range(REQUESTS):
        user, module = sample[i % len(sample)], MODULES[(i // len(sample)) % 2]
        if cold:
            redis_client.delete(keys.filters_key(user), keys.retired_key(module))
        started = time.perf_counter()
        response = client.get(f"/internal/v1/recommendations/{user}", params={"module": module, "top_n": 20}, headers=HEADERS)
        latencies.append((time.perf_counter() - started) * 1000)
        assert response.status_code == 200 and response.json()["result_type"] == "personalized", response.text
    return latencies


def _hardware() -> dict[str, str]:
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")), platform.processor())
    mem_kb = next((int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemTotal")), 0)
    return {"cpu": cpu, "cores": str(os.cpu_count()), "memory_gib": f"{mem_kb / 1024 / 1024:.1f}", "os": platform.platform(), "python": platform.python_version()}


def test_read_latency_is_independent_of_catalog_size_and_meets_sc001(api, db_factory, redis_client) -> None:
    client, services = api
    engine = sa.create_engine(db_factory.url)
    population = Population(services.engine_config.config_version)
    rng = random.Random(7)
    sample = [user_id(n) for n in range(SAMPLE_USERS)]
    results: dict[str, dict] = {"hardware": _hardware(), "requests_per_scenario": REQUESTS, "sample_users": SAMPLE_USERS}
    for factor in (1, 10):
        started = time.perf_counter()
        scale = grow(engine, population, factor)
        if factor == 1:
            declare_sample(engine, population, sample)
        _write_entries(services, sample, scale.items_per_module, rng)
        generation_s = time.perf_counter() - started
        with engine.connect() as conn:
            retired = conn.execute(sa.text("SELECT module::text, count(*) FROM items WHERE status = 'retired' GROUP BY 1")).all()
        _measure(client, redis_client, sample[:50], cold=False)  # calentamiento del proceso
        warm = _percentiles(_measure(client, redis_client, sample, cold=False))
        cold = _percentiles(_measure(client, redis_client, sample, cold=True))
        results[f"{factor}x"] = {
            "items_per_module": scale.items_per_module, "users": scale.users, "retired_in_window": dict(retired),
            "generation_seconds": round(generation_s, 1), "warm_ms": warm, "cold_ms": cold,
        }
    engine.dispose()
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    base, big = results["1x"]["warm_ms"]["p95"], results["10x"]["warm_ms"]["p95"]
    assert big <= SC_001_P95_MS, f"SC-001: p95 a 10× = {big} ms > {SC_001_P95_MS} ms"
    assert big <= max(1.5 * base, base + 5.0), f"la latencia crece con el catálogo: p95 {base} ms (1×) → {big} ms (10×)"
    # El repoblado ante miss es acceso a datos materializados que INV-1 admite; aun así no debe crecer con el
    # catálogo: la consulta de `retired:` está acotada por la ventana (RD-39), no por el histórico.
    cold_base, cold_big = results["1x"]["cold_ms"]["p95"], results["10x"]["cold_ms"]["p95"]
    assert cold_big <= SC_001_P95_MS
    assert cold_big <= max(1.5 * cold_base, cold_base + 5.0), f"el repoblado crece con el catálogo: p95 {cold_base} → {cold_big} ms"
