"""Entrypoint del Data Transformer (`reco-transformer`)."""

from __future__ import annotations


def run() -> None:
    """Ejecuta una corrida de sincronización. Falla con error explícito si falta configuración.

    `reco-transformer --health` imprime el estado del proceso (Postgres, versión activa) y sale con 0/1:
    un proceso de una corrida no sostiene un servidor HTTP, pero sí una sonda ejecutable (T041).
    """
    import sys

    from recomendaciones.config.bootstrap import settings_or_exit

    settings = settings_or_exit("transformer")
    from recomendaciones.observability.logging import configure_logging

    configure_logging("transformer", secrets=(settings.internal_api_key.get_secret_value(),))
    if "--health" in sys.argv[1:]:
        import json

        from recomendaciones.config.loader import load_engine_config
        from recomendaciones.observability.health import transformer_health
        from recomendaciones.storage.db.session import create_db_engine, session_factory

        factory = session_factory(create_db_engine(settings.database_url.get_secret_value()))
        report = transformer_health(factory=factory, config_version=load_engine_config(settings.engine_config_file).config_version)
        print(json.dumps(report.to_json()))
        raise SystemExit(0 if report.ready else 1)
    from recomendaciones.transformer.runtime import run_once

    raise SystemExit(run_once(settings))
