# Imagen única del servicio `recomendaciones`: todos los procesos salen de acá y el comando elige cuál corre.
#
#   reco-api                          API de lectura (puerto 8000; métricas en 9100)
#   reco-worker                       consumidor de eventos y recálculo (salud en 8081; métricas en 9100)
#   reco-transformer                  una corrida de sincronización con api-general
#   reco-batch <job>                  popularity | fallback | warmup | age-refresh | purge-signals | suppressions | audits
#   alembic upgrade head              migraciones de DB Recomendaciones
#   reco-demo api-general | semilla   solo demo: api-general simulado (docs/demo.md)
#
# Toda la configuración llega por variables RECO_* (ver .env.example): la imagen no trae credenciales.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
# Falla el build si el wheel no trae los archivos de datos que el servicio lee en tiempo de ejecución.
RUN pip install . \
 && python -c "import pathlib, recomendaciones as r; p = pathlib.Path(r.__file__).parent; \
assert (p / 'config/engine_config/v1.yaml').is_file(), 'falta engine_config/v1.yaml'; \
assert (p / 'worker/contracts/recomendacion-actualizar-v3.schema.json').is_file(), 'faltan los schemas del worker'" \
 && rm -rf src

COPY alembic.ini ./
COPY migrations ./migrations

RUN useradd --system --no-create-home --uid 10001 reco
USER reco

EXPOSE 8000
CMD ["reco-api"]
