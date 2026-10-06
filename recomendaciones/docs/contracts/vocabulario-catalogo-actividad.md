# Propuesta: vocabulario, catálogo y actividad

Propuesta de `recomendaciones` para los ítems 6 y 7 de la respuesta de `api-general`
(`specs/004-contratos-recomendaciones`, DEP-10 y CR-7 a CR-18, tareas T014, T027 y T037). Revisa los
endpoints que escriben los datos de esos ítems y el verificador de preparación.

> **Estado al 2026-10-05, verificado en el código de `api-general` (commit `9137825`):**
>
> | # | Pedido | Estado |
> |---|---|---|
> | 1 | Mantenimiento de catálogo y tags autenticado | ✅ Interino: clave de operador `X-Catalog-Operator-API-Key` con auditoría (opción A). Su equipo de Seguridad todavía tiene que aprobarla frente a su Principio V (su T052) |
> | 2 | Responsable del vocabulario, cinco tags por módulo y catálogo etiquetado | ⏳ Pendiente: es carga de datos y responsable operativo |
> | 3 | Omitir del snapshot los ítems desactivados sin tags | ✅ `includeInRecommendationSync` |
> | 4a | Usuario derivado de una identidad validada | ✅ JWT (`UserIdentityPrincipal`); `X-User-Id` se ignora |
> | 4b | Rechazar `occurred_at` futuro | ✅ Con 5 minutos de tolerancia |
> | 4c | Serializar el v3 con `ObjectMapper` | ✅ |
> | 5 | Correr el verificador en staging y el día del despliegue | ⏳ Pendiente (su T037) |
>
> Su sincronización de catálogo responde **503 a todo el catálogo** si un ítem incluido no tiene tags
> elegibles o tiene una clasificación fuera de `ATP`, `+13`, `+18`. Hasta completar el pedido 2, el
> Transformer no puede sincronizar el catálogo real. El resto del documento describe la situación al momento
> de la propuesta.
>
> **Al 2026-10-06 (`3f4ceab`):** los retirados ya no bloquean (RD-118). Sigue el `503` a todo el catálogo con
> menos de cinco tags elegibles en un módulo. Como la corrida de este repositorio es todo o nada, eso no deja sin
> servicio solo a ese módulo, como dice el punto 1: detiene la sincronización entera (RD-119).
>
> **Al 2026-10-06 (`0a2a1b6`):** `api-general` sacó ese chequeo de la sincronización y lo dejó en su verificador
> de preparación (RD-121). Sigue el `503` a todo el catálogo por un ítem **activo** inválido.

## En corto

1. **El ítem 6 es más grande que «cargar cinco tags».** La sync de catálogo responde 503 para **todo**
   el catálogo mientras haya menos de cinco tags elegibles en algún módulo, o mientras un solo ítem
   no tenga tags elegibles, **incluidos los desactivados**. Los ítems existentes no tienen tags, porque
   no se importan desde `metadatosBasicos`. Hasta etiquetar el catálogo entero, nuestro Transformer no
   puede sincronizar.
2. **El único canal para cargar tags y etiquetar ítems no está autenticado.** Hoy el rol sale de un
   header que manda el propio cliente. Pedimos un canal autenticado y un responsable asignado.
3. **Los endpoints de actividad confían en `X-User-Id`.** Las garantías estructurales de CR-17 y CR-18
   se cumplen, pero cualquiera puede escribir interacciones a nombre de otro usuario.
4. **El verificador existe y cubre lo que pedimos.** Falta correrlo sobre datos reales. Proponemos
   correrlo ya en staging, aunque falle, para dimensionar el trabajo.

## 1. Autenticar el mantenimiento de vocabulario y catálogo

| Endpoint | Qué hace |
|---|---|
| `GET /api/v1/catalog/items/tags?module=` | Lista tags elegibles |
| `POST /api/v1/catalog/items/tags` | Crea un tag |
| `POST /api/v1/catalog/items/tags/{tagId}/retire` | Retira un tag |
| `POST /api/v1/catalog/items` | Crea un ítem con `age_rating` y `tags` |
| `PUT /api/v1/catalog/items/{itemId}` | Modifica un ítem, incluidos `age_rating` y `tags` |
| `POST /api/v1/catalog/items/{itemId}/deactivate` | Desactiva un ítem |

**Hoy:** `CatalogService.requireAdmin` compara contra `ADMIN_VENDEDOR` el valor del header
`X-User-Role`, que manda el cliente, y `SecurityConfig` deja estas rutas en `permitAll`. Cualquiera
que llegue al servicio puede declararse administrador. Su propio
`docs/operations/recommendation-readiness.md` ya lo marca como bloqueo.

**Por qué nos afecta directamente:**

- Cualquiera puede cambiar el `age_rating` de un ítem de `+18` a `ATP`. Nuestro filtro etario toma ese
  literal tal cual (CR-15): recomendaríamos ese ítem a menores.
- Cualquiera puede retirar tags. Con menos de cinco en un módulo, la sync de catálogo cae en 503 y,
  del lado nuestro, el módulo deja de estar disponible para todo usuario nuevo (DEP-10).

**Lo que tiene que ser cierto, con cualquier implementación:**

- El rol sale de una identidad validada por `api-general`, nunca de un header que controla el cliente.
- Toda escritura sin esa identidad se rechaza, y los rechazos se miden sin loguear credenciales.
- Queda registrado quién hizo cada cambio de tags, `age_rating` y estado.
- No se reutiliza la API key de `recomendaciones`. Nuestro Transformer es de solo lectura por diseño,
  y una key que puede escribir catálogo rompería esa garantía.

**Opciones:**

- **A. Interina, la recomendamos para destrabar el ítem 6.** Mover el mantenimiento a
  `/internal/v1/catalog/...`, protegido por una key de operador **propia**, distinta por entorno y
  entregada solo al responsable del vocabulario. Reutiliza el patrón de `ServiceApiKeyFilter`: prefijo
  de entorno, rotación, vencimiento y comparación en tiempo constante. Las rutas públicas con
  `X-User-Role` quedan deshabilitadas en producción hasta tener la opción B. Les toca evaluar si una
  key operada por una persona entra en su Principio V.
- **B. Definitiva.** Tokens de usuario final emitidos por `api-general`, con el rol `ADMIN_VENDEDOR`
  evaluado del lado del servidor. Es lo que pide su Principio V, pero es un proyecto más grande, y
  el ítem 6 bloquea producción.

## 2. Responsable y procedimiento de carga (DEP-10)

Pedimos que nombren un responsable del vocabulario por entorno y que la carga siga estos pasos:

1. **Vocabulario:** al menos cinco tags elegibles por módulo, con nombres aprobados por el
   responsable. **Recomendamos apuntar a más de cinco,** por ejemplo ocho. Con cinco exactos, retirar
   uno solo corta el módulo entero, en la sync de `api-general` y en nuestra alerta
   `DeclarableTagsBelowMinimum`.
2. **Etiquetado:** asignar al menos un tag elegible del módulo correcto a **cada ítem activo**. Como
   los tags de `metadatosBasicos` no se importan, este paso abarca todo el catálogo existente.
3. **Ítems desactivados:** ver el punto 3.
4. **Evidencia:** el reporte del verificador con `eligible_tags_peliculas`, `eligible_tags_juegos` y
   `catalog_item_contract` en `failed = 0`.

## 3. Que un ítem desactivado no bloquee el catálogo

**Hoy:** `syncCatalog` proyecta `catalogItems.findAllByOrderByIdAsc()`, es decir, también los ítems
desactivados. `catalogProjection` responde 503 si **cualquier** ítem no tiene tags elegibles o tiene un
`age_rating` fuera de los tres literales. Un ítem dado de baja hace años y nunca etiquetado bloquea
toda la sync. Retirar un tag deja en la misma situación a los ítems desactivados que solo tenían ese.

**Propuesta:**

- **Ítems desactivados sin tags elegibles: omitirlos del snapshot.** Es compatible con el contrato:
  por CR-8, un ítem ausente de un listado completo lo tratamos como retirado, y eso es lo que es.
  Los desactivados que sí tienen tags pueden seguir yendo con `status: retired`.
- **Ítems activos: mantener el 503** tal como está. Un ítem activo sin tags o con clasificación
  inválida es un defecto de datos que hay que corregir, no esconder, y un listado que lo omitiera nos
  haría retirarlo.
- **Verificador:** ajustar `catalog_item_contract` para que exija tags solo a los ítems activos, igual
  que la sync.

## 4. Endpoints de actividad (CR-12, CR-17, CR-18)

Endpoint: `PUT /api/v1/activity/interactions/{itemId}`.

- **Identidad:** el usuario sale de `X-User-Id`, que manda el cliente. Cualquiera puede registrar likes
  y consumos a nombre de otro: eso infla la popularidad y contamina el perfil de gustos del usuario.
  Los hechos respetan la estructura (uno nuevo por transición, ID `BIGSERIAL` no reutilizado), pero
  su contenido no es confiable. Se resuelve con la opción B del punto 1. Pedimos una fecha estimada.
  Lo mismo aplica a `PUT /users/me/profile`, que escribe la `birth_date` y la `region` de las que
  depende el ítem 5.
- **`occurred_at` (CR-12):** hoy se acepta cualquier instante. Proponemos rechazar valores en el
  futuro, con una tolerancia de reloj de 5 minutos.
- **Payload del evento v3:** `InteractionService` arma el JSON concatenando strings. Un
  `correlation_id` con comillas produce JSON inválido: el evento queda `ERROR_BLOQUEADO`, el hecho
  queda sin evento y el check `activity_fact_event_identity` falla. Proponemos serializarlo con
  `ObjectMapper`, como ya hace `AccountDeletionService`. Los tipos de `origin_interaction_id` y de los
  IDs los tratamos en la propuesta del ítem 4 (`alineacion-sync.md`).
- **Evento v2:** cada transición emite además un `recomendacion.actualizar` v2. Es el conflicto de
  exchange del ítem 2 y se resuelve allí.

## 5. Verificación de preparación (ítem 7, T037)

El script `scripts/verify-recommendation-readiness.sh` cubre lo que necesitamos: perfiles, tags por
módulo, contrato de ítems, colisiones de formato, procedencia de la actividad, identidad entre hechos
y eventos, e integridad de snapshots. Proponemos:

1. **Correrlo ya en staging, aunque falle.** Hoy esperamos FAIL en `verified_user_profile` (ítem 5),
   en `eligible_tags_*` y `catalog_item_contract` (ítem 6), y probablemente en
   `activity_transition_provenance`, por los registros heredados. Los conteos de `total` y `failed`
   dimensionan cuánto trabajo queda en cada punto, y es mejor saberlo ahora que el día del despliegue.
2. **Mandarnos el JSON.** Es seguro compartirlo: por diseño solo contiene agregados, sin IDs de usuario
   ni credenciales.
3. **Criterio de aceptación para producción:** un reporte por entorno, con todos los checks en
   `failed = 0`, generado el día del despliegue, como pide su propia FR-019.
4. **Complemento HTTP:** el SQL no puede probar CR-8 ni CR-9, porque dependen de recorrer las páginas.
   Para eso proponemos la corrida de nuestro Transformer contra su staging, descrita en
   `alineacion-sync.md`.

## Resumen de pedidos

| # | Qué | Dónde | ¿Bloquea producción? |
|---|---|---|---|
| 1 | Rol derivado de una identidad validada en el mantenimiento de catálogo y tags | `CatalogController`, `CatalogService`, `SecurityConfig` | Sí (ítem 6) |
| 2 | Responsable del vocabulario, más de cinco tags por módulo y todos los ítems activos etiquetados | Operación, con evidencia del verificador | Sí (ítem 6) |
| 3 | Omitir del snapshot los ítems desactivados sin tags | `RecommendationIntegrationService.syncCatalog`, `recommendation-readiness.sql` | Sí: sin esto, la sync no arranca con el catálogo heredado |
| 4a | Usuario derivado de una identidad validada en actividad y perfil | `ActivityController`, `UserProfileController` | Pedimos una fecha |
| 4b | Rechazar `occurred_at` futuro | `InteractionService.upsert` | No |
| 4c | Serializar el v3 con `ObjectMapper` | `InteractionService.upsert` | No, pero evita eventos bloqueados |
| 5 | Correr el verificador en staging ahora y en cada entorno el día del despliegue | `verify-recommendation-readiness.sh` (T037) | Sí (ítem 7) |
