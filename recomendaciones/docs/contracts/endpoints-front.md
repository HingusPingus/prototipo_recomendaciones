# Propuesta: endpoints de `api-general` para el front

Propuesta de `recomendaciones` sobre lo que el front necesita de `api-general` para mostrar recomendaciones y
pedir la declaración de gustos. Se basa en el runtime de `api-general` del commit `9137825` (2026-10-01) y en
`docs/api-general-endpoints.md` de ese repositorio.

> **Estado: propuesta, sin acuerdo.** El front habla **solo** con `api-general` (Principio I de las dos
> constituciones), así que estos endpoints son de `api-general` y los define su equipo. Acá decimos qué tiene
> que ser cierto para que el front pueda usar el servicio de recomendaciones, y proponemos una forma concreta
> para destrabar.

## En corto

Hoy el front no tiene cómo:

1. **Pedir recomendaciones.** Ningún endpoint con JWT de usuario reenvía a nuestra API.
2. **Declarar gustos.** Es obligatorio para recibir recomendaciones en un módulo (FR-088), y tampoco tiene
   endpoint.
3. **Listar los tags que se pueden declarar.** El listado de tags elegibles existe, pero solo como ruta interna
   con la clave de operador.

Proponemos tres endpoints nuevos con JWT de usuario. Los tres reenvían a nuestra API con la clave interna, salvo
el listado de tags, que es de `api-general`. Además hay dos puntos a confirmar: los identificadores de ítem y el
alta de usuarios.

| # | Endpoint propuesto | Reenvía a | ¿Bloquea al front? |
|---|---|---|---|
| 1 | `GET /api/v1/users/me/recommendations` | `GET /internal/v1/recommendations/{user_id}` | Sí |
| 2 | `POST /api/v1/users/me/declarations` | `POST /internal/v1/declarations/{user_id}` | Sí |
| 3 | `GET /api/v1/catalog/tags?module=` | — (vocabulario de `api-general`) | Sí, para la pantalla de declaración |
| 4 | Identificador de ítem coherente entre recomendaciones e interacciones | — | Sí, para dar like o dislike desde una recomendación |
| 5 | Alta con fecha de nacimiento y región obligatorias | — | No, si ya se cumple |

En los tres reenvíos, `api-general` toma el `user_id` del JWT y lo traduce al `recommendation_id` (UUID) que ya
expone en la sincronización. Nunca lo recibe del cliente.

## 1. Recomendaciones del usuario

```
GET /api/v1/users/me/recommendations?module=peliculas&top_n=20
Authorization: Bearer <JWT>
```

| Parámetro | Obligatorio | Valores |
|---|---|---|
| `module` | sí | `peliculas`, `juegos` |
| `top_n` | no | 10 a 50; por defecto, el nuestro (20) |
| `prefer` | no | `stale`: aceptar un resultado obsoleto si existe (FR-056a) |

**Qué hace `api-general`**: llama a nuestro `GET /internal/v1/recommendations/{recommendation_id}` con
`X-Internal-API-Key` y completa cada `item_id` (UUID) con los datos del catálogo que muestra el front (título,
imagen, `age_rating` y el identificador que usa en el resto de sus rutas, ver punto 4).

**Reglas**:
- **Conservar el orden y no filtrar.** Los filtros de edad y exclusión ya se aplicaron de nuestro lado y no admiten
  excepción. Si un ítem ya no existe en el catálogo, se omite sin reemplazarlo: rellenar con otros ítems saltearía
  esos filtros.
- **Mostrar el `result_type`**, porque el front lo necesita para presentar el resultado:

| `result_type` | Qué significa | Qué debería mostrar el front |
|---|---|---|
| `personalized` | Recomendaciones calculadas para el usuario | La lista |
| `personalized_stale` | Calculadas para el usuario, pero vencidas; se están recalculando en segundo plano | La lista |
| `fallback` | Populares del módulo: todavía no hay cálculo personalizado | La lista, rotulada como **no personalizada** («Populares»), no como «para vos» (FR-033e) |
| `empty_pending` | Se está calculando | «Estamos preparando tus recomendaciones»; reintentar en unos segundos |
| `empty_no_candidates` | No hay ítems aptos para este usuario | Estado vacío; no es un error |

**Errores** que devolvemos y cómo traducirlos:

| Nuestro | Código | Qué significa | Propuesta para el front |
|---|---|---|---|
| `412` | `declaration_required` | El usuario no declaró gustos en ese módulo (FR-088) | `412` con el mismo código: el front abre la pantalla de declaración |
| `404` | `unknown_user` | El usuario todavía no llegó a este servicio por la sincronización | `409` con un código propio («perfil en preparación»): no es un error del usuario |
| `422` | `invalid_request` | `module` o `top_n` fuera de rango | `400` |
| `503` | `cache_unavailable`, `filters_unavailable` | Indisponibilidad momentánea; trae `Retry-After` | `503` con el mismo `Retry-After` |
| `401` | `unauthorized` | Clave interna mal configurada | `502`: es un error de configuración, nunca del usuario |

## 2. Declaración de gustos

```
POST /api/v1/users/me/declarations
Authorization: Bearer <JWT>

{"module": "peliculas", "tags": ["terror", "suspenso", "misterio", "drama", "sobrenatural"]}
```

**Qué hace `api-general`**: reenvía el cuerpo tal cual a nuestro `POST /internal/v1/declarations/{recommendation_id}`.

**Reglas que el front tiene que respetar** (FR-083, FR-086a, FR-085):
- **Al menos 5 tags**, todos del vocabulario del módulo (punto 3). Sin máximo.
- **La declaración es definitiva**: no hay edición ni retiro. El front no debería ofrecer una pantalla de edición, y
  conviene que pida confirmación antes de enviar.
- La respuesta trae `inherited_tags`: tags declarados en el otro módulo que también existen en este. Es
  informativo y sirve para preseleccionarlos en la pantalla.

| Nuestro | Código | Propuesta para el front |
|---|---|---|
| `201` | — | `201` con `module`, `declared_tags` e `inherited_tags`; sin `user_id` |
| `409` | `declaration_already_exists` | `409`: ya declaró en ese módulo |
| `422` | `invalid_request` | `400`: menos de 5 tags o tags fuera del vocabulario |
| `404` | `unknown_user` | Igual que en el punto 1 |
| `503` | — | `503` con `Retry-After` |

Después del `201`, la primera lectura puede responder `fallback` o `empty_pending` unos segundos, mientras el worker
calcula. Es el comportamiento esperado (FR-033g).

## 3. Tags declarables por módulo

```
GET /api/v1/catalog/tags?module=peliculas
Authorization: Bearer <JWT>

["accion", "aventura", "drama", "misterio", "sobrenatural", "suspenso", "terror"]
```

Hoy existe como `GET /api/v1/internal/v1/catalog/items/tags`, solo con la clave de operador. Pedimos una versión
**de solo lectura con JWT de usuario** que devuelva los **nombres canónicos** de los tags elegibles del módulo, los
mismos que la sincronización manda en el catálogo. Nuestro servicio valida la declaración contra esos nombres tal
cual llegan: no normaliza (ni mayúsculas, ni tildes, ni guiones), así que el front tiene que mandar exactamente
lo que recibió.

## 4. Identificador de ítem

Nuestras recomendaciones identifican cada ítem por su UUID (`recommendation_id`). Las rutas del front, como
`PUT /api/v1/activity/interactions/{itemId}`, usan el ID numérico del catálogo. Para que el usuario pueda dar like o
dislike desde una recomendación, la respuesta del punto 1 tiene que traer **el mismo identificador que aceptan
las demás rutas del front**. Cuál de los dos usar lo decide `api-general`; lo que pedimos es que sea uno solo.

## 5. Alta de usuarios

Toda cuenta tiene fecha de nacimiento y región desde el alta, sin excepciones (FR-079a; acuerdo del 2026-09-29). En el
inventario de endpoints no encontramos la ruta de alta, solo `PUT /api/v1/users/me/profile`. Pedimos confirmar:

- dónde se crea la cuenta y que ahí sean **obligatorias** las dos;
- que `PUT /users/me/profile` no permita vaciarlas.

Sin la fecha o la región, nuestro servicio rechaza al usuario en la ingesta y nunca recibe recomendaciones.

## Un punto de nuestro lado: la demora del alta

Un usuario recién creado no existe para nuestro servicio hasta la siguiente sincronización. Mientras tanto, los
puntos 1 y 2 responden `unknown_user`. Para acotar esa espera, la sincronización corre **cada 15 minutos** (decidido el
2026-10-05): alguien que se registra puede declarar sus gustos en ese plazo. Lo dejamos escrito para que el front
muestre el estado «perfil en preparación» en vez de un error.

## Cómo lo verificamos

Con un usuario de prueba en staging:

1. Sin declaración, `GET /users/me/recommendations?module=peliculas` responde `412 declaration_required`.
2. `GET /catalog/tags?module=peliculas` devuelve al menos 5 nombres; declarar 5 de ellos responde `201`, y repetir la
   declaración responde `409`.
3. Unos segundos después, la lectura responde `personalized` (o `fallback` mientras calcula), con los ítems en el
   mismo orden que nuestra API.
4. Un dislike sobre el primer ítem, con el identificador que trae la respuesta, hace que ese ítem desaparezca en la
   lectura siguiente.

## Qué pedimos a `api-general`

1. Definir primero en su documentación de contratos (Principio II) los endpoints 1, 2 y 3.
2. Decidir el identificador de ítem del punto 4.
3. Confirmar el punto 5.
