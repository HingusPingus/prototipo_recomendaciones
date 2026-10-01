# recomendaciones

Servicio de recomendaciones híbridas **precomputadas** para los módulos `peliculas` y `juegos`: sirve un
top-N ya calculado desde Redis, sin cómputo en la lectura, con filtros de edad y exclusión que no admiten
bypass.

- Especificación: [`specs/001-recomendaciones-precomputadas/`](specs/001-recomendaciones-precomputadas/)
  (`data-model.md` manda en la capa de datos)
- Arquitectura: [`docs/architecture.md`](docs/architecture.md)
- Operación y alertas: [`docs/runbook.md`](docs/runbook.md), [`ops/alerts.yaml`](ops/alerts.yaml)
- Lo que se necesita de `api-general`: [`docs/contracts/required-fields.md`](docs/contracts/required-fields.md)
- Contratos (copias derivadas; los custodia `api-general`):
  [`specs/001-recomendaciones-precomputadas/contracts/`](specs/001-recomendaciones-precomputadas/contracts/)

## Desarrollo

```
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'
cp .env.example .env            # completar; todos los parámetros operativos son obligatorios
.venv/bin/pytest                # los tests de integración levantan Postgres, Redis y RabbitMQ con testcontainers (requiere Docker)
```

Procesos: `reco-api`, `reco-worker`, `reco-transformer` (una corrida) y
`reco-batch popularity|fallback|warmup|age-refresh|purge-signals`.

## Demo local

Stack completo en Docker, con un `api-general` simulado mientras la integración real no está disponible:
[`docs/demo.md`](docs/demo.md). Para probar los endpoints con Postman: [`docs/postman.md`](docs/postman.md).
