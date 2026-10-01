"""Entrypoint del modo demo (`reco-demo api-general|semilla`).

- `reco-demo api-general`: sirve el `api-general` simulado (puerto `RECO_DEMO_PORT`, 8080 por defecto).
- `reco-demo semilla`: declara los gustos de los usuarios de fondo contra la API (`RECO_DEMO_API_URL`).

Usa la misma configuración `RECO_*` que el resto de los procesos: la API key interna y la URL de RabbitMQ.
"""

from __future__ import annotations

import os
import sys

_USO = "uso: reco-demo api-general | semilla"


def run(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] not in (["api-general"], ["semilla"]):
        print(_USO, file=sys.stderr)
        raise SystemExit(2)
    from recomendaciones.config.bootstrap import settings_or_exit

    settings = settings_or_exit("demo")
    api_key = settings.internal_api_key.get_secret_value()
    recomendaciones_url = os.environ.get("RECO_DEMO_API_URL", "http://localhost:8000")
    if args[0] == "semilla":
        from recomendaciones.demo.semilla import run as semilla

        raise SystemExit(semilla(api_key=api_key, recomendaciones_url=recomendaciones_url))

    import uvicorn

    from recomendaciones.demo.api_general_simulada import create_app

    app = create_app(api_key=api_key, amqp_url=settings.amqp_url.get_secret_value(), recomendaciones_url=recomendaciones_url)
    uvicorn.run(app, host=settings.api_host, port=int(os.environ.get("RECO_DEMO_PORT", "8080")))
