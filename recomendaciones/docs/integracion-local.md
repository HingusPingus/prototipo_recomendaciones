# Integración local con el `api-general` real

Cómo correr este servicio contra el `api-general` real en una sola máquina, sin el simulado de la demo. Es el lado
de `recomendaciones` de la prueba que `api-general` describe en su spec 007 («Integración local E2E»). Usa
[`docker-compose.integracion.yml`](../docker-compose.integracion.yml).

Verificado el 2026-10-26 contra `api-general` en `878fe55`, con su aplicación unida a la red compartida: el
worker declara su topología y queda sano, y una sincronización contra un catálogo de prueba cargado por su API
terminó en `success`, con los ítems, la clasificación literal y los tags materializados.

## Qué hay en el stack

| Servicio | Red | Para qué |
|---|---|---|
| `postgres`, `redis` | `interna` | Nuestras bases. **No** están en la red compartida: `api-general` también tiene un servicio `postgres`, y en una red común ese nombre sería ambiguo |
| `rabbitmq` | `recome-integracion` | El broker de la prueba. `api-general` publica acá por la red; el puerto 5672 no se publica en el host |
| `worker` | las dos | Declara los exchanges `recomendacion.actualizar.v3` y `usuario.eliminado` y sus colas al arrancar. Su estado *healthy* (`/health/ready` en 8081) significa que Redis, Postgres y el broker responden |
| `api` | las dos | La API de recomendaciones, en `127.0.0.1:8000` |
| `sincronizacion` | las dos | El Data Transformer y los jobs del respaldo. **No arranca con `up`**: se corre a pedido |

La red compartida se llama `recome-integracion`. La crea este compose; `api-general` se une a ella como red
externa, con su servicio alcanzable como **`api-general`** en el puerto 8080 (`RECO_API_GENERAL_BASE_URL` es
`http://api-general:8080/api/v1`).

No hay volúmenes: cada corrida arranca con la base vacía. Una base con datos del simulado haría abortar la primera
sincronización contra el real, porque su catálogo chico se leería como una caída de volumen (`SyncVolumeDrop`).

## Las variables de la corrida

Van en un archivo `.env.integracion` en esta carpeta (Git lo ignora). Los valores se generan para cada corrida y
no se comparten por chat ni se versionan:

```bash
{
  echo "RECO_ENVIRONMENT=test"
  echo "RECO_INTERNAL_API_KEY=test.$(openssl rand -hex 24)"
  echo "RABBITMQ_USER=reco"
  echo "RABBITMQ_PASSWORD=$(openssl rand -hex 16)"
} > .env.integracion
```

- `RECO_INTERNAL_API_KEY` empieza **exactamente** con `RECO_ENVIRONMENT` y un punto, y el secreto tiene al menos 16
  caracteres: si no, el servicio no arranca. `test` es el entorno que usa la spec 007.
- **Es una sola clave para los dos sentidos.** `api-general` la carga con el mismo valor en
  `RECOMMENDATIONS_SERVICE_API_KEY`, que valida lo que le llega, y nuestro Transformer la manda en
  `X-Internal-API-Key`.
- `api-general` usa las mismas credenciales de RabbitMQ: `SPRING_RABBITMQ_HOST=rabbitmq`,
  `SPRING_RABBITMQ_USERNAME` y `SPRING_RABBITMQ_PASSWORD`. Sin eso intenta `localhost` con `guest`.

## El orden

El orden importa por dos razones: el worker tiene que haber declarado su topología antes de que `api-general`
publique, y un evento de un usuario o un ítem que todavía no sincronizamos se descarta como
`skipped_not_materialized` (la señal se recupera después por la sincronización de actividad, pero la prueba del
evento daría un falso negativo).

1. **Nuestro stack primero:**
   ```bash
   docker compose -f docker-compose.integracion.yml --env-file .env.integracion up -d --build --wait
   ```
   `--wait` vuelve cuando el worker está *healthy*: la topología ya está declarada.
2. **`api-general`**, con su overlay de la spec 007: unido a `recome-integracion`, con la misma clave, las
   credenciales de RabbitMQ y la publicación **apagada** (`RECOMMENDATIONS_OUTBOX_ENABLED=false`,
   `RECOMMENDATIONS_OUTBOX_V2_ENABLED=false`). Crea sus datos sintéticos: el usuario con su perfil verificado, los
   ítems con clasificación y tags elegibles, y la interacción, que deja el evento v3 esperando en su outbox.
3. **Nuestra sincronización**, cuando esos datos ya existen:
   ```bash
   docker compose -f docker-compose.integracion.yml --env-file .env.integracion run --rm sincronizacion
   ```
   Termina con código 0 si la corrida fue `success`. Si falla, el motivo está en `sync_runs.failure_reason`
   ([runbook → CatalogSyncStale](runbook.md#catalogsyncstale)).
4. **`api-general` activa la publicación**, solo v3 (`RECOMMENDATIONS_OUTBOX_ENABLED=true`, v2 apagado).
5. **Ver que el worker procesó el evento**, sin entrar a nuestra base: en `http://worker:9100/metrics`, desde un
   contenedor de la red `recome-integracion`,
   - `signal_ingest_lag_seconds_count{source="evento"}` sube cuando el worker registra la señal de un evento;
   - `reco_recompute_total` sube cuando recalcula.

   Antes del primer evento esas series **no aparecen**: que falten significa cero, no un error. Por ejemplo:
   ```bash
   docker run --rm --network recome-integracion curlimages/curl -s http://worker:9100/metrics \
     | grep -E '^signal_ingest_lag_seconds_count|^reco_recompute_total'
   ```

## Ver una recomendación (opcional)

La prueba de la spec 007 termina en el procesamiento del evento. Para ver además una recomendación por nuestra API:

- El módulo necesita **al menos 5 tags declarables**: tags que tenga algún ítem **activo** del módulo. Con menos,
  nadie puede declarar sus gustos ahí. `declarable_tags_total{module}` en `http://worker:9100/metrics` lo muestra.
- El usuario declara sus gustos: `POST /internal/v1/declarations/{user_id}` en `http://localhost:8000`, con la clave
  interna (ver [postman.md](postman.md)). Sin declaración, la lectura responde `412 declaration_required`.
- Después, `GET /internal/v1/recommendations/{user_id}?module=…`.

## Limpieza

Primero se baja `api-general`, que está conectado a nuestra red; después nuestro stack:

```bash
docker compose -f docker-compose.integracion.yml --env-file .env.integracion down -v
rm .env.integracion
```

`down -v` borra la red `recome-integracion` y todos los datos de la corrida. No toca el stack de la demo
(`docker-compose.yml`), que es otro proyecto de Docker.

## Lo que no cubre

- **La baja de cuenta** (`usuario.eliminado`) y la consulta de su recepción: la spec 007 las deja fuera.
- **El servidor de Dokploy**: allá el broker es el de `notificaciones` (ver
  [despliegue.md → «Pasar al api-general real»](despliegue.md#pasar-al-api-general-real)).
