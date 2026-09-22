---
description: "Desglose de tareas ejecutables — Feature 001"
---

# Tasks: Servicio de Recomendaciones Híbridas Precomputadas

**Input**: `specs/001-recomendaciones-precomputadas/` · **Branch**: `001-recomendaciones-precomputadas`

**Actualizado**: 2026-09-22 (delta sobre la versión del 2026-09-15; T001–T050 conservan numeración e
incidencias #1–#50)

**Fuentes de verdad**:
- [**data-model.md**](./data-model.md) — **autoritativo en la capa de datos**: 16 tablas en §2,
  RD-1→RD-86 en §11, DI-1→DI-28 (**32** contando `DI-2a`…`DI-2e`) en §6, CR-1→CR-18 en §10.
  *Ante discrepancia con cualquier otro documento, manda éste.*
- [spec.md](./spec.md) — **88 requisitos base** (FR-001→FR-096, con huecos declarados), **157**
  contando sufijos · **27** criterios de éxito · **30** entradas de clarificación en **3** sesiones
  (2026-09-07, 2026-09-14, 2026-09-22) · **10** dependencias externas (DEP-1→DEP-11, con DEP-3 vacante
  a propósito y DEP-4 resuelta)
- [plan.md](./plan.md) (D1→D10)
- [checklists/requirements-contracts.md](./checklists/requirements-contracts.md) — 30/30 resueltos
- [checklists/requirements-clarify-2026-09-14.md](./checklists/requirements-clarify-2026-09-14.md) —
  **13/46 tildados, 0 bloqueantes abiertos** (los 10 🔴 se cerraron el 2026-09-22)
- [constitution v1.0.0](../../.specify/memory/constitution.md)

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
| **Declaración de gustos** obligatoria por módulo, mínimo 5 tags; sin ella se rechaza la solicitud | RD-68, RD-70 | T051+, T036, T017 |
| `tiebreak_criteria` **eliminado** de la configuración: el desempate es fijo | RD-10 | **T004** |
| `region` y `birth_date` **ambas `NOT NULL`**, ambas rechazan en la ingesta | RD-61, RD-85 | T003, T029 |
| Cuota de novedades = `floor(top_n × 0,20)`, **sin piso ni clamp** | RD-77, RD-80 | T038 |
| `top_n` acotado a **`[10, 50]`**: se rechaza por ambos extremos | RD-78 | T036 |
| Supresión verificada: aborta el recálculo en curso, con observador y escalamiento | RD-82, RD-83 | T051+ |
| **Redis primero, siempre** — regla única de orden para actualización y supresión | RD-84 (FR-080c) | T019, T020 |
| El top-N **vive solo en Redis**; ninguna tabla lo persiste | FR-080b | T022, T003 |
| Endpoint de escritura como **excepción declarada**; no calcula | RD-75 | T051+ |

## Formato: `[ID] [P?] Descripción`

- **[P]**: paralelizable — sin dependencias cruzadas ni archivos compartidos con otra tarea `[P]` activa
- **[TDD]**: la tarea se desarrolla test-first — ver *Política TDD* abajo
- **Estimación**: S (≤½ día) · M (1-2 días) · L (3-5 días)
- Toda tarea de producción declara sus tests. Una tarea sin criterio verificable no está lista para tomarse.

## Política TDD (selectiva)

**Alcance: T007–T017** — el motor de recomendación y el post-procesamiento. Son funciones puras, sin
I/O ni reloj, con entradas y salidas completamente definidas: el caso donde el test *es* la
especificación ejecutable, no su verificación posterior.

**Alcance ampliado por esta actualización: T053, T054, T055, T058, T060, T062.** El criterio no es
"tarea nueva, luego TDD" —eso sería asignar por defecto—, sino el mismo de arriba: son tareas cuyo
criterio de aceptación es **un rechazo o una invariante de conteo**, la clase de cosa que un test
escrito después acomoda al código. T054 (un tag heredado no cuenta para el mínimo), T055 (el rechazo
no agrega un sexto estado), T062 (el enum conserva cinco miembros) y T058/T060 (ordenación de
efectos observable desde afuera) sólo son verificables si el test fija el contrato antes.

**Explícitamente fuera de TDD, con motivo**: T051, T057, T063 son jobs periódicos cuyo diseño se
descubre contra el esquema real, no contra un test; T056, T059 y T061 dependen de comportamiento
numérico y de infraestructura donde el rojo previo no aporta. Para todas ellas rige la regla general:
el test debe existir y bloquear el merge.

El resto del backlog **no** es test-first. En infraestructura (T001, T018, T028) el orden aporta poco:
no se descubre el diseño de un cliente de Redis escribiendo su test antes. Ahí basta con que el test
exista y bloquee el merge.

**Razón del alcance elegido**: en T013 (filtro de edad) y T017 (batería de invariantes), un test
escrito *después* tiende a acomodarse a lo que el código ya hace. Es el modo de fallo clásico y
justamente el que no podemos permitirnos en un invariante de seguridad. Escribir el test primero
obliga a fijar el contrato antes de tener una implementación que lo condicione.

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
| **INV-1** | Cero cómputo pesado en el request path (FR-003, Principio III) | La API importa `engine/`, o abre conexión a Postgres fuera de health |
| **INV-2** | Redis nunca es fuente de verdad (FR-065) | Existe un dato solo recuperable desde Redis |
| **INV-3** | Edad y exclusión no admiten bypass (FR-049→FR-055) | Existe una ruta de datos hacia la respuesta que no atraviesa ambos filtros |
| **INV-4** | Sin acceso a DB de otros repos (Principio I) | Cualquier credencial o driver apuntando fuera de DB Recomendaciones |

## Asignación de fases (autoritativa)

Los milestones agrupan por **dominio técnico**; las fases agrupan por **entregable demostrable**. No
coinciden, y esta tabla manda sobre el encabezado de cada milestone.

| Fase | Tareas | Entregable |
|---|---|---|
| **1 — Vertical slice** | T001–T024, **T027**, **T028, T029, T030**, T033–T038, **T053, T054, T055, T063** | Ciclo completo: leer, registrar feedback, recalcular. Cierra US1, US2, US5 |
| **2 — Robustez operativa** | T025, T026, **T031, T032**, T039–T042, T046, **T049**, **T051, T052, T056, T057, T060, T061, T062** | Sobrevive a fallos. Cierra US3, US4, US6, US7 |
| **3 — Optimización y cierre** | T043–T045, T047, T048, **T050**, **T058, T059** | Rendimiento, gates de CI y gobernanza |

**Fundamento de T051–T063** *(asignadas el 2026-09-22; ninguna por proximidad numérica ni por
pertenecer al Milestone 11)*:

| Tarea | Fase | Fundamento |
|---|---|---|
| **T053** Endpoint de declaración | **1** | `FR-088` rechaza **toda** solicitud de un módulo sin declaración. Sin esta tarea, Fase 1 sirve recomendaciones a cero usuarios y **US1 no se puede demostrar**. Es condición de US1, no funcionalidad adicional |
| **T054** Herencia de tags | **1** | Parte del mismo flujo: sin ella, un usuario de ambos módulos declara dos veces desde cero y `FR-085` no se cumple en el único momento en que se ejerce |
| **T055** Rechazo por módulo | **1** | Es la mitad observable de `FR-088`. Sin ella el rechazo no existe o se confunde con un estado de resultado, rompiendo la exhaustividad de `FR-056` (DEP-6) |
| **T063** Popularidad por ventana | **1** | **Arrastrada por T038**, que está en Fase 1 por el hallazgo F2. T038 lee lo que T063 escribe; con T063 fuera, el batch corre sobre tabla vacía y `fallback` sigue inalcanzable |
| **T051** Refresco de umbrales etarios | **2** | Corrige un derivado que se desactualiza **por el paso del tiempo**, sin escritura que lo dispare. En Fase 1 el dato recién ingresado es correcto por construcción; el problema aparece con el sistema en régimen |
| **T052** Tests de ciclo de vida del ítem | **2** | Verifica el retiro, que lo produce el Data Transformer (T029, Fase 2). Un test no puede preceder al comportamiento que verifica |
| **T056** Perfil vectorial derivado puro | **2** | `FR-087` prohíbe la actualización incremental. En Fase 1 el perfil se reconstruye completo cada vez; la garantía **estructural** de que no exista un camino incremental es endurecimiento |
| **T057** Purga de señales | **2** | `FR-068a` exige retención finita, y el horizonte supera toda ventana operativa (`FR-068b`). No hay nada que purgar hasta que el sistema acumule historia |
| **T060** Disparador por conteo | **2** | `FR-080a` optimiza **cuándo** se recalcula. En Fase 1 el recálculo se dispara por evento (T023): funciona, sin la economía del umbral |
| **T061** Ponderación regional | **2** | `FR-090` la declara desactivable y `FR-090a` la arranca en intensidad mínima (`0,1`). Con factor neutro el resultado es idéntico a no segmentar, de modo que Fase 1 es demostrable sin ella. Cierra **US7** |
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
> - **F8** — T036 confirmada en Fase 1: es lo que cierra el ciclo de US2.

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

# FASE 1 — Vertical slice

> **Objetivo**: servir top-N precomputado end-to-end **y cerrar el ciclo de recálculo**.
> Cierra US1, US2, US5. Incluye T023, T024, T027 (Milestone 5), **T028, T029, T030 (Milestone 6)**,
> T033–T038 (Milestone 7) y **T053, T054, T055, T063 (Milestone 11)**.
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

**Descripción**: crear el árbol de `plan.md` §Source Code con tres entrypoints (`api`, `worker`,
`transformer`) más el job batch. `engine/` queda como librería pura sin I/O.

**Archivos**: `src/recomendaciones/{api,engine,config,worker,transformer,batch,storage,observability,shared}/`,
`pyproject.toml`, `tests/{unit,integration,contract,invariants}/`

**Criterios de aceptación**:
- [ ] Los tres entrypoints arrancan de forma independiente y fallan con error explícito si falta configuración
- [ ] `engine/` no declara dependencias de red, DB ni reloj: verificable por inspección de imports
- [ ] `pip install -e .` + `pytest --collect-only` termina sin error de importación

**Tests**: `tests/unit/test_layout.py` — cada paquete es importable y `engine/` no importa `storage/`, `api/` ni librerías de I/O.

---

### T002 — Configuración por entorno y gestión de la API key interna

**Descripción**: carga de configuración por entorno con la API key interna **inyectada desde el
entorno, nunca en repo**. La credencial es válida en un único entorno (FR-059).

**Archivos**: `src/recomendaciones/config/settings.py`, `.env.example`, `src/recomendaciones/api/deps.py`

**Dep.**: T001

**Criterios de aceptación**:
- [ ] Arranque falla si la API key no está presente — no hay default (FR-054)
- [ ] La key incluye el identificador de entorno; una key de otro entorno se rechaza (FR-059)
- [ ] El rechazo devuelve `401` genérico, sin revelar si la key es inválida o de otro entorno
- [ ] Ningún valor de credencial aparece en logs ni en la respuesta de `/health`
- [ ] `INV-4`: no existe cadena de conexión a DB fuera de DB Recomendaciones

**Tests**: `tests/unit/test_settings.py` — ausencia de key → fallo de arranque; key de otro entorno → rechazo; `repr()` del settings enmascara secretos.

---

### T003 — Esquema DB Recomendaciones + Alembic

**Descripción**: las **16 tablas de `data-model.md` §2** con pgvector —contadas sobre sus 14
subsecciones: §2.3 agrupa `tags` + `item_tags` y §2.13 agrupa `vocab_versions` + `vocab_version_tags`—.
`items.age_rating` es `NOT NULL` con default **no-apto** (FR-051): el esquema hace imposible representar
un ítem sin clasificación tratable como apto.

> **Corrección 2026-09-22**: decía «las 10 tablas de `plan.md` §2». Son **16**, y la fuente es
> `data-model.md` §2, no `plan.md` §2 —que delega en aquel—. Siete tablas **no se mencionaban ni una vez
> en todo `tasks.md`**: `user_declared_tags`, `tag_modules`, `vocab_versions`, `vocab_version_tags`,
> `item_popularity`, `user_exclusions` y `engine_config_versions`.

**Archivos**: `src/recomendaciones/storage/db/models.py`, `migrations/versions/*`, `alembic.ini`

**Dep.**: T001

**Criterios de aceptación**:
- [ ] Las **16** tablas existen con sus claves e índices; `item_vectors.vector` es pgvector
- [ ] `users`: `birth_date NOT NULL`, **`region NOT NULL` sin default** (FR-079, RD-61, RD-85),
      `max_age_ordinal`, `age_derived_at`, `age_config_version`. **Sin** `max_age_rating` (RD-2) y
      **sin** `age_resolution`
- [ ] `item_vectors`: `vocab_version` **en la PK** (RD-22) y `NOT NULL` (FR-010f)
- [ ] `items.age_rating` es `NOT NULL` y su default es el valor más restrictivo del catálogo
- [ ] `item_popularity`: **PK compuesta `(item_id, config_version)`** (RD-12, RD-13)
- [ ] `user_exclusions`: **sin `is_permanent`**, con FK **`RESTRICT`** hacia `items` (RD-35)
- [ ] `engine_config_versions`: **trigger de inmutabilidad** (RD-37)
- [ ] `user_declared_tags`: PK `(user_id, module, tag_name)`, FK `user_id` **`ON DELETE CASCADE`** y FK
      `tag_name` **`ON DELETE RESTRICT`** (§2.14) — la asimetría es deliberada: un tag no puede
      desaparecer del catálogo dejando declaraciones colgadas en silencio
- [ ] `tag_modules`, `vocab_versions`, `vocab_version_tags` existen con sus claves (§2.12, §2.13)
- [ ] `user_profiles` admite exactamente los módulos `peliculas`, `juegos`, `general` (constraint)
- [ ] `processed_events.event_id` es único (FR-011)
- [ ] `user_signals.origin_interaction_id` es `NOT NULL UNIQUE` (DEP-8, DI-21)
- [ ] **Toda FK declara su política `ON DELETE`.** Es criterio explícito del documento, que registra
      **cuatro omisiones históricas** (RD-19, RD-31, RD-35, RD-43): una FK sin política no es un olvido
      menor, es el patrón que más veces se repitió
- [ ] `upgrade` y `downgrade` se aplican limpio sobre base vacía y sobre base poblada
- [ ] `INV-2`: toda información necesaria para recalcular un top-N reside acá. **Matiz de FR-080b**: el
      top-N *resultante* **no** se persiste —vive solo en Redis y se recomputa (§3.3)—; lo que reside
      acá son sus **insumos**

**Tests**: `tests/integration/test_migrations.py` (testcontainers) — ciclo upgrade/downgrade/upgrade; insertar ítem sin `age_rating` viola constraint; insertar perfil con módulo inválido viola constraint.

---

### T004 [P] — Configuración versionada del motor + loader validante

**Descripción**: `v1.yaml` con los valores de D4 y un loader que valida rangos y **rechaza cualquier
configuración que desactive un filtro obligatorio** (FR-054). `config_version` es el hash del archivo.

**Archivos**: `src/recomendaciones/config/engine_config/v1.yaml`, `src/recomendaciones/config/loader.py`

**Dep.**: T001

**Contenido de `v1.yaml`** — inventario autoritativo en `data-model.md` §4: `alpha: 0.5`, `beta: 0.3`,
`gamma: 0.2`, `k: 20`, `lambda_mmr: 0.7`, `peso_like: 1.0`, `peso_dislike: -1.0`, peso de consumo `0.3`
(RD-73), **`top_n_min: 10`**, `top_n_default: 20`, `top_n_max: 50` (RD-78), `age_rating_catalog`,
`popularity_window_days`, **`popularity_confidence_z: 1.96`** (RD-53),
**`fallback_new_item_quota_ratio: 0.20`** (RD-77, RD-80), `diversity_max_cluster_share`,
**`declared_tags_min: 5`** (RD-68), **`region_weight_factor: 0.1`** (RD-79),
**`collab_min_neighbors: 10`** (RD-84), `vocab_regeneration_policy`.

> **`tiebreak_criteria` ya no va.** Estaba en la lista anterior y **RD-10 lo eliminó del esquema**: el
> desempate es fijo y determinista, no configurable.

**Parámetro operativo, fuera de este archivo** (RD-46): el umbral de recálculo por conteo de
interacciones (`interaction_recalc_threshold`, valor inicial **10** — FR-080a, RD-63). No altera el
valor del top-N, solo **cuándo** se lo recomputa.

**Criterios de aceptación**:
- [ ] `alpha+beta+gamma` fuera de `1.0±ε` → fallo de arranque con mensaje que nombra el campo (FR-027)
- [ ] Cualquier peso fuera de `[0,1]` → fallo de arranque
- [ ] Una clave que intente desactivar el filtro de edad o de exclusión → fallo de arranque (FR-054)
- [ ] `age_rating_catalog` es la **única** fuente de valores válidos (FR-053); no hay constantes de rating en código
- [ ] **El loader RECHAZA `tiebreak_criteria`** si aparece: fue eliminado del esquema por RD-10.
      El desempate sigue sin depender del orden de iteración (FR-070), pero por diseño fijo, no por
      configuración
- [ ] `region_weight_factor` valida `0 <= x < 1` — **límite inferior INCLUSIVO** (FR-081b, corregido por
      RD-76: excluirlo volvía **irrepresentable** el valor neutro y la configuración de `v1` no habría
      podido cargarse) y superior **estricto** (equivale al filtro duro que FR-081a prohíbe)
- [ ] `0 < fallback_new_item_quota_ratio < 1` y `10 <= top_n_min <= top_n_default <= top_n_max`
- [ ] `declared_tags_min` y `collab_min_neighbors` son enteros positivos y están presentes
- [ ] **Una versión desactivada no puede reactivarse** (DI-24): el loader rechaza el intento
- [ ] `config_version` es determinista: mismo archivo → mismo hash, en cualquier máquina
- [ ] **Deuda del prototipo resuelta**: no queda ninguna constante del motor hardcodeada

**Tests**: `tests/unit/test_config_loader.py` — tabla de configuraciones inválidas (suma ≠ 1, peso negativo, filtro desactivado, rating fuera de catálogo, tiebreak vacío), cada una debe fallar; hash reproducible entre dos cargas.

---

### T005 [P] — Modelo de dominio compartido y errores tipados

**Descripción**: tipos del dominio y jerarquía de errores que la API traduce a códigos HTTP. Incluye
el enum de `result_type` con los cinco estados de FR-056.

**Archivos**: `src/recomendaciones/shared/domain.py`, `src/recomendaciones/shared/errors.py`

**Dep.**: T001

**Criterios de aceptación**:
- [ ] `ResultType` tiene exactamente cinco valores y es cerrado (FR-056, FR-057)
- [ ] `SignalType` distingue `like`, `dislike`, `consumo` (FR-062) — sin valor por defecto
- [ ] Cada error declara su código HTTP; no hay `Exception` genérica escapando a la API
- [ ] Los tipos no dependen de SQLAlchemy ni de Redis

**Tests**: `tests/unit/test_domain.py` — exhaustividad del enum; construir una señal sin tipo falla.

---

### T006 [P] — Test de arquitectura: `api/` no importa `engine/`

**Descripción**: convertir INV-1 en un test que falla en CI. Es la única defensa automatizable contra
que alguien "resuelva" una latencia calculando en línea.

**Archivos**: `tests/unit/test_architecture.py`

**Dep.**: T001

**Criterios de aceptación**:
- [ ] Falla si cualquier módulo bajo `api/` importa, directa o transitivamente, `engine/`
- [ ] Falla si `engine/` importa `storage/`, `httpx`, `redis` o `sqlalchemy`
- [ ] Falla si el entrypoint de la API abre una conexión a DB fuera del health check
- [ ] El mensaje de fallo nombra el import ofensor y cita FR-003
- [ ] **SC-012** — 0 conexiones directas a bases de datos de otros repos y 0 rutas de acceso desde frontends. El test de arquitectura es el único lugar donde esto se verifica estructuralmente y no por inspección

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
- [ ] El vocabulario es único: un vector de película y uno de juego son comparables (FR-010d)
- [ ] **No existe** camino de código que construya un espacio por módulo (corrige P5 del prototipo)
- [ ] Todo vector emitido lleva `vocab_version`; comparar vectores de versiones distintas lanza error (FR-010f)
- [ ] El vocabulario es determinista: mismo catálogo → mismo espacio, mismo orden de dimensiones
- [ ] Función pura: sin I/O, sin reloj
- [ ] **SC-016** — 100 % de las actividades sobre ítems con al menos un tag compartido propaga el recálculo

**🔴 Paso 1 — Rojo** (`tests/unit/test_vocabulary.py`, commit propio):
determinismo con dos órdenes de entrada distintos; comparar vectores de `vocab_version` distinta
lanza error; un tag presente solo en un módulo sigue teniendo dimensión en el espacio común.

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de espacio común es el que fija el diseño:
escrito primero, hace imposible «resolverlo» con un vocabulario por módulo (P5 del prototipo).

---

### T008 [TDD] — Similitud coseno y construcción de perfil

**Descripción**: coseno acotado a `[-1,1]` y perfil de usuario L2-normalizado (FR-022c). **Solo likes
y dislikes construyen el perfil; el consumo no lo altera** (FR-022b, corrige P1 del prototipo).

**Archivos**: `src/recomendaciones/engine/similarity.py`, `src/recomendaciones/engine/profile.py`

**Dep.**: T007

**Criterios de aceptación**:
- [ ] El coseno nunca sale de `[-1,1]`, incluso con error de punto flotante
- [ ] Vector nulo → similitud 0, sin división por cero
- [ ] El perfil queda L2-normalizado (FR-022c)
- [ ] Una señal de tipo `consumo` **no modifica** el vector de perfil (FR-022b)
- [ ] `like` refuerza y `dislike` penaliza, con magnitudes de configuración (FR-029a-d)
- [ ] Ante señales contradictorias, gana la más reciente por `occurred_at` (FR-029d)
- [ ] El perfil `general` se construye agregando pesos por tag sobre ambos módulos

**🔴 Paso 1 — Rojo** (`tests/unit/test_profile.py`, commit propio): property-based — norma ≈ 1 para
cualquier conjunto no vacío de señales; una señal `consumo` **no altera** el vector; un like posterior
revierte un dislike previo; vector nulo → similitud 0 sin excepción; coseno siempre en `[-1,1]`.

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de `consumo` codifica la decisión Q3 antes de
que exista código que pueda contradecirla.

---

### T009 [P] [TDD] — Señal content-based

**Descripción**: puntuar candidatos por similitud entre el perfil del módulo y el vector del ítem.

**Archivos**: `src/recomendaciones/engine/content.py`

**Dep.**: T008

**Criterios de aceptación**:
- [ ] Score en rango acotado y comparable con las otras dos señales
- [ ] Perfil vacío (usuario sin señales) → señal neutra, sin excepción
- [ ] Función pura, determinista con semilla fija
- [ ] Vectores con `vocab_version` distinta → error, no resultado silencioso

**🔴 Paso 1 — Rojo** (`tests/unit/test_content.py`): usuario con perfil de terror puntúa más alto un
ítem de terror; perfil vacío → señal neutra sin lanzar; vectores de `vocab_version` distinta → error.

**🟢 Paso 2 — Verde**: implementar hasta pasar.

---

### T010 [P] [TDD] — Señal colaborativa (k vecinos)

**Descripción**: k vecinos más similares (k=20, D4) y agregación de sus preferencias.

**Archivos**: `src/recomendaciones/engine/collaborative.py`

**Dep.**: T008

**Criterios de aceptación**:
- [ ] `k` proviene de configuración versionada, no de constante (FR-025)
- [ ] Menos de `k` usuarios disponibles → usa los que hay, sin fallar
- [ ] Cero vecinos → señal neutra, no error
- [ ] La selección de vecinos es determinista ante empates de similitud (FR-070)
- [ ] Función pura: recibe la matriz de perfiles, no la consulta

**🔴 Paso 1 — Rojo** (`tests/unit/test_collaborative.py`): con k=3 y solo 2 usuarios no falla; cero
vecinos → señal neutra; empate de similitud resuelve idéntico en 100 ejecuciones con orden barajado.

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de empate escrito primero fuerza a definir
el criterio de desempate (FR-070) en vez de heredar el orden de iteración.

---

### T011 [P] [TDD] — Señal cross-module

**Descripción**: boost desde el perfil general del módulo opuesto, normalizado a `[-1,1]`. Es la
señal que sostiene el cold start cruzado (US4).

**Archivos**: `src/recomendaciones/engine/cross_module.py`

**Dep.**: T008

**Criterios de aceptación**:
- [ ] El boost está normalizado a `[-1,1]`, comparable con las otras señales
- [ ] Usuario sin actividad en el módulo opuesto → boost 0, no error
- [ ] El boost se calcula sobre el vocabulario compartido (posible gracias a T007)
- [ ] Un usuario con solo actividad en películas recibe recomendaciones no triviales en juegos (SC-010)

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
- [ ] Los pesos se leen de configuración; **cero constantes numéricas** en el módulo (FR-025)
- [ ] El resultado es idéntico entre ejecuciones con la misma entrada y `config_version` (SC-021)
- [ ] El desempate es determinista y **nunca** usa el orden de iteración (FR-070).
      ⚠️ **Corregido el 2026-09-22**: este criterio exigía leer `tiebreak_criteria` de configuración,
      parámetro que **RD-10 eliminó del esquema** y que T004 ahora manda rechazar en el loader. El
      criterio pedía usar algo que el sistema ya no acepta
- [ ] El `config_version` usado viaja en la salida del scoring, no se pierde
- [ ] **Los candidatos se restringen a `items.status = 'available'`** (FR-072, §4.4 punto 1), vía
      `WHERE status = 'available'` sobre `idx_items_candidates`. Un ítem retirado no entra al
      ranking: excluirlo después sería reordenar una lista ya contaminada
- [ ] **SC-021** queda verificado por el test de reproducibilidad de esta tarea

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
- [ ] `age_rating` ausente, nulo, vacío o **fuera del catálogo** → ítem **no apto** (FR-051)
- [ ] El catálogo de ratings viene de configuración versionada (FR-053) — sin `dict` hardcodeado
- [ ] **No existe** parámetro, flag ni rama que desactive el filtro (FR-054)
- [ ] Un rating desconocido nuevo (p. ej. `"NC-17"` sin declarar) se filtra, no se admite
- [ ] **SC-002** — 0 % de ítems que violen el filtro de edad. Acá se implementa; T017 y T052 lo ejercitan de forma exhaustiva

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
- [ ] Los cuatro orígenes de exclusión se aplican
- [ ] Conjunto de exclusión **no disponible** → se rechaza la solicitud, nunca se sirve sin filtrar (FR-050)
- [ ] La resolución señal→exclusión es determinista y auditable
- [ ] **Deuda del prototipo resuelta**: el conjunto de exclusión expone una interfaz pública de consulta; ningún llamador accede a sus atributos internos
- [ ] `INV-2`: las exclusiones se derivan de Postgres; Redis solo las cachea
- [ ] **SC-003** y **SC-018** — 0 % de ítems del conjunto de exclusión y 0 % de ítems con señal registrada en el top-N

**🔴 Paso 1 — Rojo** (`tests/invariants/test_exclusion.py` + `tests/unit/test_exclusion_api.py`):
ningún ítem excluido aparece en ninguno de los cinco `result_type`; like posterior revierte dislike;
consumo no se revierte; conjunto no disponible → se rechaza la solicitud; el batch no accede a
atributos privados del conjunto de exclusión.

**🟢 Paso 2 — Verde**: implementar hasta pasar. El test de acceso privado escrito primero fuerza a
diseñar la interfaz pública en vez de agregarla como refactor posterior (deuda del prototipo).

---

### T015 [TDD] — Diversificación MMR

**Descripción**: MMR con `lambda_mmr=0.7` (D4) sobre el espacio de tags. La restricción dura: **MMR
selecciona de un conjunto ya filtrado y no puede reintroducir nada** (FR-031).

**Archivos**: `src/recomendaciones/engine/postprocess.py`

**Dep.**: T012

**Criterios de aceptación**:
- [ ] La salida de MMR es un **subconjunto** de su entrada — verificado como aserción, no por convención
- [ ] `lambda_mmr` viene de configuración versionada
- [ ] La diversidad se mide como proporción máxima del top-N atribuible a un cluster (FR-071)
- [ ] Con `lambda=1` el orden coincide con el de relevancia pura (caso degenerado correcto)
- [ ] Determinista ante empates (FR-070)
- [ ] **SC-011** — ningún top-N concentra más del porcentaje máximo acordado de ítems de un mismo atributo

**🔴 Paso 1 — Rojo** (`tests/unit/test_mmr.py`): property-based — `set(salida) ⊆ set(entrada)` para
toda entrada; con `lambda=1` el orden coincide con relevancia pura; la diversidad medida mejora
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
- [ ] El orden está garantizado estructuralmente: no es posible invocar MMR antes de los filtros
- [ ] La función expone una sola entrada pública; las etapas no son invocables sueltas desde fuera
- [ ] Cada etapa registra cuántos candidatos descartó, para auditoría
- [ ] Conjunto vacío tras filtrar → resultado vacío explícito, nunca relleno con no aptos (FR-033)

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
- [ ] Cubre el producto cartesiano `age_rating` × franja etaria
- [ ] Cubre cada uno de los cuatro orígenes de exclusión
- [ ] Cubre los cinco `result_type` (FR-056) — incluido el respaldo y el obsoleto. **El rechazo por
      falta de declaración NO es un sexto estado** (FR-088): es precondición incumplida y se verifica
      como tal, antes de la precedencia
- [ ] **Cubre los 32 invariantes vigentes de `data-model.md` §6** (DI-1→DI-28, contando `DI-2a`…`DI-2e`),
      o declara por escrito cuáles quedan fuera y por qué
- [ ] **DI-28 incluido y con test propio**: un usuario con módulo declarado tiene al menos
      `declared_tags_min` filas **propias** en `user_declared_tags` —sin contar las heredadas por
      FR-085—. Es el **único invariante que el esquema no sostiene**: no hay restricción de tabla que
      exprese un mínimo de filas, de modo que su cumplimiento depende **enteramente** de este test
- [ ] **DI-10 con test propio**: retirar un ítem presente en `reco:*` **y** en `fallback:*` → la
      lectura siguiente no lo contiene. Debe cubrir **los tres puntos de §4.4** —selección, respaldo
      y guarda del request path—, no uno: cada uno es un camino distinto por el que el ítem llega al
      usuario, y verificar solo el primero deja vivos los otros dos (FR-072)
- [ ] **DI-11 con test propio**: retirar un ítem con señales → `user_signals` conserva las filas y
      los perfiles **no cambian**. El retiro es lógico (FR-073); si el perfil cambiara, un hecho
      ajeno al usuario estaría alterando sus recomendaciones
- [ ] Incluye valores límite: exactamente la edad mínima, un día antes, un día después
- [ ] Es property-based, no solo por ejemplos
- [ ] **SC-002 y SC-003 quedan verificados acá**: 0 % de violaciones del filtro de edad y 0 % de
      ítems del conjunto de exclusión, en cualquier respuesta emitida. Son los dos invariantes de
      seguridad de US5 y esta es la tarea que los hace demostrables
- [ ] **SC-018** verificado acá: 0 % de ítems con like, dislike o consumo aparece en el top-N
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

### T018 — Cliente Redis y esquema de claves

**Descripción**: las seis familias de claves de `plan.md` §2 con sus TTL (D5). `config_version` forma
parte de la clave, de modo que resultados de versiones distintas conviven sin colisionar.

**Archivos**: `src/recomendaciones/storage/cache/keys.py`, `client.py`, `ttl.py`

**Dep.**: T002, T004

**Criterios de aceptación**:
- [ ] Las claves se construyen por función tipada; **no hay concatenación de strings ad-hoc**
- [ ] `config_version` está en la clave de `reco:` **y también en la de `reco:stale:`** (hallazgo F3):
      un resultado obsoleto de una configuración anterior nunca debe servirse bajo la versión vigente
- [ ] Los TTL vienen de configuración (FR-068), no de constantes
- [ ] `filters:{user_id}` tiene TTL **más corto** que `reco:` — corrige P4 del prototipo, donde compartían 7 días
- [ ] **Deuda del prototipo resuelta**: caché en memoria reemplazada por Redis persistente
- [ ] `INV-2`: no hay dato cuya única copia esté en Redis
- [ ] Existe la familia **`retired:{module}`** (§3.1), usada como guarda del request path por T037
- [ ] Ese set contiene **solo los ítems retirados en los últimos `TTL_STALE` + 1 día** (RD-39), no
      el histórico completo. La cota no es heurística: un ítem retirado hace más de `TTL_STALE` no
      puede estar en ninguna entrada de caché viva
- [ ] La ventana **se deriva de `TTL_STALE`**, no es constante independiente. **DI-25** verifica el
      acoplamiento: subir `TTL_STALE` sin subir la ventana haría fallar la guarda **en silencio**

**Tests**: `tests/unit/test_cache_keys.py` — colisión imposible entre módulos, entre `config_version`
y entre vigente/obsoleto; una entrada obsoleta de `v1` no es legible desde `v2`.
`tests/integration/test_redis.py` — TTL efectivos; `filters:` expira antes que `reco:`.

---

### T019 — Escritura del top-N con score y `config_version`

**Descripción**: serializar el resultado con ítems, score, rank, `config_version` y `computed_at`.

**Archivos**: `src/recomendaciones/storage/cache/repository.py`

**Dep.**: T018, T016

**Criterios de aceptación**:
- [ ] Cada entrada persiste `config_version` y `computed_at` (trazabilidad exigida por Q4)
- [ ] La escritura del top-N vigente y su copia obsoleta es consistente entre sí
- [ ] Serialización y deserialización son simétricas — round-trip exacto
- [ ] Una entrada escrita con una `config_version` retirada no se sirve como vigente
- [ ] **SC-004** — 100 % de los top-N servidos incluyen la versión de configuración del motor

**Tests**: `tests/integration/test_cache_repository.py` — round-trip; la respuesta permite reconstruir con qué configuración se generó.

---

### T020 — Política de cache miss y señalización de recálculo

**Descripción**: implementar la máquina de estados de FR-056 con **precedencia estricta**: pendiente →
sin candidatos → respaldo → obsoleto → vigente. Ante miss, emitir señal de recálculo con supresión
(`recompute:lock`) para no disparar N señales por el mismo usuario.

**Archivos**: `src/recomendaciones/api/services/read_service.py`, `src/recomendaciones/storage/cache/recompute.py`

**Dep.**: T019

**Criterios de aceptación**:
- [ ] Los cinco estados son mutuamente excluyentes; la precedencia se aplica en el orden de FR-056
- [ ] Respaldo vacío tras filtrar se reporta como **sin candidatos**, no como respaldo (FR-056)
- [ ] La señal de recálculo se emite a lo sumo una vez por ventana de supresión
- [ ] La lectura **nunca falla** porque el broker esté caído: la señal es fire-and-forget con fallo registrado (D7)
- [ ] `INV-1`: el miss no dispara cómputo en línea
- [ ] **SC-015** — una ráfaga de misses del mismo par (usuario, módulo) dentro de la ventana no multiplica los recálculos

**Tests**: `tests/integration/test_cache_miss.py` — 50 lecturas concurrentes en miss producen 1 sola señal; broker caído → la lectura responde igual; tabla de los cinco estados con su entrada correspondiente.

---

### T021 [P] — Comportamiento ante Redis caído

**Descripción**: distinguir *miss* (dato ausente) de *caída* (Redis inalcanzable). Ante caída: `503`
con `Retry-After`. **Prohibido** recurrir a Postgres para calcular en línea (FR-065).

**Archivos**: `src/recomendaciones/storage/cache/client.py`, `src/recomendaciones/api/deps.py`

**Dep.**: T018

**Criterios de aceptación**:
- [ ] Redis caído → `503` con `Retry-After`, nunca `200` con resultado vacío
- [ ] **No existe** ruta de fallback que consulte Postgres desde el request path (FR-065, INV-1)
- [ ] El timeout hacia Redis es explícito y configurable — no se cuelga indefinidamente
- [ ] Miss y caída producen `result_type` / código HTTP distintos y distinguibles

**Tests**: `tests/integration/test_redis_down.py` — con Redis detenido, la respuesta es 503 y no hay ninguna query a Postgres (verificado por espía de conexiones).

---

### T022 — Reconstrucción total tras pérdida de Redis

**Descripción**: job de warm-up que republica señales de recálculo **con límite de tasa** (FR-066).
El punto es evitar la avalancha auto-infligida: la reconstrucción nunca se dispara como efecto
colateral del tráfico de lectura.

**Archivos**: `src/recomendaciones/batch/warmup.py`

**Dep.**: T020

**Criterios de aceptación**:
- [ ] Es un proceso dedicado, invocable manualmente; **no** se activa por tráfico (FR-066)
- [ ] Respeta un límite de tasa configurable
- [ ] Es reanudable: interrumpirlo y relanzarlo no duplica trabajo ni pierde usuarios
- [ ] Con Redis vacío, el servicio sigue respondiendo (pendiente/respaldo) mientras reconstruye
- [ ] `INV-2`: reconstruye íntegramente desde Postgres
- [ ] **SC-008** — tras un vaciado total de la caché, 100 % de los top-N afectados se reconstruye sin intervención manual

**Tests**: `tests/integration/test_warmup.py` — flush total de Redis; el servicio no devuelve 500; el warm-up repuebla; la tasa de publicación no supera el límite.

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
| T023 | Consumo de `recomendacion.actualizar` | **1** | T003, T005 | | M |
| T024 | Idempotencia por `event_id` | **1** | T023 | | M |
| T027 | Recálculo y propagación cross-module condicional | **1** | T024, T016, T019 | | L |
| T025 | Reintentos con backoff y DLQ | 2 | T023 | | M |
| T026 | Manejo de payload inválido sin bloquear la cola | 2 | T025 | | S |

### T023 — Consumo de `recomendacion.actualizar`

**Descripción**: consumidor con validación de schema. Campos mínimos: `event_id`, `user_id`, `module`,
`item_id`, `signal_type`, `occurred_at` (FR-061).

**Archivos**: `src/recomendaciones/worker/consumer.py`, `schemas.py`

**Dep.**: T003, T005

**Criterios de aceptación**:
- [ ] Valida contra el schema antes de tocar el dominio
- [ ] `signal_type` es **obligatorio**: sin él, el evento va a DLQ — no se infiere (FR-064)
- [ ] Módulo desconocido → DLQ sin alterar ningún top-N
- [ ] `INV-4`: el worker no llama a `api-general` ni escribe fuera de su DB

**Tests**: `tests/integration/test_consumer.py` (testcontainers RabbitMQ) — evento válido se procesa; falta `signal_type` → DLQ; módulo desconocido → DLQ y ningún top-N cambia.

---

### T024 — Idempotencia por `event_id`

**Descripción**: deduplicación por `event_id` con marca en Redis (`dedupe:event:`) respaldada por
`processed_events` en Postgres. Incluye el caso de FR-069: un duplicado que llega **después** de
expirar la marca debe poder reprocesarse sin corromper estado.

**Archivos**: `src/recomendaciones/worker/idempotency.py`

**Dep.**: T023

**Criterios de aceptación**:
- [ ] Evento ya procesado → ACK sin recomputar
- [ ] La marca vive en Redis **y** en Postgres: perder Redis no rompe la idempotencia (INV-2)
- [ ] Reprocesar tras expirar la marca produce el mismo resultado, sin duplicar señales (FR-069)
- [ ] El TTL de retención es configurable (FR-068)
- [ ] **SC-005** — reprocesar el mismo evento produce un top-N idéntico

**Tests**: `tests/integration/test_idempotency.py` — mismo evento 10 veces → 1 recálculo; con la marca expirada, el reproceso converge al mismo estado.

---

### T025 — Reintentos con backoff y DLQ

**Descripción**: backoff exponencial, máximo 5 intentos, luego DLQ. Fallo solo en el módulo opuesto
→ se conserva el principal y se reencola solo el opuesto.

**Archivos**: `src/recomendaciones/worker/retry.py`, `dlq.py`

**Dep.**: T023

**Criterios de aceptación**:
- [ ] Fallo transitorio → reintento con backoff; máximo configurable (FR-068)
- [ ] Agotados los intentos → DLQ con la causa registrada
- [ ] Fallo en el módulo opuesto no revierte el módulo principal (FR-067)
- [ ] Los mensajes en DLQ conservan el payload íntegro para reproceso manual

**Tests**: `tests/integration/test_retry_dlq.py` — inyectar fallo transitorio → reintenta; fallo permanente → DLQ tras 5; fallo del opuesto → principal persistido.

---

### T026 — Manejo de payload inválido sin bloquear la cola

**Descripción**: un mensaje malformado va a DLQ **inmediatamente**, sin reintentos. Reintentar algo
que nunca va a ser válido solo bloquea la cola.

**Archivos**: `src/recomendaciones/worker/dlq.py`

**Dep.**: T025

**Criterios de aceptación**:
- [ ] Payload inválido → DLQ sin reintento, con la causa de validación
- [ ] El consumo continúa: el mensaje siguiente se procesa normalmente
- [ ] Una ráfaga de mensajes inválidos no detiene el procesamiento de los válidos
- [ ] El log incluye el `event_id` cuando es extraíble
- [ ] **SC-007** — 100 % de los eventos con payload inválido termina en dead-letter con causa registrada

**Tests**: `tests/integration/test_invalid_payload.py` — intercalar 5 inválidos entre 5 válidos: los 5 válidos se procesan, los 5 inválidos están en DLQ, cero reintentos.

---

### T027 — Recálculo y propagación cross-module condicional

**Descripción**: ejecutar motor + post-proceso y escribir Redis. Recalcular el módulo opuesto **solo
si** algún tag del ítem pertenece al vocabulario compartido (FR-010a, decisión Q2). La decisión y su
motivo quedan registrados (FR-010c).

**Archivos**: `src/recomendaciones/worker/handler.py`

**Dep.**: T024, T016, T019

**Criterios de aceptación**:
- [ ] Ningún tag compartido → **no** recalcula el opuesto (FR-010a)
- [ ] La decisión queda registrada con su motivo, auditable (FR-010c)
- [ ] Los dos módulos son unidades independientes: sin atomicidad cruzada (FR-067)
- [ ] El resultado escrito pasó por el pipeline completo de T016
- [ ] Se registra la métrica `reco_cross_module_propagation_total{propagated}`
- [ ] **SC-010** y **SC-017** — cobertura cross-module y registro del motivo en 100 % de los recálculos

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

### T028 — Cliente REST autenticado y de solo lectura

**Descripción**: cliente `httpx` hacia `api-general` con la API key interna. **Solo lectura**: el
cliente no expone verbos de mutación.

**Archivos**: `src/recomendaciones/transformer/client.py`

**Dep.**: T002

**Criterios de aceptación**:
- [ ] El cliente **no expone** POST/PUT/PATCH/DELETE — restricción estructural, no convención
- [ ] Envía la API key interna; timeouts explícitos y configurables
- [ ] `INV-4`: no hay conexión directa a la DB de `api-general`
- [ ] Los errores HTTP se traducen a errores tipados de T005

**Tests**: `tests/unit/test_transformer_client.py` — la superficie pública no tiene verbos de mutación. `tests/integration/test_no_external_writes.py` — contra un doble, cero requests no-GET.

---

### T029 — Materialización idempotente de usuarios, catálogo y actividad

**Descripción**: proyectar usuarios, catálogo y actividad a DB Recomendaciones. Idempotente:
re-ejecutar sobre los mismos datos no duplica ni altera el resultado.

**Archivos**: `src/recomendaciones/transformer/pipeline.py`

**Dep.**: T028, T003

**Criterios de aceptación**:
- [ ] Re-ejecutar la sincronización dos veces produce estado idéntico (idempotencia)
- [ ] Un ítem sin `age_rating` se materializa con el valor **más restrictivo** (FR-051)
- [ ] La actividad conserva `signal_type` y `occurred_at` (FR-062, DEP-1, DEP-2)
- [ ] Interrupción a mitad de camino deja estado consistente, no parcial e indistinguible
- [ ] **El Data Transformer NO escribe `item_popularity`, `tag_modules` ni `vocab_*`** (DI-13).
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
- [ ] **El retiro se detecta por dos vías y se aplica por una sola rama** (FR-074, RD-91): señal
      explícita del origen (CR-7) y **ausencia** del ítem en el listado (CR-8). No hay modo
      degradado: Q31 descartó la opción de operar distinto según el origen pueda o no confirmar
      completitud, porque una rama que casi nunca se ejercita es una rama rota cuando hace falta
- [ ] **La corrida aborta sin marcar retiro alguno** si no puede confirmar que el listado es
      completo (CR-9), y en particular cuando `sync_volume_delta_ratio < 0,9`. Abortar sin marcar es
      la única conducta segura: un listado truncado que se procesa retira ítems vigentes en masa
- [ ] **El retiro es lógico** (FR-073): se cambia `status`, **no** se borra la fila ni sus señales
- [ ] **SC-006** — re-ejecutar una corrida completa del Data Transformer sobre datos sin cambios deja un estado idéntico

**Tests**: `tests/integration/test_sync_idempotent.py` — doble ejecución → mismo estado; ítem sin rating → valor restrictivo; interrupción simulada → estado consistente.

---

### T030 — Vocabulario versionado y **reconciliación de vectores**

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
- [ ] El vocabulario se versiona; la versión activa es explícita y consultable
- [ ] Regenerar el vocabulario **recalcula todos los vectores afectados antes** de activar la versión (FR-010g)
- [ ] Durante la transición nunca se comparan vectores de versiones distintas (FR-010f)
- [ ] El criterio de regeneración vive en configuración versionada (FR-010g)
- [ ] Un vocabulario desactualizado degrada calidad, **nunca** corrección ni invariantes
- [ ] No requiere aprobación de `api-general`: es interno (FR-010e)
- [ ] **Reconciliación tras cada sincronización**: todo ítem **vigente**, **con al menos un tag** y
      **sin vector bajo la versión activa** recibe uno. El disparador ya **no** es solo el cambio de
      hash — un ítem nuevo con tags preexistentes no lo altera
- [ ] **El arranque desde vacío es el caso degenerado del mismo procedimiento**, no un camino
      aparte: sin versión activa se crea la primera y se vectoriza todo el catálogo vigente. Un
      camino de arranque separado sería código que corre una vez y se pudre sin que nadie lo note
- [ ] Un ítem vigente **sin tags** queda sin vector **deliberadamente** y cuenta para
      `catalog_unvectorized_ratio`: ese es el caso que la métrica debe señalar al proveedor
- [ ] Es **idempotente**: dos corridas seguidas sin cambios de catálogo no reescriben vectores

**Tests**: `tests/integration/test_vocab_transition.py` — durante la transición no existe instante con
vectores mezclados; interrumpir la transición no activa la versión.
`tests/integration/test_vector_reconciliation.py` — **ítem nuevo cuyos tags ya existen** (el caso que
el disparador por hash no veía) obtiene vector tras el sync; arranque sobre catálogo ya sincronizado
y sin versión activa vectoriza todo lo vigente con tags; ítem sin tags no obtiene vector y suma a
`catalog_unvectorized_ratio`; segunda corrida sin cambios no reescribe nada nueva a medias.

---

### T031 [P] — Registro de freshness de sincronización

**Descripción**: poblar `sync_runs` y exponer `reco_sync_last_success_timestamp`.

**Archivos**: `src/recomendaciones/transformer/pipeline.py`, `src/recomendaciones/observability/metrics.py`

**Dep.**: T029

**Criterios de aceptación**:
- [ ] Cada corrida registra inicio, fin, estado y volumen
- [ ] La métrica de freshness refleja el **último éxito**, no el último intento
- [ ] Una corrida fallida no actualiza el timestamp de éxito
- [ ] La antigüedad es consultable operativamente sin entrar a la DB
- [ ] **SC-014** — la antigüedad de la última sincronización exitosa está disponible como métrica

**Tests**: `tests/integration/test_freshness.py` — corrida fallida no mueve la métrica; corrida exitosa sí.

---

### T032 — Comportamiento ante `api-general` no disponible

**Descripción**: la caída de `api-general` degrada la **frescura**, no la disponibilidad. El servicio
sigue sirviendo con los datos materializados.

**Archivos**: `src/recomendaciones/transformer/resilience.py` (módulo propio — **hallazgo F5**: ya no
comparte `pipeline.py` con T031)

**Dep.**: T028, T031

**Criterios de aceptación**:
- [ ] `api-general` caído → la sincronización falla de forma limpia y registrada
- [ ] La API de lectura **sigue respondiendo** con los datos ya materializados
- [ ] No se corrompe ni se vacía el estado materializado
- [ ] Reintento con backoff; se alerta si la freshness supera el umbral

**Tests**: `tests/integration/test_api_general_down.py` — con el doble caído, la lectura sigue en 200 y el estado materializado queda intacto.

---

## Milestone 7 — API de lectura

> Todo este milestone es **Fase 1**. T038 se adelantó desde Fase 2 (hallazgo F2).

| ID | Tarea | Dep. | [P] | Est. |
|---|---|---|---|---|
| T033 | Endpoint de top-N con paginación | T020, T005 | | M |
| T034 | Autenticación por API key interna y no alcanzabilidad desde frontends | T002, T033 | | M |
| T035 | Errores tipados y contrato estable | T033, T005 | | S |
| T036 | Registro de feedback y emisión del evento de recálculo | T033, T003 | | M |
| T038 | Batch de top-N de respaldo | T012, T015, T003 | [P] | M |
| T037 | Filtrado de salida sobre el respaldo (acotado) | T033, T013, T014, **T038** | | M |

### T033 — Endpoint de top-N con paginación

**Descripción**: `GET /internal/v1/recommendations/{user_id}` cache-first, con `limit` y `cursor`.

**Archivos**: `src/recomendaciones/api/routes/recommendations.py`, `schemas.py`

**Dep.**: T020, T005

**Criterios de aceptación**:
- [ ] La respuesta incluye `result_type`, `computed_at`, `config_version`, `items[]`, `next_cursor`
- [ ] `limit` acotado por `top_n_max` de configuración; exceso → `422`
- [ ] La paginación es estable: la misma consulta con el mismo cursor devuelve lo mismo
- [ ] `INV-1`: no importa `engine/`, no consulta Postgres en el camino normal (verificado por T006)
- [ ] `config_version` de la respuesta permite trazar con qué configuración se generó
- [ ] **SC-009** — 0 % de los requests de lectura ejecuta scoring, similitud o diversificación. Lo
      verifica `tests/integration/test_no_heavy_computation` de esta tarea, apoyado en el test
      estructural de T006. La guarda de vigencia de T037 **no** cuenta como excepción: es diferencia
      de conjuntos, no cómputo de recomendaciones (RD-8)

**Tests**: `tests/contract/test_read_endpoint.py` — la respuesta valida contra el OpenAPI publicado; `limit` excesivo → 422. `tests/integration/test_no_heavy_compute.py` — espía de conexiones: cero queries a Postgres en el camino normal.

---

### T034 — Autenticación por API key interna y no alcanzabilidad desde frontends

**Descripción**: exigir `X-Internal-API-Key` y garantizar que FR-008 sea **verificable** (FR-060): sin
rutas públicas declaradas y restricción de red auditable.

**Archivos**: `src/recomendaciones/api/deps.py`, `main.py`

**Dep.**: T002, T033

**Criterios de aceptación**:
- [ ] Sin API key → `401`; key inválida → `401` con el **mismo** cuerpo (no es oráculo)
- [ ] Key de otro entorno → `401` (FR-059)
- [ ] La aplicación no declara ninguna ruta pública fuera de health (FR-060)
- [ ] La restricción de red está documentada y es auditable automáticamente
- [ ] **SC-012** (mitad de frontends) — 0 rutas de acceso alcanzables desde un frontend

**Tests**: `tests/contract/test_auth.py` — matriz de casos de key; test que enumera rutas y falla si alguna no exige autenticación (salvo health).

---

### T035 — Errores tipados y contrato estable

**Descripción**: traducir la jerarquía de T005 a códigos HTTP estables. El versionado del endpoint y
la definición de cambio breaking siguen FR-058.

**Archivos**: `src/recomendaciones/api/errors.py`

**Dep.**: T033, T005

**Criterios de aceptación**:
- [ ] `401` sin auth, `422` params inválidos, `503` + `Retry-After` con Redis caído
- [ ] Ninguna excepción no manejada escapa como `500` con stack trace
- [ ] Los cuerpos de error tienen forma estable y documentada
- [ ] Ningún mensaje de error revela detalles internos (rutas, versiones de librerías, SQL)

**Tests**: `tests/contract/test_errors.py` — cada error produce su código; ningún cuerpo contiene rastros internos.

---

### T036 — Registro de feedback y emisión del evento de recálculo

**Descripción**: al registrar feedback, persistir la señal **y publicar** el evento de recálculo.
Resuelve la deuda del prototipo, donde el feedback se guardaba sin disparar recálculo y el top-N
quedaba silenciosamente desactualizado.

**Archivos**: `src/recomendaciones/api/routes/feedback.py`, `src/recomendaciones/api/services/feedback_service.py`

**Dep.**: T033, T003

**Criterios de aceptación**:
- [ ] La señal se persiste en `user_signals` con `signal_type` y `occurred_at`
- [ ] Se publica el evento de recálculo tras persistir — **deuda del prototipo resuelta**
- [ ] La publicación es fire-and-forget: broker caído **no** hace fallar el registro (D7), pero se registra y se emite métrica
- [ ] `INV-1`: el endpoint no recalcula en línea
- [ ] La exclusión derivada de la señal es efectiva en la siguiente lectura ya servida

**Tests**: `tests/integration/test_feedback.py` — feedback → señal persistida + evento publicado; broker caído → 200 con métrica de fallo; tras un dislike, el ítem no reaparece.

---

### T037 — Filtrado de salida sobre el respaldo (acotado)

**Descripción**: aplicar edad y exclusión sobre el respaldo al servir (FR-033d). **Acotado a
pertenencia y comparación** sobre una lista ya ordenada y de tamaño acotado: sin similitud, sin
recomputación de scores, sin reordenamiento, sin diversificación.

**Archivos**: `src/recomendaciones/api/services/read_service.py`

**Dep.**: T033, T013, T014, **T038** (hallazgo F4 — sin el batch no existe el respaldo que esta
tarea filtra, y su test no sería significativo)

**Criterios de aceptación**:
- [ ] Se aplican edad y exclusión sobre el respaldo antes de responder (FR-036, FR-049)
- [ ] **No** hay cálculo de similitud, recomputación, reordenamiento ni diversificación (FR-033d)
- [ ] El costo es lineal sobre una lista acotada por `top_n_max`
- [ ] Respaldo que queda vacío tras filtrar → `empty_no_candidates` (FR-056)
- [ ] Conjunto de exclusión no disponible → se rechaza, no se sirve sin filtrar (FR-050)
- [ ] **Guarda de vigencia** (§4.4 punto 3, FR-072): diferencia contra el set `retired:{module}`
      antes de responder. Es el tercero de los tres puntos donde se aplica la regla, y el único que
      alcanza a un resultado **ya precomputado**: sin él, un ítem retirado se sigue sirviendo desde
      caché durante toda la vigencia de la entrada
- [ ] La guarda es **diferencia de conjuntos sobre ≤ `top_n_max`**, no cálculo: FR-003 prohíbe
      computar recomendaciones, no ejecutar guardas de corrección (RD-8)
- [ ] **Lista reducida tras las guardas → se sirve tal cual** (FR-075), con el estado que
      corresponda a su frescura. **No** se rellena con sustitutos: reponer exige seleccionar
      candidatos, que es cómputo prohibido. Solo la lista **vacía** es `empty_no_candidates`
- [ ] **SC-026** verificado acá: 0 % de respaldos servidos viola el filtro de edad
- [ ] **SC-026** y **SC-027** — 0 % de respaldos servidos viola el filtro de edad, y 100 % se marca como no personalizado

**Tests**: `tests/invariants/test_fallback_filtering.py` — menor de edad nunca recibe contenido adulto vía respaldo. `tests/unit/test_fallback_bounded.py` — el módulo no importa `engine/` ni funciones de similitud.

---

### T038 [P] — Batch de top-N de respaldo

**Descripción**: **consumidora** de `item_popularity`. Construye el conjunto de respaldo por módulo
leyendo lo que **T063 ya calculó**, lo diversifica por MMR (decisión Q5) y lo publica en
`fallback:v{cfg}:{module}`. Global por módulo, nunca por usuario.

Esta tarea **no calcula popularidad**: la lee. El reparto quedó explícito el 2026-09-22 —T063
produce, T038 consume—, tal como `data-model.md` §2.5 ya lo declaraba: «`popularity_score` →
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
- [ ] **Lee `item_popularity` bajo la `config_version` activa**, vía `idx_popularity_ranking`
      `(config_version, popularity_score DESC)`
- [ ] **Ordena por `popularity_score`**, no por `like_count` (RD-12): ordenar por el conteo bruto
      pondría arriba a los ítems con mucho volumen y mala conversión
- [ ] Reúne con `items` filtrando `status = 'available'` y agrupando por `module`. Es el costo
      declarado de RD-12, y **T050 lo perfila** en vez de asumirlo resuelto
- [ ] **La cuota de ítems nuevos** reserva `floor(top_n × fallback_new_item_quota_ratio)`
      posiciones, con ratio **0,20**, **sin mínimo absoluto** y **sin clamp a `top_n − 1`**
      (RD-80, familia FR-033a6). *Criterio traído desde T063 el 2026-09-22: la cuota opera sobre
      el resultado servido, no sobre el cálculo del puntaje*
- [ ] **El batch se construye únicamente sobre ítems vigentes** (FR-033a1, FR-072, §4.4 punto 2):
      reunión con `item_popularity` bajo `WHERE status = 'available'` (RD-12). El respaldo es lo que
      recibe exactamente la población sin resultado propio; contaminarlo con retirados afecta a
      quien menos defensa tiene
- [ ] Se computa sobre ventana temporal configurable, no sobre histórico completo (FR-033a1)
- [ ] El resultado pasa por MMR: no se concentra en el género dominante (FR-033b)
- [ ] Es global por módulo, **no** personaliza por usuario (FR-033c)
- [ ] Sin likes suficientes → respaldo vacío y respuesta `empty_no_candidates`; **no** se sustituye por otro criterio (FR-033a2)
- [ ] Se persiste en Redis **y** en tabla, para rehidratar sin recomputar (D8)
- [ ] **SC-024** y **SC-025** — 100 % de los usuarios sin actividad recibe respaldo no vacío, y el respaldo cumple el mismo umbral de diversidad de SC-011

**Tests**: `tests/integration/test_fallback_batch.py` — diversidad medida supera la del top-N sin MMR; sistema sin likes → respaldo vacío, no relleno arbitrario.

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

### T039 — Métricas Prometheus

**Archivos**: `src/recomendaciones/observability/metrics.py`

**Dep.**: T033, T027, T031

**Criterios de aceptación**:
- [ ] `reco_cache_hits_total{result_type}` discrimina los cinco estados
- [ ] `reco_request_duration_seconds` es histograma por endpoint
- [ ] `reco_recompute_total{status,module}` y `reco_recompute_duration_seconds`
- [ ] `reco_dlq_messages_total{reason}` y `reco_queue_depth`
- [ ] `reco_sync_last_success_timestamp` (freshness) y `reco_sync_duration_seconds`
- [ ] `reco_cross_module_propagation_total{propagated}`
- [ ] `reco_active_config_version` como gauge etiquetado
- [ ] Ninguna etiqueta contiene `user_id` ni datos personales (cardinalidad y privacidad)

**Tests**: `tests/integration/test_metrics.py` — cada métrica se emite tras su operación; ninguna etiqueta es de alta cardinalidad.

---

### T040 [P] — Logging estructurado con correlation ID

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

### T041 [P] — Health, readiness y liveness por servicio

**Archivos**: `src/recomendaciones/observability/health.py`, `src/recomendaciones/api/routes/health.py`

**Dep.**: T033, T023, T028

**Criterios de aceptación**:
- [ ] `liveness` no depende de dependencias externas — solo indica que el proceso vive
- [ ] `readiness` verifica Redis y Postgres; Redis caído → not ready
- [ ] `/health` expone `config_version` activa (trazabilidad de Q4)
- [ ] Ningún endpoint de salud expone secretos ni detalles internos
- [ ] Los tres entrypoints tienen su propio health

**Tests**: `tests/integration/test_health.py` — con Redis caído readiness falla y liveness no; `/health` no filtra secretos.

---

### T042 — Alertas operativas

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
- [ ] **`orphaned_exclusions_total` NO tiene alerta**: FR-068d1 la declara informativa y **sin umbral**.
      Configurarle una contradiría el requisito
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
| T049 | Materializar `contracts/` (OpenAPI + JSON Schema) | 2 | T033, T023 | | M |
| T043 | Contract testing contra `api-general` como gate de CI | 3 | T049 | | M |
| T044 | Suite de casos críticos obligatorios | 3 | T017, T027, T032, T038 | | L |
| T045 | Pipeline de CI con gates bloqueantes | 3 | T017, T043, T044 | | M |
| T050 | Pruebas de carga y verificación de SC-001 | 3 | T033, T038 | [P] | M |

### T049 — Materializar `contracts/` (OpenAPI + JSON Schema)

**Descripción**: producir los artefactos de contrato que T043 asume existentes. **Hallazgo F6**: el
plan los referenciaba pero nadie los generaba, con lo que los contract tests no habrían tenido contra
qué validar.

**Archivos**: `specs/001-recomendaciones-precomputadas/contracts/read-api.openapi.yaml`,
`contracts/recomendacion-actualizar.schema.json`, `contracts/README.md`

**Dep.**: T033 (endpoint definido), T023 (consumo definido)

**Criterios de aceptación**:
- [ ] `read-api.openapi.yaml` describe el endpoint de lectura con los cinco `result_type` (FR-056)
      y los errores de T035 (`401`, `422`, `503`)
- [ ] `recomendacion-actualizar.schema.json` declara los seis campos mínimos de FR-061 como requeridos
- [ ] `contracts/README.md` declara explícitamente que el schema del evento es **propiedad de
      `api-general`** y que esta copia es derivada (Principio II) — no es fuente de verdad
- [ ] La copia derivada registra la versión del contrato origen y su fecha de sincronización
- [ ] El OpenAPI propio se genera desde el código, no se mantiene a mano
- [ ] **SC-023** — la versión de configuración activa es consultable en tiempo de ejecución

**Tests**: `tests/contract/test_openapi_sync.py` — el OpenAPI publicado coincide con las rutas reales
de la aplicación; falla si divergen.

---

### T050 [P] — Pruebas de carga y verificación de SC-001

**Descripción**: verificar SC-001 (`spec.md:692`) — la latencia de lectura se mantiene dentro del
umbral con el catálogo a 10×. **Hallazgo F7**: era el único Success Criterion sin tarea asignada.

**Archivos**: `tests/performance/test_read_latency.py`, `tests/performance/fixtures/catalog_10x.py`,
`docs/validation/performance-report.md`

**Dep.**: T033, T038

**Criterios de aceptación**:
- [ ] Existe un generador reproducible de catálogo a 1×, 10× y volumen de usuarios equivalente
- [ ] La latencia de lectura a 10× permanece dentro del umbral declarado en SC-001
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
- [ ] El evento consumido se valida contra el schema oficial de `api-general`
- [ ] La respuesta de lectura se valida contra el OpenAPI publicado
- [ ] Existe un test que **falla si un campo requerido desaparece** del contrato
- [ ] Cubre las seis dependencias DEP-1..DEP-6
- [ ] Es gate bloqueante: contract test roto = no hay merge (Principio VI)
- [ ] **SC-013** — 100 % de los endpoints expuestos y del evento consumido pasa la validación de contrato

**Tests**: es la tarea de test. Verificación: eliminar `signal_type` del schema del doble debe hacerla fallar.

---

### T044 — Suite de casos críticos obligatorios

**Descripción**: los nueve escenarios que el plan declara exigidos. Ninguno es opcional.

**Archivos**: `tests/integration/test_critical_scenarios.py`

**Dep.**: T017, T027, T032, T038

**Criterios de aceptación** — un test por escenario, cada uno con aserción explícita:
- [ ] **Menor de edad** → cero contenido no apto en los cinco `result_type`
- [ ] **Exclusión estricta** → cero ítems excluidos en cualquier respuesta
- [ ] **Cold start puro** → respaldo diversificado, o `empty_no_candidates` si no hay datos
- [ ] **Cold start cruzado** → actividad solo en películas produce juegos no triviales (SC-010)
- [ ] **Cache miss** → estado correcto por precedencia + una sola señal de recálculo
- [ ] **Evento duplicado** → un solo recálculo
- [ ] **Payload inválido** → DLQ sin bloquear la cola
- [ ] **Catálogo sin candidatos** → vacío explícito, nunca relleno con no aptos
- [ ] **Dependencia externa caída** → Redis: 503 sin fallback a DB; broker: la lectura sigue; `api-general`: se degrada la frescura, no la disponibilidad
- [ ] **SC-019** y **SC-020** — un dislike reduce de forma medible el score de los ítems que comparten sus tags, y un like posterior revierte el efecto

**Tests**: es la tarea de test. Cada escenario debe ser identificable por nombre en el reporte de CI.

---

### T045 — Pipeline de CI con gates bloqueantes

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
| T048 | Validación final contra el checklist y DoD | T045, T046, T047 | | M |

> **T046 se movió al Milestone 8 (Fase 2)**. Un runbook escrito mientras el sistema todavía sorprende
> es sustancialmente mejor que uno escrito de memoria dos meses después. Ver T046 arriba.


### T047 [P] — Documento de campos requeridos a `api-general`

**Descripción**: el documento único que exige FR-063, índice de **DEP-1…DEP-11** y de **CR-1…CR-18**.
**No sustituye** la documentación oficial de `api-general` (Principio II): es la lista de lo que este
repo necesita.

**Archivos**: `docs/contracts/required-fields.md`

**Dep.**: T043

**Criterios de aceptación**:
- [ ] Enumera cada campo requerido, su FR asociado y el impacto de su ausencia
- [ ] Cubre las **10 dependencias vigentes**: DEP-1, DEP-2, DEP-5, DEP-6, DEP-7, DEP-8, DEP-9, DEP-10,
      DEP-11. **DEP-4** se marca como **resuelta internamente** (la popularidad se deriva localmente) y
      **DEP-3** como **vacante a propósito**: el identificador fue retirado y **no se reasigna**
      > La versión anterior de este criterio citaba **DEP-3 como si existiera** y se detenía en DEP-6,
      > ignorando las cinco posteriores.
- [ ] Cubre **CR-1…CR-18**, marcando **CR-13 y CR-14 como retiradas** (RD-50)
- [ ] Señala cuál es la dependencia de mayor severidad y por qué: **DEP-10** es la única cuyo
      incumplimiento deja al sistema **sin ningún usuario atendible**, por encadenamiento con FR-088
- [ ] Declara explícitamente que la fuente de verdad del contrato es `api-general`
- [ ] Está enlazado desde el README y desde los contract tests

**Tests**: test que falla si el documento no menciona todos los campos que los contract tests validan.

---

### T048 — Validación final contra el checklist y DoD

**Descripción**: producir la **matriz de trazabilidad ítem → evidencia**: cada uno de los 30 ítems
del checklist mapeado al test o archivo concreto que hoy lo sostiene. No es burocracia de cierre: es
lo que permite, dentro de seis meses, saber si un refactor rompió un invariante acordado sin tener
que reconstruir el razonamiento desde cero.

**Archivos**: `docs/validation/traceability-matrix.md`, `tests/contract/test_traceability.py`

**Dep.**: T045, T046, T047, T050

**Criterios de aceptación**:
- [ ] La matriz cubre los 30 ítems del checklist, cada uno con su evidencia: ruta de test, ruta de
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

### T051 — Job `age_threshold_refresh` (refresco de derivados etarios)

**Descripción**: la edad del usuario no es un dato almacenado sino un derivado de `birth_date`, y
cambia sin que nadie escriba nada. Un derivado que sólo se recalcula ante escrituras nunca se
recalcula para este caso. El job recorre **dos criterios de selección separados**, no uno: (A) los
usuarios cuyo umbral etario cambió por el mero paso del tiempo (§7.5 causa A), y (B) los usuarios
cuya `birth_date` fue corregida. Unificarlos en una sola consulta perdería el caso A, que no deja
rastro de escritura.

**Archivos**: `src/recomendaciones/jobs/age_threshold_refresh.py`,
`src/recomendaciones/jobs/scheduler.py`

**Dep.**: T003, T023, T039

**Criterios de aceptación**:
- [ ] Los dos criterios de selección se consultan por separado y se registran por separado
- [ ] El cruce de umbral se calcula contra `birth_date`, nunca contra un campo de edad materializado
- [ ] Un usuario que cruza el umbral sin ninguna escritura queda seleccionado por el criterio A
- [ ] El job invalida la caché del usuario afectado en el mismo acto (FR-080, FR-080c: Redis primero)
- [ ] Emite la métrica de **liveness** al completar cada corrida (ver T042: la métrica de antigüedad
      no dispara cuando el job está muerto, porque nada la actualiza)
- [ ] Es idempotente: dos corridas seguidas no producen recálculos duplicados

**Tests**: `tests/integration/test_age_threshold_refresh.py` — usuario que cumple años sin escritura
alguna es recalculado; corrección de `birth_date` hacia atrás también; corrida sobre conjunto vacío
emite igualmente la métrica de liveness.

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

**Archivos**: `src/recomendaciones/api/routes/declaraciones.py`,
`src/recomendaciones/services/declaracion.py`, `contracts/openapi.yaml`

**Dep.**: T003, T049

**Criterios de aceptación**:
- [ ] Persiste en `user_declared_tags` con PK `(user_id, module, tag_name)` (FR-082)
- [ ] Rechaza declaraciones con menos de `declared_tags_min` = 5 tags propios (FR-083)
- [ ] **No impone máximo** de tags
- [ ] Responde de forma **síncrona** confirmando la persistencia (FR-089a): una confirmación diferida
      habilitaría el rechazo inmediato de FR-088 sobre un dato ya entregado por el usuario
- [ ] **No dispara el motor de recomendación** ni cómputo alguno (FR-089b); se verifica por ausencia
      de llamada, no por tiempo de respuesta
- [ ] Sólo los tags del vocabulario vigente son aceptables (DEP-10)
- [ ] **La declaración se exige al primer ingreso al módulo, no al crear la cuenta** (FR-084). El
      endpoint acepta declaración para **un** módulo por llamada y **no** exige el otro: un usuario
      que solo use recomendaciones de juegos nunca declara tags de películas, y la falta de
      declaración en un módulo **no** impide operar en el otro

**Tests**: `tests/contract/test_declaracion_endpoint.py`; `tests/unit/test_declaracion_minimo.py` —
4 tags rechaza, 5 acepta, 40 acepta; test que falla si el motor es invocado.

---

### T054 [TDD] — Herencia de tags entre módulos

**Descripción**: los tags declarados en un módulo se ofrecen preseleccionados al declarar en el otro
(FR-085), pero **no cuentan para el mínimo de FR-083**. El mínimo mide elección deliberada en ese
módulo; si la herencia contara, un usuario podría quedar "declarado" en un módulo donde nunca eligió
nada, y FR-088 lo dejaría pasar sin que hubiera declaración real.

**Archivos**: `src/recomendaciones/services/declaracion.py`

**Dep.**: T053

**Criterios de aceptación**:
- [ ] Los tags aplicables al otro módulo se resuelven vía `tag_modules`, no por copia ciega
- [ ] Los heredados se ofrecen **preseleccionados**, y confirmarlos es un acto del usuario
- [ ] Un tag heredado y **no confirmado** no cuenta para el mínimo
- [ ] Un tag heredado y confirmado cuenta como propio de ese módulo y se persiste como tal
- [ ] Un usuario con 5 heredados y 0 confirmados **no** satisface FR-083
- [ ] **El feedback no altera la pertenencia del tag a la declaración** (FR-086): un dislike reduce
      la **contribución** de sus tags al perfil y **nunca** borra ni hace caducar una fila de
      `user_declared_tags`. Se verifica sobre la tabla, no sobre el perfil: la declaración es un
      enunciado del usuario, no una inferencia del sistema, y el sistema no revoca enunciados ajenos
- [ ] Un usuario que acumula dislikes sobre todos sus tags declarados **sigue declarado** y sigue
      satisfaciendo FR-083 — de lo contrario FR-088 lo expulsaría por haber usado el producto

**Tests**: `tests/unit/test_herencia_tags.py` — el caso 5 heredados / 0 propios debe ser rechazo.

---

### T055 [TDD] — Rechazo por módulo sin declaración

**Descripción**: FR-088 manda rechazar la solicitud de un usuario sin declaración en ese módulo. El
rechazo **no introduce un sexto estado de respuesta**: ocurre *antes* de que la precedencia de
estados de FR-056 sea aplicable. Tratarlo como estado nuevo rompería la exhaustividad declarada del
contrato de lectura (DEP-6).

**Archivos**: `src/recomendaciones/api/routes/recomendaciones.py`,
`src/recomendaciones/services/precondiciones.py`

**Dep.**: T053, T012

**Criterios de aceptación**:
- [ ] El chequeo de declaración ocurre en precondiciones, antes de resolver estado de resultado
- [ ] El conjunto de estados de respuesta sigue teniendo **cinco** miembros
- [ ] El rechazo es por módulo: declarado en uno y no en el otro → rechazo sólo en el segundo
- [ ] El cuerpo del rechazo indica qué falta, sin exponer detalle interno

**Tests**: `tests/contract/test_rechazo_sin_declaracion.py` — enumera los estados posibles y falla si
aparece uno sexto.

---

### T056 — Perfil vectorial derivado puro

**Descripción**: FR-087 exige que el perfil vectorial sea **derivado y reconstruible** a partir de
sus insumos. Queda **prohibida la actualización incremental**: un perfil que se actualiza sumando
deltas deja de ser reconstruible en cuanto se pierde un delta, y el error no se manifiesta como
fallo sino como recomendaciones levemente peores, que es el modo de fallo más difícil de detectar.

**Archivos**: `src/recomendaciones/engine/user_profile.py`

**Dep.**: T053, T017

**Criterios de aceptación**:
- [ ] La única operación pública es **reconstruir desde los insumos**; no existe `update_partial`
- [ ] Reconstruir dos veces sobre los mismos insumos da el mismo vector (determinismo)
- [ ] El perfil no se persiste como fuente de verdad; si se cachea, se puede descartar sin pérdida
- [ ] Los insumos son la declaración (FR-082) y las señales vigentes, no señales purgadas

**Tests**: `tests/unit/test_user_profile_derivado.py` — reconstrucción idempotente; test que falla si
se agrega un método de actualización incremental.

---

### T057 — Purga de señales de actividad con guarda de exclusión

**Descripción**: la retención es finita y declarada (FR-068, FR-068a), y el horizonte debe ser
estrictamente mayor que toda ventana operativa (FR-068b). Antes de purgar una señal de consumo, el
procedimiento verifica la guarda de FR-068c; y la exclusión permanente persiste **aunque su señal de
origen haya sido purgada** (FR-068d), por reconstrucción aditiva, no por dependencia de la señal.

**Archivos**: `src/recomendaciones/jobs/purga_senales.py`

**Dep.**: T003, T023

**Criterios de aceptación**:
- [ ] Retención y horizonte son parámetros **obligatorios con valor explícito**, sin default oculto
- [ ] El arranque falla si el horizonte no supera estrictamente la ventana operativa mayor
- [ ] La guarda de FR-068c se evalúa **antes** de cada purga de señal de consumo
- [ ] Purgar la señal de origen **no** elimina la exclusión derivada (`user_exclusions`, RESTRICT)
- [ ] Emite `orphaned_exclusions_total` como medida **informativa y sin umbral de alerta**
      (FR-068d1) — y T042 verifica que **no** exista alerta asociada

**Tests**: `tests/integration/test_purga_senales.py` — exclusión sobrevive a la purga de su señal;
configuración con horizonte menor que la ventana no arranca.

---

### T058 [TDD] — Supresión verificada con aborto del recálculo en curso

**Descripción**: FR-092 ordena invalidar la caché **antes** de eliminar el dato de origen, y FR-092a
exige **abortar** el recálculo en curso en vez de esperarlo. Esperar no basta: suprimir el bloqueo
de recálculo no detiene al worker que ya lo tomó, sólo habilita a que entre un segundo.

**Archivos**: `src/recomendaciones/services/supresion.py`,
`src/recomendaciones/jobs/recalculo.py`

**Dep.**: T023, T028, T057

**Criterios de aceptación**:
- [ ] Orden de operaciones: Redis primero, Postgres después (FR-080c)
- [ ] El recálculo en curso se **aborta**; el worker comprueba una señal de cancelación y se detiene
- [ ] La supresión alcanza a **toda** versión de configuración y a **todos** los módulos (FR-093)
- [ ] Alcanza las **cinco** tablas de §7.11, incluida `user_declared_tags`
- [ ] **El alcance incluye la caché** (FR-091), no solo Postgres: las entradas `reco:`,
      `reco:stale:` y `filters:` del usuario se eliminan explícitamente
- [ ] **Ningún dato se da por suprimido delegando en el vencimiento de su TTL** (FR-091). Se
      verifica leyendo la clave inmediatamente después de la supresión, no esperando su expiración:
      un dato que sigue siendo legible no está suprimido, por más que vaya a expirar
- [ ] Un worker que termina después de la supresión **no** reescribe el resultado suprimido

**Tests**: `tests/integration/test_supresion_aborta_recalculo.py` — recálculo en vuelo durante la
supresión; verificar que ningún registro reaparece.

---

### T059 — Verificación ejecutable de supresión, observador y escalamiento

**Descripción**: FR-094 manda tratar la supresión parcial como fallo y FR-095 exige que la
verificación sea **ejecutable y registrada**. FR-095a agrega observador: un fallo que nadie observa
no es un fallo detectado.

**Archivos**: `src/recomendaciones/services/supresion_verify.py`, `ops/alerts.yaml`

**Dep.**: T058, T039

**Criterios de aceptación**:
- [ ] Tras suprimir, una comprobación recorre las cinco tablas **y las claves de Redis** y deja
      registro del resultado. La verificación cubre el mismo alcance que FR-091 declara: una
      comprobación que solo mira Postgres daría por exitosa una supresión que dejó la caché intacta
- [ ] Residuo detectado → la supresión se marca **fallida**, no parcialmente exitosa
- [ ] Métrica de supresiones con verificación fallida, **con alerta** (FR-095a) — a diferencia de
      `orphaned_exclusions_total`, que es informativa
- [ ] Escalamiento declarado en el runbook

**Tests**: `tests/integration/test_supresion_verificada.py` — residuo inyectado produce fallo y
dispara la alerta.

---

### T060 [TDD] — Disparador de recálculo por conteo e invalidación en el mismo acto

**Descripción**: FR-080a dispara el recálculo al acumular un número de señales; FR-080 exige que la
invalidación de caché ocurra **en el mismo acto** que la causa. Separarlos deja una ventana en la
que el sistema sirve un resultado que ya sabe obsoleto.

**Archivos**: `src/recomendaciones/services/trigger_recalculo.py`

**Dep.**: T023, T028

**Criterios de aceptación**:
- [ ] El conteo umbral es parámetro de §4, no constante en código
- [ ] Causa e invalidación son atómicas respecto del lector: no hay lectura intermedia del valor viejo
- [ ] FR-080b se respeta: el top-N reside **únicamente en Redis**; se persisten sus insumos, no él
- [ ] Redis primero, Postgres después (FR-080c)
- [ ] **SC-022** — un cambio de versión de configuración provoca 0 invalidaciones masivas

**Tests**: `tests/integration/test_trigger_recalculo.py` — n−1 señales no disparan, n sí; ninguna
lectura entre causa e invalidación devuelve el resultado viejo.

---

### T061 — Ponderación regional del término colaborativo

**Descripción**: FR-081 manda implementar la segmentación como **ponderación**, no como filtro, y
FR-081a exige degradación continua. FR-081b fija el factor como **intensidad de la segmentación**:
`0` es el neutro. `v1` arranca activo en su intensidad mínima, `region_weight_factor = 0,1`
(FR-090a), revirtiendo la prescripción de RD-74 sin revertir la capacidad de FR-090.

**Archivos**: `src/recomendaciones/engine/collaborative.py`

**Dep.**: T004, T017

**Criterios de aceptación**:
- [ ] Con `region_weight_factor = 0` el resultado es **idéntico** al de no segmentar
- [ ] El peso extraregional es positivo para todo factor `< 1`: ningún vecino queda excluido por regla
- [ ] `collab_min_neighbors` = 10: si tras ponderar no hay ese mínimo de vecinos con peso no
      despreciable, el término colaborativo no se aplica (FR-096) en vez de aplicarse sobre ruido
- [ ] El corte top-k **posterior** se verifica: un peso positivo pero ínfimo no debe volverse
      indistinguible de cero al recortar (riesgo señalado al cerrar FR-081a)

**Tests**: `tests/unit/test_ponderacion_regional.py` — factor 0 equivale a sin segmentación; región
con 3 vecinos no aplica colaborativo; barrido de factores sin discontinuidades.

---

### T062 [TDD] — Señal de resultado obsoleto como campo aparte

**Descripción**: FR-056a pide señalar que, además del respaldo servido, existe un resultado
personalizado vencido. Es **un campo aparte, no un sexto estado**: agregarlo al enum rompería la
exhaustividad acordada en DEP-6 y obligaría a renegociar el contrato de lectura con `api-general`.

**Archivos**: `src/recomendaciones/api/schemas/respuesta.py`, `contracts/openapi.yaml`

**Dep.**: T055, T049

**Criterios de aceptación**:
- [ ] El enum de estados conserva **cinco** miembros
- [ ] El campo es opcional y sólo aparece cuando se sirve respaldo existiendo personalizado vencido
- [ ] La precedencia de FR-056 aplica sólo a solicitudes que **pasaron** precondiciones

**Tests**: `tests/contract/test_estado_obsoleto.py`.

---

### T063 — Recálculo de popularidad por ventana

**Descripción**: **productora** de `item_popularity`. Recalcula la popularidad por ventana
(RD-12, RD-13) y la escribe con PK `(item_id, config_version)`. El puntaje es el **límite inferior
del intervalo de confianza de Wilson** sobre la tasa de conversión a like entre quienes
interactuaron (FR-033a3), con `popularity_confidence_z` = 1,96.

Es el **único escritor** de `item_popularity` (DI-13). T038 la consume; T029 no la toca.

**Archivos**: `src/recomendaciones/jobs/popularidad.py`

**Dep.**: T003, T004

> **Nota de fase (2026-09-22)**: **Fase 1**, no Fase 3. T038 está en Fase 1 por el hallazgo F2
> —«sin el batch de respaldo, el estado `fallback` de FR-056 es inalcanzable y T020 no puede
> testearse completa»— y al declararse que T038 **lee** lo que T063 escribe, dejar a T063 fuera de
> Fase 1 haría que ese fundamento dejara de cumplirse: T038 correría sobre una tabla vacía y
> `fallback` seguiría siendo inalcanzable. La dependencia arrastra la fase.

**Criterios de aceptación**:
- [ ] La ventana es parámetro de §4 y es **menor** que el horizonte de retención de FR-068b
- [ ] El resultado se escribe por `config_version`; cambiar de versión no pisa la anterior
- [ ] `popularity_confidence_z` se lee de configuración, no se codifica
- [ ] El puntaje es el **límite inferior del intervalo de Wilson** sobre la tasa de conversión a
      like entre quienes interactuaron (FR-033a3), no el volumen bruto de likes
- [ ] Se respetan `FR-033a3a` y `FR-033a3b` (tratamiento del denominador y de los casos sin
      interacción), `FR-033a4` y `FR-033a5`
- [ ] `CHECK (popularity_score BETWEEN 0 AND 1)` y `CHECK (like_count <= engaged_user_count)`
      (DI-26) se sostienen sobre todo lo escrito
- [ ] `computed_at` se escribe por fila, de modo que un batch **parcialmente fallido** sea
      detectable (RD-13) y alimente `catalog_popularity_last_success_timestamp`
- [ ] ⚠️ **Sin criterio de cuota.** El criterio
      `floor(top_n × fallback_new_item_quota_ratio)` se movió a **T038** el 2026-09-22: la cuota
      opera sobre el **resultado servido**, no sobre el cálculo del puntaje. Estaba en la tarea
      equivocada

**Tests**: `tests/integration/test_popularidad.py` — ventana mayor que retención no arranca; un
ítem con 1 like de 1 interacción **no** supera a uno con 80 de 100 (es el caso que distingue Wilson
del conteo bruto); batch interrumpido deja `computed_at` viejo en las filas no recalculadas.

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
T001 → T004 → T007 → T008 → T012 → T015 ─┼→ T016 → T017
T001 → T004 → T013 ────────────────────┘
                                          │
T016 → T019 → T020 → T033 → T036 → T038 → T037 → T049 → T043 → T044 → T045 → T048
   └→ T023 → T024 → T027 (worker, ahora Fase 1) ──────┘
```

**Cuello de botella real: T016** (pipeline de post-proceso). Bloquea persistencia, worker y API a la
vez. Priorizarlo por encima de cualquier tarea `[P]`.

**Ruta crítica**: `T001 → T004 → T007 → T008 → T012 → T015 → T016 → T019 → T020 → T033 → T036 →
T038 → T037 → T049 → T043 → T044 → T045 → T048` (18 tareas).

> **Cambio tras el análisis de consistencia**: la ruta creció de 15 a 18 tareas. T038 y T037 entraron
> por la cadena de dependencias corregida (F2, F4); T049 entró porque T043 no puede validar contratos
> que nadie produjo (F6). Ninguna es trabajo nuevo: eran dependencias que estaban implícitas y ahora
> son visibles. **La ruta no se alargó — se dejó de subestimar.**

**Paralelizables tempranas** (tras T001): T004, T005, T006 — luego T009/T010/T011 en simultáneo tras T008.

**Riesgo de cronograma**: T027 (propagación cross-module) es `L` y depende de casi todo el motor.
Si el contrato del evento con `api-general` no se cierra a tiempo (DEP-1), T023 se bloquea y arrastra
T024→T027. **Este riesgo se agravó al mover el worker a Fase 1** (F1): ahora DEP-1 bloquea el hito
de Fase 1 completo, no solo el de Fase 2. **Mitigación**: desarrollar contra un doble del contrato
desde el día 1 y escalar DEP-1 como bloqueante inmediato, según D1.

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
- [ ] US1 (lectura) y US2 (recálculo) demostrables end-to-end **al cierre de Fase 1** (T023, T024, T027, T036)
- [ ] US5 (filtros obligatorios) verificado por T017
- [ ] US3, US4, US6, US7 completos
- [ ] Los cinco `result_type` alcanzables y correctamente discriminados — **incluido `fallback`**,
      que requiere T038 en Fase 1
- [ ] Cold start cruzado produce recomendaciones no triviales (SC-010)

## Calidad y contratos
- [ ] **T007–T017 desarrolladas test-first**: en cada PR, el commit de test precede al de
      implementación (verificable en el historial de git)
- [ ] **Test de mutación en verde**: mutar el filtro de edad o el de exclusión hace fallar la suite
      (T017, T045)
- [ ] `contracts/` materializado con OpenAPI y JSON Schema (T049)
- [ ] Contract tests en verde como gate bloqueante (T043)
- [ ] Los nueve casos críticos en verde (T044)
- [ ] Configuración versionada trazable en cada recomendación servida
- [ ] `config_version` presente en **ambas** familias de clave, vigente y obsoleta (T018)
- [ ] `v1.yaml` valida contra el loader; configuración inválida impide el arranque
- [ ] SC-001 verificado: la latencia no depende del tamaño del catálogo (T050)

## Deuda del prototipo
- [ ] Caché en memoria → Redis persistente (T018)
- [ ] `ExclusionSet` con interfaz pública; sin acceso a atributos privados (T014)
- [ ] Feedback publica el evento de recálculo (T036)
- [ ] Constantes del motor y mapeo de `age_rating` externalizados a configuración (T004, T013)

## Operación
- [ ] **Las dieciséis métricas de observabilidad emitiéndose** (T039). La cifra anterior ("diez")
      quedó obsoleta: el recuento sobre `data-model.md` da dieciséis nombres de métrica
      (`age_stale_config_users_total`, `age_threshold_crossings_total`, `catalog_retired_total`,
      `catalog_unrated_ratio`, `catalog_unvectorized_ratio`, `contract_violations_total`,
      `exclusion_resolve_lag_seconds`, `exclusions_orphaned_permanent_total`,
      `projection_field_anomalies_total`, `signal_duplicate_rejections_total`,
      `signal_ingest_lag_seconds`, `signals_purge_deferred_total`, `sync_volume_delta_ratio`,
      `user_deletion_residual_keys_total`, `vector_recompute_lag_seconds`, y la métrica de
      **liveness** del job de T051 que reemplaza a `age_ordinal_staleness_seconds`). Un DoD que pide
      diez sobre dieciséis se da por satisfecho con seis métricas faltando.
- [ ] `contract_violations_total` se emite con contadores **separados** para `birth_date` y `region`
- [ ] `exclusions_orphaned_permanent_total` se emite **sin alerta asociada** (FR-068d1): su ausencia
      de umbral es un requisito, no un olvido de configuración
- [ ] **Ningún FR carece de tarea**, o su ausencia está declarada con motivo en la sección
      «Tareas bloqueadas por requisitos inexistentes». La cobertura supuesta es la forma más barata
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
- [ ] Sin violaciones de la constitution v1.0.0
- [ ] Decisiones abiertas: **ninguna pendiente**. `plan.md` §8 declara «Ninguna bloqueante» y
      NC-1…NC-20 **todos cerrados** (`data-model.md` §12). La lista «D1, D2, D3, D5, D6, D7, D8» que
      figuraba aquí quedó obsoleta y se retira: un DoD que exige resolver decisiones ya resueltas
      envejece hacia el ruido, y el ruido se termina tildando sin leer
