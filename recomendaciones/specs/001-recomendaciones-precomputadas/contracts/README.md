# Contratos de la feature 001 — copias derivadas

> **Custodio: `api-general`.** Estos archivos son **copias derivadas de verificación**, no la fuente de
> verdad (Principio II de la constitución). El contrato vigente es el publicado en la documentación de
> contratos de `api-general`. Ante cualquier diferencia, manda aquel y estas copias se resincronizan.

Este repositorio **redacta** las propuestas porque tiene prioridad de definición (RD-47): `api-general`
está incompleta y a la espera de este modelo. Redactar no es publicar.

## Estado de publicación

| Archivo | Contrato | Versión | Estado | Publicado en `api-general` | Fecha de sincronización |
|---|---|---|---|---|---|
| `recomendaciones-api.openapi.yaml` | Lectura del top-N y declaración de gustos (expuestos por este repo) | 1.0.0-propuesta | **Propuesta, no publicada** | ⚠️ PENDIENTE — enlazar el PR/documento | — |
| `recomendacion-actualizar.schema.json` | Evento `recomendacion.actualizar` (consumido) | 1.0.0-propuesta | **Propuesta, no publicada** | ⚠️ PENDIENTE — enlazar el PR/documento | — |
| `usuario-eliminado.schema.json` | Evento de baja de cuenta, nombre propuesto `usuario.eliminado` (CR-19, DEP-12) | 1.0.0-propuesta | **Propuesta, no publicada** | ⚠️ PENDIENTE — debe publicarse **antes** de implementar T058 | — |
| `api-general-sync.openapi.yaml` | Endpoints REST de `api-general` que consume el Data Transformer | 1.0.0-propuesta | **Propuesta, no publicada** — hueco del backlog: ninguna tarea los definía | ⚠️ PENDIENTE | — |

**Gate de merge** (T049; constitución, Flujo de Desarrollo): T023, T033 y T053 **no se fusionan**
hasta que el PR o documento de `api-general` que publica estos contratos exista, esté enlazado en la
tabla de arriba y registre la conformidad de los repos consumidores. Pueden desarrollarse y probarse
contra estas propuestas; lo que no pueden es fusionarse.

## Reglas

- La implementación se ajusta al contrato, **nunca** el contrato a la implementación:
  `tests/contract/test_openapi_conformance.py` compara el OpenAPI que genera la aplicación contra
  `recomendaciones-api.openapi.yaml` y falla si divergen una ruta, un campo requerido o un código.
- Cambiar nombre, forma, semántica o versión de un contrato **no** es un cambio interno: se actualiza
  primero en `api-general`, se coordina con los repos afectados y recién después se implementa acá.
- Los cinco `result_type` son parte del contrato (FR-057): agregar uno es cambio incompatible (FR-058).
  La falta de declaración de gustos es `412`, **no** un sexto estado (FR-088, DEP-6).
- Campos requeridos a `api-general`, uno por uno: `docs/contracts/required-fields.md` (T047).
