"""Proceso `reco-sync-usuarios`: materializa usuarios nuevos cada `RECO_SYNC_USERS_INTERVAL_SECONDS` (RD-128).

Es parte del Data Transformer: lee de `api-general` y escribe la proyección `users`, por el único módulo autorizado
(`pipeline.py`, DI-13). Solo inserta usuarios que todavía no existen; la sincronización completa (`reco-transformer`,
cada 5 minutos) sigue siendo la autoridad para todo lo demás. Si este proceso no corre, nada se rompe: las cuentas nuevas
vuelven a esperar a la próxima sincronización completa.

El log no se inunda: una vuelta sin novedades no escribe nada, una racha de fallas escribe una sola advertencia y la
recuperación una línea.
"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

from prometheus_client import start_http_server

from recomendaciones.bootstrap import Runtime, build_runtime
from recomendaciones.config.settings import Settings
from recomendaciones.transformer.client import ApiGeneralClient
from recomendaciones.transformer.pipeline import NewUserMaterializer, NewUsersReport

log = logging.getLogger(__name__)


class _Materializer(Protocol):
    def run_once(self) -> NewUsersReport: ...


class NewUsersLoop:
    """Una vuelta, y después una por intervalo hasta que `stop` se active. Una vuelta fallida nunca termina el lazo."""

    def __init__(self, materializer: _Materializer, *, interval_seconds: float, stop: threading.Event) -> None:
        self._materializer = materializer
        self._interval = interval_seconds
        self._stop = stop
        self._failing = False

    def run(self) -> None:
        self._tick()
        while not self._stop.wait(self._interval):
            self._tick()

    def _tick(self) -> None:
        try:
            report = self._materializer.run_once()
        except Exception:  # noqa: BLE001 — base o caché caídas: la próxima vuelta reintenta
            self._failed("error inesperado", exc_info=True)
            return
        if report.status == "failed":
            self._failed(report.reason or "falla sin detalle", exc_info=False)
            return
        if self._failing:
            self._failing = False
            log.info("sincronización de usuarios nuevos recuperada")
        if report.status == "inserted":
            log.info("usuarios nuevos materializados", extra={"inserted": report.inserted})

    def _failed(self, reason: str, *, exc_info: bool) -> None:
        if self._failing:
            return
        self._failing = True
        log.warning(
            "sincronización de usuarios nuevos fallando; se reintenta cada %ss sin volver a avisar hasta recuperarse",
            self._interval,
            extra={"reason": reason},
            exc_info=exc_info,
        )


def serve(
    settings: Settings,
    *,
    stop: threading.Event | None = None,
    transport=None,  # noqa: ANN001 — httpx.BaseTransport para tests
    runtime: Runtime | None = None,
) -> None:
    """Corre el lazo hasta que `stop` se active. Sin `runtime` arma el propio y expone métricas en `RECO_METRICS_PORT`."""
    if runtime is None:
        runtime = build_runtime(settings, "sync-usuarios")
        start_http_server(settings.metrics_port, registry=runtime.metrics.registry)
    client = ApiGeneralClient(
        settings.api_general_base_url,
        settings.internal_api_key.get_secret_value(),
        timeout_seconds=settings.api_general_timeout_seconds,
        transport=transport,
    )
    try:
        materializer = NewUserMaterializer(runtime.factory, client, runtime.config, runtime.metrics)
        log.info(
            "reco-sync-usuarios en marcha",
            extra={"interval_seconds": settings.sync_users_interval_seconds, "config_version": runtime.config.config_version},
        )
        NewUsersLoop(materializer, interval_seconds=settings.sync_users_interval_seconds, stop=stop or threading.Event()).run()
    finally:
        client.close()
