# Propuesta: checkpoint de recepción del evento de baja

Propuesta de `recomendaciones` para el ítem 3 de la respuesta de `api-general`
(`specs/004-contratos-recomendaciones`, FR-016, SC-003). Completa la tabla «Acuerdo medible de entrega del
evento de baja» de `contracts/approval.md`.

> **Estado: propuesta, sin acuerdo.** Nada de esto está implementado de nuestro lado. Según el Principio II,
> lo implementamos después de que los tres equipos lo aprueben por escrito.

## En corto

- **Checkpoint:** la fila en nuestra tabla `user_suppressions` con el `event_id` del evento y su
  `received_at`. La escribimos apenas el evento pasa la validación del schema.
- **Límite:** **15 minutos**, medidos desde `occurred_at` (es decir, `usuarios.deleted_at`) hasta ese
  `received_at`.
- **Cómo se entera `api-general`:** consultando un endpoint nuestro por `event_id`. La respuesta alimenta
  `OutboxConsumerReceiptMetrics.recordCheckpoint(eventId)`, que ya existe en su código pero nadie llama.
- **Dos bloqueantes** en el runtime actual de `api-general` hacen que hoy ningún evento pueda llegar
  al checkpoint (ver [Bloqueantes](#bloqueantes-en-el-runtime-actual)).

## Qué hay hoy en cada lado

| Lado | Pieza | Qué aporta al checkpoint |
|---|---|---|
| `api-general` | `AccountDeletionService.confirmLogicalDeletion` | Guarda `deleted_at` y la fila de outbox en la **misma transacción**, y `occurred_at` es ese mismo instante. Es el inicio del cronómetro. |
| `api-general` | `OutboxPublisher` | Sondea cada 5 s y espera el publisher confirm, con `mandatory: true` (un mensaje sin ruta vuelve como error). El backoff va de 1 s a 300 s, ±20 %. El `messageId` es el `evento_id`. |
| `api-general` | `OutboxBacklogMetrics` | Alerta si el evento más viejo **sin publicar** supera los 300 s. Cubre el tramo antes del broker. |
| `api-general` | `OutboxConsumerReceiptMetrics.recordCheckpoint(UUID)` | Contador de recepciones informadas por el consumidor. **No tiene llamador.** |
| `recomendaciones` | Consumidor de `usuario.eliminado` | Valida el schema. Un payload inválido va a la DLQ con `invalid_payload`. |
| `recomendaciones` | `user_suppressions` | Lápida de la supresión: nunca se borra. Hoy guarda `user_id`, `requested_at` (= `occurred_at`), `state`, `attempts` y `verified_at`. |
| `recomendaciones` | `SuppressionsUnverified`, `reco_dead_letter_depth` | Alertas existentes: supresión no completada después de 30 min, y mensajes en la DLQ. |

## El checkpoint propuesto

**Definición:** existe en `user_suppressions` una fila con `event_id` igual al `event_id` del evento.
Su `received_at` es el instante de llegada.

La fila se escribe en su propia transacción, apenas el evento pasa la validación del schema y antes de
empezar la supresión. Un evento que no pasa la validación **no llega al checkpoint** y, pasado el
límite, cuenta como incumplido. Es a propósito: un evento que recibimos pero no podemos procesar no
cumple su función.

### Qué no es checkpoint, y por qué

| Candidato | Por qué no sirve |
|---|---|
| Publisher ACK | Solo prueba que el broker aceptó el mensaje (lo dice su propia FR-016). |
| El ACK de nuestro consumidor | También lo mandamos cuando el mensaje va a la DLQ. Además no deja registro por evento. |
| `processed_events` | Se escribe **al terminar** la supresión, no al recibirla, y vence por retención. No sirve como evidencia duradera. |
| Supresión completada (`verified_at`) | Metería nuestro tiempo de procesamiento en un límite que `api-general` y `notificaciones` no controlan. Lo mantenemos como compromiso aparte (ver [Límite](#límite-numérico)). |

La fila de `user_suppressions` sirve porque es la **primera escritura duradera** del evento de nuestro
lado, queda una por evento, **nunca se borra** (es la lápida) y se cruza con el outbox de `api-general`
por `event_id`, que es su `evento_id`.

## Límite numérico

**Propuesta: 15 minutos** entre `occurred_at` y `received_at`, evento por evento.

| Tramo | Duración en condiciones normales | Peor caso razonable |
|---|---|---|
| Transacción hasta el próximo sondeo del outbox | ≤ 5 s | ≤ 5 s |
| Publicación y confirm | < 1 s | Reintentos con backoff de hasta 300 s (±20 %) mientras el broker no confirme |
| Broker hasta nuestro consumidor | < 1 s | Tiempo que el worker esté caído |
| Validación y escritura del checkpoint | < 1 s | Reintentos si falla la base de datos |

En condiciones normales el recorrido completo tarda unos 10 s. Con 15 minutos alcanza para absorber una
caída breve del broker, donde el backoff llega a su tope y hace falta más de un reintento de hasta 6 min,
sin perder de vista una baja trabada. Queda muy por debajo de nuestra ventana de reentrega de 24 h
(`RECO_EVENT_REDELIVERY_WINDOW_HOURS`), pasada la cual un evento no consumido vence a la DLQ.

**Aparte, compromiso solo nuestro:** la supresión queda completa (`verified_at`) dentro de los **30 min**
siguientes a `received_at`. Si no, salta `SuppressionsUnverified`, que ya existe.

Relojes: `occurred_at` sale del reloj de `api-general` y `received_at` del de nuestra base, ambos con NTP.
Un desfase de segundos no afecta un límite de 15 minutos. Un lag negativo se registra como 0.

## Medición y alertas

**Por evento.** La consulta es `received_at − requested_at` sobre `user_suppressions`. La correlación
usa `event_id` (= `evento_id` = `messageId` de AMQP) y el `correlation_id` del payload, que también
aparece en nuestros logs. La evidencia no vence, porque la lápida es permanente.

**Agregado.** Un histograma `user_deletion_receipt_lag_seconds`, sin etiquetas, con las cubetas de lag
que ya usamos (`LAG_BUCKETS`, que incluyen 900 s). Es el mismo patrón que `signal_ingest_lag_seconds`.

| Quién | Alerta | Qué detecta |
|---|---|---|
| `recomendaciones` | `DeletionReceiptLate` (nueva): `increase(user_deletion_receipt_lag_seconds_count[15m]) - increase(user_deletion_receipt_lag_seconds_bucket{le="900"}[15m]) > 0` | Bajas que llegaron pasado el límite |
| `recomendaciones` | `reco_dead_letter_depth{queue="recomendaciones.usuario-eliminado.dlq"} > 0` (existente) | Bajas que llegaron pero no se pueden procesar |
| `api-general` | Antigüedad del outbox ≥ 300 s (existente) | Bajas que todavía no se publicaron, o que el broker devuelve por falta de ruta |
| `api-general` | Confirmación vencida (nueva, ver abajo) | Bajas publicadas que **nunca llegaron** a nuestro checkpoint |
| `notificaciones` | Profundidad de `recomendaciones.usuario-eliminado` | Cola acumulada porque nuestro worker no consume |

La última fila de `api-general` es la única manera de detectar un evento que el broker aceptó pero que
terminó en una cola equivocada. Ninguna de las otras alertas lo ve.

## Cómo le llega la evidencia a `api-general`

**Recomendado: un endpoint de consulta en nuestra API.**

```
GET /internal/v1/deletion-receipts/{event_id}
X-Internal-API-Key: <entorno>.<secreto>

200 {"event_id": "…", "received_at": "2026-…Z", "suppression_state": "in_progress|completed|failed"}
404 recepción no registrada
```

No devuelve `user_id` ni ningún otro dato del usuario. Del lado de `api-general`, un job periódico
recorre los eventos `usuario.eliminado` en estado `PUBLICADO` que todavía no tienen recepción confirmada:

- **200:** llama a `recordCheckpoint(eventId)` y guarda `received_at` en el outbox. El contador solo
  no alcanza para la evidencia por evento que pide SC-003.
- **404 y ya pasaron 15 min desde `occurred_at`:** dispara la alerta «confirmación vencida».

Motivos para elegir esta opción: el canal ya existe (`api-general` consume nuestra API con API key por
entorno), no agrega contratos al broker y cubre justo el caso que ninguna otra alerta detecta. El
endpoint entra en `recomendaciones-api.openapi.yaml`, que custodia `api-general`.

**Alternativas descartadas:**

- **Evento de vuelta** (`usuario.eliminado.recibido`): necesita un contrato nuevo, un outbox de
  nuestro lado y una cola nueva para ellos. Es más maquinaria para lo mismo.
- **Solo nuestras métricas:** no detectan un evento que nunca llegó, y `api-general` no podría
  verificar SC-003 por su cuenta.

## Cambios de nuestro lado, una vez aprobado

1. Agregar a `user_suppressions` las columnas `event_id` (UUID, único) y `received_at` (timestamptz,
   `default now()`). Ante un evento repetido para el mismo `user_id` se conservan los valores del
   primero.
2. Escribir la marca `in_progress` **al recibir** el evento, en su propia transacción y antes de
   limpiar Redis. Hoy la escribimos junto con el borrado. Adelantarla solo hace antes lo que pide
   FR-092a, y si la limpieza de Redis falla, el barrido de supresiones la retoma.
3. Agregar el histograma, la alerta `DeletionReceiptLate` y su entrada en el runbook.
4. Agregar el endpoint de consulta.
5. Enmendar FR-095 y `data-model.md` §2.15. Hoy la constancia admite «solo identificador y marca
   temporal», y `event_id` es un identificador del evento, no un dato del usuario. Hay que dejarlo
   escrito.

## Bloqueantes en el runtime actual

Estos dos puntos no son del checkpoint, pero sin resolverlos **ningún** evento de baja llega a él.

1. **`user_id` es entero en su runtime.** `src/main/resources/schemas/usuario-eliminado-1.0.0.schema.json`
   lo declara `integer` con `additionalProperties: false`, y `AccountDeletionService` publica el `Long`
   del usuario. El contrato de su spec 004 y el nuestro dicen UUID. Nuestro consumidor mandaría **todas**
   las bajas a la DLQ con `invalid_payload`. Es el mismo desalineamiento de IDs del ítem 4
   (T019/T020/T045).
2. **Exchange.** Nuestro worker declara el exchange `fanout` `usuario.eliminado`, con la cola
   `recomendaciones.usuario-eliminado` asociada. En `api-general`, `RECOMMENDATIONS_OUTBOX_USER_DELETED_EXCHANGE`
   está vacío por defecto y hay que acordar su valor (ítem 2). Con `fanout` la routing key se ignora, pero
   su validación exige que no esté vacía.

## Valores para la tabla de `approval.md`

| Campo de acuerdo | Valor propuesto |
|---|---|
| Fecha de disponibilidad/publicación comprometida | La compromete `api-general`. Condición previa: resolver los dos bloqueantes. |
| Límite máximo desde la confirmación de la baja lógica hasta el checkpoint | **15 minutos**, por evento, desde `occurred_at` (= `usuarios.deleted_at`) |
| Checkpoint que acredita la recepción por recomendaciones | Fila en `user_suppressions` con el `event_id` del evento, escrita tras validar el schema. Su `received_at` es el fin del cronómetro. |
| Fuente de medición, identidad/correlación y retención de evidencia | `received_at − requested_at` en `user_suppressions`, más el histograma `user_deletion_receipt_lag_seconds`. Correlación por `event_id`/`evento_id` y `correlation_id`. Retención permanente (lápida). `api-general` la consulta con `GET /internal/v1/deletion-receipts/{event_id}`. |
| Regla de alerta/escalamiento al superar el límite | `recomendaciones`: `DeletionReceiptLate` y la DLQ del evento. `api-general`: antigüedad del outbox ≥ 300 s y «confirmación vencida» (404 pasados 15 min). `notificaciones`: profundidad de la cola. |
| Responsables y evidencia de conformidad | `recomendaciones`: _[a completar]_ · `api-general`: _[a completar]_ · `notificaciones`: _[a completar]_ |
