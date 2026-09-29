# Propuesta: alinear la sincronización con el contrato

Propuesta de `recomendaciones` para el ítem 4 de la respuesta de `api-general`
(`specs/004-contratos-recomendaciones`, tareas T019, T020, T045, T046 y T047). Compara el contrato
`contracts/api-general-sync.openapi.yaml` de la spec 004 con el runtime actual de `api-general` y
propone cómo cerrar cada diferencia.

> **Estado: propuesta, sin acuerdo.** El contrato lo custodia `api-general` (Principio II). Donde
> proponemos aceptar el runtime tal como está, ese cambio en el contrato lo tiene que registrar
> `api-general`.

## En corto

El formato de la API key (`<entorno>.<secreto>`) y su validación ya coinciden. Quedan tres
diferencias que impiden que nuestro Transformer se conecte, una que el contrato exige pero hoy no nos
bloquea, y tres más que proponemos aceptar como están para ahorrarles trabajo.

| # | Qué | Pedido | Esfuerzo estimado |
|---|---|---|---|
| 1 | Ruta | Registrar `/internal/v1/sync/...` | Renombrar cuatro constantes |
| 2 | Header | Aceptar `X-Internal-API-Key` en las rutas de sync | Una constante en el filtro |
| 3 | IDs | UUID estable por usuario e ítem, igual en todos los canales (T045) | El único cambio grande |
| 4 | `snapshot_id` en usuarios y actividad | Agregarlo al sobre de página. No es bloqueante | Chico: no requiere tabla nueva |
| — | `page_size`, `expires_at` + 410, campo `complete` | Dejarlos como están y documentarlos | Solo documentación |

## Diferencias entre el contrato y el runtime

| Aspecto | Contrato (spec 004) | Runtime | Efecto en nuestro Transformer |
|---|---|---|---|
| Ruta | `/internal/v1/sync/{users,catalog/items,activity}` | `/api/v1/internal/sync/...` (`context-path: /api/v1`) | 404 en las tres llamadas |
| Header | `X-Internal-API-Key` | `X-Service-Api-Key` (`ServiceApiKeyFilter`) | 401 en todas las llamadas |
| `id` de usuario e ítem | `string`, `format: uuid` | `Long` (`User`, `SyncCatalogItem`) | La pasada se aborta al convertir el ID a UUID |
| `user_id`, `item_id` en actividad | UUID | `Long` (`Interaction`) | Igual que la fila anterior |
| `origin_interaction_id` | `string`, estable y no reutilizado | `Long` (`BIGSERIAL`) | Lo guardamos como texto: un número no coincide con el mismo ID en formato string |
| `snapshot_id` | Requerido en toda página | Solo en catálogo | Hoy ninguno: solo exigimos pasada completa en el catálogo, que ya lo trae |
| `page_size` | 1–1000, por defecto 500 | 1–500, por defecto 100 | Ninguno: siempre pedimos 500 |
| `expires_at` y 410 en catálogo | No documentados | Presentes (TTL de 24 h) | Ninguno: un 410 aborta la pasada sin marcar retiros |
| `complete` en la página | No existe | Presente | Ninguno: lo ignoramos y calculamos la completitud nosotros |

## Propuesta punto por punto

### 1. Ruta

Mapear el controlador de sync a `/internal/v1/sync/...` y conservar `context-path: /api/v1`. El URL
completo queda `/api/v1/internal/v1/sync/users`. En el contrato alcanza con declarar
`servers: - url: /api/v1`.

El cambio toca cuatro lugares, todos con la constante `/internal/sync/`:
`RecommendationIntegrationController` (tres `@GetMapping`), `ServiceApiKeyFilter.SYNC_PREFIX`,
`SecurityConfig` (`requestMatchers`) y `RecommendationRequestMetricsFilter`.

**De nuestro lado** solo cambia la configuración: `RECO_API_GENERAL_BASE_URL` pasa a incluir `/api/v1`.
No tocamos código.

Si prefieren conservar `/internal/sync/...`, también nos sirve: en ese caso cambiamos tres rutas en
nuestro cliente. Pedimos que la decisión quede por escrito en el contrato, sea cual sea.

### 2. Header

Leer la key de `X-Internal-API-Key` en las rutas de sync. Es el mismo header que exige nuestra API
cuando `api-general` la llama (`/internal/v1/recommendations/{user_id}`), así que queda un solo nombre
en las dos direcciones.

El resto de `ServiceApiKeyFilter` no cambia. La validación del prefijo de entorno, el solapamiento entre
la key actual y la anterior, el vencimiento independiente y la comparación en tiempo constante ya
cumplen lo acordado. Si las rutas heredadas `/internal/recommendations/` tienen otros consumidores,
pueden seguir aceptando `X-Service-Api-Key` ahí.

### 3. IDs: un UUID estable por entidad (T045)

**Propuesta:** agregar una columna `public_id UUID NOT NULL UNIQUE` a `app_user` y a `catalog_item`. Se
genera una sola vez (`DEFAULT gen_random_uuid()` y un backfill de las filas existentes) y no se regenera
nunca. La clave primaria `Long` sigue siendo interna y no cambia.

El `public_id` es el que se expone en **todos** los canales:

| Canal | Campo |
|---|---|
| Sync de usuarios / catálogo | `id` |
| Sync de actividad | `user_id`, `item_id` |
| Evento `recomendacion.actualizar.v3` | `user_id`, `item_id` |
| Evento `usuario.eliminado` | `user_id` (hoy el schema del runtime lo declara `integer`) |
| Llamadas a nuestra API | `{user_id}` en la ruta; los `item_id` de la respuesta se resuelven con `public_id` |

**`origin_interaction_id`:** alcanza con `String.valueOf(id)` del hecho de interacción. Un `BIGSERIAL`
no se reutiliza, así que ya cumple la condición de «estable y no reutilizado». Lo único que pedimos es
que sea el **mismo string** en el REST y en el evento v3 (T047), porque deduplicamos por ese valor
comparándolo como texto.

**Por qué el mismo UUID en todos los canales.** Si el `user_id` de `usuario.eliminado` no coincide con
el `id` que llegó por sync, suprimimos a un usuario que no existe. La verificación no encuentra nada,
registra la supresión como completa, y los datos del usuario real quedan retenidos sin que ninguna
alerta lo detecte. Por la misma razón el UUID no puede cambiar: veríamos un usuario nuevo, y el viejo
quedaría como proyección huérfana que nunca se borra, porque la ausencia en el sync no cuenta como baja.

### 4. `snapshot_id` en usuarios y actividad (no bloqueante)

Hoy no nos bloquea: solo abortamos la sincronización por pasada incompleta en el catálogo. Pero el
contrato lo exige en toda página, así que conviene cumplirlo o sacarlo del contrato de forma explícita.
Puede ir después de los IDs.

Agregar `snapshot_id` al sobre `Page` de usuarios y de actividad, con el mismo valor en todas las páginas
de una pasada y un `total` calculado sobre ese mismo corte. Hoy solo lo tiene el catálogo.

No hace falta una tabla como `recommendation_catalog_snapshot`. Alcanza con un corte que se fije en la
primera página y viaje dentro del `page_token`: por ejemplo, el mayor `id` y el instante de inicio. El
`RecommendationSyncTokenService` ya firma tokens que llevan `snapshotId`.

### 5. Lo que proponemos aceptar como está

- **`page_size` de 1–500, por defecto 100.** Pedimos siempre 500. Proponemos que el contrato adopte
  los valores del runtime.
- **`expires_at` y 410 en catálogo.** T046 los quita «salvo aprobación explícita»: por nuestra parte,
  aprobamos conservarlos. Un snapshot vencido es un listado que no se puede completar, y ya lo
  tratamos así: abortamos la pasada sin marcar retiros y la corrida siguiente empieza de cero. Solo
  pedimos que el contrato documente el 410 y el TTL.
- **Campo `complete`.** Podemos ignorarlo sin problema, porque `Page` no declara
  `additionalProperties: false`.

## Cómo lo verificamos

Con la key de staging (por canal seguro, nunca en el repo ni en el mismo mensaje):

1. Corremos nuestro Transformer contra su staging. Las tres pasadas tienen que terminar completas: un
   mismo `snapshot_id`, la última página sin `next_page_token` y la cantidad recibida igual a `total`.
   En usuarios y actividad, esto aplica una vez agregado el `snapshot_id` del punto 3.
2. Tomamos un usuario de prueba y confirmamos que el `id` del sync y el `user_id` de `usuario.eliminado`
   y de `recomendacion.actualizar.v3` son el mismo UUID.
3. Pedimos una recomendación para ese usuario a nuestra API y confirmamos que `api-general` resuelve
   los `item_id` devueltos.

Del lado de `api-general`, esto se complementa con sus tests de conformidad de T021 y T048.

## Orden sugerido

1. **Ruta y header.** Son cambios mínimos y ya permiten conectarse y probar la autenticación de punta a
   punta.
2. **IDs (T045).** Es el cambio grande. También destraba el ítem 3, porque el evento de baja tiene hoy
   el mismo problema, y el evento v3 del ítem 2.
3. **`snapshot_id` en usuarios y actividad.** No es bloqueante.
