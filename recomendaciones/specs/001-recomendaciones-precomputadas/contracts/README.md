# Contratos de la feature 001 — copias derivadas

> **Custodio: `api-general`.** Estos archivos son **copias derivadas de verificación**, no la fuente de
> verdad (Principio II de la constitución). El contrato vigente es el publicado en la documentación de
> contratos de `api-general`. Ante cualquier diferencia, manda aquel y estas copias se resincronizan.

Este repositorio **redacta** las propuestas porque tiene prioridad de definición (RD-47): `api-general`
está incompleta y a la espera de este modelo. Redactar no es publicar.

**Acuerdo (2026-09-29, RD-113)**: el PR de contratos de `api-general` se dio por abierto y cerrado por
diálogo personal entre los equipos; no hay enlace a un PR. El documento de `api-general` que publica estos
contratos es su spec `specs/004-contratos-recomendaciones` (estado del 2026-09-29, commit `4636c17` de ese
repositorio), el que cita la tabla de abajo. `docs/contracts/required-fields.md` se envió a
`api-general` para su revisión.

## Estado de publicación

| Archivo | Contrato | Versión | Estado | Publicado en `api-general` | Fecha de sincronización |
|---|---|---|---|---|---|
| `recomendaciones-api.openapi.yaml` | Lectura del top-N, declaración de gustos y, desde 1.1.0, consulta de la recepción de una baja (expuestos por este repo) | 1.1.0 | **Publicado** (`publicado-en-main`, confirmado el 2026-10-06; RD-121). Agrega `GET /internal/v1/deletion-receipts/{event_id}` (T077, RD-117) con `200`, `401`, `404`, `422` y `503`, y conserva `/health` (RD-118) | ✅ Copia literal de `api-general` en `main`, commit `0a2a1b6`: `specs/004-contratos-recomendaciones/contracts/recomendaciones-api.openapi.yaml` | 2026-10-06 |
| `recomendacion-actualizar-v3.schema.json` | Evento `recomendacion.actualizar.v3` (consumido) | 3.0.0 | **Acordado**; topología aprobada por `notificaciones` el 2026-10-06 (RD-120). `api-general` lo rotula `aprobacion-reportada-no-publicada` hasta adjuntar esa respuesta | ✅ Copia literal de `api-general` en `main`, commit `0a2a1b6`: `specs/004-contratos-recomendaciones/contracts/recomendacion-actualizar-v3.schema.json`. Exige los headers AMQP `event_type` y `event_version` = `3.0.0` | 2026-10-06 |
| `usuario-eliminado.schema.json` | Evento de baja de cuenta `usuario.eliminado` (CR-19, DEP-12) | 1.0.0 | **Acordado**; `api-general` propone el **2026-10-30** para staging. Recepción registrada (T074, T075) y consultable (T077, [propuesta](../../../docs/contracts/checkpoint-baja.md)). Desde `0a2a1b6` declara headers AMQP obligatorios; el worker **no** los exige para este evento, a propósito: una baja no va a la DLQ por un header (RD-121) | ✅ Copia literal de `api-general` en `main`, commit `0a2a1b6`: `specs/004-contratos-recomendaciones/contracts/usuario-eliminado-1.0.0.schema.json` (allá con la versión en el nombre) | 2026-10-06 |
| `api-general-sync.openapi.yaml` | Endpoints REST de `api-general` que consume el Data Transformer | 1.0.0 | **Acordado**. Desde `0a2a1b6` documenta que omite los usuarios sin perfil verificado, que el mínimo de tags no bloquea el catálogo y que `since` es opcional (RD-121). Falta verificarlo contra staging ([alineación](../../../docs/contracts/alineacion-sync.md)) | ✅ Copia literal de `api-general` en `main`, commit `0a2a1b6`: `specs/004-contratos-recomendaciones/contracts/api-general-sync.openapi.yaml` (`module` obligatorio en la actividad; prefijo `/api/v1`) | 2026-10-06 |

**Gate de merge** (T049; constitución, Flujo de Desarrollo): T023, T033 y T053 **no se fusionan**
hasta que el PR o documento de `api-general` que publica estos contratos exista, esté enlazado en la
tabla de arriba y registre la conformidad de los repos consumidores. Pueden desarrollarse y probarse
contra estas propuestas; lo que no pueden es fusionarse. **Cumplido el 2026-09-29**: el documento es la
spec 004 de `api-general` citada arriba, y la conformidad quedó registrada por el acuerdo personal de
RD-113.

## Reglas

- La implementación se ajusta al contrato, **nunca** el contrato a la implementación:
  `tests/contract/test_openapi_conformance.py` compara el OpenAPI que genera la aplicación contra
  `recomendaciones-api.openapi.yaml` y falla si divergen una ruta, un campo requerido o un código.
- Cambiar nombre, forma, semántica o versión de un contrato **no** es un cambio interno: se actualiza
  primero en `api-general`, se coordina con los repos afectados y recién después se implementa acá.
- Los cinco `result_type` son parte del contrato (FR-057): agregar uno es cambio incompatible (FR-058).
  La falta de declaración de gustos es `412`, **no** un sexto estado (FR-088, DEP-6).
- Campos requeridos a `api-general`, uno por uno: `docs/contracts/required-fields.md` (T047).
