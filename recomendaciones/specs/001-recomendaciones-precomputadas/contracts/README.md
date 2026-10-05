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
| `recomendaciones-api.openapi.yaml` | Lectura del top-N y declaración de gustos (expuestos por este repo) | 1.0.0 | **Acordado** | ✅ Por diálogo personal (RD-113). Copia de `api-general`: `specs/004-contratos-recomendaciones/contracts/recomendaciones-api.openapi.yaml` | 2026-09-29 |
| `recomendacion-actualizar-v3.schema.json` | Evento `recomendacion.actualizar.v3` (consumido) | 3.0.0 | **Acordado**; el exchange propio `recomendacion.actualizar.v3` lo confirma `notificaciones` antes de habilitarlo (RD-116) | ✅ Copia literal de `api-general`: `specs/004-contratos-recomendaciones/contracts/recomendacion-actualizar-v3.schema.json`, commit `9137825`. Exige los headers AMQP `event_type` y `event_version` (`x-amqp-transport`) | 2026-10-05 |
| `usuario-eliminado.schema.json` | Evento de baja de cuenta `usuario.eliminado` (CR-19, DEP-12) | 1.0.0 | **Acordado**; `api-general` propone el **2026-10-30** para staging. El registro de la recepción está implementado (T074, T075); la consulta de recepción, bloqueada (T077) ([propuesta](../../../docs/contracts/checkpoint-baja.md)) | ✅ Por diálogo personal (RD-113); estructuralmente igual a la de `api-general` (commit `9137825`) | 2026-10-05 |
| `api-general-sync.openapi.yaml` | Endpoints REST de `api-general` que consume el Data Transformer | 1.0.0 | **Acordado**; su runtime lo implementa desde los commits `4636c17` y `9137825`. Falta verificarlo contra staging ([alineación](../../../docs/contracts/alineacion-sync.md)) | ✅ Copia literal de `api-general`: `specs/004-contratos-recomendaciones/contracts/api-general-sync.openapi.yaml`, commit `9137825` (`module` obligatorio en la actividad; prefijo `/api/v1`) | 2026-10-05 |

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
