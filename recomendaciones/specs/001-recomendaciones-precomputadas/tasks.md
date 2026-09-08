---
description: "Desglose de tareas ejecutables — Feature 001"
---

# Tasks: Servicio de Recomendaciones Híbridas Precomputadas

**Input**: `specs/001-recomendaciones-precomputadas/` · **Branch**: `001-recomendaciones-precomputadas`

**Fuentes de verdad**: [spec.md](./spec.md) (FR-001→FR-071, 5 clarificaciones) ·
[plan.md](./plan.md) (D1→D10) · [checklists/requirements-contracts.md](./checklists/requirements-contracts.md) (30/30) ·
[constitution v1.0.0](../../.specify/memory/constitution.md)

**Decisiones cerradas — no reabrir**: SWR con obsoleto (Q1) · propagación por vocabulario compartido
(Q2) · likes y dislikes puntúan, consumo solo excluye (Q3) · configuración versionada en repo (Q4) ·
respaldo diversificado por MMR (Q5) · α=0.5 β=0.3 γ=0.2 (D4) · espacio vectorial único (D9) ·
popularidad por likes propios (D10).

## Formato: `[ID] [P?] Descripción`

- **[P]**: paralelizable — sin dependencias cruzadas ni archivos compartidos con otra tarea `[P]` activa
- **[TDD]**: la tarea se desarrolla test-first — ver *Política TDD* abajo
- **Estimación**: S (≤½ día) · M (1-2 días) · L (3-5 días)
- Toda tarea de producción declara sus tests. Una tarea sin criterio verificable no está lista para tomarse.

## Política TDD (selectiva)

**Alcance: T007–T017** — el motor de recomendación y el post-procesamiento. Son funciones puras, sin
I/O ni reloj, con entradas y salidas completamente definidas: el caso donde el test *es* la
especificación ejecutable, no su verificación posterior.

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
| **1 — Vertical slice** | T001–T024, **T027**, T033–T038 | Ciclo completo: leer, registrar feedback, recalcular. Cierra US1, US2, US5 |
| **2 — Robustez operativa** | T025, T026, T028–T032, T039–T042, T046, **T049** | Sobrevive a fallos. Cierra US3, US4, US6, US7 |
| **3 — Optimización y cierre** | T043–T045, T047, T048, **T050** | Rendimiento, gates de CI y gobernanza |

> **Correcciones del análisis de consistencia (2026-09-08)**:
> - **F1** — T023, T024 y T027 se movieron a Fase 1: `plan.md` §4 promete US2 y SC-005 en esa fase,
>   y ambos dependen del worker. En Fase 2 quedan T025/T026, que son robustez ante fallos.
> - **F2** — T038 se movió a Fase 1: sin el batch de respaldo, el estado `fallback` de FR-056 es
>   inalcanzable y T020 no puede testearse completa.
> - **F8** — T036 confirmada en Fase 1: es lo que cierra el ciclo de US2.

---

# FASE 1 — Vertical slice

> **Objetivo**: servir top-N precomputado end-to-end **y cerrar el ciclo de recálculo**.
> Cierra US1, US2, US5. Incluye T023, T024, T027 (Milestone 5), T033–T038 (Milestone 7).

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

**Descripción**: las 10 tablas de `plan.md` §2 con pgvector. `items.age_rating` es `NOT NULL` con
default **no-apto** (FR-051): el esquema hace imposible representar un ítem sin clasificación tratable
como apto.

**Archivos**: `src/recomendaciones/storage/db/models.py`, `migrations/versions/*`, `alembic.ini`

**Dep.**: T001

**Criterios de aceptación**:
- [ ] Las 10 tablas existen con sus claves e índices; `item_vectors.vector` es pgvector
- [ ] `item_vectors.vocab_version` es `NOT NULL` (FR-010f)
- [ ] `items.age_rating` es `NOT NULL` y su default es el valor más restrictivo del catálogo
- [ ] `user_profiles` admite exactamente los módulos `peliculas`, `juegos`, `general` (constraint)
- [ ] `processed_events.event_id` es único (FR-011)
- [ ] `upgrade` y `downgrade` se aplican limpio sobre base vacía y sobre base poblada
- [ ] `INV-2`: toda información necesaria para recalcular un top-N reside acá

**Tests**: `tests/integration/test_migrations.py` (testcontainers) — ciclo upgrade/downgrade/upgrade; insertar ítem sin `age_rating` viola constraint; insertar perfil con módulo inválido viola constraint.

---

### T004 [P] — Configuración versionada del motor + loader validante

**Descripción**: `v1.yaml` con los valores de D4 y un loader que valida rangos y **rechaza cualquier
configuración que desactive un filtro obligatorio** (FR-054). `config_version` es el hash del archivo.

**Archivos**: `src/recomendaciones/config/engine_config/v1.yaml`, `src/recomendaciones/config/loader.py`

**Dep.**: T001

**Contenido de `v1.yaml`**: `alpha: 0.5`, `beta: 0.3`, `gamma: 0.2`, `k: 20`, `lambda_mmr: 0.7`,
`peso_like`, `peso_dislike`, `top_n_default`, `top_n_max`, `age_rating_catalog`, `tiebreak_criteria`,
`popularity_window_days`, `diversity_max_cluster_share`, `vocab_regeneration_policy`.

**Criterios de aceptación**:
- [ ] `alpha+beta+gamma` fuera de `1.0±ε` → fallo de arranque con mensaje que nombra el campo (FR-027)
- [ ] Cualquier peso fuera de `[0,1]` → fallo de arranque
- [ ] Una clave que intente desactivar el filtro de edad o de exclusión → fallo de arranque (FR-054)
- [ ] `age_rating_catalog` es la **única** fuente de valores válidos (FR-053); no hay constantes de rating en código
- [ ] `tiebreak_criteria` está poblado: el desempate nunca depende del orden de iteración (FR-070)
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
- [ ] El desempate usa `tiebreak_criteria` de configuración y **nunca** el orden de iteración (FR-070)
- [ ] El `config_version` usado viaja en la salida del scoring, no se pierde

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
- [ ] Edad del usuario indeterminable → solo contenido apto para todo público (FR-052)
- [ ] El catálogo de ratings viene de configuración versionada (FR-053) — sin `dict` hardcodeado
- [ ] **No existe** parámetro, flag ni rama que desactive el filtro (FR-054)
- [ ] Un rating desconocido nuevo (p. ej. `"NC-17"` sin declarar) se filtra, no se admite

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
- [ ] Cubre los cinco `result_type` (FR-056) — incluido el respaldo y el obsoleto
- [ ] Incluye valores límite: exactamente la edad mínima, un día antes, un día después
- [ ] Es property-based, no solo por ejemplos
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

**Tests**: `tests/integration/test_warmup.py` — flush total de Redis; el servicio no devuelve 500; el warm-up repuebla; la tasa de publicación no supera el límite.

---

# FASE 2 — Robustez operativa

> **Objetivo**: que sobreviva a fallos reales. Cierra US3, US4, US6, US7.

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

**Tests**: `tests/integration/test_propagation.py` — ítem con tag compartido → ambos módulos recalculan; ítem sin tag compartido → solo el propio, con motivo registrado.

---

## Milestone 6 — Data Transformer

| ID | Tarea | Dep. | [P] | Est. |
|---|---|---|---|---|
| T028 | Cliente REST autenticado y de solo lectura | T002 | | M |
| T029 | Materialización idempotente de usuarios, catálogo y actividad | T028, T003 | | L |
| T030 | Derivación del vocabulario compartido versionado | T029, T007 | | M |
| T031 | Registro de freshness de sincronización | T029 | [P] | S |
| T032 | Comportamiento ante `api-general` no disponible | T028, T031 | | M |

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
- [ ] Un usuario sin edad determinable se materializa con la restricción máxima (FR-052)
- [ ] La actividad conserva `signal_type` y `occurred_at` (FR-062, DEP-1, DEP-2)
- [ ] Interrupción a mitad de camino deja estado consistente, no parcial e indistinguible
- [ ] La popularidad se calcula por volumen de likes sobre la ventana configurada (FR-033a1)

**Tests**: `tests/integration/test_sync_idempotent.py` — doble ejecución → mismo estado; ítem sin rating → valor restrictivo; interrupción simulada → estado consistente.

---

### T030 — Derivación del vocabulario compartido versionado

**Descripción**: derivar el vocabulario del catálogo sincronizado como **artefacto versionado propiedad
de este repo** (FR-010e). La transición recalcula las representaciones afectadas **antes** de activar
la versión nueva (FR-010g).

**Archivos**: `src/recomendaciones/transformer/vocabulary_sync.py`

**Dep.**: T029, T007

**Criterios de aceptación**:
- [ ] El vocabulario se versiona; la versión activa es explícita y consultable
- [ ] Regenerar el vocabulario **recalcula todos los vectores afectados antes** de activar la versión (FR-010g)
- [ ] Durante la transición nunca se comparan vectores de versiones distintas (FR-010f)
- [ ] El criterio de regeneración vive en configuración versionada (FR-010g)
- [ ] Un vocabulario desactualizado degrada calidad, **nunca** corrección ni invariantes
- [ ] No requiere aprobación de `api-general`: es interno (FR-010e)

**Tests**: `tests/integration/test_vocab_transition.py` — durante la transición no existe instante con vectores mezclados; interrumpir la transición no activa la versión nueva a medias.

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

**Tests**: `tests/invariants/test_fallback_filtering.py` — menor de edad nunca recibe contenido adulto vía respaldo. `tests/unit/test_fallback_bounded.py` — el módulo no importa `engine/` ni funciones de similitud.

---

### T038 [P] — Batch de top-N de respaldo

**Descripción**: precomputar populares por módulo, **diversificados por MMR** (decisión Q5), sobre
volumen de likes propio en ventana acotada (D10, FR-033a1). Global por módulo, nunca por usuario.

**Archivos**: `src/recomendaciones/batch/fallback.py`

**Dep.**: T012, T015, T003

> **Nota de fase (hallazgo F2)**: adelantada a Fase 1. Su dependencia original de T029 (sincronización
> del catálogo, Fase 2) se sustituyó por T003: la popularidad se computa sobre `user_signals`, que ya
> se puebla con el feedback de T036. La sincronización completa de T029 **enriquece** el catálogo en
> Fase 2, pero no es condición para que el respaldo exista y sea testeable.

**Criterios de aceptación**:
- [ ] La popularidad sale del volumen de likes propio, sin campo externo (FR-033a)
- [ ] Se computa sobre ventana temporal configurable, no sobre histórico completo (FR-033a1)
- [ ] El resultado pasa por MMR: no se concentra en el género dominante (FR-033b)
- [ ] Es global por módulo, **no** personaliza por usuario (FR-033c)
- [ ] Sin likes suficientes → respaldo vacío y respuesta `empty_no_candidates`; **no** se sustituye por otro criterio (FR-033a2)
- [ ] Se persiste en Redis **y** en tabla, para rehidratar sin recomputar (D8)

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

**Descripción**: el documento único que exige FR-063, índice de DEP-1..DEP-6. **No sustituye** la
documentación oficial de `api-general` (Principio II): es la lista de lo que este repo necesita.

**Archivos**: `docs/contracts/required-fields.md`

**Dep.**: T043

**Criterios de aceptación**:
- [ ] Enumera cada campo requerido, su FR asociado y el impacto de su ausencia
- [ ] Cubre DEP-1, DEP-2, DEP-3, DEP-5, DEP-6 (DEP-4 quedó cerrada internamente)
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
- [ ] Las diez métricas emitiéndose (T039)
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
- [ ] Decisiones abiertas D1, D2, D3, D5, D6, D7, D8 resueltas o explícitamente diferidas a Fase 3
