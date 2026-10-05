# Runbook — `recomendaciones`

Guía operativa del servicio de recomendaciones precomputadas. Una sección por alerta de
`ops/alerts.yaml` (T042) con su **primer paso de diagnóstico**, y los procedimientos operativos (T046).

Componentes y puertos: API (8000, salud en `/health`, `/health/live`, `/health/ready`), métricas de los
tres procesos en `:9100/metrics`, salud del worker en `:8081`, Data Transformer como proceso de una
corrida (`reco-transformer`, sonda `reco-transformer --health`), jobs con `reco-batch <job>`.

Escalamiento general: **guardia de plataforma** → responsable del repo → equipo de `api-general` (si la
causa está en el origen de datos o en un contrato) o de `notificaciones` (si está en el broker).

---

## Alertas

### CatalogSyncStale
**Qué significa**: no hubo sincronización exitosa en más de 26 h; altas y retiros del catálogo no se
reflejan.
**Primer paso**: `SELECT id, status, failure_reason, started_at FROM sync_runs ORDER BY id DESC LIMIT 5;`
— si hay `failed`, leer `failure_reason`; si la última está `running` sin `finished_at`, la corrida se
interrumpió.
**Acción**: `api-general no disponible` → verificar su salud y reintentar (`reco-transformer`); `listado
no confirmado completo` o `volumen anómalo` → ver [SyncVolumeDrop](#syncvolumedrop); violaciones de
contrato → ver [ContractViolationRegion](#contractviolationregion).
Si `api-general` responde **503 en `/internal/v1/sync/catalog/items`** con su salud en orden, la causa más
probable es su propia validación: rechaza el catálogo entero si un ítem incluido no tiene tags elegibles o tiene
una clasificación fuera de `ATP`, `+13`, `+18`. No se arregla de este lado: escalar a `api-general` con la hora
de la corrida, para que corrija el ítem y corra su verificador de preparación.

### PopularityStale
**Qué significa**: la popularidad no se recalcula hace más de 26 h; el respaldo sirve un ranking congelado.
**Primer paso**: `SELECT config_version, max(computed_at) FROM item_popularity GROUP BY 1;` y revisar el log
del último `reco-batch popularity`.
**Acción**: re-ejecutar `reco-batch popularity` y luego `reco-batch fallback`.

### AgeRefreshStale
**Qué significa**: el job de refresco etario no completó una corrida en más de 26 h. Los usuarios que
cumplen años quedan sub-permitidos (degradación conservadora, no incidente de seguridad).
**Primer paso**: revisar el log y el estado del CronJob del refresco etario.
**Acción**: ejecutarlo manualmente (`reco-batch age-refresh`; es idempotente) e investigar la causa. La
sincronización diaria también corrige el ordinal de quien ya cruzó el umbral, de modo que un día perdido se
repara solo en la corrida siguiente de cualquiera de los dos.

### VectorRecomputeLag
**Qué significa**: hay ítems vigentes sin vector bajo la versión activa hace más de 26 h, contadas desde su
primera sincronización o desde la activación de la versión, lo que sea más reciente (T070).
**Primer paso**: `SELECT count(*) FROM items i WHERE status='available' AND NOT EXISTS (SELECT 1 FROM
item_vectors v JOIN vocab_versions vv ON vv.version = v.vocab_version WHERE v.item_id = i.id AND
vv.deactivated_at IS NULL AND vv.activated_at IS NOT NULL);`
**Acción**: re-ejecutar la corrida del Data Transformer (el job de vocabulario corre a continuación).

### VocabTransitionStalled
**Qué significa**: una transición de vocabulario quedó a mitad de camino.
**Primer paso**: `SELECT version, activated_at, deactivated_at, created_at FROM vocab_versions ORDER BY
created_at DESC LIMIT 3;` — una versión creada sin `activated_at` es la transición interrumpida.
**Acción**: re-ejecutar el Data Transformer; la transición es transaccional y se reintenta desde cero.

### DeadLetterGrowth
**Qué significa**: el worker manda a la DLQ más de 5 mensajes en 30 minutos, de forma sostenida.
**Primer paso**: inspeccionar los encabezados `x-dlq-reason` y `x-dlq-cause` de los últimos mensajes de
`recomendaciones.recomendacion-actualizar.dlq`.
**Acción**: `invalid_payload`/`contract_violation` → escalar a `api-general` con la causa;
`retries_exhausted` → revisar la salud del worker (Postgres/Redis). Reproceso: ver
[Reproceso desde DLQ](#reproceso-desde-dlq).
**Punto ciego**: esta alerta cuenta lo que manda el worker. Lo que el broker vence por TTL o por
`x-delivery-limit` llega a la DLQ sin pasar por él; se ve en `reco_dead_letter_depth{queue}`. Para las bajas
de cuenta eso tiene alerta propia: [DeletionEventsDeadLettered](#deletioneventsdeadlettered).

### DeletionEventsDeadLettered
**Qué significa**: hay eventos de baja de cuenta en `recomendaciones.usuario-eliminado.dlq`. Cada uno es una
supresión que **no se ejecutó**: estamos reteniendo datos de alguien que pidió ser eliminado (FR-091).
**Primer paso**: mirar los mensajes sin consumirlos (consola de RabbitMQ → la DLQ → *Get messages* con
*Nack message requeue true*). Si llevan `x-dlq-reason`, los mandó el worker; si llevan `x-death` con
`reason: expired`, vencieron sin que el worker los consumiera en `RECO_EVENT_REDELIVERY_WINDOW_HOURS` (worker
caído); con `reason: delivery_limit`, el worker se cayó al procesarlos `RECO_RETRY_MAX_ATTEMPTS` veces.
**Acción**: restablecer el worker y **reprocesar siempre** (ver [Reproceso desde DLQ](#reproceso-desde-dlq)): el
procedimiento es idempotente. Un `delivery_limit` repetido es un mensaje que tumba al proceso: capturar el
`event_id` y el log del worker antes de reprocesarlo. **Severidad alta**: responsable del repo en el día.

### QueueDepthGrowth
**Qué significa**: la cola de eventos crece sin drenarse.
**Primer paso**: `curl :8081/health/ready` en cada worker; ver `reco_recompute_duration_seconds`.
**Acción**: si los workers están sanos, escalar horizontalmente; si no, restablecer su dependencia.

### SignalIngestLag
**Qué significa**: el p95 de `received_at − occurred_at` por evento supera una hora.
**Primer paso**: comparar con `QueueDepthGrowth`: si la cola está alta, es atraso propio; si no, es reloj
del origen desviado.
**Acción**: atraso propio → ver QueueDepthGrowth; reloj → escalar a `api-general`.

### ExclusionResolveLag
**Qué significa**: hay señales registradas que no llegaron al conjunto de exclusión hace más de una hora.
Es degradación de un **invariante de seguridad** (DI-3).
**Primer paso**: `SELECT count(*) FROM user_signals s WHERE NOT EXISTS (SELECT 1 FROM user_exclusions e
WHERE e.user_id = s.user_id AND e.item_id = s.item_id);` y revisar errores del resolutor en el log.
**Acción**: corregir la causa y re-ejecutar la ingesta; la resolución es idempotente y aditiva.

### RedisUnavailable503
**Qué significa**: la API responde 503 (Redis caído o filtros no disponibles). No es un modo degradado:
`api-general` no recibe recomendaciones.
**Primer paso**: `curl :8000/health/ready` — `checks.redis`.
**Acción**: restablecer Redis. Si se perdió su contenido, ver
[Reconstrucción tras pérdida total de Redis](#reconstrucción-tras-pérdida-total-de-redis).

### HitRateDrop
**Qué significa**: menos de la mitad de las respuestas son personalizadas vigentes.
**Primer paso**: `reco_cache_hits_total` por `result_type`: mucho `empty_pending` tras una pérdida de caché
indica que falta el warm-up; mucho `fallback` con el worker sano indica `recompute:requests` estancado
(`recompute_requests_pending`).
**Acción**: warm-up o revisión del worker.

### ConfigVersionInconsistent
**Qué significa**: las instancias corren versiones de configuración distintas por más de 10 minutos.
**Primer paso**: `reco_active_config_version` por `component`; `/health` de cada instancia.
**Acción**: completar o revertir el despliegue (el rollback es hacia adelante, ver
[Cambio de config_version](#cambio-de-config_version)).

### RetiredSetLarge
**Qué significa**: el set de retirados supera 10 000 ítems.
**Primer paso**: verificar `sync_volume_delta_ratio`: un listado incompleto del origen retira en masa.
**Acción**: si fue un listado parcial, investigar con `api-general` antes de la próxima corrida.

### ContractViolationBirthDate
**Qué significa**: `api-general` emitió usuarios sin `birth_date` (CR-1); se rechazan en la ingesta.
**Primer paso**: log `violación de contrato: usuario sin birth_date` con `user_id` y `sync_run_id`.
**Acción**: escalar a `api-general` con los identificadores.

### ContractViolationRegion
**Qué significa**: usuarios sin `region` ISO válida (CR-5); se rechazan (RD-52). Si el valor es masivo, es
el escenario de DEP-11 (backfill no hecho).
**Primer paso**: log `violación de contrato: usuario sin region ISO válida` con `user_id`.
**Acción**: escalar a `api-general`; no hay mitigación local (FR-079 prohíbe inferir la región).

### ContractViolationInteractionId
**Qué significa**: el origen reutilizó un `origin_interaction_id` para otro hecho (FR-029e1).
**Primer paso**: log `origin_interaction_id reutilizado` y los mensajes con `x-dlq-reason=contract_violation`.
**Acción**: escalar a `api-general`: la transición se perdió y debe reemitirse con identificador nuevo.

### SyncVolumeDrop
**Qué significa**: el volumen sincronizado cayó más del 10 %; la corrida abortó sin marcar retiros.
**Primer paso**: comparar `entity_counts` de las dos últimas corridas en `sync_runs`.
**Acción**: confirmar con `api-general` si fue una respuesta parcial; si fue una baja legítima masiva, el
ratio no es la guarda adecuada (ver RD-53).

### TagProjectionAnomalies
**Qué significa**: el origen emite tags vacíos o mal formados.
**Primer paso**: `projection_field_anomalies_total` por `reason`.
**Acción**: escalar al proveedor del catálogo; no se normaliza localmente (RD-16).

### DeclarableTagsBelowMinimum
**Qué significa**: un módulo tiene menos tags elegibles que `declared_tags_min`: **ningún usuario nuevo del
módulo puede declarar** (DEP-10).
**Primer paso**: `SELECT module, count(*) FROM tag_modules GROUP BY module;`
**Acción**: escalar a producto y a `api-general`; el módulo está no disponible para usuarios nuevos.

### CatalogUnrated
**Qué significa**: más del 5 % del catálogo vigente no tiene clasificación declarada: inalcanzable para
menores por el fail-closed etario.
**Primer paso**: `SELECT module, count(*) FROM items WHERE status='available' AND
age_rating_source='unknown_defaulted' GROUP BY 1;`
**Acción**: escalar al proveedor del catálogo.

### CatalogUnvectorized
**Qué significa**: más del 10 % del catálogo vigente no tiene vector bajo la versión activa.
**Primer paso**: igual que [VectorRecomputeLag](#vectorrecomputelag).
**Acción**: re-ejecutar el Data Transformer.

### AgeStaleConfigUsers
**Qué significa**: hay ordinales derivados bajo una escala no compatible con la activa fuera de una
migración; esos usuarios reciben 503 (DI-23).
**Primer paso**: `SELECT age_config_version, count(*) FROM users GROUP BY 1;`
**Acción**: completar la rederivación (refresco etario, causa B).

### SignalsPurgeDeferred
**Qué significa**: la purga difiere consumos que no tienen su exclusión materializada (FR-068c).
**Primer paso**: ver [ExclusionResolveLag](#exclusionresolvelag): la fuga está en la materialización.
**Acción**: corregir la materialización; la purga se protege sola.

### DeclaredMinimumViolations
**Qué significa**: el job `reco-batch audits` encontró módulos declarados con menos tags propios que
`declared_tags_min` (DI-28). El endpoint de declaración no los produce (FR-083): alguien escribió
`user_declared_tags` por otra vía o hay un defecto.
**Primer paso**: el log del job (`DI-28 violado…`) trae `reco_user_id` y `reco_module`; confirmar con
`SELECT user_id, module, count(*) FROM user_declared_tags GROUP BY 1, 2 HAVING count(*) < 5;`.
**Acción**: buscar el escritor fuera del endpoint (DI-13) y corregirlo. La declaración es definitiva
(FR-086a): no se completa a mano sin el usuario.

### UserDeletionResidualKeys
**Qué significa**: una supresión dejó claves del usuario en Redis.
**Primer paso**: `SELECT user_id, state, attempts FROM user_suppressions WHERE state <> 'completed';`
**Acción**: la verificación reintenta con backoff; si queda `failed`, buscar al escritor que reescribe
(log `supresión con residuo…` lista las claves y filas halladas: una clave `reco:` que reaparece indica un
recálculo que no respetó la marca), borrar las claves a mano (`SCAN` por `*<user_id>*`) y re-ejecutar la
verificación con `reco-batch suppressions` (retoma toda supresión `failed` o trabada hace más de 30 min).
Escalar al responsable del repo.

### SuppressionsUnverified
**Qué significa**: hay supresiones sin constancia de verificación más allá del período de gracia.
**Primer paso**: `SELECT user_id, state, attempts, requested_at FROM user_suppressions WHERE state <>
'completed' ORDER BY requested_at;`
**Acción**: `failed` → [UserDeletionResidualKeys](#userdeletionresidualkeys); `in_progress` antiguo →
revisar el worker. **Escalamiento de severidad alta** (FR-095a): responsable del repo en el día.

---

## Procedimientos

> Convenciones: `$PG` es una sesión `psql` contra DB Recomendaciones; `$REDIS` es `redis-cli -u <RECO_REDIS_URL>`;
> `<cfg>` es la `config_version` activa (`curl -s :8000/health | jq -r .config_version`). Los nombres de
> deployments y CronJobs dependen del despliegue: acá se nombra el **proceso** (`reco-api`, `reco-worker`,
> `reco-transformer`, `reco-batch <job>`).

### Reconstrucción tras pérdida total de Redis

**Cuándo**: Redis volvió a estar disponible pero sin su contenido (reinicio sin persistencia, failover a una
réplica vacía, `FLUSHALL` accidental). Mientras Redis estuvo caído la API respondió `503`
([RedisUnavailable503](#redisunavailable503)); eso **no** es este procedimiento, es esperar a que vuelva.

**Qué se pierde y qué no**: Redis es caché (INV-2). Todo lo que contiene se reconstruye desde Postgres; no hay
que restaurar ningún backup de Redis, y **no conviene** hacerlo: un volcado viejo reintroduce resultados
calculados con datos anteriores (las guardas del request path los filtran, pero no hay razón para servirlos).

**Duración esperable**: el respaldo vuelve en minutos (pasos 3–4); lo personalizado, al ritmo de
`RECO_WARMUP_RATE_PER_SECOND` × usuarios declarados (con 50/s, 100 000 pares ≈ 35 min) más la capacidad de
los workers. Durante ese lapso la API sirve `fallback` o `empty_pending`: es **degradación de calidad, no
de disponibilidad**, y no requiere comunicar incidente a `api-general` salvo que el paso 4 falle.

1. **Confirmar el diagnóstico** (1 min).
   ```
   curl -s :8000/health/ready | jq .checks.redis      # "ok": Redis responde
   $REDIS DBSIZE                                      # ≈ 0 (o muy bajo): se perdió el contenido
   $REDIS EXISTS fallback:v<cfg>:peliculas            # 0
   ```
   Si `checks.redis` no es `ok`, Redis sigue caído: restablecerlo primero y volver a este paso.
2. **Verificar que los workers consumen** (1 min). El worker recrea el grupo de `recompute:requests` solo
   (desde la corrección registrada en `docs/validation/runbook-dry-run.md`). Comprobarlo:
   ```
   $REDIS XINFO GROUPS recompute:requests            # debe listar "recompute-workers"
   curl -s <worker>:8081/health/ready | jq .
   ```
   Si el Stream no existe todavía, `XINFO` responde `ERR no such key`: es normal hasta que algo se encole.
   Si tras el paso 5 el grupo no aparece en 1 min, reiniciar los workers (`reco-worker`); es seguro.
3. **Reconstruir el respaldo** (1–3 min). Es lo primero porque es lo que la API sirve mientras tanto:
   ```
   reco-batch fallback
   $REDIS EXISTS fallback:v<cfg>:peliculas fallback:v<cfg>:juegos     # 2
   ```
   Si falla por popularidad ausente o vieja, correr antes `reco-batch popularity` (ver
   [PopularityStale](#popularitystale)) y repetir.
4. **Comprobar el servicio** (1 min). Una lectura de un usuario declarado cualquiera:
   ```
   curl -s -H "X-Internal-API-Key: $KEY" ":8000/internal/v1/recommendations/<user_id>?module=peliculas" | jq .result_type
   ```
   Debe ser `fallback` (o `empty_no_candidates` si el catálogo del módulo está vacío). `filters:` y
   `retired:` se repueblan solos desde Postgres en la primera lectura de cada clave: no hay paso para ellos.
5. **Lanzar el warm-up** (minutos a decenas de minutos).
   ```
   reco-batch warmup
   ```
   Encola un recálculo por módulo declarado de cada usuario, los más activos primero, a tasa limitada. Es
   **reanudable**: si se interrumpe, relanzarlo omite los pares que ya tienen `reco:` vigente. Nunca lo
   dispara el tráfico: correrlo es una decisión del operador.
6. **Seguir el progreso.**
   ```
   $REDIS XLEN recompute:requests
   $REDIS XPENDING recompute:requests recompute-workers
   ```
   y en Prometheus `recompute_requests_pending`, `rate(reco_recompute_total{status="written"}[5m])` y la
   proporción `reco_cache_hits_total{result_type="personalized"}`. [HitRateDrop](#hitratedrop) se apaga
   sola cuando lo personalizado supera la mitad.
7. **Cerrar**: `recompute_requests_pending` vuelve a su valor de régimen y `reco_cache_hits_total` muestra
   mayoría de `personalized`. Registrar en el incidente la hora de pérdida, la de fin del paso 3 y la de fin
   del paso 6.

**Qué NO hacer**: no reiniciar la API en bucle (no ayuda: el `503` ya terminó); no correr el warm-up varias
veces en paralelo (no duplica trabajo gracias a `recompute:lock`, pero multiplica la carga sobre Postgres);
no subir `RECO_WARMUP_RATE_PER_SECOND` sin mirar la latencia de recálculo.

### Cambio de config_version

**Principio**: la configuración del motor vive en el repo (`src/recomendaciones/config/engine_config/vN.yaml`)
y su identidad es el hash del contenido. Una versión desactivada **no se reactiva**: el rollback se hace
**hacia adelante**, con una versión nueva y otro `version_label` (RD-94, DI-24).

**Desplegar una versión nueva**:
1. Crear `vN+1.yaml` (no editar `vN.yaml`: su hash cambiaría y dejaría de ser la versión registrada) con un
   `version_label` nuevo. Validar localmente: `pytest tests/unit/test_config_loader.py` y
   `python -c "from recomendaciones.config.loader import load_engine_config as l; print(l('vN+1.yaml').config_version)"`.
2. **¿Cambia `age_rating_catalog`?** Si **no**, seguir al paso 3: los resultados de `vN` siguen siendo
   legibles hasta `TTL_STALE` y no hay invalidación masiva (RD-103, SC-022). Si **sí**, es una migración de
   escala etaria: coordinar antes con `api-general` (el enum `age_rating` existe en ambos repos), y tras el
   paso 3 correr `reco-batch age-refresh` y `reco-transformer` para rederivar usuarios e ítems; hasta que
   termine, los usuarios bajo la escala vieja reciben `503` (DI-23, alerta
   [AgeStaleConfigUsers](#agestaleconfigusers)).
3. Apuntar `RECO_ENGINE_CONFIG_FILE=vN+1.yaml` y desplegar **todos** los procesos. El primero que arranca
   registra la versión en `engine_config_versions` y desactiva la anterior; los demás la encuentran activa.
4. Verificar: `reco_active_config_version` por `component` muestra la misma versión en todas las instancias
   (si no, [ConfigVersionInconsistent](#configversioninconsistent) salta a los 10 min).
5. Correr `reco-batch popularity` y `reco-batch fallback`: la popularidad y el respaldo se escriben por
   `config_version` y la nueva arranca sin filas. Lo personalizado se recalcula por el curso normal (umbral de
   interacciones, misses y declaraciones); si se quiere acelerar, `reco-batch warmup`.

**Revertir**: copiar el contenido de `vN.yaml` a `vN+2.yaml` con otro `version_label` y desplegar como arriba.
Apuntar de nuevo a `vN.yaml` **falla al arrancar** a propósito, con un mensaje que indica esto mismo.

**Regeneración de vocabulario**: no es un paso manual. El job de vocabulario corre al final de cada
`reco-transformer`; si el conjunto de tags cambió, escribe los vectores de la versión nueva **junto a** los
vigentes y la activa en un único `UPDATE` (RD-22). Para forzarla, re-ejecutar `reco-transformer`. Una
transición interrumpida se reintenta desde cero en la corrida siguiente ([VocabTransitionStalled](#vocabtransitionstalled)).
Los perfiles de usuario se reconstruyen bajo la versión nueva en su próximo recálculo.

### Reproceso desde DLQ

**Principio**: un mensaje en DLQ ya fue reintentado (`retries_exhausted`) o es inválido
(`invalid_payload`, `contract_violation`). Reprocesarlo sin corregir la causa lo devuelve a la DLQ. El
reproceso es **seguro** de repetir: el worker deduplica por `event_id` y la señal por
`origin_interaction_id`.

Colas (prefijo según entorno): `recomendaciones.recomendacion-actualizar.dlq` y
`recomendaciones.usuario-eliminado.dlq`.

1. **Clasificar** por el encabezado `x-dlq-reason` (consola de RabbitMQ → la cola DLQ → *Get messages* con
   *Ack mode: Nack message requeue true*, que no los consume). Los que no lo tienen los mandó el **broker** y
   llevan `x-death`: `reason: expired` (nadie los consumió dentro de `RECO_EVENT_REDELIVERY_WINDOW_HOURS`) o
   `reason: delivery_limit` (el worker se cayó al procesarlos `RECO_RETRY_MAX_ATTEMPTS` veces). Ambos son
   reprocesables una vez que el worker está sano; el segundo, después de capturar su `event_id` y el log:
   - `invalid_payload` / `contract_violation`: el productor envió algo que el contrato no admite. **No
     reprocesar**: escalar a `api-general` con `x-dlq-cause` y el `event_id`. Si el productor reemite el
     evento corregido, llega por la cola normal. Los mensajes de la DLQ se descartan después de registrarlos.
   - `retries_exhausted`: falla transitoria que duró más que los reintentos (Postgres o Redis caídos).
     Reprocesables **una vez restablecida la dependencia**.
2. **Verificar** que la causa se fue: `curl <worker>:8081/health/ready` con todos los checks en `ok`.
3. **Mover** los `retries_exhausted` a la cola principal con una *shovel* de un solo uso (consola →
   *Admin → Shovel Management*, o por CLI):
   ```
   rabbitmqctl set_parameter shovel dlq-reproceso '{"src-uri":"amqp://","src-queue":"recomendaciones.recomendacion-actualizar.dlq","dest-uri":"amqp://","dest-queue":"recomendaciones.recomendacion-actualizar","src-delete-after":"queue-length"}'
   ```
   `src-delete-after: queue-length` la hace moverse solo lo que había al crearla y borrarse sola. Si la DLQ
   mezcla motivos, mover primero a mano los inválidos a una cola aparte (o descartarlos tras registrarlos).
4. **Seguir**: `reco_dlq_messages_total` no debe crecer y `reco_queue_depth` vuelve a su régimen. Mensajes
   que regresan a la DLQ con el mismo motivo indican que la causa sigue: parar y volver al paso 2.

**Topología de las colas.** El worker declara al arrancar sus colas como *quorum*, con la convención del
broker de `notificaciones`: la principal lleva `x-message-ttl` = `RECO_EVENT_REDELIVERY_WINDOW_HOURS`,
`x-delivery-limit` = `RECO_RETRY_MAX_ATTEMPTS` y dead-letter a su DLQ; la DLQ no tiene TTL. **Los argumentos de
una cola quorum no se pueden cambiar en caliente**: si cambia alguno de esos dos valores, el worker falla al
arrancar con `PRECONDITION_FAILED`. Para aplicarlo: detener los workers, esperar que la cola principal quede en
0, borrarla (`rabbitmqctl delete_queue recomendaciones.recomendacion-actualizar`, y lo mismo con
`recomendaciones.usuario-eliminado`) y arrancar con el valor nuevo;
la DLQ no se toca. Mientras tanto `api-general` puede seguir publicando: el exchange sin cola descarta, y la
sincronización diaria trae esas interacciones (los eventos de baja no: hacerlo fuera de horario y con el
productor de bajas avisado).

**Cuánto esperar**: los eventos tienen valor mientras la señal es útil; más allá de
`RECO_EVENT_REDELIVERY_WINDOW_HOURS` la sincronización diaria ya trajo la misma interacción desde
`api-general` (es idempotente por `origin_interaction_id`), de modo que una DLQ vieja de `recomendacion.actualizar`
puede descartarse sin pérdida. Los de `usuario.eliminado` **nunca** se descartan: son supresiones
pendientes (FR-091) y se reprocesan siempre.

### Jobs periódicos

| Job | Frecuencia | Qué hace | Si falla |
|---|---|---|---|
| `reco-transformer` | diaria (o más) | sincroniza y regenera vocabulario | [CatalogSyncStale](#catalogsyncstale) |
| `reco-batch popularity` | diaria | Wilson por ventana, promociones | [PopularityStale](#popularitystale) |
| `reco-batch fallback` | tras `popularity`, y cada `TTL_FALLBACK` | top-N de respaldo | [HitRateDrop](#hitratedrop) |
| `reco-batch age-refresh` | diaria, fuera de pico | cruces de umbral etario y escala no compatible | [AgeRefreshStale](#agerefreshstale) |
| `reco-batch purge-signals` | diaria o semanal | purga por retención con guarda de exclusión | [SignalsPurgeDeferred](#signalspurgedeferred) |
| `reco-batch suppressions` | cada hora | retoma supresiones trabadas o fallidas | [SuppressionsUnverified](#suppressionsunverified) |
| `reco-batch audits` | diaria | audita DI-28: declaraciones bajo el mínimo (T069) | [DeclaredMinimumViolations](#declaredminimumviolations) |

**Reducir `RECO_SIGNAL_RETENTION_DAYS` exige aprobación registrada** (RD-54): la purga es irreversible. Cada
corrida registra en el log el valor vigente (`reco_signal_retention_days`), de modo que una reducción no
aprobada sea detectable después. Aumentarlo es configuración normal.

### CI

`.github/workflows/ci.yml` (en la raíz del repositorio git) corre nueve gates —lint (`ruff`, versión fijada en `pyproject.toml`, T067), configuración, arquitectura,
unitarios con cobertura de `engine/` ≥ 95 %, mutación de `postprocess`, invariantes, contratos, casos
críticos e integración— y un job agregado `gates` que falla salvo que los nueve terminen en verde.

**Configuración obligatoria en GitHub** (no la puede hacer este archivo): una regla sobre `main` que
exija el check **`gates`**. Sin ella un gate rojo no impide el merge, y un commit con `[skip ci]` deja el PR
sin checks: con la regla, el check requerido queda pendiente y el merge sigue bloqueado.

**Estado actual** (verificado el 2026-09-30): el ruleset `main` del repositorio (id `24128939`, activo desde
el 2026-09-28) exige `gates` y prohíbe borrar `main` y forzar pushes. **No** exige que la rama esté al día
con `main` (`strict` desactivado) ni revisión del PR. Recomendado: activar ambos en *Settings → Rules →
Rulesets → main* —*Require branches to be up to date before merging* y *Require a pull request before
merging* con al menos una aprobación—, que es lo que la constitución pide en su Flujo de Desarrollo.

Mutante sobreviviente en el job `mutation`: los tests de invariantes dejaron de detectar una rotura del
filtro de edad o de exclusión. No se «arregla» el mutante: se escribe el test que lo mata.
