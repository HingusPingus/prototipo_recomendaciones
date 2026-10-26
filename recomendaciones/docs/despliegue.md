# Despliegue en Dokploy

Cada merge a `main` que pasa el CI termina desplegado en el servidor, sin pasos manuales:

```
merge a main ──► ci (los gates) ──► deploy: imagen en ghcr.io ──► Dokploy redespliega reco-api y después reco-worker
                     │ si falla un gate
                     └──► no se construye ni se despliega nada
```

- **`.github/workflows/ci.yml`**: los gates de siempre (ver [runbook → CI](runbook.md#ci)).
- **`.github/workflows/deploy.yml`**: arranca cuando `ci` termina en verde sobre un push a `main`. Construye la
  imagen **del commit que pasó el CI**, la publica como `ghcr.io/hinguspingus/recomendaciones` con los tags `main`
  y `sha-<commit>`, y le pide a Dokploy que redespliegue las Applications `reco-api` y `reco-worker`
  (`POST /api/application.deploy`), en ese orden: la API aplica las migraciones al arrancar.

`tests/unit/test_deploy.py` fija estas garantías: si alguien hace que el deploy saltee el CI, despliegue otra rama
o redespliegue el worker antes que la API, el CI falla. La configuración del servidor (variables, credenciales,
bases) vive en Dokploy, no en el repositorio (RD-124).

> **El flujo arranca recién cuando `deploy.yml` esté en `main`.** GitHub solo dispara un workflow encadenado a
> otro si el archivo está en la rama por defecto.

## Qué corre en el servidor

Desde el 2026-10-26 el servicio usa el **`api-general` real**, sin el simulado (RD-124). Todo son servicios de
Dokploy en el mismo proyecto, que se alcanzan entre sí por su **App Name** completo: el nombre que aparece debajo del
título de cada servicio, con el sufijo que agrega Dokploy (por ejemplo `recomeapp-recoapi-gl665j`).

| Servicio | Tipo en Dokploy | Qué es |
|---|---|---|
| `reco-postgres` | Database → PostgreSQL | Nuestra base. Imagen **`pgvector/pgvector:pg16`**: las migraciones usan `pgvector` |
| `reco-redis` | Database → Redis | La caché (INV-2: se reconstruye desde Postgres) |
| `reco-api` | Application | La API de recomendaciones, en el puerto 8000. La llama `api-general` |
| `reco-worker` | Application | Consume eventos, recalcula y corre los jobs periódicos (Schedules) |
| RabbitMQ | Application de `notificaciones` | El broker compartido (RD-120). No es nuestro: se usa con un usuario y un vhost propios |
| `api-general` | Application de `recome-api-general` | La fuente de usuarios, catálogo y actividad (guía en su repo) |

`reco-api` y `reco-worker` usan la misma imagen y el mismo Environment; cambia el comando de arranque.

## Configuración, una sola vez

### 1. Las bases

- **`reco-postgres`**: *Create Service → Database → PostgreSQL*. Database `recomendaciones`, usuario `reco`,
  contraseña al azar con **solo letras y números** (va dentro de una URL), Docker Image `pgvector/pgvector:pg16`.
- **`reco-redis`**: *Create Service → Database → Redis*, imagen `redis:7-alpine`, contraseña al azar con solo letras y
  números.

**Deploy** en cada una: las bases no arrancan solas al crearlas. Su host interno es el *Internal Host* que muestra
cada una.

### 2. Las Applications

*Create Service → Application*, una para `reco-api` y otra para `reco-worker`. En **General**, proveedor **Docker**:

| Campo | Valor |
|---|---|
| Docker Image | `ghcr.io/hinguspingus/recomendaciones:main` (escrito a mano: si el navegador autocompleta algo delante, la descarga falla con `invalid reference format`) |
| Registry URL | `ghcr.io` |
| Username | el usuario de GitHub dueño del token (no el email) |
| Password | un token classic de GitHub con solo `read:packages`. La imagen es **privada** (RD-124); si el token no es de `HingusPingus`, su cuenta necesita rol *Read* en el paquete (*Package settings → Manage access*) |

En **Advanced → Run Command**:

| Application | Run Command |
|---|---|
| `reco-api` | `reco-api-con-migraciones`: aplica las migraciones pendientes y arranca la API |
| `reco-worker` | `reco-worker` |

Dokploy separa el Run Command por espacios sin respetar comillas: un `sh -c "… && …"` le llega partido y falla con
`Unterminated quoted string`. Por eso la API tiene un comando propio de una sola palabra.

### 3. Variables de entorno

En **Environment**, las mismas en las dos Applications:

```
RECO_ENVIRONMENT=produccion
RECO_INTERNAL_API_KEY=produccion.<secreto al azar>
RECO_DATABASE_URL=postgresql+psycopg://reco:<pass de reco-postgres>@<Internal Host de reco-postgres>:5432/recomendaciones
RECO_REDIS_URL=redis://default:<pass de reco-redis>@<Internal Host de reco-redis>:6379/0
RECO_AMQP_URL=amqp://<usuario>:<pass>@<App Name del RabbitMQ>:5672/<vhost>
RECO_API_GENERAL_BASE_URL=http://<App Name de api-general>:8080/api/v1
RECO_ENGINE_CONFIG_FILE=v1.yaml
RECO_TTL_FRESH_SECONDS=86400
RECO_TTL_STALE_SECONDS=604800
RECO_TTL_FILTERS_SECONDS=3600
RECO_TTL_FALLBACK_SECONDS=21600
RECO_TTL_SUPPRESS_SECONDS=300
RECO_TTL_DEDUPE_SECONDS=86400
RECO_IDEMPOTENCY_RETENTION_HOURS=168
RECO_SIGNAL_RETENTION_DAYS=730
RECO_SYNC_VOLUME_DELTA_RATIO=0.9
RECO_INTERACTION_RECALC_THRESHOLD=10
RECO_RECOMPUTE_REQUESTS_MAXLEN=100000
RECO_RECOMPUTE_REQUESTS_MAX_DELIVERIES=5
RECO_EVENT_REDELIVERY_WINDOW_HOURS=24
RECO_RETRY_MAX_ATTEMPTS=5
RECO_RETRY_BACKOFF_BASE_SECONDS=1
RECO_REDIS_TIMEOUT_SECONDS=0.5
RECO_API_GENERAL_TIMEOUT_SECONDS=10
RECO_WARMUP_RATE_PER_SECOND=50
```

- **`RECO_INTERNAL_API_KEY` es una sola clave para los dos sentidos.** En `api-general` va con el mismo valor en
  `RECOMMENDATIONS_SERVICE_API_KEY` (valida lo que le manda nuestro Data Transformer) y en
  `RECOMMENDATIONS_SERVICE_CLIENT_API_KEY` (la manda cuando llama a `reco-api`). Empieza **exactamente** con
  `RECO_ENVIRONMENT` y un punto: si no, el servicio no arranca.
- **El RabbitMQ lo opera `notificaciones`** (RD-120): el usuario, la contraseña y el vhost los dan ellos, con permiso
  para declarar los exchanges `recomendacion.actualizar.v3` y `usuario.eliminado` y sus colas, que el worker declara
  al arrancar. Con el vhost por defecto (`/`), la URL termina en `:5672/`.
- **En `api-general`**, `RECOMMENDATIONS_SERVICE_BASE_URL=http://<App Name de reco-api>:8000`.

### 4. Los jobs periódicos

Los jobs no corren solos: los programa Dokploy. En la Application **`reco-worker`**, pestaña **Schedules**, una
entrada por fila. Las horas son las del servidor (normalmente UTC).

| Nombre | Cron | Comando |
|---|---|---|
| sincronización | `*/15 * * * *` | `reco-transformer` |
| popularidad y respaldo | `0 3 * * *` | `reco-batch popularity && reco-batch fallback` |
| respaldo | `0 */6 * * *` | `reco-batch fallback` |
| refresco etario | `30 3 * * *` | `reco-batch age-refresh` |
| purga de señales | `0 4 * * 0` | `reco-batch purge-signals` |
| supresiones | `0 * * * *` | `reco-batch suppressions` |
| auditoría de declaraciones | `0 5 * * *` | `reco-batch audits` |

Son las frecuencias del [runbook → Jobs periódicos](runbook.md#jobs-periódicos). `reco-batch warmup` no se
programa: se corre a mano después de perder Redis (runbook, «Reconstrucción tras pérdida total de Redis»). Un
schedule corre dentro del contenedor de `reco-worker`: si el worker no está *running*, falla con `Container not
found`.

### 5. GitHub: que el workflow pueda pedir el deploy

En GitHub, **Settings → Secrets and variables → Actions** del repositorio:

| Secret | Valor |
|---|---|
| `DOKPLOY_URL` | La URL del panel de Dokploy |
| `DOKPLOY_API_KEY` | La API key de Dokploy |
| `DOKPLOY_API_APPLICATION_ID` | El `applicationId` de `reco-api`: el último tramo de la URL del servicio en Dokploy (`…/services/application/<applicationId>`) |
| `DOKPLOY_WORKER_APPLICATION_ID` | El de `reco-worker` |

Si falta alguno, el job `dokploy` falla diciendo cuál.

### 6. GitHub: aprobación antes de producción

El Principio V exige aprobación explícita antes de llevar a producción un cambio en la configuración del motor. Un
merge a `main` **es** un deploy, así que el ruleset de `main` tiene que exigir *Require a pull request before
merging* con al menos una aprobación (ver [runbook → CI](runbook.md#ci)).

## Primer despliegue

1. `api-general` desplegado y *running* (guía en su repo).
2. Las bases *running*, después **Deploy** en `reco-api` (migra) y, cuando esté *running*, en `reco-worker`.
3. En `reco-worker`, ejecutar a mano (**Run**) «sincronización» y después «popularidad y respaldo».
4. Verificar como se indica abajo.

## Verificación

No se publica ningún puerto: los servicios se ven por la red interna de Dokploy.

- **Logs de `reco-api`**: `Uvicorn running on http://0.0.0.0:8000`. Las migraciones corren antes **sin imprimir
  nada** (`migrations/env.py` no configura el logging de alembic): si una falla, la API no llega a arrancar y el
  error queda en el log.
- **Logs de `reco-worker`**: arranca sin errores y queda *running*. Es la prueba de que las migraciones corrieron: sin
  ellas, falla con `relation "engine_config_versions" does not exist`.
- **Schedules**: «sincronización» termina con `"status": "success"`. Las primeras corridas después de un deploy de
  `api-general` pueden reintentar («api-general no disponible») mientras él termina de arrancar.

## Problemas conocidos

| Síntoma | Causa |
|---|---|
| Deploy: `denied` al descargar la imagen | Faltan o están mal las credenciales de registry, o la cuenta del token no tiene acceso al paquete |
| Deploy: `invalid reference format` | El campo Docker Image tiene algo antes de `ghcr.io` |
| Logs: `failed to resolve host '<host>'` | Esa base no está desplegada, o la URL no usa su Internal Host exacto |
| Logs: `relation "…" does not exist` | No corrieron las migraciones: redesplegar `reco-api` y revisar que su Run Command sea `reco-api-con-migraciones` |
| Logs: `extension "vector" is not available` | `reco-postgres` no usa la imagen `pgvector/pgvector:pg16` |
| Schedule: `Container not found for application` | `reco-worker` no está *running*: ver sus logs |
| Sincronización: «api-general no disponible» en todos los intentos | `api-general` caído, `RECO_API_GENERAL_BASE_URL` mal (App Name, puerto `8080`, `/api/v1`) o las claves de servicio no coinciden |

## Riesgos abiertos

RD-123 aceptó no tener backups ni alertas evaluadas **mientras corriera el `api-general` simulado**, y fijó como
condición de revisión conectar el real con usuarios de verdad. Esa condición se cumplió el 2026-10-26 (RD-124) sin
que ninguna de las dos estuviera resuelta:

- **Backups de Postgres.** Perder `reco-postgres` pierde las declaraciones, las exclusiones, el historial de señales
  y las constancias de baja, sin forma de recuperarlos. Ya no son datos de la demo.
- **Alertas evaluadas.** `ops/alerts.yaml` no lo evalúa nadie. Una falla se descubre entrando a mirar: el estado de
  las Schedules en Dokploy y los logs.

Lo mínimo es un backup diario de Postgres a un destino externo y alguien que reciba las alertas críticas.

## Eventos

`api-general` todavía no publica eventos (`RECOMMENDATIONS_OUTBOX_ENABLED=false`): las interacciones y las bajas
llegan con la sincronización cada 15 minutos, no al instante. El worker ya escucha en el broker de `notificaciones`.
Para encenderlos, `api-general` se conecta al mismo broker y vhost, se corre la prueba de humo de
[`migracion-v3.md`](contracts/migracion-v3.md) («Cómo lo verificamos») junto con `notificaciones` y `api-general`,
y recién entonces `api-general` activa el outbox v3, con el v2 apagado.

## Volver a una versión anterior

Cada imagen queda publicada con el tag del commit (`sha-<commit completo>`). En las dos Applications, cambiar la
Docker Image a `ghcr.io/hinguspingus/recomendaciones:sha-<commit>` y apretar **Deploy**, primero en `reco-api`. Para
volver a seguir `main`, restaurar el tag `main`. Si el problema está en el código, lo correcto es revertir el commit
en `main` por PR: el flujo redespliega solo.

**Cuidado con las migraciones.** Cada arranque de `reco-api` corre `alembic upgrade head`, y volver a una imagen
anterior no deshace nada: si esa imagen es de antes de una migración, la base queda adelante del código. Para
bajarla hay que correr `alembic downgrade <revisión>` a mano (por ejemplo, con un schedule temporal en
`reco-worker`), y **algunas bajadas borran datos**: la `0006`, por ejemplo, borra las recepciones de bajas. Por eso,
ante un problema, conviene revertir por PR en lugar de volver a una imagen anterior a una migración.
