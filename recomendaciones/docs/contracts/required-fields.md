# Campos requeridos a `api-general`

Lo que el servicio `recomendaciones` necesita recibir de `api-general` para funcionar (FR-063): cada campo,
el requisito que lo exige y qué pasa si falta.

> **La fuente de verdad del contrato es `api-general`** (Principio II). Este documento **no** sustituye su
> documentación oficial: es la lista de lo que este repositorio consume. Los schemas propuestos están en
> [`specs/001-recomendaciones-precomputadas/contracts/`](../../specs/001-recomendaciones-precomputadas/contracts/)
> —copias derivadas, pendientes de publicación en `api-general`— y el gate de CI que los verifica es
> [`tests/contract/test_contract_gate.py`](../../tests/contract/test_contract_gate.py).

## La dependencia más grave: DEP-10

**DEP-10 (vocabulario de tags con al menos 5 tags elegibles por módulo) es la única cuyo incumplimiento
deja al sistema sin ningún usuario atendible.** La cadena: sin 5 tags elegibles, ningún usuario puede
completar la declaración de gustos (FR-083); sin declaración, toda lectura de ese módulo se rechaza (FR-088).
Ninguna de las dos reglas cede, y el módulo queda no disponible para todos los usuarios nuevos. DEP-7 es la
más grave **para el motor** (sin tags no existe la mitad del score), pero DEP-10 es la que corta el acceso.
Se vigila con `declarable_tags_total{module}` y la alerta `DeclarableTagsBelowMinimum`.

## Por canal

### Sincronización REST (Data Transformer) — contrato propuesto `api-general-sync.openapi.yaml`

Todas las respuestas son páginas con `snapshot_id`, `total` y `next_page_token` (CR-9): sin ellas no se
distingue un listado completo de uno truncado y **un listado parcial retiraría ítems vigentes en masa**.

| Registro | Campo | Obligatorio | Requisito | Si falta |
|---|---|---|---|---|
| Usuario | `id` | sí | — | El registro no es procesable |
| Usuario | `birth_date` | sí | DEP-5, CR-1, CR-2, CR-3, FR-030, FR-051 | El usuario **se rechaza** en la ingesta y no recibe recomendaciones (`contract_violations_total{field="birth_date"}`) |
| Usuario | `region` (ISO 3166-1 alfa-2, mayúsculas) | sí | DEP-11, CR-5, CR-6, FR-079 | El usuario **se rechaza** en la ingesta (`contract_violations_total{field="region"}`) |
| Ítem | `id` | sí | — | El registro no es procesable |
| Ítem | `module` (`peliculas` \| `juegos`) | sí | FR-010d | El ítem se descarta |
| Ítem | `age_rating` (literal exacto del catálogo, con `+`) | sí | CR-15, FR-051 | El ítem toma el valor **no apto** y desaparece en silencio para todo menor (`catalog_unrated_ratio`) |
| Ítem | `tags` (no vacío, nombres estables) | sí | DEP-7, DEP-10, CR-10, CR-11, CR-16 | El ítem se rechaza (FR-021b); sin tags no hay término content-based ni cruce entre módulos |
| Ítem | `status` (`available` \| `retired`) | deseable | CR-7, CR-8 | El retiro se detecta igual, por desaparición del listado completo, con el rezago del sync |
| Interacción | `origin_interaction_id` | sí | DEP-8, CR-17 | Sin idempotencia de ingesta: una reentrega entra como interacción nueva e infla la popularidad |
| Interacción | `user_id`, `item_id` | sí | — | La interacción no es procesable |
| Interacción | `signal_type` (`like` \| `dislike` \| `consumo`) | sí | DEP-1, FR-062 | El perfil no puede construirse |
| Interacción | `occurred_at` | sí | DEP-2, CR-12, FR-029d | No se resuelve el conflicto entre señales contradictorias |

### Dónde publicar los eventos

Cada evento se publica en un exchange *fanout* con el nombre del evento: **`recomendacion.actualizar.v3`** y
**`usuario.eliminado`**. El v2 (`recomendacion.actualizar`) queda en su propio exchange y este repositorio no lo
consume: un exchange compartido le entregaría también los v2 a nuestra cola. El worker declara al arrancar esos
exchanges y sus propias colas quorum, con la convención del broker de `notificaciones`: TTL de 24 h y
`x-delivery-limit` de 5. `api-general` no necesita crear colas: solo publicar en el exchange. Si se acuerdan
otros nombres, se cambian en un único lugar de este repositorio (`worker/topology.py`) (RD-116).

Cada mensaje de v3 lleva los headers AMQP **`event_type = recomendacion.actualizar.v3`** y
**`event_version = 3.0.0`**, que el contrato declara obligatorios (`x-amqp-transport`). Sin ellos, o con otro
valor, el mensaje va a la dead-letter sin interpretarse.

### Evento `recomendacion.actualizar.v3` — `recomendacion-actualizar-v3.schema.json`

| Campo | Obligatorio | Requisito | Si falta |
|---|---|---|---|
| `event_id` | sí | FR-011, DEP-9 | Sin idempotencia de evento: un reintento del broker recalcula dos veces |
| `origin_interaction_id` | sí | DEP-8, CR-17, FR-061 | El mensaje va a dead-letter; es el **mismo** identificador que en la actividad REST |
| `user_id` | sí | FR-061 | Dead-letter |
| `module` | sí | FR-061 | Dead-letter |
| `item_id` | sí | FR-061 | Dead-letter |
| `signal_type` | sí | DEP-1, FR-064 | Dead-letter: el tipo **nunca** se infiere |
| `occurred_at` (con zona horaria) | sí | DEP-2, CR-12 | Dead-letter |
| `correlation_id` | no | FR-045 | La traza no cruza el salto asíncrono |

Cada transición de estado se emite como un hecho propio, con identificador nuevo (DEP-9, CR-18): sin eso
este repositorio recibe estado y no historial.

### Evento de baja de cuenta (nombre propuesto `usuario.eliminado`) — `usuario-eliminado.schema.json`

| Campo | Obligatorio | Requisito | Si falta |
|---|---|---|---|
| `event_id` | sí | FR-091a | Sin idempotencia |
| `user_id` | sí | DEP-12, CR-19 | Dead-letter |
| `occurred_at` | sí | CR-19 | Dead-letter |

**Sin este evento la supresión no tiene disparo** (DEP-12): por sincronización la baja se ve como ausencia,
y este repositorio retendría los datos de quien pidió ser eliminado.

### Contrato de lectura (lo que `api-general` recibe)

DEP-6: el conjunto de estados de respuesta es cerrado y tiene **cinco** miembros (`personalized`,
`personalized_stale`, `fallback`, `empty_pending`, `empty_no_candidates`). La falta de declaración de gustos
**no** es un sexto estado: es un `412` de precondición (FR-088).

## Índice de dependencias (DEP-1…DEP-12)

| DEP | Qué | Estado | Dónde |
|---|---|---|---|
| DEP-1 | Tipo de señal por interacción | vigente | `signal_type` (REST y evento) |
| DEP-2 | Marca temporal por señal | vigente | `occurred_at` (REST y evento) |
| DEP-3 | — | **vacante a propósito**: el identificador fue retirado y no se reasigna | — |
| DEP-4 | Popularidad global por ítem | **resuelta internamente**: se deriva de las señales propias (Wilson, FR-033a3) | — |
| DEP-5 | Fecha de nacimiento | vigente | `birth_date` |
| DEP-6 | Acuerdo sobre los estados de respuesta | vigente | contrato de lectura |
| DEP-7 | Tags temáticos por ítem | vigente | `tags` |
| DEP-8 | Identificador propio de interacción | vigente | `origin_interaction_id` (REST **y** evento, FR-061) |
| DEP-9 | Cada transición como emisión propia | vigente | `event_id` + `origin_interaction_id` nuevos por transición |
| DEP-10 | Vocabulario con ≥ 5 tags elegibles por módulo | vigente — **la de mayor severidad** | `tags` del catálogo |
| DEP-11 | Backfill de `region` antes del despliegue | vigente | `region` de los usuarios preexistentes |
| DEP-12 | Evento de baja de cuenta | vigente | `usuario.eliminado` |

**DEP-11 merece aviso explícito**: si el backfill no está completo el día del despliegue, **todo usuario
preexistente sin `region` deja de recibir recomendaciones a la vez**. Es el comportamiento correcto según
FR-079 (la región no se infiere) y es catastrófico al mismo tiempo.

## Índice de requisitos de contrato (CR-1…CR-19)

| CR | Requisito | Estado |
|---|---|---|
| CR-1 | `birth_date` obligatoria y no nula | vigente |
| CR-2 | `birth_date` confiable, validada en origen | vigente |
| CR-3 | Sin campo `age` ni escalar equivalente | vigente |
| CR-4 | Toda corrección de `birth_date` genera evento de sincronización | vigente |
| CR-5 | `region` ISO 3166-1 alfa-2 obligatoria | vigente |
| CR-6 | Toda corrección de `region` se refleja en la siguiente sincronización | vigente |
| CR-7 | Estado de disponibilidad y retiro explícito del ítem | vigente, deseable no bloqueante |
| CR-8 | Un ítem que desaparece del catálogo se interpreta como retirado | vigente |
| CR-9 | El listado permite distinguir completo de parcial | vigente, **crítico** |
| CR-10 | Nombres de tag estables entre sincronizaciones | vigente |
| CR-11 | Sin tags que difieran solo en formato | vigente |
| CR-12 | `occurred_at` provisto por el origen | vigente |
| CR-13 | ~~`occurred_at` estable ante reentrega~~ | **retirada** (RD-50) |
| CR-14 | ~~Sin dos señales distintas con `occurred_at` idéntico~~ | **retirada** (RD-50) |
| CR-15 | `age_rating` con los literales exactos del catálogo | vigente |
| CR-16 | Conjunto de tags no vacío por ítem | vigente |
| CR-17 | Identificador de interacción único, estable y no reutilizado | vigente |
| CR-18 | Cada transición de estado se emite como hecho propio | vigente |
| CR-19 | Baja de cuenta como evento propio (`usuario.eliminado`) | vigente |

## Expectativa externa sin tarea en este repositorio

**FR-079a** — el formulario de alta de la aplicación web recoge `birth_date` y `region` como obligatorias.
Lo cumple la aplicación web; este repositorio solo verifica su efecto: el rechazo en la ingesta de un
usuario sin esos campos (SC-028).
