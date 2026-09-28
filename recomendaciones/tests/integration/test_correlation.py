"""T040 — logging estructurado con correlation ID que sobrevive al salto asíncrono (FR-046, Principio VII)."""

from __future__ import annotations

import io
import json
import logging

from recomendaciones.observability.logging import JsonFormatter, configure_logging, correlation_scope
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from tests.contract.conftest import auth
from tests.integration import seed

SECRET = "test.s3cr3t-0123456789abcdef"


def _capture(secrets: tuple[str, ...] = (SECRET,)) -> tuple[logging.Handler, io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(component="test", secrets=secrets))
    return handler, stream


def test_json_lines_with_stable_fields_and_no_secrets() -> None:
    handler, stream = _capture()
    log = logging.getLogger("recomendaciones.test.json")
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        with correlation_scope("corr-123"):
            log.info("procesado %s", "x", extra={"event_id": "e-1", "reco_module": "juegos", "config_version": "sha256:v1"})
            log.warning(f"la key filtrada por error: {SECRET}")
    finally:
        log.removeHandler(handler)
    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert {"timestamp", "level", "logger", "message", "component", "correlation_id"} <= set(lines[0])
    assert lines[0]["correlation_id"] == "corr-123" and lines[0]["event_id"] == "e-1"
    assert lines[0]["config_version"] == "sha256:v1" and lines[0]["message"] == "procesado x"
    assert SECRET not in stream.getvalue()


def test_correlation_id_travels_api_to_stream_to_worker(api, valid_env, db_factory, redis_client) -> None:  # noqa: ANN001
    """Un ID emitido en la API aparece en el log del worker que procesa la solicitud derivada."""
    from recomendaciones.config.loader import ENGINE_CONFIG_DIR, load_engine_config
    from recomendaciones.observability.metrics import Metrics
    from recomendaciones.storage.cache.client import CacheClient
    from recomendaciones.storage.cache.repository import RecommendationRepository
    from recomendaciones.worker.handler import Recomputer
    from recomendaciones.worker.requests_stream import RecomputeRequestConsumer

    configure_logging("test", secrets=(SECRET,))
    client, _ = api
    with db_factory.begin() as s:
        user = seed.user(s)
        for tag in ("horror", "drama", "comedia", "scifi", "western"):
            seed.item(s, "peliculas", [tag])
        seed.declare(s, user, "peliculas", ["horror", "drama", "comedia", "scifi", "western"])
        seed.vectorize_all(s)
    headers = {**auth(valid_env), "X-Correlation-ID": "corr-desde-api-general"}
    response = client.get(f"/internal/v1/recommendations/{user}", params={"module": "peliculas"}, headers=headers)
    assert response.headers["X-Correlation-ID"] == "corr-desde-api-general"
    entry = redis_client.xrange(keys.RECOMPUTE_STREAM)[0][1]
    assert entry["correlation_id"] == "corr-desde-api-general"

    handler, stream = _capture()
    logging.getLogger("recomendaciones").addHandler(handler)
    try:
        cache = CacheClient(redis_client)
        repo = RecommendationRepository(cache, ttl_fresh=86_400, ttl_stale=604_800, ttl_fallback=21_600)
        cfg = load_engine_config(ENGINE_CONFIG_DIR / "v1.yaml")
        RecomputeRequestConsumer(cache, Recomputer(db_factory, repo, cfg, Metrics()), Metrics(), consumer_name="w", max_deliveries=5, block_ms=10).poll_once()
    finally:
        logging.getLogger("recomendaciones").removeHandler(handler)
    worker_lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert any(line.get("correlation_id") == "corr-desde-api-general" for line in worker_lines), worker_lines
    assert repo.read_fresh(cfg.config_version, user, Module.PELICULAS) is not None


def test_api_generates_a_correlation_id_when_absent(api, valid_env) -> None:  # noqa: ANN001
    client, _ = api
    response = client.get("/internal/v1/recommendations/not-a-uuid", params={"module": "peliculas"}, headers=auth(valid_env))
    assert response.headers.get("X-Correlation-ID")
