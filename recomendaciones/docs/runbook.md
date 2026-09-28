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

### PopularityStale
**Qué significa**: la popularidad no se recalcula hace más de 26 h; el respaldo sirve un ranking congelado.
**Primer paso**: `SELECT config_version, max(computed_at) FROM item_popularity GROUP BY 1;` y revisar el log
del último `reco-batch popularity`.
**Acción**: re-ejecutar `reco-batch popularity` y luego `reco-batch fallback`.

### AgeRefreshStale
**Qué significa**: el job de refresco etario no completó una corrida en más de 26 h. Los usuarios que
cumplen años quedan sub-permitidos (degradación conservadora, no incidente de seguridad).
**Primer paso**: revisar el log y el estado del CronJob del refresco etario.
**Acción**: ejecutarlo manualmente e investigar la causa.

### VectorRecomputeLag
**Qué significa**: hay vectores de la versión activa sin recalcular hace más de 26 h.
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
**Qué significa**: la DLQ crece de forma sostenida.
**Primer paso**: inspeccionar los encabezados `x-dlq-reason` y `x-dlq-cause` de los últimos mensajes de
`recomendaciones.recomendacion-actualizar.dlq`.
**Acción**: `invalid_payload`/`contract_violation` → escalar a `api-general` con la causa;
`retries_exhausted` → revisar la salud del worker (Postgres/Redis). Reproceso: ver
[Reproceso desde DLQ](#reproceso-desde-dlq).

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

### UserDeletionResidualKeys
**Qué significa**: una supresión dejó claves del usuario en Redis.
**Primer paso**: `SELECT user_id, state, attempts FROM user_suppressions WHERE state <> 'completed';`
**Acción**: la verificación reintenta con backoff; si queda `failed`, borrar las claves a mano
(`SCAN` por `*<user_id>*`) y re-ejecutar la verificación. Escalar al responsable del repo.

### SuppressionsUnverified
**Qué significa**: hay supresiones sin constancia de verificación más allá del período de gracia.
**Primer paso**: `SELECT user_id, state, attempts, requested_at FROM user_suppressions WHERE state <>
'completed' ORDER BY requested_at;`
**Acción**: `failed` → [UserDeletionResidualKeys](#userdeletionresidualkeys); `in_progress` antiguo →
revisar el worker. **Escalamiento de severidad alta** (FR-095a): responsable del repo en el día.

---

## Procedimientos

### Reconstrucción tras pérdida total de Redis
*(T022, T046 — procedimiento completo en la sección de T046.)*

### Cambio de config_version
*(T046.)*

### Reproceso desde DLQ
*(T046.)*
