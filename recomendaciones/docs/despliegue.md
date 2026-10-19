# Despliegue en Dokploy

Cada merge a `main` que pasa el CI termina desplegado en el servidor, sin pasos manuales:

```
merge a main ──► ci (los nueve gates) ──► deploy: imagen en ghcr.io ──► Dokploy descarga la imagen y redespliega
                     │ si falla un gate
                     └──► no se construye ni se despliega nada
```

- **`.github/workflows/ci.yml`**: los gates de siempre (ver [runbook → CI](runbook.md#ci)).
- **`.github/workflows/deploy.yml`**: arranca cuando `ci` termina en verde sobre un push a `main`. Construye la
  imagen **del commit que pasó el CI**, la publica como `ghcr.io/hinguspingus/recomendaciones` con los tags `main`
  y `sha-<commit>`, y le pide a Dokploy que redespliegue (`POST /api/compose.deploy`).
- **[`docker-compose.dokploy.yml`](../docker-compose.dokploy.yml)**: el stack del servidor. Son los mismos
  servicios que la demo local, con el **api-general simulado** mientras el real no tenga datos (decisión del
  2026-10-19). Toma la imagen publicada, sin credenciales escritas, con Postgres y RabbitMQ en volúmenes y los
  puertos solo en el loopback del servidor.

`tests/unit/test_deploy.py` fija estas garantías: si alguien hace que el deploy saltee el CI, despliegue otra rama
o escriba una credencial en el compose, el CI falla.

> **El flujo arranca recién cuando `deploy.yml` esté en `main`.** GitHub solo dispara un workflow encadenado a
> otro si el archivo está en la rama por defecto. Mientras `dev` no pase a `main`, no se despliega nada.

## Configuración, una sola vez

### 1. Dokploy: el servicio Compose

En Dokploy: **Create Project**, y dentro **Create Service → Compose**.

| Campo | Valor |
|---|---|
| Compose Type | `Docker Compose` (no `Stack`) |
| Provider | GitHub, repositorio `HingusPingus/prototipo_recomendaciones`, rama `main` |
| Compose Path | `./recomendaciones/docker-compose.dokploy.yml` |
| **Autodeploy** | **Desactivado.** Si queda activo, Dokploy despliega en cada push, antes de que termine el CI y con la imagen anterior. El deploy lo pide `deploy.yml` |

El compose se lee del repositorio en cada deploy, así que sus cambios llegan por PR como cualquier otro archivo.

### 2. Dokploy: variables de entorno

En el servicio, pestaña **Environment**. Las cuatro primeras son obligatorias: sin ellas el deploy falla con un
mensaje que dice cuál falta.

| Variable | Valor |
|---|---|
| `RECO_ENVIRONMENT` | Nombre del entorno, por ejemplo `produccion` |
| `RECO_INTERNAL_API_KEY` | `<RECO_ENVIRONMENT>.<secreto>`, por ejemplo `produccion.` seguido de 32 caracteres al azar. El api-general simulado usa la misma |
| `POSTGRES_PASSWORD` | Al azar. **Solo letras y números**: va dentro de una URL de conexión |
| `RABBITMQ_PASSWORD` | Al azar. **Solo letras y números**, por la misma razón |
| `RECO_IMAGE_TAG` | Opcional. Por defecto `main`; `sha-<commit>` fija una versión (ver «Volver a una versión anterior») |
| `RECO_API_PORT`, `RECO_DEMO_PORT`, `RECO_RABBITMQ_CONSOLE_PORT` | Opcionales. Puertos en el loopback del servidor; por defecto `18000`, `18080` y `15672` |

Las contraseñas de Postgres y RabbitMQ se fijan **la primera vez** que se crean sus volúmenes. Cambiarlas después
en Dokploy no cambia la del servicio, y la conexión falla.

### 3. Dokploy: los jobs periódicos

Los jobs no corren solos: los programa Dokploy. En el servicio, pestaña **Schedules**, una entrada por fila, todas
con servicio **`worker`** y shell **`bash`**. Las horas son las del servidor (normalmente UTC).

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
programa: se corre a mano después de perder Redis (runbook, «Reconstrucción tras pérdida total de Redis»).

### 4. GitHub: que Dokploy pueda descargar la imagen

La imagen es **pública** (decisión del 2026-10-19: el repositorio ya lo es y la imagen no tiene credenciales).
GitHub crea el paquete **privado** la primera vez que `deploy.yml` lo publica, así que hay que cambiarlo una vez:
en el perfil, **Packages → `recomendaciones` → Package settings → Change visibility → Public**. Hasta hacerlo,
el deploy de Dokploy falla al descargarla.

### 5. GitHub: que el workflow pueda pedir el deploy

En Dokploy, **Settings → Profile → API/CLI → Generate**, para crear una API key. El `composeId` está en la URL
del servicio Compose en Dokploy, o en `GET <dokploy>/api/project.all` con el header `x-api-key`.

En GitHub, **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Valor |
|---|---|
| `DOKPLOY_URL` | La URL del panel de Dokploy, por ejemplo `https://dokploy.ejemplo.com` |
| `DOKPLOY_API_KEY` | La API key generada |
| `DOKPLOY_COMPOSE_ID` | El `composeId` del servicio |

### 6. GitHub: aprobación antes de producción

El Principio V exige aprobación explícita antes de llevar a producción un cambio en la configuración del motor.
Desde ahora un merge a `main` **es** un deploy, así que hay que activar en el ruleset de `main` *Require a pull
request before merging* con al menos una aprobación (ver [runbook → CI](runbook.md#ci)). Sin eso, un merge
sin revisión llega al servidor.

## Primer despliegue

1. Pasar `dev` a `main` por PR. El CI corre, `deploy.yml` publica la imagen y pide el deploy.
2. Ese primer deploy falla al descargar la imagen, porque todavía es privada: hacer el paso 4 de arriba y apretar
   **Deploy** en Dokploy.
3. Verificar como se indica abajo.

## Verificación

Los puertos se publican solo en el loopback del servidor, así que se entra por túnel SSH:

```
ssh -L 18000:127.0.0.1:18000 -L 18080:127.0.0.1:18080 -L 15672:127.0.0.1:15672 <usuario>@<servidor>
```

- `curl http://localhost:18000/health/ready`: `200` con Postgres y Redis en `ok`.
- `http://localhost:18080/docs`: el Swagger de la demo, con el mismo recorrido que [demo.md](demo.md).
- `http://localhost:15672`: la consola de RabbitMQ, usuario `reco` y la `RABBITMQ_PASSWORD` del entorno.
- En Dokploy, pestaña **Schedules**: cada job tiene su última corrida exitosa.

## Riesgos aceptados

Dos cosas que este servidor **no** tiene, aceptadas mientras corra con el `api-general` simulado (RD-123):

- **Backups de Postgres.** Perder el volumen pierde las declaraciones, las exclusiones, el historial de señales y
  las constancias de baja, sin forma de recuperarlos. Hoy son datos de la demo.
- **Alertas evaluadas.** `ops/alerts.yaml` no lo evalúa nadie. Una falla se descubre entrando a mirar: el estado de
  las Schedules en Dokploy, los logs y `/health/ready`.

Las dos se revisan **antes de conectar el `api-general` real** con usuarios de verdad.

## Volver a una versión anterior

Cada imagen queda publicada con el tag del commit (`sha-<commit completo>`). En Dokploy, poner
`RECO_IMAGE_TAG=sha-<commit>` en **Environment** y apretar **Deploy**. Para volver a seguir `main`, borrar la
variable. Si el problema está en el código, lo correcto es revertir el commit en `main` por PR: el flujo
redespliega solo.

**Cuidado con las migraciones.** Cada deploy corre `alembic upgrade head`, y volver a una imagen anterior no deshace
nada: si esa imagen es de antes de una migración, la base queda adelante del código. Para bajarla hay que correr
`alembic downgrade <revisión>` a mano en el contenedor `worker`, y **algunas bajadas borran datos**: la `0006`, por
ejemplo, borra las recepciones de bajas. Por eso, ante un problema, conviene revertir por PR en lugar de volver a
una imagen anterior a una migración.

## Pasar al api-general real

Cuando el api-general real tenga datos (ver [demo.md → «Cuando esté el `api-general` real»](demo.md#cuando-esté-el-api-general-real)),
el servidor deja de usar el simulado **y también su propio RabbitMQ**. Hoy el compose trae un RabbitMQ porque el
simulado publica ahí, pero el broker oficial lo opera `notificaciones` (RD-120), y el api-general real publica en
**ese** broker. Si nuestro worker siguiera escuchando el RabbitMQ propio, no le llegaría ningún evento: ni las
interacciones ni las bajas.

El orden importa:

1. **Resolver los dos riesgos aceptados** (RD-123): un backup diario de Postgres a un destino externo y alguien que
   reciba las alertas críticas. Con usuarios reales, los datos dejan de ser regenerables.
2. **Coordinar con `notificaciones`**: el vhost del entorno, un usuario para el worker con los permisos de RD-120, y
   que el servidor pueda llegar a su broker (host y puerto 5672).
3. **Vaciar el RabbitMQ propio** antes de sacarlo: la cola principal y las DLQ en cero (consola de RabbitMQ, por
   túnel). Lo que quede ahí se pierde con su volumen. La DLQ de `usuario.eliminado` **nunca** se descarta: se
   reprocesa primero (runbook, «Reproceso desde DLQ»).
4. **Un PR que cambie el compose del servidor**:
   - sacar `api-general-simulada`, `semilla-declaraciones` y `rabbitmq` (con su volumen y sus `depends_on`);
   - `RECO_AMQP_URL` pasa a venir completa del entorno de Dokploy (`${RECO_AMQP_URL:?…}`), con el host, el usuario
     y el vhost del broker de `notificaciones`, en lugar de armarse con `RABBITMQ_PASSWORD`;
   - apuntar `RECO_API_GENERAL_BASE_URL` a su servicio, con `/api/v1` (los dos stacks en una misma red de Docker);
   - bajar `RECO_INTERACTION_RECALC_THRESHOLD` a `10`, el valor de producción;
   - actualizar `tests/unit/test_deploy.py`, que hoy fija el stack con el simulado y el RabbitMQ propio.
5. **Desplegar**. El worker arranca y declara en el broker de `notificaciones` los exchanges
   `recomendacion.actualizar.v3` y `usuario.eliminado` y sus colas.
6. **Correr la prueba de humo** de [`migracion-v3.md`](contracts/migracion-v3.md) («Cómo lo verificamos») junto con
   `notificaciones` y `api-general`. Recién entonces `api-general` activa `RECOMMENDATIONS_OUTBOX_ENABLED=true`,
   con el v2 apagado.

La demo local (`docker-compose.yml`) sigue usando su propio RabbitMQ: este cambio es solo para el servidor.
