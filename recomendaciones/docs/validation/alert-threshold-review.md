# Revisión de umbrales de alertas (B7, T042)

Revisión humana de las 27 alertas de `ops/alerts.yaml`. Los tests prueban que cada regla dispara y se
apaga con su condición. Lo que falta decidir es si **el valor es razonable**, y eso no se puede
automatizar.

**Fecha**: 2026-09-29 · **Revisión**: 2026-10-01, por HingusPingus — 26 aprobadas, 1 pendiente (CatalogUnrated)

## Cómo usarla

1. Revisá las **27 alertas de las secciones 1 y 2**. Tildá cada una al terminarla y marcá **aprobar** o
   **ajustar**. Si es «ajustar», anotá el valor o el cambio que proponés.
2. La sección 3 queda vacía: `VectorRecomputeLag` ya se redefinió en T070. *(Hasta el 2026-09-30,
   once alertas estaban bloqueadas porque su métrica no se exponía; T066 lo corrigió.)*
3. Cuando termines, pasame las decisiones: actualizo `ops/alerts.yaml` y sus justificaciones, y cierro el
   criterio de T042.

**Para mirar en cada alerta**:
- **Umbral y `for`**: ¿el valor tiene sentido? El `for` es cuánto tiene que sostenerse la condición antes
  de disparar. Si el valor depende del tráfico real, podés aprobarlo como valor inicial y marcarlo para
  recalibrar en staging.
- **Severidad**: ¿una alerta crítica justifica despertar a alguien?
- **Dueño**: hoy hay dos roles genéricos, `guardia-de-plataforma` y `dueno-de-producto`. Hay que decidir
  qué persona o equipo real es cada uno.
- **Justificación**: ¿se entiende sin haber diseñado el sistema?

## 1. Para revisar (15)

- [x] **CatalogSyncStale** · crítica · dueño `guardia-de-plataforma`
  - **Condición**: `time() - catalog_sync_last_success_timestamp > 93600` durante `10m`
  - **Qué avisa**: El catálogo no se sincroniza con éxito hace más de 26 horas
  - **Justificación actual**: §7.7 fija > 26 h: la sincronización es diaria, y 2 h de margen absorben una corrida demorada sin tolerar una perdida. Pasado ese punto altas y retiros no se reflejan y un ítem retirado se sigue recomendando.
  - **A tener en cuenta**: El `for: 10m` cubre el valor 0 que exporta el worker al reiniciarse, antes de su primer refresco. Si la sincronización nunca tuvo éxito, el valor se queda en 0 y la alerta dispara a los 10 minutos, que es lo correcto.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **ExclusionResolveLag** · crítica · dueño `guardia-de-plataforma`
  - **Condición**: `exclusion_resolve_lag_seconds > 3600` durante `5m`
  - **Qué avisa**: Hay señales que no llegaron al conjunto de exclusión hace más de una hora
  - **Justificación actual**: §7.12 fija > 1 h. Es degradación de un invariante de seguridad (DI-3): un ítem ya rechazado puede volver a recomendarse. Por eso es crítica y con for corto.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [ ] **CatalogUnrated** · warning · dueño `dueno-de-producto`
  - **Condición**: `catalog_unrated_ratio > 0.05` durante `1h`
  - **Qué avisa**: Más del 5 % del catálogo vigente no tiene clasificación etaria declarada
  - **Justificación actual**: §7.7 fija > 5 %: esa fracción es inalcanzable para menores por el fail-closed etario (FR-051) y la degradación es silenciosa por naturaleza. Se escala al proveedor del catálogo.
  - **A tener en cuenta**: El dueño es `dueno-de-producto`: la acción es escalar a api-general, no reparar algo de nuestro lado.
  - **Decisión**: ⏳ **pendiente** — el revisor indica que no puede ocurrir, porque api-general debe enviar siempre la clasificación (CR-15). Falta decidir si se elimina la alerta o se ajusta a valor esperado 0

- [x] **DeadLetterGrowth** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `sum(increase(reco_dlq_messages_total[30m])) > 5` durante `15m`
  - **Qué avisa**: Crecimiento sostenido de la dead-letter
  - **Justificación actual**: Un mensaje aislado en DLQ es un payload inválido puntual y queda auditado; más de 5 en 30 minutos sostenidos durante 15 es un productor roto o un fallo permanente del worker, que exige intervención antes de que la cola de reproceso manual se vuelva inmanejable.
  - **A tener en cuenta**: Depende del tráfico: 5 mensajes en 30 minutos puede ser mucho o poco según el volumen real. Si api-general publica v2 y v3 en el mismo exchange (`docs/contracts/migracion-v3.md`), esta alerta queda disparada todo el tiempo.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **DeletionEventsDeadLettered** · crítica · dueño `guardia-de-plataforma`
  - **Condición**: `max(reco_dead_letter_depth{queue=~".*usuario-eliminado\\.dlq"}) > 0` durante `15m`
  - **Qué avisa**: Hay eventos de baja de cuenta en dead-letter
  - **Justificación actual**: Cada mensaje en esa DLQ es una supresión que no se ejecutó (FR-091): retener datos de quien pidió ser eliminado no admite umbral mayor que cero. El broker también manda ahí los vencidos por TTL o por x-delivery-limit sin pasar por el consumidor, así que reco_dlq_messages_total no alcanza. Los 15 minutos cubren un reproceso manual en curso.
  - **A tener en cuenta**: Una baja en la DLQ significa que retenemos datos de quien pidió ser eliminado. Por eso es crítica aunque sea un solo mensaje.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **QueueDepthGrowth** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `max by (queue) (reco_queue_depth) > 1000` durante `15m`
  - **Qué avisa**: La cola de eventos crece sin drenarse
  - **Justificación actual**: Con el objetivo de recálculo ≤ 2 s p95 por usuario, 1000 eventos pendientes son más de media hora de atraso para un worker; sostenido 15 minutos distingue un pico de tráfico de un consumo detenido.
  - **A tener en cuenta**: El valor 1000 depende del tráfico; conviene recalibrarlo en staging.
  - **Decisión**: ☑ aprobada (2026-10-01) — el umbral `1000` se recalibra a futuro con el tráfico real

- [x] **SignalIngestLag** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `histogram_quantile(0.95, sum by (le) (rate(signal_ingest_lag_seconds_bucket{source="evento"}[15m]))) > 3600` durante `15m`
  - **Qué avisa**: El p95 del rezago de ingesta por evento supera una hora
  - **Justificación actual**: §7.10 fija p95 > 1 h en la vía de evento: sin sincronización de por medio, un desfasaje así es reloj del origen desviado o cola acumulada en el broker; segmentar por source permite distinguirlos.
  - **A tener en cuenta**: la métrica se mide por los dos caminos, pero la alerta mira solo `source="evento"`, a propósito: por sincronización el rezago llega a un día porque la sync es diaria, y eso es normal. Si el worker está caído esta alerta no puede disparar, porque él mide y expone; ese caso lo cubre `QueueDepthGrowth`.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **RedisUnavailable503** · crítica · dueño `guardia-de-plataforma`
  - **Condición**: `sum(rate(reco_unavailable_responses_total[5m])) > 0.1` durante `5m`
  - **Qué avisa**: La API responde 503 por caché o filtros no disponibles
  - **Justificación actual**: Redis caído no es un modo degradado: la API responde 503 y no sirve nada (FR-065). Más de 6 respuestas 503 por minuto durante 5 minutos excluye un reinicio breve de Redis y significa que api-general no está recibiendo recomendaciones.
  - **A tener en cuenta**: 0,1 respuestas 503 por segundo durante 5 minutos son unas 30 respuestas fallidas.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **HitRateDrop** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `sum(rate(reco_cache_hits_total{result_type="personalized"}[15m])) / sum(rate(reco_cache_hits_total[15m])) < 0.5` durante `30m`
  - **Qué avisa**: Menos de la mitad de las respuestas son personalizadas vigentes
  - **Justificación actual**: En régimen, la mayoría de las lecturas de usuarios declarados deberían ser personalizadas; por debajo del 50 % sostenido 30 minutos, el worker no está reponiendo resultados o hubo una pérdida de caché sin warm-up. El umbral es inicial y se recalibra con tráfico real.
  - **A tener en cuenta**: ⚠️ En el lanzamiento casi todos los usuarios reciben el respaldo hasta su primer recálculo, así que la proporción de personalizados puede estar debajo del 50 % en funcionamiento normal. Conviene recalibrar después del lanzamiento o silenciarla los primeros días.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **ConfigVersionInconsistent** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `count(count by (config_version) (reco_active_config_version)) > 1` durante `10m`
  - **Qué avisa**: Las instancias corren versiones de configuración del motor distintas
  - **Justificación actual**: Debe haber exactamente una versión activa por entorno (FR-025b). Durante un despliegue conviven dos unos minutos; más de 10 indica un rollout trabado y resultados calculados con pesos distintos.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **RetiredSetLarge** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `max by (module) (retired_set_size) > 10000` durante `1h`
  - **Qué avisa**: El set de retirados supera los 10 000 ítems
  - **Justificación actual**: §4.4 fija > 10 000: a esa escala el repoblado horario deja de ser trivial y una tasa de retiro tan alta sugiere listados incompletos del origen (CR-9) antes que retiros reales. Verificar sync_volume_delta_ratio primero.
  - **A tener en cuenta**: El valor 10 000 depende del tamaño del catálogo real.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **SuppressionsUnverified** · crítica · dueño `guardia-de-plataforma`
  - **Condición**: `suppressions_unverified_total > 0` durante `30m`
  - **Qué avisa**: Hay supresiones sin constancia de verificación
  - **Justificación actual**: FR-095a: valor esperado 0, con observador y responsable. El for de 30 minutos es el período de gracia de una supresión en curso (hallazgo A5 del análisis: la métrica cuenta también las que están en progreso); pasado ese tiempo, la supresión está trabada o fallida.
  - **A tener en cuenta**: El `for: 30m` es el período de gracia de una supresión en curso (RD-112) y coincide con nuestro compromiso de completar la supresión dentro de los 30 minutos siguientes a la recepción (`docs/contracts/checkpoint-baja.md`).
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **ContractViolationInteractionId** · crítica · dueño `guardia-de-plataforma`
  - **Condición**: `sum(increase(contract_violations_total{field="origin_interaction_id"}[1h])) > 0` (sin `for`: dispara en la primera evaluación)
  - **Qué avisa**: El origen reutilizó un origin_interaction_id para otro hecho (FR-029e1)
  - **Justificación actual**: §7.10: valor esperado 0. Un identificador reutilizado hace perder una transición en silencio; nunca se absorbe, se rechaza y se alerta.
  - **A tener en cuenta**: cuenta las violaciones por los dos caminos: las del evento las cuenta el worker y las de la sincronización el Transformer, que las expone a través del worker desde T066. Sin `for`, a propósito: una sola violación ya es un incumplimiento del contrato.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **AgeStaleConfigUsers** · crítica · dueño `guardia-de-plataforma`
  - **Condición**: `age_stale_config_users_total > 0` durante `1h`
  - **Qué avisa**: Hay ordinales etarios derivados bajo una escala no compatible con la activa
  - **Justificación actual**: §7.5.1: > 0 fuera de una migración en curso. El for de una hora absorbe la ventana de migración de un cambio de catálogo; pasado ese tiempo, esos usuarios reciben 503 (DI-23) hasta rederivarse.
  - **A tener en cuenta**: la fija el job de refresco etario con la cantidad de usuarios pendientes, y el worker la expone desde T066. Desde T072 la API ya no la incrementa. Es el último valor conocido: no baja hasta la próxima corrida del job.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **UserDeletionResidualKeys** · crítica · dueño `guardia-de-plataforma`
  - **Condición**: `sum(increase(user_deletion_residual_keys_total[1h])) > 0` (sin `for`: dispara en la primera evaluación)
  - **Qué avisa**: Una supresión dejó residuos en la caché
  - **Justificación actual**: §7.11 fija > 0: una supresión incompleta es peor que ninguna, porque existe constancia de haberla ejecutado. Denominador acotado a la supresión en curso.
  - **A tener en cuenta**: cuenta lo que encuentran la supresión del worker y el barrido `reco-batch suppressions`; el barrido se expone a través del worker desde T066. Sin `for`, a propósito.
  - **Decisión**: ☑ aprobada (2026-10-01)

## 2. Desbloqueadas por T066/T070 o nuevas: para revisar (12)

> *Actualizado el 2026-09-30.* Estas alertas no podían dispararse porque su métrica la fija un proceso que
> corre una vez y termina. Desde T066 cada corrida deja su resultado en `process_runs` y el worker lo expone
> (`data-model.md` §2.17); `tests/integration/test_one_shot_metrics.py` induce cada condición con el proceso
> real. Ya se pueden revisar como las de la sección 1.

- [x] **ContractViolationBirthDate** · crítica · dueño `guardia-de-plataforma`
  - **Condición**: `sum(increase(contract_violations_total{field="birth_date"}[1h])) > 0` (sin `for`)
  - **Qué avisa**: api-general emitió usuarios sin birth_date (CR-1)
  - **Justificación actual**: §7.5: valor esperado exactamente 0. No mide un fenómeno con umbral arbitrario sino un incumplimiento binario de contrato que deja usuarios fuera del sistema; cualquier valor > 0 alerta.
  - **A tener en cuenta**: El contador lo re-expone el worker con las corridas terminadas desde que arrancó más la última hora: una violación dispara la alerta aunque el Data Transformer ya haya terminado.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **ContractViolationRegion** · crítica · dueño `guardia-de-plataforma`
  - **Condición**: `sum(increase(contract_violations_total{field="region"}[1h])) > 0` (sin `for`)
  - **Qué avisa**: api-general emitió usuarios sin region ISO válida (CR-5)
  - **Justificación actual**: §7.6 (RD-52): contador propio y separado del de birth_date, valor esperado 0. Desde que la región es obligatoria, cada violación deja a un usuario sin recomendaciones; DEP-11 es el escenario de activación masiva.
  - **A tener en cuenta**: Mismo mecanismo que ContractViolationBirthDate.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **DeclarableTagsBelowMinimum** · crítica · dueño `dueno-de-producto`
  - **Condición**: `min by (module) (declarable_tags_total) < 5` durante `15m`
  - **Qué avisa**: El vocabulario elegible de un módulo tiene menos de declared_tags_min tags
  - **Justificación actual**: DEP-10 (RD-110): con menos de declared_tags_min (5 en v1) tags elegibles, FR-083 impide completar la declaración y FR-088 rechaza a todo usuario nuevo del módulo. Ninguna regla cede: el módulo queda no disponible y hay que saberlo antes que el usuario.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **VocabTransitionStalled** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `vocab_transition_progress < 1` durante `2h`
  - **Qué avisa**: Transición de vocabulario detenida a mitad de camino
  - **Justificación actual**: §7.9 fija estancamiento > 2 h: una transición completa sobre el catálogo declarado (10⁴–10⁵ ítems) toma minutos; dos horas sin llegar a 1 solo se explican por una corrida interrumpida.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **CatalogUnvectorized** · warning · dueño `dueno-de-producto`
  - **Condición**: `catalog_unvectorized_ratio > 0.1` durante `1h`
  - **Qué avisa**: Más del 10 % del catálogo vigente no tiene vector bajo la versión activa
  - **Justificación actual**: §7.9 fija > 10 %. Tras RD-60 no existen vigentes sin tags, de modo que mide rezago propio de vectorización: esa fracción no participa de α ni de γ (la mitad del score).
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **TagProjectionAnomalies** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `sum(increase(projection_field_anomalies_total{field="tag_name"}[1h])) > 0` (sin `for`)
  - **Qué avisa**: El origen emite tags vacíos, mal formados o que colisionan
  - **Justificación actual**: §7.7 fija > 0: los tags alimentan el espacio vectorial y no se normalizan localmente (RD-16); cada anomalía es un ítem con menos insumo de contenido y un reclamo pendiente al proveedor.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **SyncVolumeDrop** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `min by (entity) (sync_volume_delta_ratio) < 0.9` (sin `for`)
  - **Qué avisa**: El volumen sincronizado cayó más del 10 % respecto de la última corrida exitosa
  - **Justificación actual**: §7.12 fija < 0,9 (RD-53, no calibrado): una caída así es casi siempre una respuesta parcial del origen; la corrida aborta sin marcar retiros y esta alerta pide mirar al origen antes de la próxima.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **PopularityStale** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `time() - catalog_popularity_last_success_timestamp > 93600` durante `10m`
  - **Qué avisa**: La popularidad no se recalcula hace más de 26 horas
  - **Justificación actual**: §7.7 fija > 26 h con el mismo criterio que la sincronización: el batch es diario y su falla congela en silencio el ranking del respaldo (RD-11); no afecta a la seguridad, por eso es warning.
  - **A tener en cuenta**: El worker expone el último timestamp de éxito que el job dejó en `process_runs`, aunque el job deje de correr: por eso la alerta ahora puede dispararse.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **AgeRefreshStale** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `time() - age_refresh_last_success_timestamp > 93600` durante `10m`
  - **Qué avisa**: El job de refresco etario no completa una corrida hace más de 26 horas
  - **Justificación actual**: §7.5.1 fija > 26 h y reemplaza a age_ordinal_staleness_seconds, que no disparaba con el job muerto. El desfasaje es siempre conservador (menos contenido, nunca más): warning, no crítica.
  - **A tener en cuenta**: Mismo mecanismo que PopularityStale: el último éxito queda en `process_runs` y el worker lo expone.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **SignalsPurgeDeferred** · warning · dueño `guardia-de-plataforma`
  - **Condición**: `sum(increase(signals_purge_deferred_total[1d])) > 0` durante `1d`
  - **Qué avisa**: La purga difiere consumos por falta de su exclusión materializada
  - **Justificación actual**: §7.10 fija > 0 sostenido: la purga se protege sola (FR-068c), pero un valor persistente durante un día entero es una fuga en la materialización de exclusiones aguas arriba que no se arregla sola.
  - **A tener en cuenta**: El `for: 1d` y la ventana de un día suponen una purga diaria: si la purga corre con otra periodicidad, conviene alinearlos.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **DeclaredMinimumViolations** · warning · dueño `guardia-de-plataforma` *(nueva, T069)*
  - **Condición**: `declared_minimum_violations_total > 0` durante `5m`
  - **Qué avisa**: Hay declaraciones de gustos con menos tags propios que el mínimo
  - **Justificación actual**: DI-28 no lo sostiene el esquema: lo garantiza la transacción de declaración (FR-083) y lo audita este job (T069). Cualquier valor mayor que 0 es una escritura que saltó el endpoint o un defecto; el usuario sigue siendo atendido, por eso es warning. El for de 5 minutos cubre la corrida del job.
  - **Decisión**: ☑ aprobada (2026-10-01)

- [x] **VectorRecomputeLag** · warning · dueño `guardia-de-plataforma` *(redefinida, T070)*
  - **Condición**: `vector_recompute_lag_seconds > 93600` durante `10m`
  - **Qué avisa**: Hay ítems vigentes sin vector bajo la versión activa hace más de 26 horas
  - **Justificación actual**: §7.9 fija > 26 h: la sincronización es diaria y el job de vocabulario vectoriza en la misma corrida, así que un ítem sin vector pasado ese plazo es una reconciliación que falla. Se mide desde lo último entre la primera sincronización del ítem y la activación de la versión (T070); con un catálogo estable vale 0. Degrada calidad, no corrección.
  - **Decisión**: ☑ aprobada (2026-10-01)

## 3. Bloqueadas: ninguna

*(Actualizado el 2026-09-30: `VectorRecomputeLag` se redefinió en T070 y pasó a la sección 2.)*
