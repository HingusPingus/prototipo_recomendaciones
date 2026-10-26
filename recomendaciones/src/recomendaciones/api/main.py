"""Entrypoint de la API (`reco-api`)."""

from __future__ import annotations


def run() -> None:
    """Arranca la API. Falla con error explícito si falta configuración (T001, FR-027)."""
    import uvicorn

    from recomendaciones.config.bootstrap import settings_or_exit

    settings = settings_or_exit("api")
    from recomendaciones.observability.logging import configure_logging

    configure_logging("api", secrets=(settings.internal_api_key.get_secret_value(),))
    from prometheus_client import start_http_server

    from recomendaciones.api.app import build_services, create_app

    services = build_services(settings)
    start_http_server(settings.metrics_port, registry=services.metrics.registry)  # puerto propio, no una ruta (FR-060)
    uvicorn.run(create_app(settings, services), host=settings.api_host, port=settings.api_port)


def run_with_migrations() -> None:
    """`reco-api-con-migraciones`: aplica las migraciones pendientes y arranca la API (RD-124).

    Es el Run Command de la Application `reco-api` en Dokploy, que separa ese campo por espacios sin respetar
    comillas: no admite `sh -c "alembic upgrade head && reco-api"`. Si una migración falla, alembic termina el
    proceso y la API no arranca sobre un esquema a medias.
    """
    from alembic.config import main as alembic

    alembic(argv=["upgrade", "head"])
    run()
