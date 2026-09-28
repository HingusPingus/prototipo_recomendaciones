---
description: "Desglose de tareas ejecutables — Feature 001"
---

# Tasks: Servicio de Recomendaciones Híbridas Precomputadas

**Input**: `specs/001-recomendaciones-precomputadas/` · **Branch**: `001-recomendaciones-precomputadas`

**Actualizado**: 2026-09-27 (saneamiento de consistencia sobre la versión del 2026-09-22; T001–T050
conservan numeración e incidencias #1–#50; **T036 retirada** y reemplazada por **T064**; decisiones del
autor RD-98…RD-110 aplicadas el mismo día, con **T065** nueva y **TDD extendido a toda tarea de
producción**)

**Fuentes de verdad** *(recontadas el 2026-09-27; cada cifra se obtiene con un `grep` sobre el archivo)*:
- [**data-model.md**](./data-model.md) — **autoritativo en la capa de datos**: 18 tablas en §2,
  RD-1→RD-111 en §11, DI-1→DI-29 (**34** contando `DI-2a'`…`DI-2e`) en §6, CR-1→CR-19 en §10.
  *Ante discrepancia con cualquier otro documento, manda éste.*
- [spec.md](./spec.md) — **167 requisitos definidos** (FR-001→FR-096, con sufijos y huecos
  declarados) · **31** criterios de éxito · **53** entradas de clarificación en **6** sesiones, más los
  registros de saneamiento (2026-09-27) y de remediación del análisis (2026-09-28) · **12** dependencias declaradas (DEP-1→DEP-12: **10 vigentes**,
  DEP-3 vacante a propósito y DEP-4 resuelta)
- [plan.md](./plan.md) — el plan regenerado ya **no** tiene decisiones D1…D10: las que se cerraron
  viven en `data-model.md` y las referencias `D4`/`D5` de este archivo remiten a valores fijados allí
- [checklists/requirements-contracts.md](./checklists/requirements-contracts.md) — 30/30 resueltos
- [checklists/requirements-clarify-2026-09-14.md](./checklists/requirements-clarify-2026-09-14.md) —
  **46/46 tildados — cerrado** (los 10 🔴 se cerraron el 2026-09-22)
- [constitution v1.1.1](../../.specify/memory/constitution.md) — enmendada el 2026-09-27 (RD-98) y
  aclarada el 2026-09-28 (RD-111), pendiente de aprobación por PR según su sección de gobernanza

> **Corrección del encabezado anterior**: decía «FR-001→FR-071, 5 clarificaciones» y no citaba
> `data-model.md` ni una vez en todo el documento, pese a ser el que especifica la capa de datos que
> T003, T004, T018 y T029 implementan.

**Decisiones cerradas — no reabrir**:

*Primera sesión (2026-09-07)*: SWR con obsoleto (Q1) · propagación por vocabulario compartido (Q2) ·
likes y dislikes puntúan, consumo solo excluye (Q3) · configuración versionada en repo (Q4) · respaldo
diversificado por MMR (Q5) · α=0.5 β=0.3 γ=0.2 (D4) · espacio vectorial único (D9) · popularidad por
likes propios (D10).

*Segunda y tercera sesión (2026-09-14 / 2026-09-22) — las que cambian el trabajo de alguna tarea*:

| Decisión | RD | Tareas afectadas |
|---|---|---|
| Popularidad = **límite inferior de Wilson** materializado; nunca se calcula al servir | RD-53 | T038, T012 |
| **Declaración de gustos** obligatoria por módulo, mínimo 5 tags; sin ella se rechaza la solicitud | RD-68, RD-70 | T053, T054, T055, T008, T017 |
| `tiebreak_criteria` **eliminado** de la configuración: el desempate es fijo | RD-10 | **T004** |
| `region` y `birth_date` **ambas `NOT NULL`**, ambas rechazan en la ingesta | RD-61, RD-85 | T003, T029 |
| Cuota de novedades = `floor(top_n × 0,20)`, **sin piso ni clamp** | RD-77, RD-80 | T038 |
| `top_n` acotado a **`[10, 50]`**: se rechaza por ambos extremos | RD-78 | T033 |
| Supresión verificada: aborta el recálculo en curso, con observador y escalamiento | RD-82, RD-83 | T058, T059 |
| **Redis primero, siempre** — regla única de orden para actualización y supresión | FR-080c (CHK061, CHK062; la cita anterior a «RD-84» era errónea: RD-84 es `collab_min_neighbors`) | T019, T020, T058, T064 |
| El top-N **vive solo en Redis**; ninguna tabla lo persiste | FR-080b | T022, T003, T038 |
| Endpoint de escritura como **excepción declarada**; no calcula | RD-75 | T053 |
| **Sin endpoint de feedback**: las señales entran por sincronización o por evento; el worker persiste la del evento | RD-95 | T064 (reemplaza a T036), T023, T029 |
| La exclusión es efectiva en la siguiente lectura: **invalidación de `filters:`** al ingresar la señal o la declaración; `filters:` porta los módulos declarados | RD-96 | T014, T018, T029, T053, T055, T064 |
| Herencia de tags entre módulos **derivada**, no persistida | RD-97 | T008, T053, T054 |
| Rollback de configuración **hacia adelante** | RD-94 | T004 |
| Escritura de la declaración **amparada por la constitución v1.1.0** (única excepción, Principio III) | RD-98 | T053 |
| **Sin peso de consumo** sobre el perfil (FR-022b prevalece sobre RD-73) | RD-99 | T004, T008 |
| Solicitudes internas de recálculo por **Stream de Redis `recompute:requests`**, no por el broker | RD-100 | T018, T020, T022, T027, T051, T053, T058 |
| Supresión **disparada por evento de baja** (CR-19, DEP-12); constancia y lápida en `user_suppressions` | RD-101 | T003, T029, T058, T059 |
| Cuota de novedades **en el top-N personalizado** (posiciones `ceil(k/ratio)`); promoción registrada en `item_promotions` | RD-102 | T003, T004, T038, T063, **T065** |
| Tras un cambio de versión se **siguen leyendo** las entradas previas, salvo cambio del catálogo etario | RD-103 | T018, T020 |
| Contador de FR-080a **derivado** de `user_signals`, no almacenado | RD-104 | T003, T060 |
| IDF `ln((1+N)/(1+df))+1` · vecinos con similitud ≤ 0 **excluidos** · SC-001 = **p95 ≤ 50 ms** | RD-105 | T007, T010, T050 |
| Respaldo **sin umbral de likes**: sin evidencia se ordena por desempate | RD-106 | T038 |
| Lectura **sin paginación** (solo `top_n`); obsoleto con `stale_available` y `prefer=stale` | RD-107 | T033, T049, T062 |
| Conteo de FR-080a **por (usuario, módulo)** | RD-104 | T060 |
| Ventana 90 d · umbral emergente 20 · `MAXLEN` 100 000 · cluster = tag principal, tope 0,4 **aplicado en la selección** · vecinos por recálculo (D3) | RD-108 | T004, T010, T015, T038, T063, T065 |
| Declaración **definitiva** (sin edición ni retiro); un dislike puede anular el peso de un tag declarado | RD-109 | T008, T053 |
| FR-068e (irreversibilidad) · FR-068b con **tres** ventanas · mínimo de tags elegibles dentro de DEP-10, con métrica | RD-110 | T004, T030, T042 |
| Remediación de `/speckit-analyze`: evento de baja con contrato, contract test y DLQ · cuota y tope de cluster garantizados sobre la lista precalculada · `fallback_stored_size` = 100 · tope de entregas del stream = 5 · «peso no despreciable» definido | RD-111 | T003, T004, T006, T008, T017, T019, T020, T027, T039, T043, T047, T049, T058 |

## Formato: `[ID] [P?] Descripción`

- **[P]**: paralelizable — sin dependencias cruzadas ni archivos compartidos con otra tarea `[P]` activa
- **[TDD]**: la tarea se desarrolla test-first — ver *Política TDD* abajo
- **Estimación**: S (≤½ día) · M (1-2 días) · L (3-5 días)
- Toda tarea de producción declara sus tests. Una tarea sin criterio verificable no está lista para tomarse.

## Política TDD (toda tarea de producción)

**Alcance (desde el 2026-09-27)**: **toda tarea que produce código de producción es `[TDD]`**. Quedan
fuera solo las tareas cuyo entregable **es** un test, un documento o una configuración de CI, porque
no hay implementación que el test preceda:

| Exenta | Motivo |
|---|---|
| T001 | Andamiaje del paquete y entrypoints: no tiene comportamiento que especificar; lo verifican T006 y T041 |
| T006, T017, T044, T050, T052 | **Son** tests. T017 y T052 conservan la marca `[TDD]` porque su verificación de poder de detección (mutación, rojo previo) sí aplica |
| T043, T045 | Configuración de CI y gates |
| T046, T047, T048, T049 | Documentación, contratos y validación final |

> **Alcance anterior (selectivo), conservado como registro**: T007–T017 —motor y post-procesamiento,
> funciones puras— más T053, T054, T055, T058, T060, T062 y T064. Se excluía la infraestructura (T018,
> T028), los jobs periódicos (T051, T057, T063) y T056, T059, T061 con el argumento de que «el rojo
> previo no aporta» y de que su diseño «se descubre contra el esquema real». **El autor decidió
> extenderlo** porque el proyecto se declara guiado por TDD y porque varios criterios de esas tareas son
> exactamente la clase que un test escrito después acomoda al código: la lápida de T029, el aborto de
> T058, la ventana de T063, la idempotencia de T022. En infraestructura el rojo se ve con
> testcontainers: el test de integración escrito primero falla contra el esquema o la clave que aún no
> existen.

**Qué cambia para las tareas que entraron**: su sección `**Tests**` es el **Paso 1 — Rojo** y debe
llegar en un commit propio que precede a la implementación, con la misma regla de revisión de abajo.
No se reescriben sus secciones: el ciclo de la tabla siguiente rige igual.

**Razón de fondo**: en T013 (filtro de edad) y T017 (batería de invariantes), un test escrito
*después* tiende a acomodarse a lo que el código ya hace. Es el modo de fallo clásico y justamente el
que no podemos permitirnos en un invariante de seguridad. Escribir el test primero obliga a fijar el
contrato antes de tener una implementación que lo condicione.

### Ciclo obligatorio en tareas `[TDD]`

| Paso | Acción | Evidencia exigida |
|---|---|---|
| **1 — Rojo** | Escribir el test que codifica el criterio de aceptación. Ejecutarlo y **verlo fallar** | Commit propio, solo con tests. CI en rojo esperado |
| **2 — Verde** | Implementar lo mínimo para pasar | Commit siguiente. CI en verde |
| **3 — Refactor** | Limpiar sin cambiar comportamiento | Tests siguen en verde, sin modificarlos |

**Regla de revisión**: en un PR de tarea `[TDD]`, el commit de test **debe preceder** al de
implementación en el historial. Un PR con un solo commit que trae test e implementación juntos no
demuestra haber visto el rojo y se rechaza.

> **Por qué importa ver el rojo**: un test que nunca falló no prueba nada. Puede estar afirmando algo
> trivialmente cierto, o no estar ejecutándose. El paso 1 no es ceremonia — es la única evidencia de
> que el test tiene poder de detección.

## Invariantes transversales

Estos cuatro se verifican en **toda** tarea, no solo donde se mencionan:

| Inv | Regla | Cómo falla la revisión |
|---|---|---|
| **INV-1** | Cero cómputo pesado en el request path (FR-003, Principio III) | La API importa `engine/`, o lee Postgres en el **camino normal** (acierto de caché). Admitido: repoblado acotado de `filters:` y `retired:` ante **miss de esa clave** —respaldo degradado sobre datos materializados que el Principio III permite— y la escritura de declaración (T053). *(Precisado 2026-09-27: la regla anterior, «abre conexión a Postgres fuera de health», volvía imposibles T053 y el repoblado de `data-model.md` §3.1.1)* |
| **INV-2** | Redis nunca es fuente de verdad (FR-065) | Existe un dato solo recuperable desde Redis |
| **INV-3** | Edad y exclusión no admiten bypass (FR-049→FR-055) | Existe una ruta de datos hacia la respuesta que no atraviesa ambos filtros |
| **INV-4** | Sin acceso a DB de otros repos (Principio I) | Cualquier credencial o driver apuntando fuera de DB Recomendaciones |

## Asignación de fases (autoritativa)

Los milestones agrupan por **dominio técnico**; las fases agrupan por **entregable demostrable**. No
coinciden, y esta tabla manda sobre el encabezado de cada milestone.

| Fase | Tareas | Entregable |
|---|---|---|
| **1 — Vertical slice** | T001–T024, **T027**, **T028, T029, T030**, T033–T035, T037, T038, **T049**, **T053, T054, T055, T063, T064** | Ciclo completo: declarar, leer, ingresar señales por evento y sincronización, recalcular. Cierra US1, US2, US5 |
| **2 — Robustez operativa** | T025, T026, **T031, T032**, T039–T042, T046, **T051, T052, T056, T057, T060, T061, T062, T065** | Sobrevive a fallos. Cierra US3, US4, US6, US7 |
| **3 — Optimización y cierre** | T043–T045, T047, T048, **T050**, **T058, T059** | Rendimiento, gates de CI y gobernanza |

> *Cambios del 2026-09-27*: **T036 retirada** (endpoint de feedback, RD-95) y reemplazada por **T064**
> en Fase 1. **T049 pasa a Fase 1**: el Principio II exige definir el contrato **antes** de
> implementarlo, y T033, T053 y T062 lo consumen — en Fase 2 quedaba después de lo que debía preceder.

**Fundamento de T051–T063** *(asignadas el 2026-09-22; ninguna por proximidad numérica ni por
pertenecer al Milestone 11)*:

| Tarea | Fase | Fundamento |
|---|---|---|
| **T053** Endpoint de declaración | **1** | `FR-088` rechaza **toda** solicitud de un módulo sin declaración. Sin esta tarea, Fase 1 sirve recomendaciones a cero usuarios y **US1 no se puede demostrar**. Es condición de US1, no funcionalidad adicional |
| **T054** Herencia de tags | **1** | Parte del mismo flujo: sin ella, un usuario de ambos módulos declara dos veces desde cero y `FR-085` no se cumple en el único momento en que se ejerce |
| **T055** Rechazo por módulo | **1** | Es la mitad observable de `FR-088`. Sin ella el rechazo no existe o se confunde con un estado de resultado, rompiendo la exhaustividad de `FR-056` (DEP-6) |
| **T063** Popularidad por ventana | **1** | **Arrastrada por T038**, que está en Fase 1 por el hallazgo F2. T038 lee lo que T063 escribe; con T063 fuera, el batch corre sobre tabla vacía y `fallback` sigue inalcanzable |
| **T051** Refresco de umbrales etarios | **2** | Corrige un derivado que se desactualiza **por el paso del tiempo**, sin escritura que lo dispare. En Fase 1 el dato recién ingresado es correcto por construcción; el problema aparece con el sistema en régimen |
| **T052** Tests de ciclo de vida del ítem | **2** | Suite exhaustiva del retiro, que produce el Data Transformer (T029). *El fundamento original —«T029 está en Fase 2»— caducó con la corrección F9, que movió T029 a Fase 1; T052 queda en Fase 2 como endurecimiento, y su adelantamiento es revisable* |
| **T056** Perfil vectorial derivado puro | **2** | `FR-087` prohíbe la actualización incremental. En Fase 1 el perfil se reconstruye completo cada vez; la garantía **estructural** de que no exista un camino incremental es endurecimiento |
| **T057** Purga de señales | **2** | `FR-068a` exige retención finita, y el horizonte supera toda ventana operativa (`FR-068b`). No hay nada que purgar hasta que el sistema acumule historia |
| **T060** Disparador por conteo | **2** | `FR-080a` optimiza **cuándo** se recalcula. En Fase 1 el recálculo se dispara por evento (T023): funciona, sin la economía del umbral |
| **T061** Ponderación regional | **2** | `FR-090a` exige que `v1` arranque **activa** en `0,1` desde el **primer despliegue productivo**. Fase 1 es un vertical slice, no un despliegue productivo: demuestra el ciclo sin segmentar, pero **ningún despliegue productivo puede ocurrir sin T061**. No cierra historia de usuario: implementa FR-081…FR-096. *(Corregido 2026-09-27: el fundamento anterior suponía el factor neutro —que es el de la revertida RD-74— y decía «cierra US7», que es la historia de observabilidad)* |
| **T064** Persistencia de la señal del evento | **1** | Reemplaza a T036. Sin ella, la señal que llega por evento no se registra hasta la siguiente sincronización y el recálculo de T027 corre sobre datos viejos: **US2 no se puede demostrar** |
| **T065** Cuota de novedades en el personalizado | **2** | FR-033a6 da exposición a lo nuevo, pero en Fase 1 el catálogo recién cargado es todo emergente y el personalizado funciona sin la cuota. Depende de T063 (promociones) y de T027; es calidad del resultado, no condición de ninguna historia (RD-102) |
| **T062** Señal de obsoleto | **2** | `FR-056a` **no agrega estado**: enriquece una respuesta que Fase 1 ya produce correctamente. Es mejora de contrato sobre comportamiento existente |
| **T058** Supresión con aborto | **3** | Requiere que existan recálculos en curso que abortar y verificación registrada (`FR-095`). Depende de T057 y del régimen operativo completo |
| **T059** Verificación de supresión | **3** | Depende de T058 y suma alerta (`FR-095a`), que exige la observabilidad de Fase 2 ya en pie |

> ⚠️ **T058 y T059 en Fase 3 son la asignación más discutible de esta tabla.** La supresión de datos
> a pedido puede ser una obligación con plazo, y en ese caso no es «optimización y cierre». Se ubican
> por **dependencia técnica** —T057 y la observabilidad—, no por prioridad. Si existe un plazo
> externo, esta asignación se revisa.

> **Correcciones del análisis de consistencia (2026-09-08)**:
> - **F1** — T023, T024 y T027 se movieron a Fase 1: `plan.md` §4 promete US2 y SC-005 en esa fase,
>   y ambos dependen del worker. En Fase 2 quedan T025/T026, que son robustez ante fallos.
> - **F2** — T038 se movió a Fase 1: sin el batch de respaldo, el estado `fallback` de FR-056 es
>   inalcanzable y T020 no puede testearse completa.
> - **F8** — T036 confirmada en Fase 1: es lo que cierra el ciclo de US2. *(T036 fue retirada el
>   2026-09-27; el ciclo de US2 lo cierra ahora T064.)*

> **Corrección F9 (2026-09-22) — `item_vectors` no tenía quién la poblara en Fase 1**:
> **T028, T029 y T030 se mueven a Fase 1.**
>
> El hallazgo: `item_vectors` tiene **un único escritor, T030**, que estaba en Fase 2. **T009**
> (señal content-based) la **lee** y está en Fase 1, y **T012** depende de T009. Con la tabla vacía,
> `α = 0,5` —la mitad del score— aporta cero y el ranking queda gobernado solo por β y γ.
>
> **Lo grave no era el error sino su forma**: el pipeline **corre sin fallar**. No hay excepción, no
> hay test rojo, no hay alerta; hay recomendaciones peores. Un vertical slice que produce resultados
> plausibles con la mitad del motor apagado es peor que uno que no arranca, porque se da por
> demostrado.
>
> **La cadena arrastra**: T030 depende de T029, y T029 de T028. No se puede mover la reconciliación
> de vectores sin mover el sincronizador que la alimenta. Los tres pasan a Fase 1.
>
> **Qué queda en Fase 2**: **T031** (freshness de sincronización) y **T032** (comportamiento ante
> `api-general` no disponible). Es el corte correcto: lo que Fase 1 necesita es que la
> sincronización **funcione**; lo que Fase 2 agrega es que **sobreviva a que falle**, que es la
> definición del entregable de esa fase.
>
> **Costo declarado, sin atenuar**: Fase 1 crece de forma apreciable y deja de ser un slice
> mínimo — absorbe el Data Transformer completo y con él la dependencia de `api-general`, que
> **está incompleta** (RD-47). Se aceptaron las alternativas descartadas con conocimiento de eso:
> partir T030 en dos (reconciliación en Fase 1, transición en Fase 2) dividía un job que
> `data-model.md` sitúa entero en un lugar, y sembrar vectores por fixture dejaba el vertical slice
> **sin ser end-to-end**, que es lo único que un vertical slice aporta.

---

## Índice de tareas (formato Spec Kit)

> Una línea por tarea, en el formato `[ID] [P?] [Story] Descripción` de la plantilla de Spec Kit. **Es la
> casilla que `/speckit-implement` marca `[X]` al completar una tarea.** Las casillas de *Criterios de
> aceptación* dentro de cada tarea son subítems de verificación, no tareas. `[USn]` solo aparece en
> tareas dedicadas a una historia; las fundacionales o transversales no llevan etiqueta. `(TDD)` indica
> test primero (*Política TDD*). T036 está retirada y no figura. *(Agregado el 2026-09-27.)*

### Fase 1 — Vertical slice

- [X] T001 Estructura del paquete y entrypoints en `src/recomendaciones/{api,engine,config,worker,transformer,batch,storage,observability,shared}/`
- [X] T002 Configuración por entorno y gestión de la API key interna en `src/recomendaciones/config/settings.py` (TDD)
- [X] T003 Esquema DB Recomendaciones + Alembic en `src/recomendaciones/storage/db/models.py` (TDD)
- [X] T004 [P] Configuración versionada del motor + loader validante en `src/recomendaciones/config/engine_config/v1.yaml` (TDD)
- [X] T005 [P] Modelo de dominio compartido y errores tipados en `src/recomendaciones/shared/domain.py` (TDD)
- [X] T006 [P] Test de arquitectura: `api/` no importa `engine/` en `tests/unit/test_architecture.py`
- [X] T007 Vectorización TF-IDF sobre vocabulario compartido en `src/recomendaciones/engine/content.py` (TDD)
- [X] T008 Similitud coseno y construcción de perfil en `src/recomendaciones/engine/similarity.py` (TDD)
- [X] T009 [P] Señal content-based en `src/recomendaciones/engine/content.py` (TDD)
- [X] T010 [P] Señal colaborativa (k vecinos) en `src/recomendaciones/engine/collaborative.py` (TDD)
- [X] T011 [P] [US4] Señal cross-module en `src/recomendaciones/engine/cross_module.py` (TDD)
- [X] T012 Combinación lineal y desempate determinista en `src/recomendaciones/engine/scoring.py` (TDD)
- [X] T013 [US5] Filtro de edad por `age_rating` (fail-closed) en `src/recomendaciones/engine/postprocess.py` (TDD)
- [X] T014 [US5] Filtro de exclusión en `src/recomendaciones/engine/postprocess.py` (TDD)
- [X] T015 Diversificación MMR en `src/recomendaciones/engine/postprocess.py` (TDD)
- [X] T016 [US5] Pipeline de post-proceso con orden garantizado en `src/recomendaciones/engine/postprocess.py` (TDD)
- [X] T017 [US5] Batería exhaustiva de invariantes en `tests/invariants/` (TDD)
- [X] T018 Cliente Redis y esquema de claves en `src/recomendaciones/storage/cache/keys.py` (TDD)
- [X] T019 Escritura del top-N con score y `config_version` en `src/recomendaciones/storage/cache/repository.py` (TDD)
- [X] T020 [US6] Política de cache miss y señalización de recálculo en `src/recomendaciones/api/services/read_service.py` (TDD)
- [X] T021 [P] [US6] Comportamiento ante Redis caído en `src/recomendaciones/storage/cache/client.py` (TDD)
- [X] T022 [US6] Reconstrucción total tras pérdida de Redis en `src/recomendaciones/batch/warmup.py` (TDD)
- [X] T023 [US2] Consumo de `recomendacion.actualizar` en `src/recomendaciones/worker/consumer.py` (TDD)
- [X] T024 [US2] Idempotencia por `event_id` en `src/recomendaciones/worker/idempotency.py` (TDD)
- [X] T027 [US2] Recálculo y propagación cross-module condicional en `src/recomendaciones/worker/handler.py` (TDD)
- [X] T028 [US3] Cliente REST autenticado y de solo lectura en `src/recomendaciones/transformer/client.py` (TDD)
- [X] T029 [US3] Materialización idempotente de usuarios, catálogo y actividad en `src/recomendaciones/transformer/pipeline.py` (TDD)
- [X] T030 [US3] Vocabulario versionado y reconciliación de vectores en `src/recomendaciones/transformer/vocabulary_sync.py` (TDD)
- [X] T033 [US1] Endpoint de lectura del top-N en `src/recomendaciones/api/routes/recommendations.py` (TDD)
- [X] T034 [US1] Autenticación por API key interna y no alcanzabilidad desde frontends en `src/recomendaciones/api/deps.py` (TDD)
- [X] T035 [US1] Errores tipados y contrato estable en `src/recomendaciones/api/errors.py` (TDD)
- [X] T037 [US6] Filtrado de salida sobre el respaldo (acotado) en `src/recomendaciones/api/services/read_service.py` (TDD)
- [X] T038 [P] [US6] Batch de top-N de respaldo en `src/recomendaciones/batch/fallback.py` (TDD)
- [ ] T049 Definir `contracts/` primero (OpenAPI + JSON Schema) en `specs/001-recomendaciones-precomputadas/contracts/recomendaciones-api.openapi.yaml`
- [X] T053 [P] [US4] Endpoint de declaración de gustos en `src/recomendaciones/api/routes/declaraciones.py` (TDD)
- [X] T054 [US4] Herencia de tags entre módulos en `src/recomendaciones/api/services/declaracion.py` (TDD)
- [X] T055 [US4] Rechazo por módulo sin declaración en `src/recomendaciones/api/routes/recommendations.py` (TDD)
- [X] T063 [US6] Recálculo de popularidad por ventana en `src/recomendaciones/batch/popularidad.py` (TDD)
- [X] T064 [US2] Persistencia de la señal del evento y materialización de su exclusión en `src/recomendaciones/worker/signals.py` (TDD)

### Fase 2 — Robustez operativa

- [X] T025 [US2] Reintentos con backoff y DLQ en `src/recomendaciones/worker/retry.py` (TDD)
- [X] T026 [US2] Manejo de payload inválido sin bloquear la cola en `src/recomendaciones/worker/dlq.py` (TDD)
- [X] T031 [P] [US3] Registro de freshness de sincronización en `src/recomendaciones/transformer/pipeline.py` (TDD)
- [ ] T032 [US3] Comportamiento ante `api-general` no disponible en `src/recomendaciones/transformer/resilience.py` (TDD)
- [X] T039 [US7] Métricas Prometheus en `src/recomendaciones/observability/metrics.py` (TDD)
- [ ] T040 [P] [US7] Logging estructurado con correlation ID en `src/recomendaciones/observability/logging.py` (TDD)
- [ ] T041 [P] [US7] Health, readiness y liveness por servicio en `src/recomendaciones/observability/health.py` (TDD)
- [ ] T042 [US7] Alertas operativas en `ops/alerts.yaml` (TDD)
- [ ] T046 [US7] Documentación operativa mínima en `docs/runbook.md`
- [ ] T051 [US5] Job `age_threshold_refresh` (refresco de derivados etarios) en `src/recomendaciones/batch/age_threshold_refresh.py` (TDD)
- [ ] T052 [US3] Tests de ciclo de vida del ítem en `tests/invariants/test_item_lifecycle.py` (TDD)
- [ ] T056 Perfil vectorial derivado puro en `src/recomendaciones/engine/profile.py` (TDD)
- [ ] T057 Purga de señales de actividad con guarda de exclusión en `src/recomendaciones/batch/purga_senales.py` (TDD)
- [ ] T060 [US2] Disparador de recálculo por conteo e invalidación en el mismo acto en `src/recomendaciones/worker/trigger.py` (TDD)
- [ ] T061 Ponderación regional del término colaborativo en `src/recomendaciones/engine/collaborative.py` (TDD)
- [ ] T062 [US6] Señal de resultado obsoleto como campo aparte en `src/recomendaciones/api/schemas/respuesta.py` (TDD)
- [ ] T065 [US2] Cuota de novedades en el top-N personalizado en `src/recomendaciones/engine/postprocess.py` (TDD)

### Fase 3 — Optimización y cierre

- [ ] T043 Contract testing contra `api-general` como gate de CI en `tests/contract/`
- [ ] T044 Suite de casos críticos obligatorios en `tests/integration/test_critical_scenarios.py`
- [ ] T045 Pipeline de CI con gates bloqueantes en `.github/workflows/ci.yml`
- [ ] T047 [P] Documento de campos requeridos a `api-general` en `docs/contracts/required-fields.md`
- [ ] T048 Validación final contra el checklist y DoD en `docs/validation/traceability-matrix.md`
- [ ] T050 [P] [US1] Pruebas de carga y verificación de SC-001 en `tests/performance/test_read_latency.py`
- [ ] T058 Supresión verificada con aborto del recálculo en curso en `src/recomendaciones/worker/suppression.py` (TDD)
- [ ] T059 Verificación ejecutable de supresión, observador y escalamiento (TDD)

# FASE 1 — Vertical slice

> **Objetivo**: servir top-N precomputado end-to-end **y cerrar el ciclo de recálculo**.
> Cierra US1, US2, US5. Incluye T023, T024, T027 (Milestone 5), **T028, T029, T030 (Milestone 6)**,
> T033–T035, T037, T038 (Milestone 7), **T049** (Milestone 9, contract-first) y **T053, T054, T055,
> T063, T064 (Milestone 11)**.
>
> **«End-to-end» se toma literalmente**: el catálogo se sincroniza de verdad (T029) y los vectores
> se pueblan de verdad (T030). Sin eso, `item_vectors` queda vacía, la señal content-based aporta
> cero y el slice demuestra medio motor creyendo demostrarlo entero (corrección F9).

## Milestone 1 — Fundaciones

| ID | Tarea | Dep. | [P] | Est. |
|---|---|---|---|---|
| T001 | Estructura del paquete y entrypoints | — | | S |
| T002 | Configuración por entorno y gestión de la API key interna | T001 | | M |
| T003 | Esquema DB Recomendaciones + Alembic | T001 | | L |
| T004 | Configuración versionada del motor + loader validante | T001 | [P] | M |
| T005 | Modelo de dominio compartido y errores tipados | T001 | [P] | S |
| T006 | Test de arquitectura: `api/` no importa `engine/` | T001 | [P] | S |

### T001 — Estructura del paquete y entrypoints

**Requisitos**: estructura de `plan.md` (Project Structure); base de INV-1…INV-4 y de T006 *(explicitados el 2026-09-28 para la trazabilidad de T048, RD-111)*

**Descripción**: crear el árbol de `plan.md` §Source Code con tres entrypoints (`api`, `worker`,
`transformer`) más el job batch. `engine/` queda como librería pura sin I/O.

**Archivos**: `src/recomendaciones/{api,engine,config,worker,transformer,batch,storage,observability,shared}/`,
`pyproject.toml`, `tests/{unit,integration,contract,invariants}/`

**Criterios de aceptación**:
- [X] Los tres entrypoints arrancan de forma independiente y fallan con error explícito si falta configuración
- [X] `engine/` no declara dependencias de red, DB ni reloj: verificable por inspección de imports
- [X] `pip install -e .` + `pytest --collect-only` termina sin error de importación

**Tests**: `tests/unit/test_layout.py` — cada paquete es importable y `engine/` no importa `storage/`, `api/` ni librerías de I/O.

---

### T002 [TDD] — Configuración por entorno y gestión de la API key interna

**Descripción**: carga de configuración por entorno con la API key interna **inyectada desde el
entorno, nunca en repo**. La credencial es válida en un único entorno (FR-059).

**Archivos**: `src/recomendaciones/config/settings.py`, `.env.example`, `src/recomendaciones/api/deps.py`

**Dep.**: T001

**Criterios de aceptación**:
- [X] Arranque falla si la API key no está presente — no hay default (FR-054)
- [X] La key incluye el identificador de entorno; una key de otro entorno se rechaza (FR-059)
- [X] El rechazo devuelve `401` genérico, sin revelar si la key es inválida o de otro entorno
- [ ] Ningún valor de credencial aparece en logs ni en la respuesta de `/health`
- [X] `INV-4`: no existe cadena de conexión a DB fuera de DB Recomendaciones

**Tests**: `tests/unit/test_settings.py` — ausencia de key → fallo de arranque; key de otro entorno → rechazo; `repr()` del settings enmascara secretos.

---

### T003 [TDD] — Esquema DB Recomendaciones + Alembic

**Descripción**: las **18 tablas de `data-model.md` §2** con pgvector —contadas sobre sus 16
subsecciones: §2.3 agrupa `tags` + `item_tags` y §2.13 agrupa `vocab_versions` + `vocab_version_tags`—.
*(16 hasta el 2026-09-27; RD-101 y RD-102 agregaron `user_suppressions` e `item_promotions`.)*
`items.age_rating` es `NOT NULL` con default **no-apto** (FR-051): el esquema hace imposible representar
un ítem sin clasificación tratable como apto.

> **Corrección 2026-09-22**: decía «las 10 tablas de `plan.md` §2». Son **16**, y la fuente es
> `data-model.md` §2, no `plan.md` §2 —que delega en aquel—. Siete tablas **no se mencionaban ni una vez
> en todo `tasks.md`**: `user_declared_tags`, `tag_modules`, `vocab_versions`, `vocab_version_tags`,
> `item_popularity`, `user_exclusions` y `engine_config_versions`.

**Archivos**: `src/recomendaciones/storage/db/models.py`, `migrations/versions/*`, `alembic.ini`

**Dep.**: T001

**Criterios de aceptación**:
- [X] Las **18** tablas existen con sus claves e índices; `item_vectors.vector` es pgvector
- [X] `user_suppressions` (§2.15): PK `user_id` **sin FK** a `users` —sobrevive al `CASCADE`—, `state`
      enum(`in_progress`,`completed`,`failed`), `CHECK ((state = 'completed') = (verified_at IS NOT NULL))`,
      índice parcial `idx_suppressions_open` (RD-101)
- [X] `item_promotions` (§2.16): PK `item_id` con FK **`RESTRICT`** a `items`, `config_version` FK
      **`RESTRICT`** (RD-102)
- [X] `user_signals` tiene `idx_signals_user_received (user_id, received_at)` para el conteo de FR-080a
      (RD-104)
- [X] `users`: `birth_date NOT NULL`, **`region NOT NULL` sin default** (FR-079, RD-61, RD-85),
      `max_age_ordinal`, `age_derived_at`, `age_config_version`. **Sin** `max_age_rating` (RD-2) y
      **sin** `age_resolution`
- [X] `item_vectors`: `vocab_version` **en la PK** (RD-22) y `NOT NULL` (FR-010f)
- [X] `items.age_rating` es `NOT NULL` y su default es el valor más restrictivo del catálogo
- [X] `item_popularity`: **PK compuesta `(item_id, config_version)`** (RD-12, RD-13)
- [X] `user_exclusions`: **sin `is_permanent`**, con FK **`RESTRICT`** hacia `items` (RD-35)
- [X] `engine_config_versions`: **trigger de inmutabilidad** (RD-37) e **índice parcial único** sobre
      `deactivated_at IS NULL`: a lo sumo una versión activa (DI-7, FR-025b)
- [X] `user_declared_tags`: PK `(user_id, module, tag_name)`, FK `user_id` **`ON DELETE CASCADE`** y FK
      `tag_name` **`ON DELETE RESTRICT`** (§2.14) — la asimetría es deliberada: un tag no puede
      desaparecer del catálogo dejando declaraciones colgadas en silencio
- [X] `tag_modules`, `vocab_versions`, `vocab_version_tags` existen con sus claves (§2.12, §2.13)
- [X] `user_profiles` admite exactamente los módulos `peliculas`, `juegos`, `general` (constraint)
- [X] `processed_events.event_id` es único (FR-011)
- [X] `user_signals.origin_interaction_id` es `NOT NULL UNIQUE` (DEP-8, DI-21)
- [X] **Toda FK declara su política `ON DELETE`.** Es criterio explícito del documento, que registra
      **cuatro omisiones históricas** (RD-19, RD-31, RD-35, RD-43): una FK sin política no es un olvido
      menor, es el patrón que más veces se repitió
- [X] `upgrade` y `downgrade` se aplican limpio sobre base vacía y sobre base poblada
- [X] `INV-2`: toda información necesaria para recalcular un top-N reside acá. **Matiz de FR-080b**: el
      top-N *resultante* **no** se persiste —vive solo en Redis y se recomputa (§3.3)—; lo que reside
      acá son sus **insumos**

**Tests**: `tests/integration/test_migrations.py` (testcontainers) — ciclo upgrade/downgrade/upgrade; insertar ítem sin `age_rating` viola constraint; insertar perfil con módulo inválido viola constraint.

---

### T004 [P] [TDD] — Configuración versionada del motor + loader validante

**Descripción**: `v1.yaml` con los valores de D4 y un loader que valida rangos y **rechaza cualquier
configuración que desactive un filtro obligatorio** (FR-054). `config_version` es el hash del archivo.

**Archivos**: `src/recomendaciones/config/engine_config/v1.yaml`, `src/recomendaciones/config/loader.py`

**Dep.**: T001

**Contenido de `v1.yaml`** — inventario autoritativo en `data-model.md` §4: **`version_label`** (RD-94),
`alpha: 0.5`, `beta: 0.3`, `gamma: 0.2`, `k: 20`, `lambda_mmr: 0.7`, `peso_like: 1.0`,
`peso_dislike: -1.0` —**sin peso de consumo**: RD-99 lo eliminó (FR-022b)—, **`top_n_min: 10`**, `top_n_default: 20`, `top_n_max: 50` (RD-78), `age_rating_catalog`,
**`popularity_window_days: 90`** (RD-108), **`popularity_confidence_z: 1.96`** (RD-53),
**`fallback_new_item_quota_ratio: 0.20`** (RD-77, RD-80), **`diversity_max_cluster_share: 0.4`** (RD-108),
**`declared_tags_min: 5`** (RD-68), **`region_weight_factor: 0.1`** (RD-79),
**`collab_min_neighbors: 10`** (RD-84), `vocab_regeneration_policy`,
**`emergent_evidence_threshold: 20`** (RD-102, RD-108).

> **`tiebreak_criteria` ya no va.** Estaba en la lista anterior y **RD-10 lo eliminó del esquema**: el
> desempate es fijo y determinista, no configurable.

**Parámetros operativos, fuera de este archivo** (RD-46): el umbral de recálculo por conteo de
interacciones (`interaction_recalc_threshold`, valor inicial **10** — FR-080a, RD-63), que no altera el
valor del top-N, solo **cuándo** se lo recomputa; **`recompute_requests_maxlen` = 100 000** (RD-100,
RD-108); y **`event_redelivery_window_hours`** (RD-110), copiado de la configuración real del broker.

**Criterios de aceptación**:
- [X] `alpha+beta+gamma` fuera de `1.0±ε` → fallo de arranque con mensaje que nombra el campo (FR-027)
- [X] `alpha`, `beta`, `gamma` y `lambda_mmr` fuera de `[0,1]` → fallo de arranque. `peso_like > 0` y
      `peso_dislike < 0`: el like refuerza y el dislike penaliza (FR-022a). *(Decía «cualquier peso
      fuera de `[0,1]`», que rechazaba el propio `peso_dislike: -1.0` de `v1`.)*
- [X] `popularity_confidence_z > 0` **estricto**: `0` se rechaza explícitamente porque degenera el
      estimador de Wilson en la proporción cruda (FR-033a3, RD-44)
- [X] Una clave que intente desactivar el filtro de edad o de exclusión → fallo de arranque (FR-054)
- [X] `age_rating_catalog` es la **única** fuente de valores válidos (FR-053); no hay constantes de rating en código
- [X] `age_rating_catalog`: ordinal **único, contiguo y creciente** con `min_age`; si no, fallo de
      arranque (`data-model.md` §4.1)
- [X] **El loader RECHAZA `tiebreak_criteria`** si aparece: fue eliminado del esquema por RD-10.
      El desempate sigue sin depender del orden de iteración (FR-070), pero por diseño fijo, no por
      configuración
- [X] `region_weight_factor` valida `0 <= x < 1` — **límite inferior INCLUSIVO** (FR-081b, corregido por
      RD-76: excluirlo volvía **irrepresentable** el valor neutro y la configuración de `v1` no habría
      podido cargarse) y superior **estricto** (equivale al filtro duro que FR-081a prohíbe)
- [X] `0 < fallback_new_item_quota_ratio < 1` y `10 <= top_n_min <= top_n_default <= top_n_max`
- [X] `declared_tags_min` y `collab_min_neighbors` son enteros positivos y están presentes
- [X] `emergent_evidence_threshold` es entero positivo y está presente (RD-102)
- [X] `0 < diversity_max_cluster_share ≤ 1` (FR-071)
- [X] `fallback_stored_size` (**100**) presente y `≥ top_n_max` (FR-033f, RD-111); el operativo
      `recompute_requests_max_deliveries` (**5**) presente y positivo
- [X] **FR-068b con lista cerrada** (RD-110): `signal_retention_days` debe superar estrictamente a
      **las tres** ventanas —`popularity_window_days`, la retención de idempotencia y
      `event_redelivery_window_hours`—; si alguna falta o no se cumple, el arranque falla nombrándola
- [X] **Una clave de peso de consumo se rechaza** si aparece (RD-99): un parámetro sin consumidor es una
      invitación a conectarlo
- [X] **Una versión desactivada no puede reactivarse** (DI-24): si el hash del archivo coincide con una
      versión desactivada, el arranque falla con un mensaje que indica que el rollback se hace
      **hacia adelante** —versión nueva con otro `version_label`— (RD-94)
- [X] `config_version` es determinista: mismo archivo → mismo hash, en cualquier máquina
- [X] **Deuda del prototipo resuelta**: no queda ninguna constante del motor hardcodeada

**Tests**: `tests/unit/test_config_loader.py` — tabla de configuraciones inválidas (suma ≠ 1, `alpha` fuera de `[0,1]`, `peso_dislike ≥ 0`, `popularity_confidence_z = 0`, catálogo etario con ordinal repetido o salteado, filtro desactivado, rating fuera de catálogo, **`tiebreak_criteria` presente**), cada una debe fallar; hash reproducible entre dos cargas; archivo idéntico a una versión desactivada → fallo con mensaje de rollback hacia adelante.

---

### T005 [P] [TDD] — Modelo de dominio compartido y errores tipados

**Descripción**: tipos del dominio y jerarquía de errores que la API traduce a códigos HTTP. Incluye
el enum de `result_type` con los cinco estados de FR-056.

**Archivos**: `src/recomendaciones/shared/domain.py`, `src/recomendaciones/shared/errors.py`

**Dep.**: T001

**Criterios de aceptación**:
- [X] `ResultType` tiene exactamente cinco valores y es cerrado (FR-056, FR-057)
- [X] `SignalType` distingue `like`, `dislike`, `consumo` (FR-062) — sin valor por defecto
- [X] Cada error declara su código HTTP; no hay `Exception` genérica escapando a la API
- [X] Los tipos no dependen de SQLAlchemy ni de Redis

**Tests**: `tests/unit/test_domain.py` — exhaustividad del enum; construir una señal sin tipo falla.

---

### T006 [P] — Test de arquitectura: `api/` no importa `engine/`

**Descripción**: convertir INV-1 en un test que falla en CI. Es la única defensa automatizable contra
que alguien "resuelva" una latencia calculando en línea.

**Archivos**: `tests/unit/test_architecture.py`

**Dep.**: T001

**Criterios de aceptación**:
- [X] Falla si cualquier módulo bajo `api/` importa, directa o transitivamente, `engine/`
- [X] Falla si `engine/` importa `storage/`, `httpx`, `redis` o `sqlalchemy`
- [X] Falla si la API accede a Postgres fuera de los tres repositorios admitidos por INV-1: repoblado
      de `filters:` ante miss, repoblado de `retired:` ante miss y escritura de declaración (T053).
      Ninguna ruta de lectura de resultados los importa. *(Decía «fuera del health check», regla que
      T053 y `data-model.md` §3.1.1 no podían cumplir.)*
- [X] **FR-068e**: falla si algún módulo fuera de la purga (T057) y de la supresión (T058) emite `DELETE`
      o `TRUNCATE` sobre `user_signals`, `user_declared_tags`, `user_exclusions`, `user_suppressions` o
      `item_promotions` (RD-111)
- [X] El mensaje de fallo nombra el import ofensor y cita FR-003
- [X] **SC-012** — 0 conexiones directas a bases de datos de otros repos y 0 rutas de acceso desde frontends. El test de arquitectura es el único lugar donde esto se verifica estructuralmente y no por inspección

**Tests**: es la tarea de test. Se verifica con un caso negativo temporal que debe hacerla fallar.

---

## Milestone 2 — Motor de recomendación

> 🔴 **Milestone test-first.** Todas las tareas son `[TDD]`: ver *Política TDD*. El commit de test
> precede al de implementación, y el rojo debe haberse visto.

| ID | Tarea | Dep. | [P] | [TDD] | Est. |
|---|---|---|---|---|---|
| T007 | Vectorización TF-IDF sobre vocabulario compartido | T004, T005 | | ✅ | M |
| T008 | Similitud coseno y construcción de perfil | T007 | | ✅ | S |
| T009 | Señal content-based | T008 | [P] | ✅ | M |
| T010 | Señal colaborativa (k vecinos) | T008 | [P] | ✅ | M |
| T011 | Señal cross-module | T008 | [P] | ✅ | M |
| T012 | Combinación lineal y desempate determinista | T009, T010, T011 | | ✅ | M |

### T007 [TDD] — Vectorización TF-IDF sobre vocabulario compartido

**Descripción**: TF-IDF sobre un **espacio vectorial único** para ambos módulos (FR-010d). Cada vector
producido registra la `vocab_version` con la que se generó (FR-010f).

**Archivos**: `src/recomendaciones/engine/content.py`, `src/recomendaciones/engine/vocabulary.py`

**Dep.**: T004, T005

**Criterios de aceptación**:
- [X] El vocabulario es único: un vector de película y uno de juego son comparables (FR-010d)
- [X] **No existe** camino de código que construya un espacio por módulo (corrige P5 del prototipo)
- [X] Todo vector emitido lleva `vocab_version`; comparar vectores de versiones distintas lanza error (FR-010f)
- [X] El vocabulario es determinista: mismo catálogo → mismo espacio, mismo orden de dimensiones
- [X] Función pura: sin I/O, sin reloj
- [X] **Ninguna ponderación IDF es negativa**: un tag presente en todos los ítems no puede invertir el
      sentido de su pertenencia. *El prototipo usa `log(N / (1 + df))`, que da `−0,405` para un tag
      presente en todo el catálogo.* La fórmula es **`ln((1 + N) / (1 + df)) + 1`** (RD-105, FR-022):
      un tag en todo el catálogo pesa exactamente 1
- [X] Los ítems **retirados** no participan de la ponderación del corpus (RD-25)

> *SC-016 (propagación al módulo opuesto) estaba atribuido acá; es comportamiento del worker y se
> movió a T027 el 2026-09-27.*

**🔴 Paso 1 — Rojo** (`tests/unit/test_vocabulary.py`, commit propio):
determinismo con dos órdenes de entrada distintos; comparar vectores de `vocab_version` distinta
lanza error; un tag presente solo en un módulo sigue teniendo dimensión en el espacio común; un tag
presente en todos los ítems tiene peso exactamente 1 (regresión del prototipo, RD-105).

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de espacio común es el que fija el diseño:
escrito primero, hace imposible «resolverlo» con un vocabulario por módulo (P5 del prototipo).

---

### T008 [TDD] — Similitud coseno y construcción de perfil

**Descripción**: coseno acotado a `[-1,1]` y perfil de usuario L2-normalizado (FR-022c). **Solo likes
y dislikes construyen el perfil; el consumo no lo altera** (FR-022b, corrige P1 del prototipo).

**Archivos**: `src/recomendaciones/engine/similarity.py`, `src/recomendaciones/engine/profile.py`

**Dep.**: T007

**Criterios de aceptación**:
- [X] El coseno nunca sale de `[-1,1]`, incluso con error de punto flotante
- [X] Vector nulo → similitud 0, sin división por cero
- [X] El perfil queda L2-normalizado (FR-022c)
- [X] Una señal de tipo `consumo` **no modifica** el vector de perfil (FR-022b)
- [X] `like` refuerza y `dislike` penaliza, con magnitudes de configuración (FR-029a-d)
- [X] Ante señales contradictorias, gana la más reciente por `occurred_at` (FR-029d)
- [X] El perfil `general` se construye agregando pesos por tag sobre ambos módulos
- [X] **Los insumos del perfil son la declaración de gustos y las señales vigentes** (FR-087, RD-68):
      la declaración se traduce a señales sintéticas de tipo `like` sobre los ítems que contienen los
      tags declarados —mecanismo de `cli_preferencias.py`—, que **no** se persisten en `user_signals`.
      Un usuario con declaración y sin señales tiene perfil no vacío
- [X] Los tags **heredados** del otro módulo (compartidos según `tag_modules`) se incorporan al insumo
      **derivándolos** en la construcción, no leyéndolos de una tabla (FR-085, RD-97)
- [X] Las señales sobre ítems **retirados** siguen alimentando el perfil (FR-073)
- [X] **FR-086b**: dislikes suficientes llevan el peso de un tag declarado a cero o a negativo; la
      declaración no se toca y un like posterior lo vuelve a subir

> *Agregado el 2026-09-27: la siembra por declaración estaba solo en T056 (Fase 2), mientras T053–T055
> (Fase 1) ya obligan a declarar. En Fase 1 el usuario declaraba y el motor lo ignoraba: sin señales,
> α = 0,5 aportaba cero. El conflicto del peso del consumo (RD-73 frente a FR-022b) quedó resuelto por
> **RD-99** a favor de FR-022b: el criterio de arriba es definitivo.*

**🔴 Paso 1 — Rojo** (`tests/unit/test_profile.py`, commit propio): property-based — norma ≈ 1 para
cualquier conjunto no vacío de señales; una señal `consumo` **no altera** el vector; un like posterior
revierte un dislike previo; vector nulo → similitud 0 sin excepción; coseno siempre en `[-1,1]`;
declaración de 5 tags sin señales → perfil no vacío y afín a esos tags; tag heredado presente en el
insumo sin fila propia en la declaración; tres dislikes sobre ítems de un tag declarado → su componente
del perfil ≤ 0 y la declaración intacta (FR-086b).

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de `consumo` codifica la decisión Q3 antes de
que exista código que pueda contradecirla.

---

### T009 [P] [TDD] — Señal content-based

**Requisitos**: FR-022, FR-021 *(explicitados el 2026-09-28 para la trazabilidad de T048, RD-111)*

**Descripción**: puntuar candidatos por similitud entre el perfil del módulo y el vector del ítem.

**Archivos**: `src/recomendaciones/engine/content.py`

**Dep.**: T008

**Criterios de aceptación**:
- [X] Score en rango acotado y comparable con las otras dos señales
- [X] Perfil vacío (usuario sin señales) → señal neutra, sin excepción
- [X] Función pura, determinista con semilla fija
- [X] Vectores con `vocab_version` distinta → error, no resultado silencioso

**🔴 Paso 1 — Rojo** (`tests/unit/test_content.py`): usuario con perfil de terror puntúa más alto un
ítem de terror; perfil vacío → señal neutra sin lanzar; vectores de `vocab_version` distinta → error.

**🟢 Paso 2 — Verde**: implementar hasta pasar.

---

### T010 [P] [TDD] — Señal colaborativa (k vecinos)

**Descripción**: k vecinos más similares (k=20, D4) y agregación de sus preferencias.

**Archivos**: `src/recomendaciones/engine/collaborative.py`

**Dep.**: T008

**Criterios de aceptación**:
- [X] `k` proviene de configuración versionada, no de constante (FR-025)
- [X] Menos de `k` usuarios disponibles → usa los que hay, sin fallar
- [X] Cero vecinos → señal neutra, no error
- [X] La selección de vecinos es determinista ante empates de similitud (FR-070)
- [X] Función pura: recibe la matriz de perfiles, no la consulta
- [X] **Un vecino con similitud ≤ 0 nunca eleva el score de un ítem** (edge case «sin invertir el
      sentido de la recomendación»). *Regresión verificada en el prototipo: cuando todos los vecinos
      tienen similitud negativa, normalizar por el máximo invierte el signo y un ítem likeado por
      usuarios de gustos opuestos recibe +3,23 (`recommenders.py`, `CollaborativeRecommender`).* Los
      vecinos con similitud ≤ 0 **se excluyen** del vecindario (RD-105, FR-023)
- [X] La señal colaborativa queda acotada a `[-1, 1]`, comparable con las otras dos (T012)

**🔴 Paso 1 — Rojo** (`tests/unit/test_collaborative.py`): con k=3 y solo 2 usuarios no falla; cero
vecinos → señal neutra; empate de similitud resuelve idéntico en 100 ejecuciones con orden barajado;
**todos los vecinos con similitud negativa → ningún ítem sube por su like** (fixture: el usuario 1 del
`data.py` del prototipo, que dislikeó *Avengers: Endgame*); un vecino con similitud exactamente 0 no
cuenta para `k` ni para `collab_min_neighbors`.

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de empate escrito primero fuerza a definir
el criterio de desempate (FR-070) en vez de heredar el orden de iteración.

---

### T011 [P] [TDD] — Señal cross-module

**Descripción**: boost desde el perfil general del módulo opuesto, normalizado a `[-1,1]`. Es la
señal que sostiene el cold start cruzado (US4).

**Archivos**: `src/recomendaciones/engine/cross_module.py`

**Dep.**: T008

**Criterios de aceptación**:
- [X] El boost está normalizado a `[-1,1]`, comparable con las otras señales
- [X] Usuario sin actividad en el módulo opuesto → boost 0, no error
- [X] El boost se calcula sobre el vocabulario compartido (posible gracias a T007)
- [X] Un usuario con solo actividad en películas recibe recomendaciones no triviales en juegos (SC-010)

**🔴 Paso 1 — Rojo** (`tests/unit/test_cross_module.py`): usuario con likes de terror en películas
obtiene juegos de terror por encima del ordenamiento base; sin actividad en el módulo opuesto → 0;
el boost nunca sale de `[-1,1]`.

**🟢 Paso 2 — Verde**: implementar hasta pasar. Este test es la definición ejecutable de SC-010.

---

### T012 [TDD] — Combinación lineal y desempate determinista

**Descripción**: `score = α·content + β·collaborative + γ·cross`, con pesos de configuración versionada.
Desempate por criterio secundario estable (FR-070).

**Archivos**: `src/recomendaciones/engine/scoring.py`

**Dep.**: T009, T010, T011

**Criterios de aceptación**:
- [X] Los pesos se leen de configuración; **cero constantes numéricas** en el módulo (FR-025)
- [X] El resultado es idéntico entre ejecuciones con la misma entrada y `config_version` (SC-021)
- [X] El desempate es determinista y **nunca** usa el orden de iteración (FR-070).
      ⚠️ **Corregido el 2026-09-22**: este criterio exigía leer `tiebreak_criteria` de configuración,
      parámetro que **RD-10 eliminó del esquema** y que T004 ahora manda rechazar en el loader. El
      criterio pedía usar algo que el sistema ya no acepta
- [X] El `config_version` usado viaja en la salida del scoring, no se pierde
- [X] **Los candidatos se restringen a `items.status = 'available'`** (FR-072, §4.4 punto 1), vía
      `WHERE status = 'available'` sobre `idx_items_candidates`. Un ítem retirado no entra al
      ranking: excluirlo después sería reordenar una lista ya contaminada
- [X] **SC-021** queda verificado por el test de reproducibilidad de esta tarea

**🔴 Paso 1 — Rojo** (`tests/unit/test_scoring.py`): reproducibilidad exacta en 100 corridas con el
orden de entrada barajado; cambiar `config_version` cambia el resultado de forma trazable; el módulo
no contiene constantes numéricas (test de inspección).

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de reproducibilidad es SC-021 ejecutable.

---

## Milestone 3 — Post-procesamiento (invariantes de seguridad)

> Este milestone implementa INV-3. Ninguna tarea acá admite una excepción "por performance".
>
> 🔴 **Milestone test-first.** Es donde el TDD más importa: un test de invariante escrito *después*
> tiende a describir lo que el código hace, no lo que la spec exige. Escrito antes, es la spec.

| ID | Tarea | Dep. | [P] | [TDD] | Est. |
|---|---|---|---|---|---|
| T013 | Filtro de edad por `age_rating` (fail-closed) | T004, T005 | | ✅ | M |
| T014 | Filtro de exclusión | T003, T005 | | ✅ | M |
| T015 | Diversificación MMR | T012 | | ✅ | M |
| T016 | Pipeline de post-proceso con orden garantizado | T013, T014, T015 | | ✅ | M |
| T017 | Batería exhaustiva de invariantes | T016 | | ✅ | L |

### T013 [TDD] — Filtro de edad por `age_rating` (fail-closed)

**Descripción**: filtrar por clasificación etaria en modo **fail-closed** (FR-049→FR-053). Corrige
directamente P2 del prototipo, donde un rating desconocido se trataba como apto para todo público.

**Archivos**: `src/recomendaciones/engine/postprocess.py`

**Dep.**: T004, T005

**Criterios de aceptación**:
- [X] `age_rating` ausente, nulo, vacío o **fuera del catálogo** → ítem **no apto** (FR-051)
- [X] El catálogo de ratings viene de configuración versionada (FR-053) — sin `dict` hardcodeado
- [X] **No existe** parámetro, flag ni rama que desactive el filtro (FR-054)
- [X] Un rating desconocido nuevo (p. ej. `"NC-17"` sin declarar) se filtra, no se admite
- [X] **SC-002** — 0 % de ítems que violen el filtro de edad. Acá se implementa; T017 y T052 lo ejercitan de forma exhaustiva

**🔴 Paso 1 — Rojo** (`tests/invariants/test_age_filter.py`, commit propio): producto cartesiano
`age_rating` × franja etaria (FR-055); property-based — para todo usuario menor, ningún ítem para
adultos sobrevive; valores basura (`None`, `""`, `"XYZ"`, `123`, `"NC-17"` no declarado) → no apto.

**🟢 Paso 2 — Verde**: implementar hasta pasar. **Este es el caso más importante del alcance TDD**:
el test de valores basura escrito primero hace estructuralmente imposible reintroducir el
`.get(rating, 0)` permisivo del prototipo (P2). Escrito después, se habría acomodado a él.

---

### T014 [TDD] — Filtro de exclusión

**Descripción**: excluir ítems ya vistos/jugados/dislikeados/likeados. La exclusión se deriva de
`user_signals` con "gana la más reciente"; consumo excluye permanentemente, dislike es revertible.

**Archivos**: `src/recomendaciones/engine/postprocess.py`, `src/recomendaciones/storage/db/exclusions.py`

**Dep.**: T003, T005

**Criterios de aceptación**:
- [X] Los cuatro orígenes de exclusión se aplican
- [X] Conjunto de exclusión **no disponible** → se rechaza la solicitud, nunca se sirve sin filtrar (FR-050)
- [X] La resolución señal→exclusión es determinista y auditable
- [X] **Deuda del prototipo resuelta**: el conjunto de exclusión expone una interfaz pública de consulta; ningún llamador accede a sus atributos internos
- [X] `INV-2`: las exclusiones se derivan de Postgres; Redis solo las cachea
- [X] `storage/db/exclusions.py` es el **resolutor de exclusiones**, **escritor único** de
      `user_exclusions` (`data-model.md` §2.7, DI-13), invocado por T029 y T064
- [X] Escritura **aditiva**: el resolutor **nunca** trunca ni vacía la tabla para reconstruirla
      (DI-20, FR-029b1); las filas con `origin = 'consumo'` sobreviven a la purga de su señal
- [X] Escribe `resolved_at` (consumidor: `exclusion_resolve_lag_seconds`, §7.12) y desempata con
      `ORDER BY occurred_at DESC, id DESC` (DI-22)
- [X] **Invalida `filters:{user_id}` antes de escribir** cada exclusión nueva o revertida (RD-96,
      FR-080c)
- [X] **SC-003** y **SC-018** — 0 % de ítems del conjunto de exclusión y 0 % de ítems con señal registrada en el top-N

> *Criterios del resolutor agregados el 2026-09-27: `data-model.md` §9 se los asignaba a «T009», que en
> este backlog es la señal content-based; el archivo del resolutor ya era de esta tarea.*

**🔴 Paso 1 — Rojo** (`tests/invariants/test_exclusion.py` + `tests/unit/test_exclusion_api.py`):
ningún ítem excluido aparece en ninguno de los cinco `result_type`; like posterior revierte dislike;
consumo no se revierte; conjunto no disponible → se rechaza la solicitud; el batch no accede a
atributos privados del conjunto de exclusión; reconstruir tras purgar la señal de un consumo conserva
la exclusión (DI-20); una exclusión nueva invalida `filters:`.

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de acceso privado escrito primero fuerza a
diseñar la interfaz pública en vez de agregarla como refactor posterior (deuda del prototipo).

---

### T015 [TDD] — Diversificación MMR

**Descripción**: MMR con `lambda_mmr=0.7` (D4) sobre el espacio de tags. La restricción dura: **MMR
selecciona de un conjunto ya filtrado y no puede reintroducir nada** (FR-031).

**Archivos**: `src/recomendaciones/engine/postprocess.py`

**Dep.**: T012

**Criterios de aceptación**:
- [X] La salida de MMR es un **subconjunto** de su entrada — verificado como aserción, no por convención
- [X] `lambda_mmr` viene de configuración versionada
- [X] La diversidad se mide como proporción máxima del top-N atribuible a un cluster (FR-071)
- [X] Con `lambda=1` el orden coincide con el de relevancia pura (caso degenerado correcto)
- [X] Determinista ante empates (FR-070)
- [X] **Tope de cluster en la selección** (FR-071a, RD-108): cluster = tag principal del ítem (mayor peso,
      desempate por nombre); en la posición `p` se omite un candidato cuyo cluster superaría
      `ceil(0,4 × p)`; si solo quedan candidatos de clusters topados, se relaja y se incrementa
      `diversity_cap_relaxed_total`
- [X] **SC-011** — ningún prefijo de longitud N concentra más de `ceil(0,4 × N)` ítems de un mismo
      cluster, salvo las relajaciones contadas

**🔴 Paso 1 — Rojo** (`tests/unit/test_mmr.py`): property-based — `set(salida) ⊆ set(entrada)` para
toda entrada; con `lambda=1` el orden coincide con relevancia pura; para todo prefijo, ningún cluster
supera `ceil(0,4 × N)` cuando hay candidatos de otros clusters; la diversidad medida mejora
frente al top-N sin diversificar; determinista ante empates.

**🟢 Paso 2 — Verde**: implementar hasta pasar. La property de subconjunto escrita primero es FR-031
convertido en spec ejecutable: hace imposible que MMR reintroduzca un ítem filtrado.

---

### T016 [TDD] — Pipeline de post-proceso con orden garantizado

**Descripción**: componer scoring → edad → exclusión → MMR **en ese orden**, de forma que el orden
sea una propiedad del tipo y no una convención de llamada.

**Archivos**: `src/recomendaciones/engine/postprocess.py`

**Dep.**: T013, T014, T015

**Criterios de aceptación**:
- [X] El orden está garantizado estructuralmente: no es posible invocar MMR antes de los filtros
- [X] La función expone una sola entrada pública; las etapas no son invocables sueltas desde fuera
- [X] Cada etapa registra cuántos candidatos descartó, para auditoría
- [X] Conjunto vacío tras filtrar → resultado vacío explícito, nunca relleno con no aptos (FR-033)

**🔴 Paso 1 — Rojo** (`tests/invariants/test_pipeline_order.py`): para toda entrada, la salida
satisface simultáneamente las tres restricciones (edad, exclusión, subconjunto); las etapas no son
invocables sueltas desde fuera del módulo; conjunto vacío tras filtrar → vacío explícito, no relleno.

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de no-invocabilidad escrito primero empuja al
diseño estructural del orden; escrito después, se habría aceptado el orden como convención de llamada.

---

### T017 [TDD] — Batería exhaustiva de invariantes

**Descripción**: la suite que hace de INV-3 algo demostrable y no aspiracional (FR-055).

**Archivos**: `tests/invariants/`

**Dep.**: T016

**Criterios de aceptación**:
- [X] Cubre el producto cartesiano `age_rating` × franja etaria
- [X] Cubre cada uno de los cuatro orígenes de exclusión
- [X] Cubre los cinco `result_type` (FR-056) — incluido el respaldo y el obsoleto. **El rechazo por
      falta de declaración NO es un sexto estado** (FR-088): es precondición incumplida y se verifica
      como tal, antes de la precedencia
- [X] **Cubre los 34 invariantes vigentes de `data-model.md` §6** (DI-1→DI-29, contando `DI-2a'`…`DI-2e`),
      o declara por escrito cuáles quedan fuera y por qué. **DI-29** (lápida de supresión) se verifica con
      T029 y T058. *(Decía «32, DI-1→DI-28», anterior a RD-101.)*
- [X] **DI-28 incluido y con test propio**: un usuario con módulo declarado tiene al menos
      `declared_tags_min` filas **propias** en `user_declared_tags` —sin contar las heredadas por
      FR-085—. Es el **único invariante que el esquema no sostiene**: no hay restricción de tabla que
      exprese un mínimo de filas, de modo que su cumplimiento depende **enteramente** de este test
- [X] **DI-10 con test propio**: retirar un ítem presente en `reco:*` **y** en `fallback:*` → la
      lectura siguiente no lo contiene. Debe cubrir **los tres puntos de §4.4** —selección, respaldo
      y guarda del request path—, no uno: cada uno es un camino distinto por el que el ítem llega al
      usuario, y verificar solo el primero deja vivos los otros dos (FR-072)
- [X] **DI-11 con test propio**: retirar un ítem con señales → `user_signals` conserva las filas y
      los perfiles **no cambian**. El retiro es lógico (FR-073); si el perfil cambiara, un hecho
      ajeno al usuario estaría alterando sus recomendaciones
- [X] Incluye valores límite: exactamente la edad mínima, un día antes, un día después
- [X] Es property-based, no solo por ejemplos
- [X] **SC-002 y SC-003 quedan verificados acá**: 0 % de violaciones del filtro de edad y 0 % de
      ítems del conjunto de exclusión, en cualquier respuesta emitida. Son los dos invariantes de
      seguridad de US5 y esta es la tarea que los hace demostrables
- [X] **SC-018** verificado acá: 0 % de ítems con like, dislike o consumo aparece en el top-N
- [ ] Corre en CI como **gate bloqueante**: si falla, no hay merge

**Tests**: es la tarea de test — consolida y extiende las suites de T013–T016. Verificación de poder
de detección: **mutar deliberadamente el filtro de edad debe hacer fallar la suite**. Si una mutación
pasa, el test no está afirmando lo que dice afirmar. Esta comprobación es obligatoria antes de cerrar
la tarea y se documenta en el PR.

---

## Milestone 4 — Persistencia y caché

| ID | Tarea | Dep. | [P] | Est. |
|---|---|---|---|---|
| T018 | Cliente Redis y esquema de claves | T002, T004 | | M |
| T019 | Escritura del top-N con score y `config_version` | T018, T016 | | S |
| T020 | Política de cache miss y señalización de recálculo | T019 | | M |
| T021 | Comportamiento ante Redis caído | T018 | [P] | S |
| T022 | Reconstrucción total tras pérdida de Redis | T020 | | M |

### T018 [TDD] — Cliente Redis y esquema de claves

**Descripción**: las **ocho** familias de claves de `data-model.md` §3.1 con sus TTL (§3.1; eran
«seis de `plan.md` §2», una cuenta anterior a `retired:`, y siete antes del Stream `recompute:requests`
de RD-100). `config_version` forma parte de la clave, de
modo que resultados de versiones distintas conviven sin colisionar.

**Archivos**: `src/recomendaciones/storage/cache/keys.py`, `client.py`, `ttl.py`

**Dep.**: T002, T004

**Criterios de aceptación**:
- [X] Las claves se construyen por función tipada; **no hay concatenación de strings ad-hoc**
- [X] `config_version` está en la clave de `reco:` **y también en la de `reco:stale:`** (hallazgo F3):
      un resultado de una configuración anterior nunca se sirve **rotulado** con la versión vigente
- [X] **Versiones legibles** (RD-103): al arrancar se calcula la lista de versiones desactivadas hace
      menos de `TTL_STALE` **con catálogo etario idéntico** al activo; una versión con catálogo etario
      distinto **nunca** es legible
- [X] Existe la familia **`recompute:requests`** (Stream, sin TTL, `MAXLEN` aproximado desde
      `recompute_requests_maxlen`) con productor `XADD` y lectura por grupo de consumidores (RD-100)
- [X] Los TTL vienen de configuración (FR-068), no de constantes
- [X] `filters:{user_id}` tiene TTL **más corto** que `reco:` — corrige P4 del prototipo, donde compartían 7 días
- [X] **Deuda del prototipo resuelta**: caché en memoria reemplazada por Redis persistente
- [X] `INV-2`: no hay dato cuya única copia esté en Redis
- [X] Existe la familia **`retired:{module}`** (§3.1), usada como guarda del request path por T037
- [X] Ese set contiene **solo los ítems retirados en los últimos `TTL_STALE` + 1 día** (RD-39), no
      el histórico completo. La cota no es heurística: un ítem retirado hace más de `TTL_STALE` no
      puede estar en ninguna entrada de caché viva
- [X] La ventana **se deriva de `TTL_STALE`**, no es constante independiente. **DI-25** verifica el
      acoplamiento: subir `TTL_STALE` sin subir la ventana haría fallar la guarda **en silencio**
- [X] `filters:{user_id}` porta **`declared_modules`** además de edad y exclusiones, y se repuebla
      desde `users`, `user_exclusions` y `user_declared_tags` ante miss (RD-96)
- [X] Existe una operación de **invalidación de `filters:{user_id}`**, usada por el resolutor de
      exclusiones (T014) y por el endpoint de declaración (T053), siempre **antes** de la escritura en
      Postgres (FR-080c)
- [X] **SC-022** — un cambio de versión de configuración provoca 0 invalidaciones masivas: la
      versión en la clave hace que las entradas viejas expiren solas, y mientras viven **se siguen
      leyendo** por la lista de versiones legibles (RD-103, FR-025c). *(Movido desde T060; el conflicto
      con FR-025c quedó resuelto por RD-103.)*

**Tests**: `tests/unit/test_cache_keys.py` — colisión imposible entre módulos, entre `config_version`
y entre vigente/obsoleto; con `v2` activa, una entrada de `v1` es legible **si y solo si** ambas comparten
catálogo etario, y se sirve con la etiqueta `v1`.
`tests/integration/test_redis.py` — TTL efectivos; `filters:` expira antes que `reco:`; tras invalidar
`filters:`, la lectura siguiente repuebla con la exclusión o la declaración nueva.

---

### T019 [TDD] — Escritura del top-N con score y `config_version`

**Descripción**: serializar el resultado con ítems, score, rank, `config_version` y `computed_at`.

**Archivos**: `src/recomendaciones/storage/cache/repository.py`

**Dep.**: T018, T016

**Criterios de aceptación**:
- [X] Cada entrada persiste `config_version` y `computed_at` (trazabilidad exigida por Q4)
- [X] `items` se guarda con **`min(top_n_max, candidatos)`** ítems, no con el `top_n` de ninguna
      solicitud: el truncado ocurre al servir (`data-model.md` §3.2, RD-102, RD-111)
- [X] La escritura del top-N vigente y su copia obsoleta es consistente entre sí
- [X] Serialización y deserialización son simétricas — round-trip exacto
- [X] Una entrada escrita con una `config_version` retirada no se sirve como vigente
- [X] **SC-004** — 100 % de los top-N servidos incluyen la versión de configuración del motor

**Tests**: `tests/integration/test_cache_repository.py` — round-trip; la respuesta permite reconstruir con qué configuración se generó.

---

### T020 [TDD] — Política de cache miss y señalización de recálculo

**Descripción**: implementar la máquina de estados de FR-056 con **precedencia estricta**: pendiente →
sin candidatos → respaldo → obsoleto → vigente. Sin top-N vigente, el **respaldo precede al obsoleto**
y se acompaña de la señal de FR-056a cuando existe un obsoleto (FR-034, RD-56). Ante miss, emitir
señal de recálculo con supresión (`recompute:lock`) para no disparar N señales por el mismo usuario.

> **Canal decidido (RD-100, 2026-09-27)**: la señal es un `XADD` al Stream interno `recompute:requests`,
> con `recompute:lock` como supresión de duplicados. No es un evento del broker ni contrato con
> `api-general`. Sigue detrás de la interfaz `RecomputeSignaler`, que ahora tiene una sola
> implementación. *(Esta tarea decía «fire-and-forget (D7)» —publicar a RabbitMQ desde la API—, decisión
> del plan del 2026-09-07 que el plan regenerado no conservaba.)*

**Archivos**: `src/recomendaciones/api/services/read_service.py`, `src/recomendaciones/storage/cache/recompute.py`

**Dep.**: T019

**Criterios de aceptación**:
- [X] Los cinco estados son mutuamente excluyentes; la precedencia se aplica en el orden de FR-056
- [X] Respaldo vacío tras filtrar se reporta como **sin candidatos**, no como respaldo (FR-056)
- [X] La señal de recálculo se emite a lo sumo una vez por ventana de supresión
- [X] La lectura **nunca falla** porque la escritura de la señal falle: se registra y se mide, y la respuesta no cambia. (Si Redis entero cae, rige T021: `503`)
- [X] Ante miss bajo la versión activa, consulta las **versiones legibles** de T018 antes de declarar miss; un acierto así se sirve con su etiqueta y **no** emite señal (RD-103)
- [X] Con respaldo y obsoleto disponibles, se sirve el **respaldo** con la señal de FR-056a; el obsoleto solo se sirve si no hay respaldo servible
- [X] `INV-1`: el miss no dispara cómputo en línea
- [X] **FR-038**: dos lecturas consecutivas sobre el mismo estado de caché devuelven la misma respuesta
      degradada (US6-5)
- [X] **SC-015** — una ráfaga de misses del mismo par (usuario, módulo) dentro de la ventana no multiplica los recálculos

**Tests**: `tests/integration/test_cache_miss.py` — 50 lecturas concurrentes en miss producen 1 sola entrada en `recompute:requests`; broker caído → la lectura responde igual y la entrada se escribe; tabla de los cinco estados con su entrada correspondiente; entrada de la versión anterior con igual catálogo etario → servida con su etiqueta, sin señal.

---

### T021 [P] [TDD] — Comportamiento ante Redis caído

**Descripción**: distinguir *miss* (dato ausente) de *caída* (Redis inalcanzable). Ante caída: `503`
con `Retry-After`. **Prohibido** recurrir a Postgres para calcular en línea (FR-065).

**Archivos**: `src/recomendaciones/storage/cache/client.py`, `src/recomendaciones/api/deps.py`

**Dep.**: T018

**Criterios de aceptación**:
- [X] Redis caído → `503` con `Retry-After`, nunca `200` con resultado vacío
- [X] **No existe** ruta de fallback que consulte Postgres desde el request path (FR-065, INV-1)
- [X] El timeout hacia Redis es explícito y configurable — no se cuelga indefinidamente
- [X] Miss y caída producen `result_type` / código HTTP distintos y distinguibles

**Tests**: `tests/integration/test_redis_down.py` — con Redis detenido, la respuesta es 503 y no hay ninguna query a Postgres (verificado por espía de conexiones).

---

### T022 [TDD] — Reconstrucción total tras pérdida de Redis

**Descripción**: job de warm-up que encola solicitudes de recálculo en `recompute:requests` **con
límite de tasa** (FR-066, RD-100).
El punto es evitar la avalancha auto-infligida: la reconstrucción nunca se dispara como efecto
colateral del tráfico de lectura.

**Archivos**: `src/recomendaciones/batch/warmup.py`

**Dep.**: T020

**Criterios de aceptación**:
- [X] Es un proceso dedicado, invocable manualmente; **no** se activa por tráfico (FR-066)
- [X] Respeta un límite de tasa configurable
- [X] Es reanudable: interrumpirlo y relanzarlo no duplica trabajo ni pierde usuarios
- [X] Con Redis vacío, el servicio sigue respondiendo (pendiente/respaldo) mientras reconstruye
- [X] `INV-2`: reconstruye íntegramente desde Postgres
- [X] **SC-008** — tras un vaciado total de la caché, 100 % de los top-N afectados se reconstruye sin intervención manual

**Tests**: `tests/integration/test_warmup.py` — flush total de Redis; el servicio no devuelve 500; el warm-up repuebla; la tasa de `XADD` no supera el límite.

---

# FASE 2 — Robustez operativa

> **Objetivo**: que sobreviva a fallos reales. Cierra US3, US4, US6, US7.
>
> **No incluye T028–T030**, que se movieron a Fase 1 (corrección F9). De Milestone 6 quedan acá
> **T031** y **T032**, que es el corte natural: lo que sobrevive a un fallo, no lo que produce el
> dato.

## Milestone 5 — Worker de recálculo asíncrono

> ⚠️ **Este milestone está repartido entre fases** (hallazgo F1). T023, T024 y T027 son **Fase 1**:
> sin ellas no hay US2 ni SC-005. T025 y T026 son Fase 2: robustez ante fallos, no funcionalidad.

| ID | Tarea | Fase | Dep. | [P] | Est. |
|---|---|---|---|---|---|
| T023 | Consumo de `recomendacion.actualizar` | **1** | T003, T005, **T049** | | M |
| T024 | Idempotencia por `event_id` | **1** | T023 | | M |
| T027 | Recálculo y propagación cross-module condicional | **1** | T024, T016, T019, T064 | | L |
| T025 | Reintentos con backoff y DLQ | 2 | T023 | | M |
| T026 | Manejo de payload inválido sin bloquear la cola | 2 | T025 | | S |

### T023 [TDD] — Consumo de `recomendacion.actualizar`

**Descripción**: consumidor con validación de schema. Campos mínimos: `event_id`,
**`origin_interaction_id`**, `user_id`, `module`, `item_id`, `signal_type`, `occurred_at` (FR-061).
*(`origin_interaction_id` agregado el 2026-09-27: sin él, T064 no puede deduplicar la señal contra la
misma interacción recibida por sincronización.)*

**Archivos**: `src/recomendaciones/worker/consumer.py`, `schemas.py`

**Dep.**: T003, T005, **T049** (el schema del evento se define antes de consumirlo)

**Criterios de aceptación**:
- [X] Valida contra el schema antes de tocar el dominio
- [X] `signal_type` es **obligatorio**: sin él, el evento va a DLQ — no se infiere (FR-064)
- [X] `origin_interaction_id` es **obligatorio**: sin él, el evento va a DLQ (FR-061, DEP-8)
- [X] Módulo desconocido → DLQ sin alterar ningún top-N
- [X] `INV-4`: el worker no llama a `api-general` ni escribe fuera de su DB

**Tests**: `tests/integration/test_consumer.py` (testcontainers RabbitMQ) — evento válido se procesa; falta `signal_type` → DLQ; módulo desconocido → DLQ y ningún top-N cambia.

---

### T024 [TDD] — Idempotencia por `event_id`

**Descripción**: deduplicación por `event_id` con marca en Redis (`dedupe:event:`) respaldada por
`processed_events` en Postgres. Incluye el caso de FR-069: un duplicado que llega **después** de
expirar la marca debe poder reprocesarse sin corromper estado.

**Archivos**: `src/recomendaciones/worker/idempotency.py`

**Dep.**: T023

**Criterios de aceptación**:
- [X] Evento ya procesado → ACK sin recomputar
- [X] La marca vive en Redis **y** en Postgres: perder Redis no rompe la idempotencia (INV-2)
- [X] Reprocesar tras expirar la marca produce el mismo resultado, sin duplicar señales (FR-069)
- [X] El TTL de retención es configurable (FR-068)
- [X] **SC-005** — reprocesar el mismo evento produce un top-N idéntico

**Tests**: `tests/integration/test_idempotency.py` — mismo evento 10 veces → 1 recálculo; con la marca expirada, el reproceso converge al mismo estado.

---

### T025 [TDD] — Reintentos con backoff y DLQ

**Descripción**: backoff exponencial, máximo 5 intentos, luego DLQ. Fallo solo en el módulo opuesto
→ se conserva el principal y se reencola solo el opuesto.

**Archivos**: `src/recomendaciones/worker/retry.py`, `dlq.py`

**Dep.**: T023

**Criterios de aceptación**:
- [X] Fallo transitorio → reintento con backoff; máximo configurable (FR-068)
- [X] Agotados los intentos → DLQ con la causa registrada
- [X] Fallo en el módulo opuesto no revierte el módulo principal (FR-067)
- [X] Los mensajes en DLQ conservan el payload íntegro para reproceso manual

**Tests**: `tests/integration/test_retry_dlq.py` — inyectar fallo transitorio → reintenta; fallo permanente → DLQ tras 5; fallo del opuesto → principal persistido.

---

### T026 [TDD] — Manejo de payload inválido sin bloquear la cola

**Descripción**: un mensaje malformado va a DLQ **inmediatamente**, sin reintentos. Reintentar algo
que nunca va a ser válido solo bloquea la cola.

**Archivos**: `src/recomendaciones/worker/dlq.py`

**Dep.**: T025

**Criterios de aceptación**:
- [X] Payload inválido → DLQ sin reintento, con la causa de validación
- [X] El consumo continúa: el mensaje siguiente se procesa normalmente
- [X] Una ráfaga de mensajes inválidos no detiene el procesamiento de los válidos
- [X] El log incluye el `event_id` cuando es extraíble
- [X] **SC-007** — 100 % de los eventos con payload inválido termina en dead-letter con causa registrada

**Tests**: `tests/integration/test_invalid_payload.py` — intercalar 5 inválidos entre 5 válidos: los 5 válidos se procesan, los 5 inválidos están en DLQ, cero reintentos.

---

### T027 [TDD] — Recálculo y propagación cross-module condicional

**Descripción**: ejecutar motor + post-proceso y escribir Redis. Recalcular el módulo opuesto **solo
si** algún tag del ítem pertenece al vocabulario compartido (FR-010a, decisión Q2). La decisión y su
motivo quedan registrados (FR-010c).

**Archivos**: `src/recomendaciones/worker/handler.py`

**Dep.**: T024, T016, T019, **T064** (la señal del evento debe estar persistida antes de recalcular)

**Criterios de aceptación**:
- [X] Ningún tag compartido → **no** recalcula el opuesto (FR-010a)
- [X] La decisión queda registrada con su motivo, auditable (FR-010c)
- [X] Los dos módulos son unidades independientes: sin atomicidad cruzada (FR-067)
- [X] El resultado escrito pasó por el pipeline completo de T016
- [X] **Reconstruye y persiste `user_profiles`** del usuario (los tres alcances) antes de puntuar: es el
      proceso de perfiles, **escritor único** de esa tabla (`data-model.md` §2.5), con la función pura
      de T008. *(Agregado 2026-09-27: ninguna tarea escribía `user_profiles`, que T010 necesita para
      los vecinos.)*
- [X] **Consume también `recompute:requests`** (RD-100) con grupo de consumidores: confirma (`XACK`)
      solo después de escribir el resultado, de modo que una caída a mitad reentrega la solicitud; una
      solicitud de un usuario con supresión en curso se descarta (FR-092a)
- [X] Una solicitud entregada **`recompute_requests_max_deliveries` (5)** veces sin confirmarse se
      confirma y se descarta, incrementando `recompute_requests_dropped_total`; nunca se reentrega
      indefinidamente (RD-111). Se emite `recompute_requests_pending`
- [X] El resultado escrito tiene `min(top_n_max, candidatos)` ítems (T019, RD-102)
- [X] Se registra la métrica `reco_cross_module_propagation_total{propagated}`
- [X] **SC-010**, **SC-016** y **SC-017** — cobertura cross-module, propagación en el 100 % de las
      actividades con tag compartido y 0 % sin él, y registro del motivo en 100 % de los recálculos
      *(SC-016 movido desde T007)*

> En **Fase 1** esta tarea recalcula por cada evento; el umbral de FR-080a llega con T060 (Fase 2).

**Tests**: `tests/integration/test_propagation.py` — ítem con tag compartido → ambos módulos recalculan; ítem sin tag compartido → solo el propio, con motivo registrado.

---

## Milestone 6 — Data Transformer

| ID | Tarea | Dep. | [P] | Est. | Fase |
|---|---|---|---|---|---|
| T028 | Cliente REST autenticado y de solo lectura | T002 | | M | **Fase 1** |
| T029 | Materialización idempotente de usuarios, catálogo y actividad | T028, T003 | | L | **Fase 1** |
| T030 | Vocabulario versionado y **reconciliación de vectores** | T029, T007 | | M | **Fase 1** |
| T031 | Registro de freshness de sincronización | T029 | [P] | S | Fase 2 |
| T032 | Comportamiento ante `api-general` no disponible | T028, T031 | | M | Fase 2 |

> ⚠️ **Este milestone está partido entre fases** (corrección F9, 2026-09-22). T028, T029 y T030 son
> **Fase 1**: sin ellos `item_vectors` queda vacía y la señal content-based —`α = 0,5`— aporta cero
> sin que nada falle. T031 y T032 siguen en **Fase 2**: Fase 1 necesita que la sincronización
> *funcione*, Fase 2 agrega que *sobreviva a que falle*.
>
> La tabla «Asignación de fases (autoritativa)» manda sobre este encabezado de milestone.

> **Hallazgo F5**: T032 perdió su marca `[P]`. Compartía `transformer/pipeline.py` con T031, lo que
> garantizaba conflicto de merge si se tomaban en paralelo. Ahora depende de T031 y su lógica de
> resiliencia vive en un módulo propio.

### T028 [TDD] — Cliente REST autenticado y de solo lectura

**Requisitos**: FR-015, FR-017, FR-040 *(explicitados el 2026-09-28 para la trazabilidad de T048, RD-111)*

**Descripción**: cliente `httpx` hacia `api-general` con la API key interna. **Solo lectura**: el
cliente no expone verbos de mutación.

**Archivos**: `src/recomendaciones/transformer/client.py`

**Dep.**: T002

**Criterios de aceptación**:
- [X] El cliente **no expone** POST/PUT/PATCH/DELETE — restricción estructural, no convención
- [X] Envía la API key interna; timeouts explícitos y configurables
- [X] `INV-4`: no hay conexión directa a la DB de `api-general`
- [X] Los errores HTTP se traducen a errores tipados de T005

**Tests**: `tests/unit/test_transformer_client.py` — la superficie pública no tiene verbos de mutación. `tests/integration/test_no_external_writes.py` — contra un doble, cero requests no-GET.

---

### T029 [TDD] — Materialización idempotente de usuarios, catálogo y actividad

**Descripción**: proyectar usuarios, catálogo y actividad a DB Recomendaciones. Idempotente:
re-ejecutar sobre los mismos datos no duplica ni altera el resultado.

**Archivos**: `src/recomendaciones/transformer/pipeline.py`

**Dep.**: T028, T003

**Criterios de aceptación**:
- [X] Re-ejecutar la sincronización dos veces produce estado idéntico (idempotencia)
- [X] Un ítem sin `age_rating` se materializa con el valor **más restrictivo** (FR-051)
- [X] La actividad conserva `signal_type` y `occurred_at` (FR-062, DEP-1, DEP-2)
- [X] Interrupción a mitad de camino deja estado consistente, no parcial e indistinguible
- [X] **El Data Transformer NO escribe `item_popularity`, `tag_modules` ni `vocab_*`** (DI-13).
      Verificable por los módulos que el pipeline importa, que es la forma que DI-13 propone.
      ⚠️ **Criterio eliminado el 2026-09-22**: esta tarea tenía un criterio sobre el cálculo de
      popularidad. T029 **es** el Data Transformer, de modo que el criterio mandaba hacer
      exactamente lo que DI-13 prohíbe — y la orden de corregirlo estaba en `data-model.md` §9
      desde el 2026-09-10, sin aplicar. No se reformuló a Wilson: el defecto no era la fórmula
      sino la **zona**. Una redacción relajada habría sonado compatible con FR-033a1 y vuelto la
      violación más difícil de ver.
      > **Tercera vez que un derivado se aloja en la zona de proyección**: RD-12 sacó
      > `like_count_window` de `items`, RD-14 sacó `is_shared` de `tags`, y esto. El patrón está
      > anunciado en §1.1 —«la zona proyectada tiende a alojar datos derivados»— y DI-13 existe
      > precisamente para detectarlo
- [X] **El retiro se detecta por dos vías y se aplica por una sola rama** (FR-074, RD-91): señal
      explícita del origen (CR-7) y **ausencia** del ítem en el listado (CR-8). No hay modo
      degradado: Q31 descartó la opción de operar distinto según el origen pueda o no confirmar
      completitud, porque una rama que casi nunca se ejercita es una rama rota cuando hace falta
- [X] **La corrida aborta sin marcar retiro alguno** si no puede confirmar que el listado es
      completo (CR-9), y en particular cuando `sync_volume_delta_ratio < 0,9`. Abortar sin marcar es
      la única conducta segura: un listado truncado que se procesa retira ítems vigentes en masa
- [X] **El retiro es lógico** (FR-073): se cambia `status`, **no** se borra la fila ni sus señales
- [X] **Política de ingesta de usuarios** (`data-model.md` §7.5, §7.6): un usuario sin `birth_date` **o**
      sin `region` válida (ISO 3166-1 alfa-2) **se rechaza** —sin fila ni derivados por default—, se
      registra como violación de contrato con `user_id` y `sync_run_id`, e incrementa
      `contract_violations_total{field="birth_date"}` o `{field="region"}`, **contadores separados**
      con valor esperado 0. La corrida queda `failed` con `failure_reason`
- [X] **Un ítem sin tags se rechaza** (FR-021b, RD-60) y queda registrado como anomalía de contrato,
      **sin bloquear** la ingesta del resto del catálogo
- [X] **Tags sin normalizar** (§7.8, RD-16): se persisten tal cual; nombre vacío → se descarta la
      asignación y se cuenta en `projection_field_anomalies_total{field="tag_name"}`, sin abortar
- [X] **Señales de actividad**: `source = 'sync'`; deduplicación por `origin_interaction_id` con la
      comparación de §7.10 —idénticas: reentrega; distintas: `contract_violations_total{field="origin_interaction_id"}`
      (FR-029e1)—; tras la ingesta se invoca al **resolutor de exclusiones** (T014), que invalida
      `filters:{user_id}` de los usuarios afectados (RD-96)
- [X] Una corrección de `birth_date` (CR-4) rederiva el ordinal y **invalida** los resultados del
      usuario en el mismo acto (DI-2c, FR-080c)
- [X] **Lápida** (FR-091b, DI-29, RD-101): un `user_id` con fila en `user_suppressions` se descarta en la
      ingesta de usuarios y de actividad, aunque el origen lo siga listando; la **ausencia** de un
      usuario en el listado **no** dispara supresión (FR-091a)
- [X] **SC-006** — re-ejecutar una corrida completa del Data Transformer sobre datos sin cambios deja un estado idéntico
- [X] **SC-028** — 100 % de los usuarios sin `birth_date` o sin `region` válida rechazados y contados; 0 materializados con valor por defecto

> *Criterios de ingesta agregados el 2026-09-27: `data-model.md` §7.5–§7.8 y §9 los asignaban a T029
> desde el 2026-09-10, y el backlog solo tenía el de `age_rating`.*

**Tests**: `tests/integration/test_sync_idempotent.py` — doble ejecución → mismo estado; ítem sin rating → valor restrictivo; interrupción simulada → estado consistente; usuario sin `region` → rechazado y contador de `region` en 1 (el de `birth_date` en 0); ítem sin tags → rechazado sin abortar la corrida; misma interacción con otro `signal_type` → violación de contrato, no duplicado silencioso; usuario suprimido todavía presente en el listado → ninguna fila nueva.

---

### T030 [TDD] — Vocabulario versionado y **reconciliación de vectores**

**Descripción**: derivar el vocabulario del catálogo sincronizado como **artefacto versionado
propiedad de este repo** (FR-010e), y **garantizar que todo ítem vigente con tags tenga vector** bajo
la versión activa. Son dos responsabilidades del mismo job, no dos tareas: `data-model.md` ya sitúa
ambas ahí —«tras cada sincronización de catálogo, en el mismo job que vectoriza (T030)»—.

Es el **escritor de `item_vectors`**. T007 aporta la función de vectorización, que es pura y no
escribe; T030 la usa y persiste.

> **Agujero cerrado el 2026-09-22**: el disparador era **solo el cambio de hash del vocabulario**, y
> el hash es función del conjunto de **tags**, no de ítems. Un ítem nuevo cuyos tags ya existen **no
> cambia el hash, no dispara nada y quedaba sin vector de forma permanente** — no era un problema de
> arranque sino de régimen. El poblado inicial sobre un catálogo ya sincronizado era el caso
> particular en que lo que falta es todo.
>
> Importa porque **α = 0,5 es la mitad del score**, y porque la métrica `catalog_unvectorized_ratio`
> alerta por encima del 10 % mandando «escalar al proveedor»: fue pensada para ítems que llegan
> **sin tags**, culpa del origen. Con este agujero habría subido por ítems **con** tags que nadie
> vectorizó, y la alerta habría apuntado a `api-general` por un defecto propio.

**Archivos**: `src/recomendaciones/transformer/vocabulary_sync.py`

**Dep.**: T029, T007

**Criterios de aceptación**:
- [X] El vocabulario se versiona; la versión activa es explícita y consultable
- [X] Regenerar el vocabulario **recalcula todos los vectores afectados antes** de activar la versión (FR-010g)
- [X] Durante la transición nunca se comparan vectores de versiones distintas (FR-010f)
- [X] El criterio de regeneración vive en configuración versionada (FR-010g)
- [X] Un vocabulario desactualizado degrada calidad, **nunca** corrección ni invariantes
- [X] No requiere aprobación de `api-general`: es interno (FR-010e)
- [X] **Reconciliación tras cada sincronización**: todo ítem **vigente**, **con al menos un tag** y
      **sin vector bajo la versión activa** recibe uno. El disparador ya **no** es solo el cambio de
      hash — un ítem nuevo con tags preexistentes no lo altera
- [X] **El arranque desde vacío es el caso degenerado del mismo procedimiento**, no un camino
      aparte: sin versión activa se crea la primera y se vectoriza todo el catálogo vigente. Un
      camino de arranque separado sería código que corre una vez y se pudre sin que nadie lo note
- [X] **Calcula `tag_modules` solo sobre ítems vigentes** (`data-model.md` §2.12, RD-20, DI-15), después
      de aplicar retiros: es el escritor único de esa tabla, de `vocab_versions` y de
      `vocab_version_tags` (DI-13)
- [X] Emite `vector_recompute_lag_seconds` (solo versión activa), `vocab_transition_progress` y
      `catalog_unvectorized_ratio` (§7.9). Tras RD-60 no existen ítems vigentes sin tags, de modo que
      `catalog_unvectorized_ratio` mide **rezago propio de vectorización**, no un defecto del origen
- [X] Es **idempotente**: dos corridas seguidas sin cambios de catálogo no reescriben vectores
- [X] Emite **`declarable_tags_total{module}`**: tags elegibles para declarar por módulo, según
      `tag_modules` sobre ítems vigentes (DEP-10, RD-110). T042 alerta si baja de `declared_tags_min`

> *Corregido el 2026-09-27: un criterio decía que «un ítem vigente sin tags queda sin vector
> deliberadamente» y que la métrica lo señala al proveedor; desde RD-60 ese ítem se rechaza en la
> ingesta (T029). Y faltaba `tag_modules`, que `data-model.md` asigna a este job y de la que depende
> la propagación de T027.*

**Tests**: `tests/integration/test_vocab_transition.py` — durante la transición no existe instante con
vectores mezclados; interrumpir la transición no activa la versión.
`tests/integration/test_vector_reconciliation.py` — **ítem nuevo cuyos tags ya existen** (el caso que
el disparador por hash no veía) obtiene vector tras el sync; arranque sobre catálogo ya sincronizado
y sin versión activa vectoriza todo lo vigente con tags; segunda corrida sin cambios no reescribe nada.
`tests/integration/test_tag_modules.py` — retirar el último ítem de un módulo para un tag lo quita de
ese módulo y deja de propagar (DI-15).

---

### T031 [P] [TDD] — Registro de freshness de sincronización

**Descripción**: poblar `sync_runs` y exponer `catalog_sync_last_success_timestamp` —nombre de
`data-model.md` §7.7; decía `reco_sync_last_success_timestamp`— junto con las métricas del lado de la
sincronización que `data-model.md` §7 define con umbral y responsable.

**Archivos**: `src/recomendaciones/transformer/pipeline.py`, `src/recomendaciones/observability/metrics.py`

**Dep.**: T029

**Criterios de aceptación**:
- [X] Cada corrida registra inicio, fin, estado y volumen
- [X] La métrica de freshness refleja el **último éxito**, no el último intento
- [X] Una corrida fallida no actualiza el timestamp de éxito
- [X] La antigüedad es consultable operativamente sin entrar a la DB
- [X] **SC-014** — la antigüedad de la última sincronización exitosa está disponible como métrica
- [X] Emite, con los nombres de `data-model.md` §7: `sync_volume_delta_ratio{entity}`,
      `catalog_unrated_ratio`, `catalog_retired_total`, `projection_field_anomalies_total{field}`,
      `contract_violations_total{field}` (`birth_date`, `region`, `origin_interaction_id`),
      `signal_ingest_lag_seconds{source}`, `signal_duplicate_rejections_total{source}` y
      `exclusion_resolve_lag_seconds`. *(Agregado 2026-09-27: el DoD exigía estas métricas y ninguna
      tarea las emitía.)*

**Tests**: `tests/integration/test_freshness.py` — corrida fallida no mueve la métrica; corrida exitosa sí.

---

### T032 [TDD] — Comportamiento ante `api-general` no disponible

**Requisitos**: FR-019, FR-040 *(explicitados el 2026-09-28 para la trazabilidad de T048, RD-111)*

**Descripción**: la caída de `api-general` degrada la **frescura**, no la disponibilidad. El servicio
sigue sirviendo con los datos materializados.

**Archivos**: `src/recomendaciones/transformer/resilience.py` (módulo propio — **hallazgo F5**: ya no
comparte `pipeline.py` con T031)

**Dep.**: T028, T031

**Criterios de aceptación**:
- [X] `api-general` caído → la sincronización falla de forma limpia y registrada
- [X] La API de lectura **sigue respondiendo** con los datos ya materializados
- [X] No se corrompe ni se vacía el estado materializado
- [ ] Reintento con backoff; se alerta si la freshness supera el umbral

**Tests**: `tests/integration/test_api_general_down.py` — con el doble caído, la lectura sigue en 200 y el estado materializado queda intacto.

---

## Milestone 7 — API de lectura

> Todo este milestone es **Fase 1**. T038 se adelantó desde Fase 2 (hallazgo F2).

| ID | Tarea | Dep. | [P] | Est. |
|---|---|---|---|---|
| T033 | Endpoint de lectura del top-N | T020, T005, **T049** | | M |
| T034 | Autenticación por API key interna y no alcanzabilidad desde frontends | T002, T033 | | M |
| T035 | Errores tipados y contrato estable | T033, T005 | | S |
| ~~T036~~ | ~~Registro de feedback y emisión del evento de recálculo~~ — **retirada** (RD-95), reemplazada por T064 | — | | — |
| T038 | Batch de top-N de respaldo | T012, T015, T003, T063 | [P] | M |
| T037 | Filtrado de salida sobre el respaldo (acotado) | T033, T013, T014, **T038** | | M |

### T033 [TDD] — Endpoint de lectura del top-N

**Descripción**: `GET /internal/v1/recommendations/{user_id}?module=…&top_n=…[&prefer=stale]`
cache-first, según el contrato de T049. **Sin paginación** (FR-005, RD-107): `top_n` es el único
parámetro de tamaño y la respuesta trae el resultado completo.

> *Decidido el 2026-09-27 (RD-107): el título decía «con paginación» y esta tarea tenía la forma de la
> paginación pendiente de decisión. Se eliminan `limit`, `cursor` y `next_cursor`.*

**Archivos**: `src/recomendaciones/api/routes/recommendations.py`, `schemas.py`

**Dep.**: T020, T005, **T049** (el contrato se define antes que el endpoint, Principio II)

**Criterios de aceptación**:
- [X] `module` es **obligatorio** y pertenece a `peliculas | juegos`; otro valor → `422` (FR-001, US1-3).
      *(El endpoint no tenía parámetro de módulo; el plan original lo declaraba como `?module=`.)*
- [X] La respuesta incluye `result_type`, `computed_at`, `config_version`, `items[]` (con posición y
      score, FR-004) y `stale_available` (FR-056a, T062). **No** incluye `next_cursor`
- [X] El tamaño de resultado solicitado se valida en **`[top_n_min, top_n_max]` = `[10, 50]`**: debajo
      del mínimo **y** encima del máximo → `422` (FR-005, FR-006a). *(Solo se validaba el máximo.)*
- [X] `limit` o `cursor` en la solicitud → `422`: no son parámetros del contrato (FR-005)
- [X] `INV-1`: no importa `engine/`, no consulta Postgres en el camino normal —solo ante miss de
      `filters:`/`retired:`— (verificado por T006)
- [X] `config_version` de la respuesta permite trazar con qué configuración se generó
- [X] **SC-009** — 0 % de los requests de lectura ejecuta scoring, similitud o diversificación. Lo
      verifica `tests/integration/test_no_heavy_computation` de esta tarea, apoyado en el test
      estructural de T006. La guarda de vigencia de T037 **no** cuenta como excepción: es diferencia
      de conjuntos, no cómputo de recomendaciones (RD-8)

**Tests**: `tests/contract/test_read_endpoint.py` — la respuesta valida contra el OpenAPI de T049; tamaño 9 → 422, 10 → 200, 50 → 200, 51 → 422; sin `module` o con módulo inválido → 422. `tests/integration/test_no_heavy_compute.py` — espía de conexiones: cero queries a Postgres en el camino normal (con `filters:` poblado).

---

### T034 [TDD] — Autenticación por API key interna y no alcanzabilidad desde frontends

**Descripción**: exigir `X-Internal-API-Key` y garantizar que FR-008 sea **verificable** (FR-060): sin
rutas públicas declaradas y restricción de red auditable.

**Archivos**: `src/recomendaciones/api/deps.py`, `main.py`

**Dep.**: T002, T033

**Criterios de aceptación**:
- [X] Sin API key → `401`; key inválida → `401` con el **mismo** cuerpo (no es oráculo)
- [X] Key de otro entorno → `401` (FR-059)
- [X] La aplicación no declara ninguna ruta pública fuera de health (FR-060)
- [X] La restricción de red está documentada y es auditable automáticamente
- [X] **SC-012** (mitad de frontends) — 0 rutas de acceso alcanzables desde un frontend

**Tests**: `tests/contract/test_auth.py` — matriz de casos de key; test que enumera rutas y falla si alguna no exige autenticación (salvo health).

---

### T035 [TDD] — Errores tipados y contrato estable

**Descripción**: traducir la jerarquía de T005 a códigos HTTP estables. El versionado del endpoint y
la definición de cambio breaking siguen FR-058.

**Archivos**: `src/recomendaciones/api/errors.py`

**Dep.**: T033, T005

**Criterios de aceptación**:
- [X] `401` sin auth, `422` params inválidos, `503` + `Retry-After` con Redis caído
- [X] Ninguna excepción no manejada escapa como `500` con stack trace
- [X] Los cuerpos de error tienen forma estable y documentada
- [X] Ningún mensaje de error revela detalles internos (rutas, versiones de librerías, SQL)

**Tests**: `tests/contract/test_errors.py` — cada error produce su código; ningún cuerpo contiene rastros internos.

---

### ~~T036 — Registro de feedback y emisión del evento de recálculo~~ — RETIRADA (2026-09-27)

**Estado**: **retirada y no reasignable**, igual que `FR-052`, `DEP-3` y `FR-070a`…`FR-070e`. La
reemplaza **T064**. La incidencia #36 debe cerrarse como «no se hará», no reutilizarse.

**Por qué**: la tarea creaba un endpoint de feedback en esta API que persistía la señal y **publicaba**
`recomendacion.actualizar`. Choca con tres principios no negociables de la constitución: la actividad
es dato de `api-general` y solo entra por REST o por evento (I, IV); ese evento lo publica
`api-general`, no este repositorio (II); y la API es de solo lectura (III). Además contradecía FR-089 y
RD-75, que fijan la declaración como **única** excepción de escritura. Era un resto de la Fase 1 del
plan del 2026-09-07 que el plan regenerado ya no contenía (RD-95).

**Qué se conserva**: lo valioso de la tarea —que una reacción del usuario no deje el top-N
silenciosamente desactualizado y que la exclusión sea efectiva en la siguiente lectura— pasa a T064,
por la vía correcta: `api-general` registra la actividad y publica el evento; el worker la persiste.

---

### T037 [TDD] — Filtrado de salida sobre el respaldo (acotado)

**Descripción**: aplicar edad y exclusión sobre el respaldo al servir (FR-033d). **Acotado a
pertenencia y comparación** sobre una lista ya ordenada y de tamaño acotado: sin similitud, sin
recomputación de scores, sin reordenamiento, sin diversificación.

**Archivos**: `src/recomendaciones/api/services/read_service.py`

**Dep.**: T033, T013, T014, **T038** (hallazgo F4 — sin el batch no existe el respaldo que esta
tarea filtra, y su test no sería significativo)

**Criterios de aceptación**:
- [X] Se aplican edad y exclusión sobre el respaldo antes de responder (FR-036, FR-049)
- [X] **No** hay cálculo de similitud, recomputación, reordenamiento ni diversificación (FR-033d)
- [X] El costo es lineal sobre una lista acotada por `top_n_max`
- [X] Respaldo que queda vacío tras filtrar → `empty_no_candidates` (FR-056)
- [X] Conjunto de exclusión no disponible → se rechaza, no se sirve sin filtrar (FR-050)
- [X] **Guarda de vigencia** (§4.4 punto 3, FR-072): diferencia contra el set `retired:{module}`
      antes de responder. Es el tercero de los tres puntos donde se aplica la regla, y el único que
      alcanza a un resultado **ya precomputado**: sin él, un ítem retirado se sigue sirviendo desde
      caché durante toda la vigencia de la entrada
- [X] La guarda es **diferencia de conjuntos sobre ≤ `top_n_max`**, no cálculo: FR-003 prohíbe
      computar recomendaciones, no ejecutar guardas de corrección (RD-8)
- [X] **Lista reducida tras las guardas → se sirve tal cual** (FR-075), con el estado que
      corresponda a su frescura. **No** se rellena con sustitutos: reponer exige seleccionar
      candidatos, que es cómputo prohibido. Solo la lista **vacía** es `empty_no_candidates`
- [X] **SC-026** y **SC-027** — 0 % de respaldos servidos viola el filtro de edad o de exclusión, y
      100 % se marca como no personalizado *(había una línea duplicada de SC-026)*

**Tests**: `tests/invariants/test_fallback_filtering.py` — menor de edad nunca recibe contenido adulto vía respaldo. `tests/unit/test_fallback_bounded.py` — el módulo no importa `engine/` ni funciones de similitud.

---

### T038 [P] [TDD] — Batch de top-N de respaldo

**Descripción**: **consumidora** de `item_popularity`. Construye el conjunto de respaldo por módulo
leyendo lo que **T063 ya calculó**, lo diversifica por MMR (decisión Q5) y lo publica en
`fallback:v{cfg}:{module}`. Global por módulo, nunca por usuario.

Esta tarea **no calcula popularidad**: la lee. El reparto quedó explícito el 2026-09-22 —T063
produce, T038 consume—, tal como `data-model.md` §2.11 ya lo declaraba: «`popularity_score` →
Consumidores: Batch de respaldo T038».

**Archivos**: `src/recomendaciones/batch/fallback.py`

**Dep.**: T012, T015, T003, **T063** *(agregada el 2026-09-22: sin la productora, `item_popularity` está vacía y este batch no tiene qué leer)*

> **Nota de fase (hallazgo F2, actualizada el 2026-09-22)**: adelantada a Fase 1 porque sin el batch
> de respaldo el estado `fallback` de FR-056 es inalcanzable y T020 no puede testearse completa.
>
> Su dependencia original de T029 (Fase 2) se sustituyó por T003 con el argumento de que «la
> popularidad se computa sobre `user_signals`». **Ese argumento caducó**: era válido cuando esta
> tarea calculaba la popularidad, y ahora la calcula T063. La sustitución **sigue siendo correcta**
> —T029 no es condición para que el respaldo exista—, pero el motivo real es otro: el respaldo
> depende de `item_popularity`, que puebla **T063**, y por eso T063 se movió a Fase 1 con esta.

**Criterios de aceptación**:
- [X] **Lee `item_popularity` bajo la `config_version` activa**, vía `idx_popularity_ranking`
      `(config_version, popularity_score DESC)`
- [X] **Ordena por `popularity_score`**, no por `like_count` (RD-12): ordenar por el conteo bruto
      pondría arriba a los ítems con mucho volumen y mala conversión
- [X] Reúne con `items` filtrando `status = 'available'` y agrupando por `module`. Es el costo
      declarado de RD-12, y **T050 lo perfila** en vez de asumirlo resuelto
- [X] **El respaldo NO lleva cuota de novedades** (RD-102). ~~La cuota de ítems nuevos reserva
      `floor(top_n × fallback_new_item_quota_ratio)` posiciones~~: el criterio **se trasladó a T065**,
      porque el emergente se ordena por afinidad con el perfil del usuario (FR-033a6f1) y este batch es
      global (FR-033c); componerlos al servir sería reordenar, que FR-033d prohíbe. *(El criterio había
      llegado acá desde T063 el 2026-09-22 y quedó bloqueado por ese conflicto hasta RD-102.)*
- [X] **El batch se construye únicamente sobre ítems vigentes** (FR-033a1, FR-072, §4.4 punto 2):
      reunión con `item_popularity` bajo `WHERE status = 'available'` (RD-12). El respaldo es lo que
      recibe exactamente la población sin resultado propio; contaminarlo con retirados afecta a
      quien menos defensa tiene
- [X] Se computa sobre ventana temporal configurable, no sobre histórico completo (FR-033a1)
- [X] Publica **`min(fallback_stored_size, candidatos)`** ítems (100): margen para el filtrado por
      usuario de FR-033f (`data-model.md` §3.2, RD-111)
- [X] El resultado pasa por MMR: no se concentra en el género dominante (FR-033b)
- [X] Es global por módulo, **no** personaliza por usuario (FR-033c)
- [X] **Sin likes, el respaldo existe igual** (FR-033a2, RD-106): todos los puntajes son 0 y el orden lo da el desempate determinista (FR-070); queda vacío solo si no hay ítems vigentes del módulo. *(Decía «sin likes suficientes → respaldo vacío», sin umbral definido y en conflicto con SC-024.)*
- [X] El respaldo respeta el **tope de cluster** de FR-071a (SC-025)
- [X] Se persiste **solo en Redis** (`fallback:v{cfg}:{module}`); ante pérdida se **recomputa** ejecutando este batch (`data-model.md` §3.3: «no existe una tabla de respaldo»). *(Decía «Redis y tabla (D8)»: D8 era una recomendación del plan del 2026-09-07 que el modelo de datos no adoptó — ninguna de las 16 tablas es de respaldo.)*
- [X] **SC-024** y **SC-025** — 100 % de los usuarios declarados sin top-N personalizado vigente recibe respaldo no vacío en ese módulo, y el respaldo cumple el mismo umbral de diversidad de SC-011

**Tests**: `tests/integration/test_fallback_batch.py` — diversidad medida supera la del top-N sin MMR; sistema sin likes → respaldo **no vacío**, ordenado por desempate, idéntico en dos corridas; módulo sin
ítems vigentes → respaldo vacío.

---

## Milestone 8 — Observabilidad y operación

> Incluye **T046** (runbook), movida desde el Milestone 10. La documentación operativa se escribe
> mientras el sistema todavía sorprende, no de memoria durante el cierre.

| ID | Tarea | Dep. | [P] | Est. |
|---|---|---|---|---|
| T039 | Métricas Prometheus | T033, T027, T031 | | M |
| T040 | Logging estructurado con correlation ID | T033, T023 | [P] | M |
| T041 | Health, readiness y liveness por servicio | T033, T023, T028 | [P] | M |
| T042 | Alertas operativas (con prueba de disparo) | T039 | | M |
| T046 | Documentación operativa mínima | T042, T022 | | M |

### T039 [TDD] — Métricas Prometheus

**Requisitos**: FR-042, FR-043, FR-044, FR-025d, FR-095a *(explicitados el 2026-09-28 para la trazabilidad de T048, RD-111)*

**Archivos**: `src/recomendaciones/observability/metrics.py`

**Dep.**: T033, T027, T031

**Criterios de aceptación**:
- [X] `reco_cache_hits_total{result_type}` discrimina los cinco estados
- [X] `reco_request_duration_seconds` es histograma por endpoint
- [X] `reco_recompute_total{status,module}` y `reco_recompute_duration_seconds`
- [X] `reco_dlq_messages_total{reason}` y `reco_queue_depth`
- [X] `catalog_sync_last_success_timestamp` (freshness, nombre de `data-model.md` §7.7) y `reco_sync_duration_seconds`
- [X] `reco_cross_module_propagation_total{propagated}`
- [X] `reco_active_config_version` como gauge etiquetado
- [X] El registro de métricas **declara** (nombre, tipo, etiquetas) las agregadas desde RD-100…RD-111;
      cada una la **emite** la tarea que produce el hecho, en su fase: `recompute_requests_pending` y
      `recompute_requests_dropped_total` (T027), `diversity_cap_relaxed_total` (T015, FR-071a),
      `declarable_tags_total{module}` (T030, DEP-10), `fallback_new_item_share` (T065, FR-033a8) y
      `suppressions_unverified_total` (T059, FR-095a, valor esperado 0). Esta tarea no espera a las de
      fases posteriores: el nombre declarado sin emisor todavía es el estado esperado hasta que llegan
- [X] Ninguna etiqueta contiene `user_id` ni datos personales (cardinalidad y privacidad)

**Tests**: `tests/integration/test_metrics.py` — cada métrica se emite tras su operación; ninguna etiqueta es de alta cardinalidad.

---

### T040 [P] [TDD] — Logging estructurado con correlation ID

**Archivos**: `src/recomendaciones/observability/logging.py`

**Dep.**: T033, T023

**Criterios de aceptación**:
- [ ] Logs en JSON con campos estables
- [ ] Correlation ID se propaga desde la request y **sobrevive** al salto asíncrono API → broker → worker
- [ ] Ningún log contiene la API key ni datos personales innecesarios
- [ ] Cada decisión de propagación cross-module se registra con su motivo (FR-010c)
- [ ] Cada mensaje a DLQ se registra con su causa

**Tests**: `tests/integration/test_correlation.py` — un ID emitido en la API aparece en el log del worker que procesa el evento derivado.

---

### T041 [P] [TDD] — Health, readiness y liveness por servicio

**Archivos**: `src/recomendaciones/observability/health.py`, `src/recomendaciones/api/routes/health.py`

**Dep.**: T033, T023, T028

**Criterios de aceptación**:
- [ ] `liveness` no depende de dependencias externas — solo indica que el proceso vive
- [ ] `readiness` verifica Redis y Postgres; Redis caído → not ready
- [ ] `/health` expone `config_version` activa (trazabilidad de Q4) — **SC-023** *(movido desde T049)*
- [ ] Ningún endpoint de salud expone secretos ni detalles internos
- [ ] Los tres entrypoints tienen su propio health

**Tests**: `tests/integration/test_health.py` — con Redis caído readiness falla y liveness no; `/health` no filtra secretos.

---

### T042 [TDD] — Alertas operativas

**Descripción**: definir las alertas y **demostrar que disparan**. Una alerta configurada pero nunca
verificada da sensación de cobertura sin darla: el modo de fallo típico no es que falte la alerta,
sino que su umbral esté mal y jamás se active.

**Archivos**: `ops/alerts.yaml`, `docs/runbook.md`, `tests/integration/test_alerts.py`

**Dep.**: T039

**Criterios de aceptación**:
- [ ] Alerta por freshness de sincronización por encima del umbral
- [ ] Alerta por crecimiento sostenido de DLQ y de profundidad de cola
- [ ] Alerta por tasa de `503` (Redis caído)
- [ ] Alerta por caída abrupta de hit rate
- [ ] Alerta por `config_version` inconsistente entre instancias
- [ ] **Liveness del job de refresco etario**: `age_refresh_last_success_timestamp` por encima de su
      umbral. **Reemplaza a la alerta de `age_ordinal_staleness_seconds`**, eliminada por
      `data-model.md` §7.6 — que la califica como la corrección más importante de aquella auditoría:
      la métrica de *staleness* **no dispara cuando el job está muerto**, que es precisamente el único
      caso en que la alerta hace falta. Medía el desfasaje de lo que el job procesó, no el hecho de que
      hubiera dejado de procesar
- [ ] Alerta por `contract_violations_total{field="birth_date"} > 0` y
      `contract_violations_total{field="region"} > 0` — contadores **separados** (§7.5, RD-85)
- [ ] Alerta por supresiones sin constancia registrada, **valor esperado 0** (FR-095a, RD-83)
- [ ] **Toda métrica de `data-model.md` §4.4, §7.5.1, §7.7, §7.9, §7.10, §7.11 y §7.12 que declara
      umbral, acción y responsable tiene su alerta** con ese umbral —entre otras
      `retired_set_size`, `catalog_unrated_ratio`, `vector_recompute_lag_seconds`,
      `signal_ingest_lag_seconds`, `signals_purge_deferred_total`, `exclusion_resolve_lag_seconds`,
      `sync_volume_delta_ratio`, `user_deletion_residual_keys_total` y
      `contract_violations_total{field="origin_interaction_id"}`—. Los umbrales no se copian acá: la
      fuente es el modelo de datos. *(Agregado 2026-09-27: la lista de esta tarea cubría una parte.)*
- [ ] **`exclusions_orphaned_permanent_total` NO tiene alerta**: FR-068d1 la declara informativa y **sin umbral**.
      Configurarle una contradiría el requisito
- [ ] Alerta **`declarable_tags_total{module} < declared_tags_min`** (DEP-10, RD-110): con menos tags
      elegibles que el mínimo, el módulo queda no disponible para todo usuario nuevo
- [ ] Cada alerta tiene entrada en el runbook con primer paso de diagnóstico
- [ ] **Cada alerta se probó induciendo su condición** en entorno de prueba, no solo por revisión
- [ ] Ninguna alerta permanece activa tras normalizarse la condición (no se queda pegada)

**Tests**: `tests/integration/test_alerts.py` (testcontainers, reutiliza la infraestructura de T041) —
detener Redis dispara la alerta de `503`; congelar la sincronización dispara la de freshness; inyectar
mensajes a DLQ dispara la suya; al restablecer cada condición, la alerta se apaga.

**Revisión humana (no automatizable)**: la **justificación del umbral** de cada alerta. El valor
elegido debe estar argumentado en `ops/alerts.yaml`; un umbral sin justificación es deuda operativa.

---

### T046 — Documentación operativa mínima

**Descripción**: runbook y documentación de arquitectura. **Movida desde el Milestone 10 a Fase 2**:
se escribe mientras el sistema todavía sorprende, no de memoria dos meses después. El criterio "un
ingeniero sin contexto puede seguirlo" no se declara: se **demuestra** con una ejecución real.

**Archivos**: `docs/runbook.md`, `docs/architecture.md`, `docs/validation/runbook-dry-run.md`, `README.md`

**Dep.**: T042 (alertas ya probadas), T022 (procedimiento de reconstrucción existente)

**Criterios de aceptación**:
- [ ] Runbook: cómo diagnosticar cada alerta de T042
- [ ] Procedimiento de reconstrucción tras pérdida de Redis (T022)
- [ ] Procedimiento de cambio de `config_version` y de regeneración de vocabulario
- [ ] Procedimiento de reproceso desde DLQ
- [ ] **Ejecución de prueba realizada** del procedimiento de reconstrucción por alguien ajeno a la
      feature, con registro de cada punto donde se trabó o tuvo que preguntar
- [ ] **Los puntos registrados fueron corregidos** en el runbook antes de cerrar la tarea
- [ ] El registro queda versionado en `docs/validation/runbook-dry-run.md` con fecha y ejecutor

**Tests**: entregable verificable — `docs/validation/runbook-dry-run.md` existe, está fechado, nombra
al ejecutor y cada bloqueo registrado tiene su corrección enlazada. Se eligió el procedimiento de
**pérdida total de Redis** por ser el más caro de improvisar bajo incidente y el que más piezas
involucra.

---

## Milestone 9 — Testing y verificación

| ID | Tarea | Fase | Dep. | [P] | Est. |
|---|---|---|---|---|---|
| T049 | Definir `contracts/` primero (OpenAPI + JSON Schema) | **1** | T005 | | M |
| T043 | Contract testing contra `api-general` como gate de CI | 3 | T049 | | M |
| T044 | Suite de casos críticos obligatorios | 3 | T017, T027, T032, T038 | | L |
| T045 | Pipeline de CI con gates bloqueantes | 3 | T017, T043, T044 | | M |
| T050 | Pruebas de carga y verificación de SC-001 | 3 | T033, T038 | [P] | M |

### T049 — Definir `contracts/` primero (OpenAPI + JSON Schema)

**Descripción**: definir los contratos **antes** de implementarlos y publicarlos en `api-general`, que
es su custodio. **Hallazgo F6**: el plan los referenciaba pero nadie los generaba. **Corrección del
2026-09-27**: esta tarea dependía de T033 y T023 y generaba el OpenAPI «desde el código», es decir,
implementaba primero y documentaba después — exactamente lo que el Principio II prohíbe («se define
primero en la documentación de `api-general` y recién después se implementa»). Pasa a **Fase 1**,
antes de T023, T033, T053 y T062, que ahora dependen de ella. Este repositorio **redacta** la
propuesta —tiene prioridad de definición (RD-47)—, pero el contrato vigente es el publicado allá.

**Archivos**: `specs/001-recomendaciones-precomputadas/contracts/recomendaciones-api.openapi.yaml`
(lectura **y** declaración), `contracts/recomendacion-actualizar.schema.json`, `contracts/README.md`

**Dep.**: T005 (tipos de dominio y `result_type`)

**Criterios de aceptación**:
- [X] El OpenAPI describe el endpoint de lectura —con `module` obligatorio, el tamaño de resultado en
      `[10, 50]`, los cinco `result_type` (FR-056), la señal de FR-056a y los errores de T035 (`401`,
      `422`, `503`)— y el **endpoint de declaración** (FR-089), incluido el rechazo por módulo sin
      declaración (FR-088) como error de precondición y **no** como sexto estado
- [X] `recomendacion-actualizar.schema.json` declara como requeridos los **siete** campos mínimos de
      FR-061, incluido `origin_interaction_id`
- [ ] `usuario-eliminado.schema.json` (CR-19, DEP-12) declara como requeridos el identificador único de
      evento, el identificador del usuario y la marca temporal, y se publica en `api-general` **antes** de
      implementar T058 (Principio II, RD-111)
- [X] `contracts/README.md` declara explícitamente que los contratos son **custodiados por
      `api-general`** y que estas copias son derivadas (Principio II) — no son fuente de verdad
- [ ] Existe el PR o documento en `api-general` que publica los contratos, **enlazado** desde el
      README, y la conformidad de los consumidores registrada (Principio II; Flujo de Desarrollo de la
      constitución) — **antes** de mergear T023, T033 y T053
- [ ] Cada copia derivada registra la versión del contrato origen y su fecha de sincronización
- [X] El OpenAPI que la aplicación **genera** se compara contra el contrato publicado: la
      implementación se ajusta al contrato, nunca el contrato a la implementación

> *SC-023 (versión de configuración consultable) estaba atribuido acá; lo verifica T041 (`/health`).*

**Tests**: `tests/contract/test_openapi_conformance.py` — el OpenAPI que genera la aplicación es
compatible con el contrato publicado; falla si una ruta, un campo requerido o un código de estado
divergen.

---

### T050 [P] — Pruebas de carga y verificación de SC-001

**Descripción**: verificar SC-001 — la latencia de lectura se mantiene en **p95 ≤ 50 ms**, medida en el
servicio (RD-105), con el catálogo a 10×. **Hallazgo F7**: era el único Success Criterion sin tarea asignada.

**Archivos**: `tests/performance/test_read_latency.py`, `tests/performance/fixtures/catalog_10x.py`,
`docs/validation/performance-report.md`

**Dep.**: T033, T038

**Criterios de aceptación**:
- [ ] Existe un generador reproducible de catálogo a 1× (**10 000 ítems por módulo**, línea base de
      SC-001, RD-111), 10× (100 000) y volumen de usuarios equivalente
- [ ] La latencia de lectura a 10× permanece en **p95 ≤ 50 ms** (SC-001, RD-105) sobre el hardware
      declarado en el reporte
- [ ] Se mide con caché **poblada** y con caché **fría**, y ambos escenarios se reportan por separado
- [ ] Se verifica que la latencia no depende del tamaño del catálogo — si dependiera, habría cómputo
      en el request path y sería violación de INV-1
- [ ] El resultado queda versionado en `docs/validation/performance-report.md` con la configuración
      de hardware usada
- [ ] **No es gate bloqueante de CI** (sería demasiado lento): corre bajo demanda y antes de release

**Tests**: es la tarea de test. La aserción clave es la **independencia respecto del tamaño del
catálogo**, no el valor absoluto de latencia, que depende del hardware.

---

### T043 — Contract testing contra `api-general` como gate de CI

**Descripción**: validar el payload consumido contra el JSON Schema de `api-general` y la respuesta
propia contra el OpenAPI publicado. Detecta el drift de contrato **antes** de producción.

**Archivos**: `tests/contract/`

**Dep.**: T049 (los artefactos de contrato deben existir antes de validarlos)

**Criterios de aceptación**:
- [ ] **Cada** evento consumido se valida contra su schema oficial de `api-general`:
      `recomendacion.actualizar` y la **baja de cuenta** (CR-19, RD-111)
- [ ] La respuesta de lectura se valida contra el OpenAPI publicado
- [ ] Existe un test que **falla si un campo requerido desaparece** del contrato
- [ ] Cubre las dependencias externas **vigentes**: DEP-1, DEP-2, DEP-5…DEP-11. *(Decía «DEP-1..DEP-6», que incluía la vacante DEP-3 y la resuelta DEP-4 y omitía DEP-7…DEP-11)*
- [ ] Es gate bloqueante: contract test roto = no hay merge (Principio VI)
- [ ] **SC-013** — 100 % de los endpoints expuestos y del evento consumido pasa la validación de contrato

**Tests**: es la tarea de test. Verificación: eliminar `signal_type` del schema del doble debe hacerla fallar.

---

### T044 — Suite de casos críticos obligatorios

**Descripción**: los escenarios críticos que `plan.md` §5 exige, más los que introdujo la declaración
de gustos. Ninguno es opcional. *(Decía «los nueve que el plan declara»; la lista vive acá.)*

**Archivos**: `tests/integration/test_critical_scenarios.py`

**Dep.**: T017, T027, T032, T038

**Criterios de aceptación** — un test por escenario, cada uno con aserción explícita:
- [ ] **Menor de edad** → cero contenido no apto en los cinco `result_type`
- [ ] **Exclusión estricta** → cero ítems excluidos en cualquier respuesta
- [ ] **Usuario sin declaración en el módulo** → rechazo por precondición, sin sexto estado (FR-088)
- [ ] **Usuario recién declarado, sin top-N calculado** → respaldo diversificado marcado como no
      personalizado, o `empty_no_candidates` si no hay datos; tras el recálculo, personalizado (US4-2, US4-5)
- [ ] **Cold start cruzado** → actividad solo en películas **y declaración en juegos** produce juegos
      no triviales (SC-010)
- [ ] **Cache miss** → estado correcto por precedencia + una sola señal de recálculo
- [ ] **Evento duplicado** → un solo recálculo
- [ ] **Payload inválido** → DLQ sin bloquear la cola
- [ ] **Catálogo sin candidatos** → vacío explícito, nunca relleno con no aptos
- [ ] **Dependencia externa caída** → Redis: 503 sin fallback a DB; broker: la lectura sigue; `api-general`: se degrada la frescura, no la disponibilidad
- [ ] **SC-019** y **SC-020** — un dislike reduce de forma medible el score de los ítems que comparten sus tags, y un like posterior revierte el efecto

**Tests**: es la tarea de test. Cada escenario debe ser identificable por nombre en el reporte de CI.

---

### T045 — Pipeline de CI con gates bloqueantes

**Requisitos**: FR-048, FR-055 (Principio VI) *(explicitados el 2026-09-28 para la trazabilidad de T048, RD-111)*

**Archivos**: `.github/workflows/ci.yml`

**Dep.**: T017, T043, T044

**Criterios de aceptación**:
- [ ] Gates bloqueantes: invariantes (T017), contract (T043), arquitectura (T006), críticos (T044)
- [ ] Los tests de integración corren con testcontainers reales, no mocks
- [ ] La cobertura de `engine/` y `postprocess` es reportada; caída bajo el umbral bloquea
- [ ] El pipeline falla si `v1.yaml` no valida contra el loader
- [ ] **Test de mutación** sobre `engine/postprocess.py`: si una mutación del filtro de edad o de
      exclusión sobrevive, el pipeline falla. Es la verificación de que los tests de T017 tienen poder
      de detección real y no solo cobertura de líneas
- [ ] Ningún gate puede saltarse con un flag desde el PR

**Tests**: verificación: un PR que rompa un invariante no puede mergearse.

---

## Milestone 10 — Cierre

| ID | Tarea | Dep. | [P] | Est. |
|---|---|---|---|---|
| T047 | Documento de campos requeridos a `api-general` | T043 | [P] | S |
| T048 | Validación final contra el checklist y DoD | T045, T046, T047, T050 | | M |

> **T046 se movió al Milestone 8 (Fase 2)**. Un runbook escrito mientras el sistema todavía sorprende
> es sustancialmente mejor que uno escrito de memoria dos meses después. Ver T046 arriba.


### T047 [P] — Documento de campos requeridos a `api-general`

**Descripción**: el documento único que exige FR-063, índice de **DEP-1…DEP-12** y de **CR-1…CR-19**.
**No sustituye** la documentación oficial de `api-general` (Principio II): es la lista de lo que este
repo necesita.

**Archivos**: `docs/contracts/required-fields.md`

**Dep.**: T043

**Criterios de aceptación**:
- [ ] Enumera cada campo requerido, su FR asociado y el impacto de su ausencia
- [ ] Cubre las **10 dependencias vigentes** *(eran nueve hasta DEP-12, RD-101)*: DEP-1, DEP-2, DEP-5,
      DEP-6, DEP-7, DEP-8, DEP-9, DEP-10, DEP-11, DEP-12 — con DEP-8 exigido **también en el evento** (FR-061). **DEP-4** se marca como **resuelta internamente** (la popularidad se deriva localmente) y
      **DEP-3** como **vacante a propósito**: el identificador fue retirado y **no se reasigna**
      > La versión anterior de este criterio citaba **DEP-3 como si existiera** y se detenía en DEP-6,
      > ignorando las cinco posteriores.
- [ ] Cubre **CR-1…CR-19**, marcando **CR-13 y CR-14 como retiradas** (RD-50); CR-19 y DEP-12 son el
      evento de baja de cuenta
- [ ] Registra **FR-079a** (formulario de alta) como expectativa externa sin tarea en este repo: la
      cumple la aplicación web y aquí solo se verifica su efecto (rechazo en la ingesta, SC-028)
- [ ] Señala cuál es la dependencia de mayor severidad y por qué: **DEP-10** es la única cuyo
      incumplimiento deja al sistema **sin ningún usuario atendible**, por encadenamiento con FR-088
- [ ] Declara explícitamente que la fuente de verdad del contrato es `api-general`
- [ ] Está enlazado desde el README y desde los contract tests

**Tests**: test que falla si el documento no menciona todos los campos que los contract tests validan.

---

### T048 — Validación final contra el checklist y DoD

**Requisitos**: trazabilidad de todo FR y SC; Definition of Done *(explicitados el 2026-09-28 para la trazabilidad de T048, RD-111)*

**Descripción**: producir la **matriz de trazabilidad ítem → evidencia**: cada uno de los **76** ítems
de los **dos** checklists (30 de `requirements-contracts.md` y 46 de
`requirements-clarify-2026-09-14.md`; decía «los 30 ítems del checklist», anterior al segundo) mapeado
al test o archivo concreto que hoy lo sostiene. No es burocracia de cierre: es
lo que permite, dentro de seis meses, saber si un refactor rompió un invariante acordado sin tener
que reconstruir el razonamiento desde cero.

**Archivos**: `docs/validation/traceability-matrix.md`, `tests/contract/test_traceability.py`

**Dep.**: T045, T046, T047, T050

**Criterios de aceptación**:
- [ ] La matriz cubre los 76 ítems de ambos checklists, cada uno con su evidencia: ruta de test, ruta de
      archivo o commit que lo sostiene
- [ ] Cada evidencia referenciada **existe** y está en verde — verificado automáticamente
- [ ] **Un ítem sin evidencia concreta NO se marca.** Prohibido dar por bueno lo que "obviamente está"
- [ ] Los cuatro invariantes transversales (INV-1..4) tienen su test identificado por nombre
- [ ] Todos los Success Criteria de Fase 1 y 2 verificados, con su evidencia
- [ ] Las cuatro deudas del prototipo cerradas, cada una con la tarea y el test que lo demuestra
- [ ] La DoD de abajo está completa

**Tests**: `tests/contract/test_traceability.py` — falla si la matriz referencia un test que no
existe, si un ítem del checklist no aparece en la matriz, o si un ítem marcado no tiene evidencia.
Esto automatiza la *integridad* de la matriz; el juicio sobre si la evidencia es **suficiente** sigue
siendo revisión humana y así debe quedar declarado en el PR de cierre.

---

## Milestone 11 — Requisitos de la segunda y tercera sesión de clarificación

> Tareas incorporadas por **actualización delta**. T001–T050 conservan su numeración, sus issues
> (#1–#50) y sus milestones. La numeración de issues **no** coincide con la de tareas a partir de
> aquí: `#51–#60` ya están tomados por épicas, de modo que T051 → #61 y así sucesivamente
> (`data-model.md` §9.4). Esa ruptura se declara en vez de disimularse: una correspondencia
> `TXXX`→`#XXX` que falla en silencio es peor que una que se documenta.

| ID | Tarea | Fase | Dep. | [P] | Est. |
|---|---|---|---|---|---|
| T051 | Job `age_threshold_refresh` (refresco de derivados etarios) | 2 | T003, T023, T039 |  | M |
| T052 | Tests de ciclo de vida del ítem | 2 | T017, T029, T037, T038 |  | M |
| T053 | Endpoint de declaración de gustos | 1 | T003, T018, T049 | [P] | M |
| T054 | Herencia de tags entre módulos | 1 | T008, T053 |  | S |
| T055 | Rechazo por módulo sin declaración | 1 | T018, T033, T053 |  | S |
| T056 | Perfil vectorial derivado puro | 2 | T017, T053 |  | S |
| T057 | Purga de señales de actividad con guarda de exclusión | 2 | T003, T023 |  | M |
| T058 | Supresión verificada con aborto del recálculo en curso | 3 | T023, T024, T025, T026, T028, T049, T057 |  | L |
| T059 | Verificación ejecutable de supresión, observador y escalamiento | 3 | T039, T058 |  | M |
| T060 | Disparador de recálculo por conteo e invalidación en el mismo acto | 2 | T023, T064 |  | M |
| T061 | Ponderación regional del término colaborativo | 2 | T004, T017 |  | M |
| T062 | Señal de resultado obsoleto como campo aparte | 2 | T049, T055 |  | M |
| T063 | Recálculo de popularidad por ventana | 1 | T003, T004 |  | M |
| T064 | Persistencia de la señal del evento y materialización de su exclusión | 1 | T003, T014, T018, T023, T024 |  | M |
| T065 | Cuota de novedades en el top-N personalizado | 2 | T016, T027, T063 |  | M |

> *Tabla agregada el 2026-09-27 junto con las tallas de `gen_issues.py`, medidas con la misma vara que
> T001–T050: **S** hasta ~5 criterios en un módulo, **M** hasta ~14 criterios o 2–3 módulos, **L** cuando
> la tarea cruza procesos y almacenes (hoy solo T058).*

### T051 [TDD] — Job `age_threshold_refresh` (refresco de derivados etarios)

**Descripción**: la edad del usuario no es un dato almacenado sino un derivado de `birth_date`, y
cambia sin que nadie escriba nada. Un derivado que sólo se recalcula ante escrituras nunca se
recalcula para este caso. El job recorre **dos criterios de selección separados**, no uno, que son las
dos causas de `data-model.md` §7.5: (A) los usuarios que **cruzan hoy un umbral** del catálogo —igualdad
exacta sobre `birth_date`, `idx_users_birth_date`— y (B) los usuarios cuyo ordinal se derivó bajo una
**versión de configuración distinta de la activa** —`age_config_version <> :activa`, índice parcial—.
Unificarlos perdería el caso A, que no deja rastro de escritura.

> *Corregido el 2026-09-27: el criterio B decía «usuarios cuya `birth_date` fue corregida». Esa
> corrección llega por sincronización (CR-4) y la resuelve T029 en el mismo acto; la causa B del
> modelo de datos es el cambio de catálogo etario, y sin ella DI-2e no tenía quién la sostuviera.*

**Archivos**: `src/recomendaciones/batch/age_threshold_refresh.py`,
`src/recomendaciones/batch/scheduler.py` *(decía `jobs/`, paquete que no existe en el árbol de T001)*

**Dep.**: T003, T023, T039

**Criterios de aceptación**:
- [ ] Los dos criterios de selección se consultan por separado y se registran por separado
- [ ] El cruce de umbral se calcula contra `birth_date`, nunca contra un campo de edad materializado
- [ ] Un usuario que cruza el umbral sin ninguna escritura queda seleccionado por el criterio A
- [ ] El job invalida la caché del usuario afectado en el mismo acto (FR-080, FR-080c: Redis primero)
- [ ] Emite la métrica de **liveness** `age_refresh_last_success_timestamp` al completar cada corrida,
      más `age_stale_config_users_total` y `age_threshold_crossings_total` (`data-model.md` §7.5.1)
- [ ] Es idempotente: dos corridas seguidas no producen recálculos duplicados
- [ ] La señalización de recálculo por usuario usa el mismo canal que T020: `XADD` a
      `recompute:requests` con `reason = 'age_threshold'`, respetando `recompute:lock` (RD-100)

**Tests**: `tests/integration/test_age_threshold_refresh.py` — usuario que cumple años sin escritura
alguna es recalculado (causa A); usuario con `age_config_version` no activa es rederivado (causa B);
corrida sobre conjunto vacío emite igualmente la métrica de liveness.

---

### T052 [TDD] — Tests de ciclo de vida del ítem

**Descripción**: la suite que hace verificable la familia «Ciclo de vida del ítem» (`FR-072` a
`FR-075`). Es la tarea que estuvo **bloqueada doce días** porque sus cuatro requisitos existían solo
como propuesta en `data-model.md` §9.1; se desbloqueó el 2026-09-22 al aprobarse con RD-87, RD-88 y
RD-91.

El identificador `T052` es el que la sección de bloqueo reservó para este contenido. No se reasignó a
otra cosa mientras estuvo vacante, que era exactamente el punto.

**Archivos**: `tests/invariants/test_item_lifecycle.py`,
`tests/integration/test_sync_retirement.py`

**Dep.**: T017, T029, T037, T038

**Criterios de aceptación**:

- [ ] **El retiro lógico preserva señales** (FR-073, DI-11): retirar un ítem con señales registradas
      deja intactas las filas de `user_signals` y **no altera ningún perfil vectorial**. Se verifica
      comparando el perfil antes y después, no solo la presencia de las filas: conservar la señal y
      dejar de usarla tendría el mismo efecto observable que borrarla
- [ ] **El ítem retirado no es servible por ninguno de los tres caminos** (FR-072, DI-10, §4.4).
      Un solo test no alcanza; hacen falta tres, porque son tres mecanismos distintos:
      - selección de candidatos → `WHERE status = 'available'` (T012)
      - construcción del respaldo → reunión bajo el mismo filtro (T038)
      - guarda del request path → diferencia contra `retired:{module}` (T037)
      El caso crítico es el tercero: un ítem retirado **después** de precomputarse el resultado.
      Los dos primeros filtros ya pasaron y no lo detienen
- [ ] **La desaparición del origen equivale a retiro** (FR-074, RD-91): un ítem ausente del listado
      sincronizado, sin señal explícita, queda `retired`
- [ ] **La corrida aborta sin marcar retiros** si no puede confirmar que el listado es completo
      (CR-9), y cuando `sync_volume_delta_ratio < 0,9`. Test obligatorio: listado truncado al 50 % →
      **cero** ítems marcados como retirados y corrida abortada con causa registrada
- [ ] **La lista reducida se sirve sin relleno** (FR-075): un top-N que queda en 7 de 20 tras
      excluir retirados se sirve con 7, y el estado sigue siendo el que corresponde a su frescura.
      Solo la lista **vacía** es `empty_no_candidates` (FR-056, RD-42)
- [ ] **Un ítem retirado y repuesto vuelve a ser recomendable**, y las señales previas siguen
      aplicando — es el corolario de que el retiro sea lógico y de que FR-074 sea revocable
- [ ] Verificación de poder de detección: **mutar la guarda de vigencia debe hacer fallar la suite**.
      Si la mutación pasa, la suite no afirma lo que dice afirmar

> **No incluye caso de modo degradado.** Q31 descartó la opción (c) —operar distinto según el origen
> pueda o no confirmar completitud—, de modo que **no existen dos modos** entre los cuales probar la
> transición. Escribir ese test crearía cobertura de una rama inexistente, que es peor que no
> tenerla: sugiere que la rama existe.

**Tests**: es la tarea de test. Corre en CI como gate bloqueante, junto con T017.

---

### T053 [P] [TDD] — Endpoint de declaración de gustos

**Descripción**: FR-089 abre una **excepción declarada** a la prohibición de escritura de FR-003. La
excepción alcanza a la escritura, **no al cómputo**: el endpoint persiste la declaración y responde,
y no ejecuta el motor (FR-089b). Si ejecutara el motor, la excepción dejaría de ser una excepción y
pasaría a ser una revocación de FR-003.

> **Tensión constitucional resuelta (RD-98, 2026-09-27)**: la constitución v1.1.0 declara esta
> escritura como la **única excepción** del Principio III, con los mismos límites que FR-089b. El
> endpoint se despliega en la API. **Sujeto a la aprobación de la enmienda por PR** (gobernanza de la
> constitución): hasta entonces, la tarea puede desarrollarse pero no fusionarse.

**Archivos**: `src/recomendaciones/api/routes/declaraciones.py`,
`src/recomendaciones/api/services/declaracion.py`; contrato en
`contracts/recomendaciones-api.openapi.yaml` (T049) *(rutas normalizadas al árbol de T001 el 2026-09-27)*

**Dep.**: T003, T018, T049

**Criterios de aceptación**:
- [X] Persiste en `user_declared_tags` con PK `(user_id, module, tag_name)` (FR-082); **solo** los tags
      que el usuario declaró en ese módulo — los heredados **no** se escriben (RD-97)
- [X] **Invalida `filters:{user_id}` antes de escribir** (FR-080c, RD-96): sin esto, un `filters:`
      vigente sin el módulo haría rechazar por FR-088, durante hasta `TTL_FILTERS`, a quien acaba de
      declarar — lo que FR-089a existe para impedir
- [X] Solicita el recálculo asíncrono del usuario para ese módulo (FR-089b, US4-5) con `XADD` a
      `recompute:requests` y `reason = 'declaration'` (RD-100), después de confirmar la escritura
- [X] Rechaza declaraciones con menos de `declared_tags_min` = 5 tags propios (FR-083)
- [X] **La declaración es definitiva** (FR-086a, RD-109): una segunda declaración para un módulo ya
      declarado → `409`, sin modificar la existente; no existe operación de edición ni de retiro
- [X] **No impone máximo** de tags
- [X] **SC-029** — 100 % de las declaraciones válidas confirmadas sin ejecutar el motor, y 100 % de las
      segundas declaraciones rechazadas sin cambios (la parte de lectura sin declaración la verifica T055)
- [X] Responde de forma **síncrona** confirmando la persistencia (FR-089a): una confirmación diferida
      habilitaría el rechazo inmediato de FR-088 sobre un dato ya entregado por el usuario
- [X] **No dispara el motor de recomendación** ni cómputo alguno (FR-089b); se verifica por ausencia
      de llamada, no por tiempo de respuesta
- [X] Sólo los tags del vocabulario vigente son aceptables (DEP-10)
- [X] **La declaración se exige al primer ingreso al módulo, no al crear la cuenta** (FR-084). El
      endpoint acepta declaración para **un** módulo por llamada y **no** exige el otro: un usuario
      que solo use recomendaciones de juegos nunca declara tags de películas, y la falta de
      declaración en un módulo **no** impide operar en el otro

**Tests**: `tests/contract/test_declaracion_endpoint.py`; `tests/unit/test_declaracion_minimo.py` —
4 tags rechaza, 5 acepta, 40 acepta; segunda declaración del mismo módulo → 409 y filas intactas; test
que falla si el motor es invocado.

---

### T054 [TDD] — Herencia de tags entre módulos

**Descripción**: los tags declarados en un módulo que pertenecen al vocabulario compartido se
**incorporan al insumo** del otro módulo **sin volver a pedirse** (FR-085), pero **no cuentan para el
mínimo de FR-083**: el mínimo mide elección deliberada en ese módulo. La herencia es **derivada, no
persistida** (RD-97): se calcula al construir el perfil (T008), y el endpoint (T053) solo la calcula
para validar e informar.

> *Reescrita el 2026-09-27. La versión anterior convertía la herencia en «preselección que el usuario
> confirma», donde lo confirmado **contaba** para el mínimo y se persistía como propio: contradecía
> las dos mitades de FR-085 —«sin volver a pedirse» y «no cuenta para el mínimo»— y volvía DI-28
> inverificable, porque la tabla no distingue filas propias de heredadas.*

**Archivos**: `src/recomendaciones/api/services/declaracion.py`, `src/recomendaciones/engine/profile.py`

**Dep.**: T053, T008

**Criterios de aceptación**:
- [X] Los tags heredables se resuelven vía `tag_modules` (declarados en el otro módulo ∩ compartidos),
      no por copia ciega
- [X] Los heredados **no** se escriben en `user_declared_tags`: toda fila de la tabla es propia (RD-97)
- [X] Los heredados **sí** forman parte del insumo del perfil del módulo nuevo (T008)
- [X] El mínimo de FR-083 se cuenta **solo** sobre los tags declarados en ese módulo: un usuario con
      5 heredados y 0 propios **no** satisface FR-083 y su declaración se rechaza
- [X] Si el usuario declara en el otro módulo un tag compartido **nuevo**, el insumo heredado lo
      refleja en el siguiente recálculo sin escritura adicional (consecuencia de derivar)
- [X] **El feedback no altera la pertenencia del tag a la declaración** (FR-086): un dislike reduce
      la **contribución** de sus tags al perfil y **nunca** borra ni hace caducar una fila de
      `user_declared_tags`. Se verifica sobre la tabla, no sobre el perfil: la declaración es un
      enunciado del usuario, no una inferencia del sistema, y el sistema no revoca enunciados ajenos
- [X] Un usuario que acumula dislikes sobre todos sus tags declarados **sigue declarado** y sigue
      satisfaciendo FR-083 — de lo contrario FR-088 lo expulsaría por haber usado el producto

**Tests**: `tests/unit/test_herencia_tags.py` — el caso 5 heredados / 0 propios debe ser rechazo; tras
declarar 5 propios, la tabla contiene exactamente esos 5 y el insumo del perfil contiene además los
heredados.

---

### T055 [TDD] — Rechazo por módulo sin declaración

**Descripción**: FR-088 manda rechazar la solicitud de un usuario sin declaración en ese módulo. El
rechazo **no introduce un sexto estado de respuesta**: ocurre *antes* de que la precedencia de
estados de FR-056 sea aplicable. Tratarlo como estado nuevo rompería la exhaustividad declarada del
contrato de lectura (DEP-6).

**Archivos**: `src/recomendaciones/api/routes/recommendations.py` (la ruta de T033, no una segunda),
`src/recomendaciones/api/services/precondiciones.py` *(rutas normalizadas el 2026-09-27)*

**Dep.**: T053, T018, T033

**Criterios de aceptación**:
- [X] El chequeo de declaración ocurre en precondiciones, antes de resolver estado de resultado
- [X] La declaración se lee de `filters:{user_id}.declared_modules` (RD-96): el camino normal no consulta
      Postgres (INV-1). *(La dependencia de T012 —motor— era espuria: el rechazo ocurre antes de todo
      resultado.)*
- [X] El conjunto de estados de respuesta sigue teniendo **cinco** miembros
- [X] El rechazo es por módulo: declarado en uno y no en el otro → rechazo sólo en el segundo
- [X] El cuerpo del rechazo indica qué falta, sin exponer detalle interno
- [X] **SC-029** (parte de lectura) — 100 % de las lecturas de un módulo sin declaración rechazadas como
      precondición incumplida, sin un sexto estado

**Tests**: `tests/contract/test_rechazo_sin_declaracion.py` — enumera los estados posibles y falla si
aparece uno sexto.

---

### T056 [TDD] — Perfil vectorial derivado puro

**Descripción**: FR-087 exige que el perfil vectorial sea **derivado y reconstruible** a partir de
sus insumos. Queda **prohibida la actualización incremental**: un perfil que se actualiza sumando
deltas deja de ser reconstruible en cuanto se pierde un delta, y el error no se manifiesta como
fallo sino como recomendaciones levemente peores, que es el modo de fallo más difícil de detectar.

**Archivos**: `src/recomendaciones/engine/profile.py` *(el módulo de perfil de T008; decía `user_profile.py`, un segundo módulo para lo mismo)*

**Dep.**: T053, T017

**Criterios de aceptación**:
- [ ] La única operación pública es **reconstruir desde los insumos**; no existe `update_partial`
- [ ] Reconstruir dos veces sobre los mismos insumos da el mismo vector (determinismo)
- [ ] El perfil no se persiste como fuente de verdad; si se cachea, se puede descartar sin pérdida
- [ ] Los insumos son la declaración (FR-082) y las señales vigentes, no señales purgadas

**Tests**: `tests/unit/test_user_profile_derivado.py` — reconstrucción idempotente; test que falla si
se agrega un método de actualización incremental.

---

### T057 [TDD] — Purga de señales de actividad con guarda de exclusión

**Descripción**: la retención es finita y declarada (FR-068, FR-068a), y el horizonte debe ser
estrictamente mayor que toda ventana operativa (FR-068b). Antes de purgar una señal de consumo, el
procedimiento verifica la guarda de FR-068c; y la exclusión permanente persiste **aunque su señal de
origen haya sido purgada** (FR-068d), por reconstrucción aditiva, no por dependencia de la señal.

**Archivos**: `src/recomendaciones/batch/purga_senales.py` *(decía `jobs/`, paquete inexistente en T001)*

**Dep.**: T003, T023

**Criterios de aceptación**:
- [ ] Retención y horizonte son parámetros **obligatorios con valor explícito**, sin default oculto
- [ ] El arranque falla si el horizonte no supera estrictamente la ventana operativa mayor
- [ ] La guarda de FR-068c se evalúa **antes** de cada purga de señal de consumo
- [ ] Purgar la señal de origen **no** elimina la exclusión derivada: `user_exclusions` no tiene FK hacia
      `user_signals`, y la reconstrucción es aditiva (FR-068d, DI-20). *(Decía «RESTRICT»: esa política
      es la de `user_exclusions → items`, no protege frente a la purga de señales.)*
- [ ] Cada corrida **registra el valor vigente** de `signal_retention_days`, para que una reducción no
      aprobada sea detectable después (ceremonia asimétrica, RD-54)
- [ ] Emite `signals_purge_deferred_total` (consumos no purgados por faltarles la exclusión
      materializada, FR-068c), con alerta si es > 0 sostenido (`data-model.md` §7.10)
- [ ] Emite `exclusions_orphaned_permanent_total` como medida **informativa y sin umbral de alerta**
      (FR-068d1) — y T042 verifica que **no** exista alerta asociada

**Tests**: `tests/integration/test_purga_senales.py` — exclusión sobrevive a la purga de su señal;
configuración con horizonte menor que la ventana no arranca.

---

### T058 [TDD] — Supresión verificada con aborto del recálculo en curso

**Descripción**: FR-092 ordena invalidar la caché **antes** de eliminar el dato de origen, y FR-092a
exige **abortar** el recálculo en curso en vez de esperarlo. Esperar no basta: suprimir el bloqueo
de recálculo no detiene al worker que ya lo tomó, sólo habilita a que entre un segundo.

> **Decidido (RD-101, 2026-09-27)**: la supresión la **dispara el evento de baja de cuenta** que publica
> `api-general` (CR-19, DEP-12), consumido por el worker con idempotencia por `event_id`. La marca, la
> constancia y el fallo visible viven en **`user_suppressions`** (§2.15). **Dependencia externa**: sin el
> evento definido en `api-general`, la tarea se implementa y prueba contra el esquema propuesto, pero no
> tiene disparo en producción.

**Archivos**: `src/recomendaciones/worker/suppression.py` (consumo del evento de baja y procedimiento de
§7.11) y `src/recomendaciones/worker/handler.py` —el recálculo de T027, que consulta la marca antes de
escribir— *(decía `services/` y `jobs/recalculo.py`, paquetes inexistentes en T001)*

**Dep.**: T023, T024, T025, T026, T028, T057, **T049** (el esquema del evento de baja, contract-first)

**Criterios de aceptación**:
- [ ] Se dispara por el evento de baja (FR-091a); reprocesar el mismo evento no repite efectos
- [ ] La cola del evento de baja tiene los **mismos reintentos con backoff y dead-letter** que
      `recomendacion.actualizar` (reutiliza T025) y el payload inválido va a DLQ sin reintento
      (reutiliza T026) — Principios VI y VII, RD-111
- [ ] Orden de operaciones: Redis primero, Postgres después (FR-080c)
- [ ] La marca es la fila `user_suppressions` con `state = 'in_progress'` (FR-092a)
- [ ] Las entradas pendientes del usuario en `recompute:requests` se purgan (RD-100)
- [ ] El recálculo en curso se **aborta**; el worker comprueba una señal de cancelación y se detiene
- [ ] La supresión alcanza a **toda** versión de configuración y a **todos** los módulos (FR-093)
- [ ] Alcanza las **cinco** tablas de §7.11, incluida `user_declared_tags`
- [ ] **El alcance incluye la caché** (FR-091), no solo Postgres: las **cuatro** claves de alcance de
      usuario —`filters:`, `reco:`, `reco:stale:` y `recompute:lock:`— se eliminan explícitamente, para
      toda `config_version` y módulo (`data-model.md` §7.11). *(Faltaba `recompute:lock:`.)*
- [ ] La marca de «en supresión» se consulta **inmediatamente antes de escribir** el resultado, no solo
      al inicio del recálculo (FR-092a)
- [ ] **Ningún dato se da por suprimido delegando en el vencimiento de su TTL** (FR-091). Se
      verifica leyendo la clave inmediatamente después de la supresión, no esperando su expiración:
      un dato que sigue siendo legible no está suprimido, por más que vaya a expirar
- [ ] Un worker que termina después de la supresión **no** reescribe el resultado suprimido

**Tests**: consumo real del evento de baja contra un broker de prueba (Principio VI): duplicado → un solo
efecto; payload inválido → DLQ; fallo transitorio → reintento. `tests/integration/test_supresion_aborta_recalculo.py` — recálculo en vuelo durante la
supresión; verificar que ningún registro reaparece.

---

### T059 [TDD] — Verificación ejecutable de supresión, observador y escalamiento

**Descripción**: FR-094 manda tratar la supresión parcial como fallo y FR-095 exige que la
verificación sea **ejecutable y registrada**. FR-095a agrega observador: un fallo que nadie observa
no es un fallo detectado.

**Archivos**: verificación junto al módulo de supresión de T058, `ops/alerts.yaml`

**Dep.**: T058, T039

**Criterios de aceptación**:
- [ ] Tras suprimir, una comprobación recorre las cinco tablas **y las claves de Redis** y deja
      registro del resultado. La verificación cubre el mismo alcance que FR-091 declara: una
      comprobación que solo mira Postgres daría por exitosa una supresión que dejó la caché intacta
- [ ] Sin residuo → `verified_at` y `state = 'completed'` en `user_suppressions` (FR-095); la fila
      conserva solo identificador y marcas temporales
- [ ] Residuo detectado → reintento acotado con backoff (`attempts`); agotado, `state = 'failed'` —el
      estado **fallido visible** de FR-095a— e incrementa `user_deletion_residual_keys_total`
      (`data-model.md` §7.11)
- [ ] Métrica de supresiones con verificación fallida, **con alerta** (FR-095a) — a diferencia de
      `exclusions_orphaned_permanent_total`, que es informativa
- [ ] Escalamiento declarado en el runbook
- [ ] **SC-030** — 100 % de las supresiones terminan verificadas sin residuo o en estado fallido visible
      con alerta; 0 usuarios suprimidos rematerializados (junto con la lápida de T029)

**Tests**: `tests/integration/test_supresion_verificada.py` — residuo inyectado produce fallo y
dispara la alerta.

---

### T060 [TDD] — Disparador de recálculo por conteo e invalidación en el mismo acto

**Descripción**: FR-080a dispara el recálculo al acumular un número de señales; FR-080 exige que la
invalidación de caché ocurra **en el mismo acto** que la causa. Separarlos deja una ventana en la
que el sistema sirve un resultado que ya sabe obsoleto.

> **Decidido (RD-104, 2026-09-27)**: el contador **no se almacena**; se cuenta sobre `user_signals` desde
> el `computed_at` del perfil **del módulo**, con `idx_signals_user_received`. El conteo es **por
> (usuario, módulo)** —decidido por el autor, CHK064—: el módulo es el del ítem de la señal.

**Archivos**: `src/recomendaciones/worker/trigger.py` *(decía `services/`)*

**Dep.**: T023, T064

*(La dependencia anterior era el cliente REST del Data Transformer, que el disparador no usa; el
conteo ocurre sobre la señal que persiste T064.)*

**Criterios de aceptación**:
- [ ] El conteo umbral es parámetro de §4, no constante en código
- [ ] El conteo es una consulta sobre `user_signals` (`received_at` posterior al último cálculo del
      perfil de ese módulo), filtrada por el módulo del ítem; no existe columna ni clave de contador
      (RD-104). El reinicio es consecuencia de recalcular ese módulo
- [ ] Alcanzar el umbral en el módulo M recalcula M; el opuesto solo si corresponde propagar (FR-010a)
- [ ] Causa e invalidación son atómicas respecto del lector: no hay lectura intermedia del valor viejo
- [ ] FR-080b se respeta: el top-N reside **únicamente en Redis**; se persisten sus insumos, no él
- [ ] Redis primero, Postgres después (FR-080c)
- [ ] Un evento que no alcanza el umbral queda en `processed_events` con resultado `signal_recorded`
      (RD-95)

> *SC-022 (sin invalidación masiva por cambio de configuración) estaba atribuido acá; es propiedad de
> las claves y se movió a T018.*

**Tests**: `tests/integration/test_trigger_recalculo.py` — n−1 señales no disparan, n sí; 5 señales de
películas y 5 de juegos **no** disparan (conteo por módulo); ninguna
lectura entre causa e invalidación devuelve el resultado viejo.

---

### T061 [TDD] — Ponderación regional del término colaborativo

**Descripción**: FR-081 manda implementar la segmentación como **ponderación**, no como filtro, y
FR-081a exige degradación continua. FR-081b fija el factor como **intensidad de la segmentación**:
`0` es el neutro. `v1` arranca activo en su intensidad mínima, `region_weight_factor = 0,1`
(FR-090a), revirtiendo la prescripción de RD-74 sin revertir la capacidad de FR-090.

**Archivos**: `src/recomendaciones/engine/collaborative.py`

**Dep.**: T004, T017

**Criterios de aceptación**:
- [ ] Con `region_weight_factor = 0` el resultado es **idéntico** al de no segmentar
- [ ] **SC-031** — factor 0 idéntico a sin región en el 100 % de los casos de prueba; 100 % de los
      recálculos con al menos `collab_min_neighbors` vecinos con peso no despreciable, o registro de que
      no los hubo
- [ ] El peso extraregional es positivo para todo factor `< 1`: ningún vecino queda excluido por regla
- [ ] `collab_min_neighbors` = 10: si la región del usuario no aporta ese mínimo de vecinos con peso
      no despreciable, el vecindario **se completa con usuarios de otras regiones** hasta alcanzarlo
      (FR-096). *(Corregido el 2026-09-27: decía que en ese caso «el término colaborativo no se
      aplica», que es exactamente el apagado discontinuo que FR-081a y FR-096 prohíben.)*
- [ ] El corte top-k **posterior** se verifica: un peso positivo pero ínfimo no debe volverse
      indistinguible de cero al recortar (riesgo señalado al cerrar FR-081a)

**Tests**: `tests/unit/test_ponderacion_regional.py` — factor 0 equivale a sin segmentación; usuario en
una región con 3 usuarios obtiene un vecindario de tamaño ≥ `collab_min_neighbors` completado con
extrarregionales (el criterio falsable de FR-096); barrido de factores sin discontinuidades.

---

### T062 [TDD] — Señal de resultado obsoleto como campo aparte

**Descripción**: FR-056a pide señalar que, además del respaldo servido, existe un resultado
personalizado vencido. Es **un campo aparte, no un sexto estado**: agregarlo al enum rompería la
exhaustividad acordada en DEP-6 y obligaría a renegociar el contrato de lectura con `api-general`.

**Archivos**: `src/recomendaciones/api/schemas/respuesta.py`, `contracts/openapi.yaml`

**Dep.**: T055, T049

**Criterios de aceptación**:
- [ ] El enum de estados conserva **cinco** miembros
- [ ] El campo se llama **`stale_available`** (booleano) y vale `true` sólo cuando se sirve respaldo
      existiendo personalizado vencido dentro del límite (RD-107)
- [ ] **`prefer=stale`**: con obsoleto disponible, se sirve como `personalized_stale` tras las mismas
      guardas de edad, exclusión y vigencia; sin obsoleto, rige la precedencia normal. Sin el
      parámetro, la precedencia no cambia
- [ ] La precedencia de FR-056 aplica sólo a solicitudes que **pasaron** precondiciones

**Tests**: `tests/contract/test_estado_obsoleto.py` — respaldo con obsoleto → `stale_available: true`;
mismo estado con `prefer=stale` → `personalized_stale` filtrado; `prefer=stale` sin obsoleto →
respuesta idéntica a la de sin parámetro.

---

### T063 [TDD] — Recálculo de popularidad por ventana

**Descripción**: **productora** de `item_popularity`. Recalcula la popularidad por ventana
(RD-12, RD-13) y la escribe con PK `(item_id, config_version)`. El puntaje es el **límite inferior
del intervalo de confianza de Wilson** sobre la tasa de conversión a like entre quienes
interactuaron (FR-033a3), con `popularity_confidence_z` = 1,96.

Es el **único escritor** de `item_popularity` (DI-13). T038 la consume; T029 no la toca.

**Archivos**: `src/recomendaciones/batch/popularidad.py` *(decía `jobs/`)*

**Dep.**: T003, T004

> **Nota de fase (2026-09-22)**: **Fase 1**, no Fase 3. T038 está en Fase 1 por el hallazgo F2
> —«sin el batch de respaldo, el estado `fallback` de FR-056 es inalcanzable y T020 no puede
> testearse completa»— y al declararse que T038 **lee** lo que T063 escribe, dejar a T063 fuera de
> Fase 1 haría que ese fundamento dejara de cumplirse: T038 correría sobre una tabla vacía y
> `fallback` seguiría siendo inalcanzable. La dependencia arrastra la fase.

**Criterios de aceptación**:
- [X] La ventana es parámetro de §4 y es **menor** que el horizonte de retención de FR-068b
- [X] El resultado se escribe por `config_version`; cambiar de versión no pisa la anterior
- [X] `popularity_confidence_z` se lee de configuración, no se codifica
- [X] El puntaje es el **límite inferior del intervalo de Wilson** sobre la tasa de conversión a
      like entre quienes interactuaron (FR-033a3), no el volumen bruto de likes
- [X] Se respetan `FR-033a3a` y `FR-033a3b` (tratamiento del denominador y de los casos sin
      interacción), `FR-033a4` y `FR-033a5`
- [X] `CHECK (popularity_score BETWEEN 0 AND 1)` y `CHECK (like_count <= engaged_user_count)`
      (DI-26) se sostienen sobre todo lo escrito
- [X] `computed_at` se escribe por fila, de modo que un batch **parcialmente fallido** sea
      detectable (RD-13) y alimente `catalog_popularity_last_success_timestamp`
- [X] **Sin criterio de cuota**: la cuota vive en **T065** (RD-102). *(Se había movido a T038 el
      2026-09-22; RD-102 la sacó del respaldo.)*
- [X] **Escribe `item_promotions`** (RD-102, FR-033a6e): inserta la fila la **primera** vez que
      `engaged_user_count ≥ emergent_evidence_threshold`; **nunca** borra ni actualiza una existente
      (DI-27). Es el único escritor de la tabla

**Tests**: `tests/integration/test_popularidad.py` — ventana mayor que retención no arranca; un
ítem con 1 like de 1 interacción **no** supera a uno con 80 de 100 (es el caso que distingue Wilson
del conteo bruto); batch interrumpido deja `computed_at` viejo en las filas no recalculadas; ítem que
cruza el umbral → fila en `item_promotions`; su evidencia cae por debajo en la corrida siguiente → la
fila **sigue**.

---

### T064 [TDD] — Persistencia de la señal del evento y materialización de su exclusión

**Descripción**: el worker **persiste la señal** que transporta cada `recomendacion.actualizar`
(FR-010, FR-029e) y, en el mismo acto, **materializa su exclusión** e **invalida `filters:{user_id}`**
(RD-96). Reemplaza a **T036**, retirada (RD-95): lo que aquella resolvía —que una reacción del
usuario no deje el top-N desactualizado ni el ítem visible— se resuelve acá por la vía que la
constitución admite: `api-general` registra la actividad y publica el evento; este repositorio la
proyecta.

**Archivos**: `src/recomendaciones/worker/signals.py`

**Dep.**: T003, T014, T018, T023, T024

**Criterios de aceptación**:
- [X] Persiste en `user_signals` con `source = 'evento'`, `occurred_at` **del origen** y `received_at`
      local (CR-12, RD-32)
- [X] Deduplica por `origin_interaction_id` (DI-21) con la comparación de `data-model.md` §7.10:
      idéntica → reentrega, se descarta e incrementa `signal_duplicate_rejections_total{source="evento"}`;
      **distinta** → incumplimiento de contrato (FR-029e1): no se persiste, incrementa
      `contract_violations_total{field="origin_interaction_id"}` y el evento va a **DLQ** con la causa
      (FR-012) — nunca se absorbe en silencio
- [X] Invoca al resolutor de exclusiones (T014), que materializa la exclusión e **invalida
      `filters:{user_id}` antes de escribir en Postgres** (FR-080c): la exclusión es efectiva en la
      **siguiente lectura** (RD-96, SC-003, SC-018)
- [X] Usuario o ítem **aún no materializados** → no se persiste, se registra como
      `skipped_not_materialized` en `processed_events`, **sin reintento ni DLQ**: la sincronización la
      incorporará y la deduplicación impedirá contarla dos veces (edge cases de `spec.md`)
- [X] Un evento que no alcanza el umbral de FR-080a termina como `signal_recorded`; el que lo alcanza
      delega el recálculo en T027
- [X] `INV-4`: no llama a `api-general` ni escribe fuera de su DB; **no publica** ningún evento
- [X] Reprocesar el mismo evento deja una sola señal y la misma exclusión (FR-011, FR-011a)

**🔴 Paso 1 — Rojo** (`tests/integration/test_event_signals.py`, commit propio): evento válido →
una fila con `source='evento'`; el mismo evento dos veces → una fila; la misma interacción llegada
antes por sincronización → una fila; mismo `origin_interaction_id` con otro `signal_type` → DLQ y
contador de violación, ninguna fila nueva; tras un dislike por evento, la lectura siguiente **no**
contiene el ítem aunque `filters:` estuviera poblado; ítem inexistente → `skipped_not_materialized`
sin reintento.

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de «la lectura siguiente no contiene el ítem
con `filters:` poblado» es el que obliga a invalidar: con el TTL solo, pasa en rojo durante una hora.

---

### T065 [TDD] — Cuota de novedades en el top-N personalizado

**Descripción**: paso **(4)** del post-procesamiento (FR-028): colocar ítems del **conjunto emergente**
en posiciones reservadas del top-N personalizado que precalcula el worker (FR-033a6…FR-033a8, RD-102).
El emergente es todo ítem vigente **sin** fila en `item_promotions`; se ordena por afinidad de contenido
con el perfil (FR-033a6f1) y el k-ésimo ocupa la posición `ceil(k / fallback_new_item_quota_ratio)` de
una lista de longitud `top_n_max`. Así, truncar a cualquier `top_n` deja exactamente
`floor(top_n × ratio)` posiciones reservadas **sin cálculo al servir** (FR-003, FR-033d).

**Archivos**: `src/recomendaciones/engine/postprocess.py` (etapa nueva del pipeline de T016),
`src/recomendaciones/worker/handler.py` (lee `item_promotions` y pasa el conjunto al motor)

**Dep.**: T016, T027, T063

**Criterios de aceptación**:
- [ ] La etapa corre **después** de MMR y solo reubica candidatos que ya superaron edad y exclusión: su
      salida es una permutación de un subconjunto de su entrada (FR-031)
- [ ] Posiciones reservadas en `ceil(k / ratio)`; para todo `top_n ∈ [10, 50]`, el prefijo de longitud
      `top_n` contiene exactamente `min(floor(top_n × ratio), emergentes disponibles)` emergentes en
      posiciones reservadas (FR-033a6a)
- [ ] **Máximo, no mínimo**: si faltan emergentes, las posiciones reservadas se ocupan por el orden
      ordinario y ninguna queda vacía (FR-033a6)
- [ ] El orden entre emergentes es la afinidad de contenido con el perfil, **no** el puntaje de
      popularidad (FR-033a6d, FR-033a6f1); sin aleatoriedad (FR-033a6f2)
- [ ] El score de cada ítem no se altera (FR-033a7): cambia la posición, no el valor
- [ ] Ningún ítem aparece dos veces; un emergente que ya estaba en el orden ordinario no se duplica
- [ ] La colocación respeta el **tope de cluster** de FR-071a: un emergente que lo haría superar en su
      posición se salta por el siguiente emergente
- [ ] Se emite `fallback_new_item_share` (nombre histórico, RD-102) distinguiendo cuota **disponible** de
      **ocupada** (FR-033a8)
- [ ] Determinista ante empates (FR-070)

**🔴 Paso 1 — Rojo** (`tests/unit/test_novelty_quota.py`, commit propio): property-based — para toda
entrada y todo `top_n` en `[10, 50]`, conteo de emergentes reservados = `floor(top_n × 0,20)` cuando
sobran emergentes; con cero emergentes, la salida es idéntica a la de MMR; la salida es permutación de
un subconjunto de la entrada; scores idénticos antes y después; dos perfiles distintos ordenan los
mismos emergentes de forma distinta.

**🟢 Paso 2 — Verde**: implementar hasta pasar. La propiedad de truncado escrita primero es la que
impide «resolver» la cuota al servir.

---

# Bloqueo levantado — ciclo de vida del ítem *(registro histórico)*

> **Estado: LEVANTADO el 2026-09-22.** Esta sección se conserva como registro de un bloqueo real que
> duró doce días, no se borra. Lo que sigue describe qué bloqueaba, qué lo levantó y qué se aplicó
> en consecuencia.

**El bloqueo**: entre el 2026-09-10 y el 2026-09-22, `data-model.md` §9 citaba **FR-072 a FR-078**
veinticinco veces, y **ninguno de los siete existía en `spec.md`** — el documento saltaba de FR-071 a
FR-079. No era omisión de lectura: §9.1 los **proponía** y §9 lo advertía con todas las letras —«el
modelo de datos los anticipa; no los autoriza»—. El backlog respetó la advertencia y no propagó nada.

**Qué lo levantó**: la sesión de clarificación del 2026-09-22 incorporó la familia «Ciclo de vida del
ítem — FR-072 a FR-075» a `spec.md`. `FR-072`, `FR-073` y `FR-075` se aprobaron con **RD-87** sobre
identificadores **vacantes** —nunca designaron otra cosa—; `FR-074` quedó reservado por **RD-88** y
se cerró el mismo día con **RD-91**, al confirmarse la premisa de `CR-8`.

| ID | Contenido | Estado hoy |
|---|---|---|
| FR-072 | Ítem retirado no recomendable, por ninguno de los tres caminos | ✅ **Vigente** en `spec.md` (RD-87) |
| FR-073 | Retiro lógico, señales históricas conservadas | ✅ **Vigente** (RD-87) |
| FR-074 | Desaparición del origen equivale a retiro | ✅ **Vigente** (RD-91, cierra la reserva de RD-88) |
| FR-075 | Lista reducida sin relleno | ✅ **Vigente** (RD-87) |
| FR-076 | Ítem sin tags | Absorbido por **FR-021b**. Identificador **retirado y no reasignable** (RD-90) |
| FR-077 | Reconstrucción aditiva de exclusiones | Absorbido por **FR-068d**. Ídem (RD-90) |
| FR-078 | Umbral 0,9 de volumen anómalo | Absorbido por el registro de clarificación. Ídem (RD-90) |

**Qué se aplicó al levantarse** (2026-09-22):

- ✅ **T052 creada**, con el alcance que `data-model.md` §9.3 tenía redactado desde el 2026-09-10 y
  en el identificador que esta sección mantuvo reservado. **Sin caso de modo degradado**: Q31
  descartó la opción (c) y no hay dos modos de operación que contrastar.
- ✅ **Las seis tareas congeladas, modificadas**: **T012** (candidatos restringidos a
  `status='available'`), **T017** (DI-10 y DI-11 con test propio cada uno), **T018** (familia
  `retired:{module}` acotada a `TTL_STALE` + 1 día por RD-39), **T029** (retiro por CR-7 y CR-8 con
  **una sola rama**, aborto por CR-9 y por `< 0,9`), **T037** (guarda de vigencia del request path),
  **T038** (respaldo solo sobre vigentes).
- ✅ **El hueco de numeración se cerró correctamente**: `T052` quedó ocupada por el contenido que
  tenía reservado, no por otra tarea. Era el riesgo declarado — reutilizar el identificador habría
  repetido el patrón de identificador recolocado que este proyecto registra cuatro veces (`FR-052`,
  `FR-022c`, la reasignación de §9.9, `FR-070a`…`FR-070e`) y por el que `DEP-3` sigue vacante.

**Lo que este episodio deja registrado**: un requisito citado veinticinco veces en un documento y
ausente del otro puede sobrevivir doce días sin que nadie lo note, porque **cada cita individual
parece una referencia legítima**. Lo detectó una verificación de existencia, no una lectura. La
lección operativa es la regla que rige estas sesiones: contar y verificar contra el archivo, nunca
copiar identificadores de un documento derivado.

---


# Ruta crítica

```
T001 → T003 → T014 ─┐
T001 → T004 → T007 → T008 → T009/T010/T011 → T012 → T015 ─┼→ T016 → T017
T001 → T004 → T013 ────────────────────────────────────┘
T001 → T005 → T049 (contratos primero) ──┬→ T023 → T024 → T064 → T027 (worker)
                                          └→ T033 (lectura), T053 (declaración)
T016 → T019 → T020 → T033 → T039 → T042 → T046 → T048
```

**Cuello de botella real: T016** (pipeline de post-proceso). Bloquea persistencia, worker y API a la
vez. Priorizarlo por encima de cualquier tarea `[P]`.

**Ruta crítica** *(recalculada el 2026-09-27 desde las líneas `Dep.` de cada tarea, como la cadena
de dependencias más larga hasta T048; cuenta tareas, no duración)*: `T001 → T004 → T007 → T008 →
T009 → T012 → T015 → T016 → T019 → T020 → T033 → T039 → T042 → T046 → T048` (15 tareas).

> La versión anterior tenía 18 tareas e incluía **T036** (retirada) y un tramo `T033 → T036 → T038 →
> T037 → T049 → T043`, que las líneas `Dep.` no sostenían —T038 no depende de T036 ni T049 de T037—;
> también omitía **T009**, del que depende T012. Con **T049 contract-first**, el contrato sale de la
> ruta crítica y pasa a ser prerequisito temprano de T023, T033 y T053.

> **Cambio tras el análisis de consistencia**: la ruta creció de 15 a 18 tareas. T038 y T037 entraron
> por la cadena de dependencias corregida (F2, F4); T049 entró porque T043 no puede validar contratos
> que nadie produjo (F6). Ninguna es trabajo nuevo: eran dependencias que estaban implícitas y ahora
> son visibles. **La ruta no se alargó — se dejó de subestimar.**

**Paralelizables tempranas** (tras T001): T004, T005, T006 — luego T009/T010/T011 en simultáneo tras T008.

**Riesgo de cronograma**: T027 (propagación cross-module) es `L` y depende de casi todo el motor.
Si el contrato del evento con `api-general` no se cierra a tiempo (DEP-1), T023 se bloquea y arrastra
T024→T027. **Este riesgo se agravó al mover el worker a Fase 1** (F1): ahora DEP-1 bloquea el hito
de Fase 1 completo, no solo el de Fase 2. **Mitigación**: desarrollar contra un doble del contrato
desde el día 1 y escalar DEP-1 como bloqueante inmediato (recomendación D1 del plan del 2026-09-07).

---

# Definition of Done — habilita `/speckit.implement`

## Invariantes (bloqueantes)
- [ ] Cero violaciones de edad en los cinco `result_type` — batería exhaustiva en verde (T017)
- [ ] Cero ítems excluidos en cualquier respuesta (T014, T017)
- [ ] MMR nunca reintroduce un ítem filtrado — property-based en verde (T015)
- [ ] `api/` no importa `engine/` — test de arquitectura en verde (T006)
- [ ] Cero queries a Postgres en el request path normal (T033)
- [ ] Redis caído → 503, sin fallback a cómputo en línea (T021)
- [ ] Todo dato es recuperable desde Postgres tras pérdida total de Redis (T022)
- [ ] Cero conexiones a DB de otros repos (T002, T028)

## Funcionalidad
- [ ] US1 (lectura) y US2 (recálculo) demostrables end-to-end **al cierre de Fase 1** (T023, T024, T027, T064, T053)
- [ ] US5 (filtros obligatorios) verificado por T017
- [ ] US3, US4, US6, US7 completos
- [ ] Los cinco `result_type` alcanzables y correctamente discriminados — **incluido `fallback`**,
      que requiere T038 en Fase 1
- [ ] Cold start cruzado produce recomendaciones no triviales (SC-010)

## Calidad y contratos
- [ ] **Toda tarea `[TDD]` desarrollada test-first** —desde el 2026-09-27, toda tarea de producción salvo
      las exentas de la *Política TDD*—: en cada PR, el commit de test precede al de implementación
      (verificable en el historial de git). *(Decía «T007–T017», el alcance selectivo anterior.)*
- [ ] **Test de mutación en verde**: mutar el filtro de edad o el de exclusión hace fallar la suite
      (T017, T045)
- [ ] `contracts/` materializado con OpenAPI y JSON Schema (T049)
- [ ] Contract tests en verde como gate bloqueante (T043)
- [ ] Los nueve casos críticos en verde (T044)
- [ ] Configuración versionada trazable en cada recomendación servida
- [ ] `config_version` presente en **ambas** familias de clave, vigente y obsoleta (T018)
- [ ] `v1.yaml` valida contra el loader; configuración inválida impide el arranque
- [ ] SC-001 verificado: p95 ≤ 50 ms y la latencia no depende del tamaño del catálogo (T050)

## Deuda del prototipo
- [ ] Caché en memoria → Redis persistente (T018)
- [ ] `ExclusionSet` con interfaz pública; sin acceso a atributos privados (T014)
- [ ] Una reacción del usuario no deja el top-N silenciosamente desactualizado: la señal del evento se
      persiste, su exclusión es efectiva en la siguiente lectura y el recálculo se dispara (T064, T027,
      T060). *(Decía «Feedback publica el evento de recálculo (T036)», tarea retirada por RD-95.)*
- [ ] Constantes del motor y mapeo de `age_rating` externalizados a configuración (T004, T013)

## Operación
- [ ] **Las veintidós métricas de observabilidad emitiéndose** (T039). La cifra anterior ("diez")
      quedó obsoleta: el recuento sobre `data-model.md` da dieciséis nombres de métrica
      (`age_stale_config_users_total`, `age_threshold_crossings_total`, `catalog_retired_total`,
      `catalog_unrated_ratio`, `catalog_unvectorized_ratio`, `contract_violations_total`,
      `exclusion_resolve_lag_seconds`, `exclusions_orphaned_permanent_total`,
      `projection_field_anomalies_total`, `signal_duplicate_rejections_total`,
      `signal_ingest_lag_seconds`, `signals_purge_deferred_total`, `sync_volume_delta_ratio`,
      `user_deletion_residual_keys_total`, `vector_recompute_lag_seconds`, y la métrica de
      **liveness** del job de T051 que reemplaza a `age_ordinal_staleness_seconds`). Un DoD que pide
      diez sobre dieciséis se da por satisfecho con seis métricas faltando. *(Recontado el 2026-09-28:
      a las dieciséis se suman `declarable_tags_total`, `diversity_cap_relaxed_total`,
      `fallback_new_item_share`, `recompute_requests_pending`, `recompute_requests_dropped_total` y
      `suppressions_unverified_total`, nombradas por RD-108, RD-110, RD-102 y RD-111.)*
- [ ] `contract_violations_total` se emite con contadores **separados** para `birth_date` y `region`
- [ ] `exclusions_orphaned_permanent_total` se emite **sin alerta asociada** (FR-068d1): su ausencia
      de umbral es un requisito, no un olvido de configuración
- [ ] **Ningún FR carece de tarea**, o su ausencia está declarada con motivo (hoy: las tareas marcadas
      ⚠️ «pendiente» que quedan y `plan.md` §8; la antigua sección «Tareas bloqueadas por requisitos
      inexistentes» es hoy el registro histórico «Bloqueo levantado»). La cobertura supuesta es la forma más barata
      de aparentar completitud
- [ ] Correlation ID sobrevive el salto asíncrono (T040)
- [ ] Health/readiness/liveness en los tres entrypoints (T041)
- [ ] **Cada alerta probada induciendo su condición**, y se apaga al normalizarse (T042)
- [ ] Umbral de cada alerta justificado por escrito (T042)
- [ ] **Ejecución de prueba del runbook registrada** en `docs/validation/runbook-dry-run.md`, con sus
      bloqueos ya corregidos (T046)
- [ ] Documento de campos requeridos publicado (T047)

## Gobernanza
- [ ] **Matriz de trazabilidad ítem → evidencia completa** en `docs/validation/traceability-matrix.md`;
      ningún ítem marcado sin evidencia concreta (T048)
- [ ] `test_traceability.py` en verde: toda evidencia referenciada existe (T048)
- [ ] Sin violaciones de la constitution v1.1.1, **aprobada** por PR (RD-98, RD-111)
- [ ] Valores cargados: `popularity_window_days` = 90, `emergent_evidence_threshold` = 20,
      `diversity_max_cluster_share` = 0,4, `recompute_requests_maxlen` = 100 000 (RD-108), y
      `event_redelivery_window_hours` copiado del broker real (RD-110)
- [ ] Evento de baja de cuenta publicado por `api-general` (DEP-12, CR-19): sin él, T058 no tiene disparo
- [ ] Decisiones abiertas: **ninguna pendiente**. `plan.md` §8 declara «Ninguna bloqueante» y
      NC-1…NC-20 **todos cerrados** (`data-model.md` §12). La lista «D1, D2, D3, D5, D6, D7, D8» que
      figuraba aquí quedó obsoleta y se retira: un DoD que exige resolver decisiones ya resueltas
      envejece hacia el ruido, y el ruido se termina tildando sin leer
