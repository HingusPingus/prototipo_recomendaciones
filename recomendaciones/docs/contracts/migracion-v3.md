# Propuesta: consumir `recomendacion.actualizar.v3`

Propuesta de `recomendaciones` para el ítem 2 de la respuesta de `api-general` (nombres y schemas finales
de los eventos, `specs/004-contratos-recomendaciones`). Se basa en el runtime de `api-general` del commit
`4636c17` (2026-09-29) y en `docs/operations/recommendation-outbox-routing.md`.

> **Estado: aplicada el 2026-10-05 (RD-116).** `api-general` separó el exchange de v3 y alineó el contrato
> (commit `9137825` de su repositorio); de nuestro lado se aplicaron los pasos de «Cambios de nuestro lado».
> Falta que `notificaciones` confirme la topología antes de habilitar la publicación en un entorno compartido.
> El resto del documento describe la situación al momento de la propuesta.

## En corto

- **Consumimos solo v3.** v2 sigue existiendo para quien lo use, pero no lo leemos.
- **Pedimos un exchange propio para v3: `recomendacion.actualizar.v3`.** Hoy la propuesta de ruteo publica
  v2 y v3 en el mismo exchange `recomendacion.actualizar`, y eso nos manda **un mensaje a la dead-letter
  por cada interacción** (ver [abajo](#por-qué-no-el-mismo-exchange)).
- **Para `api-general` el cambio es de configuración:** `RECOMMENDATIONS_OUTBOX_V3_EXCHANGE=recomendacion.actualizar.v3`.
  Además pedimos alinear el contrato con el runtime en tres puntos.
- **De nuestro lado:** una constante, el schema, un chequeo de headers y los tests. Alrededor de medio día.

## Qué hay hoy en cada lado

| Lado | Pieza | Estado |
|---|---|---|
| `api-general` | `InteractionService` | Por cada interacción guarda **dos** filas de outbox: v2 (`{evento_id, usuario_id}`) y v3 (los siete campos), cada una con su propio `event_id` y el mismo `correlation_id` |
| `api-general` | `OutboxPublisher` | Manda `messageId` = `event_id` y los headers AMQP `event_type` y `event_version` (`recomendacion.actualizar.v3` / `3.0.0`) |
| `api-general` | Payload v3 | Ya usa UUID (`recommendation_id`) para `user_id` e `item_id`, y texto no vacío para `origin_interaction_id` |
| `api-general` | Ruteo propuesto | Los dos exchanges de actualización apuntan a `recomendacion.actualizar` (fanout) |
| `recomendaciones` | Worker | Declara el exchange fanout `recomendacion.actualizar` y su cola quorum `recomendaciones.recomendacion-actualizar`, y valida cada mensaje contra el schema de siete campos |
| `recomendaciones` | Alerta `DeadLetterGrowth` | Dispara con más de 5 mensajes en la DLQ en 30 minutos, sostenido durante 15 |

## Por qué no el mismo exchange

Un exchange fanout copia **todo** mensaje a **toda** cola ligada. Si v2 y v3 van al mismo exchange, cada
interacción nos deja dos mensajes:

1. **v3:** se valida y se procesa. Correcto.
2. **v2:** no trae `signal_type`, `origin_interaction_id` ni los demás campos. Falla el schema y va a la DLQ
   como `invalid_payload`.

Con más de 5 interacciones cada 30 minutos, `DeadLetterGrowth` queda **disparada todo el tiempo**. Además,
la DLQ se llena de mensajes que no son fallos, y un payload roto de verdad queda escondido entre ellos.

Tampoco nos sirve procesar los dos: sus `event_id` son distintos, así que nuestra idempotencia no los
reconoce como el mismo hecho, y v2 no trae la señal. Para usarlo tendríamos que pedirla por REST en cada
evento.

### Alternativas

| Opción | Qué implica para `api-general` | Qué implica para nosotros | Riesgo |
|---|---|---|---|
| **A. Exchange propio para v3** (recomendada) | Un valor de configuración | Una constante | Ninguno: un v2 nunca llega a nuestra cola |
| B. Mismo exchange; descartamos v2 por header | Nada | Confirmar y descartar sin DLQ todo mensaje cuyo `event_type` no sea v3, con un contador propio | Recibimos el doble de mensajes. Si un v2 llega sin header, no podemos distinguirlo de un v3 roto |
| C. Exchange de tipo *headers* con filtro por `event_type` | Cambiar el tipo del exchange, que afecta a los demás consumidores de v2 | Ligar la cola con el filtro | Toca a terceros |

## Qué conservamos de v2

v2 garantizaba tres cosas. Ninguna se pierde con v3:

| Garantía de v2 | Cómo sigue vigente |
|---|---|
| El ID del evento es estable entre reintentos y distinto del `correlation_id` | v3 tiene `event_id` con la misma regla. Es nuestra clave de idempotencia (`processed_events`) |
| El REST de actividad es la autoridad; el evento solo avisa | Guardamos la señal del evento, pero la sincronización sigue mandando y descarta duplicados por `origin_interaction_id` (T064, FR-020). Si el evento y el REST no coinciden, se cuenta como violación de contrato |
| Schema estricto (`additionalProperties: false`) | Aceptamos campos extra, así que un v3 que agregue un campo opcional no nos rompe |

## Diferencias entre el contrato y el runtime de v3

Nuestra copia del schema tiene que ser idéntica al contrato publicado (FR-009: no lo redefinimos). Hoy el
contrato de la spec 004 y el runtime no dicen lo mismo:

| Aspecto | Contrato (spec 004) | Runtime (`4636c17`) | Pedido |
|---|---|---|---|
| `origin_interaction_id` | Texto, sin mínimo | Texto, `minLength: 1` | Llevar `minLength: 1` al contrato. Un texto vacío pasaría el contrato y haría colisionar todas esas interacciones en nuestra deduplicación |
| `additionalProperties` | `true` | `false` | Elegir uno y dejarlo igual en los dos. A nosotros nos sirve cualquiera |
| Headers `event_type` y `event_version` | No documentados | Presentes | Documentarlos en el contrato, así podemos apoyarnos en ellos |

## Cambios de nuestro lado, una vez aprobado

Siguiendo TDD: primero los tests, en un commit propio, y después la implementación.

1. **Exchange.** El worker declara y se liga a `recomendacion.actualizar.v3` en lugar de
   `recomendacion.actualizar`. Es una sola constante en `src/recomendaciones/worker/topology.py`. La
   declaración es idempotente; si `notificaciones` prefiere crear el exchange, no molesta.
2. **Colas sin cambio de nombre.** `recomendaciones.recomendacion-actualizar`, su `.retry` y su `.dlq` son
   nuestras y no forman parte del contrato. Mantenerlas evita tocar alertas y runbook.
3. **Schema.** Reemplazar nuestra copia por la publicada, `recomendacion-actualizar-v3.schema.json`
   (3.0.0), idéntica en `specs/001-recomendaciones-precomputadas/contracts/` y en `worker/contracts/`. El
   test de copias idénticas ya lo verifica.
4. **Chequeo de headers.** Si llega `event_type` y no es `recomendacion.actualizar.v3`, o `event_version`
   no es de la versión mayor 3, el mensaje va a la DLQ con una causa explícita (`evento de otra versión`).
   Si el header no viene, se valida solo por el schema, porque hoy el contrato no lo exige. Con la opción A
   esto no debería ocurrir nunca: es la red para un error de configuración.
5. **Tests.** Se ajustan los del consumidor, la topología y el gate de contratos. Se agregan dos:
   - un mensaje v2 publicado en `recomendacion.actualizar` **no llega** a nuestra cola;
   - un mensaje con `event_type` de v2 que llegue a nuestra cola va a la DLQ con la causa de versión.
6. **Documentos.** El nombre `recomendacion.actualizar` aparece 41 veces en spec, plan, tasks, data-model y
   constitución. No lo renombramos: un registro de decisión declara que en esos textos designa al contrato
   publicado como `recomendacion.actualizar.v3`. Sí se actualizan los documentos operativos: la sección
   «Dónde publicar los eventos» de `required-fields.md`, la arquitectura y el runbook.

**Qué no cambia:** idempotencia, reintentos con backoff, DLQ, persistencia de la señal, alertas y el evento
`usuario.eliminado`.

## Cómo lo verificamos

En staging, con la cola del worker ligada al exchange nuevo:

1. Registrar una interacción en `api-general`: llega **un** mensaje a nuestra cola, se procesa y la DLQ
   queda en cero.
2. Confirmar que el v2 de esa misma interacción no aparece en nuestra cola.
3. Confirmar que el `user_id` y el `item_id` del evento son los mismos UUID que devuelve la sincronización,
   y que `origin_interaction_id` coincide con el de la actividad REST.
4. Del lado del repositorio, el gate de contratos comprueba que nuestra copia es idéntica a la publicada.

## Qué pedimos a `api-general`

1. Aprobar la opción A y configurar `RECOMMENDATIONS_OUTBOX_V3_EXCHANGE=recomendacion.actualizar.v3`. El
   exchange de v2 queda como está.
2. Alinear el contrato v3 con el runtime en los tres puntos de la tabla de diferencias.
3. Confirmar la opción elegida por escrito en `contracts/approval.md`. Con eso migramos y avisamos, y
   coordinamos la cola con `notificaciones`.

El retiro de v2 no nos afecta: como no lo consumimos, puede deprecarse cuando lo decidan sus consumidores.
