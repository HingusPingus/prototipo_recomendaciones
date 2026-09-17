# Implementation Plan: Servicio de Recomendaciones Híbridas Precomputadas (MVP)

**Branch**: `001-recomendaciones-precomputadas` | **Regenerado**: 2026-09-17 | **Spec**: [spec.md](./spec.md)
**Modelo de datos**: [data-model.md](./data-model.md) | **Tareas**: [tasks.md](./tasks.md)

> **Nota de regeneración.** Este archivo se reescribió por completo el 2026-09-17 tras detectarse que el
> plan resultante de la regeneración anterior había quedado **entrelazado línea a línea** con la versión
> del 2026-09-07: cada línea contenía el texto nuevo concatenado con el viejo. El daño era mecánico, no
> de contenido. La versión original del 2026-09-07 se conserva íntegra en `.plan-2026-09-07.bak`.
>
> **Ante discrepancia entre documentos, manda `data-model.md`.** Este plan es derivado; los recuentos de
> abajo se verificaron contra los archivos fuente en el momento de escribirlo.

---

## Estado verificado de los insumos

| Magnitud | Valor | Fuente |
|---|---|---|
| Requisitos funcionales | **152** identificadores `FR-` únicos | `spec.md` |
| Criterios de éxito | **27** (`SC-1`…`SC-27`) | `spec.md` |
| Entradas de clarificación | **29** (sesiones 2026-09-07 y 2026-09-14) | `spec.md` |
| Dependencias externas | **10 declaradas**, de las cuales **8 vigentes**, 1 resuelta (DEP-4) y DEP-3 **vacante a propósito** | `spec.md` |
| Registros de decisión | **RD-1 … RD-80** | `data-model.md` §11 |
| Invariantes de datos | **32** (`DI-1`…`DI-28`, contando `DI-2a`…`DI-2e`) | `data-model.md` §6 |
| Cláusulas de contrato a `api-general` | **CR-1 … CR-18** (CR-13 y CR-14 tachadas) | `data-model.md` §10 |
| Tablas en PostgreSQL | **16**, agrupadas en 14 subsecciones | `data-model.md` §2 |
| Familias de claves Redis | **7** | `data-model.md` §3 |
| Historias de usuario | **7** (US1…US7) | `spec.md` |
| Tareas | **50** (T001…T050) | `tasks.md` |
| Checklist de calidad de requisitos | **30/30** | `checklists/` |

---

## Summary

Servicio de recomendaciones **híbridas y precomputadas** para RecoMe. Expone una API de lectura que sirve
top-N ya calculados; un worker asíncrono recalcula al recibir eventos de actividad; un Data Transformer
sincroniza **unidireccionalmente** desde `api-general` y materializa perfiles, vectores y popularidad.

El motor combina tres términos: `score = α·content + β·collaborative + γ·cross_module`, con
`α = 0,5`, `β = 0,3`, `γ = 0,2`, `k = 20` vecinos y `λ_MMR = 0,7`.

**Nada de eso se calcula durante una solicitud.** El request path solo lee, filtra por edad y exclusión,
y recorta. Es el Principio III de la constitución y la restricción que más decisiones ha gobernado.

**Posición en el sistema**: `api-general` (Java/Spring) está **incompleta y a la espera de este modelo**,
de modo que la prioridad de definición de este repositorio (RD-47) no es una postura de diseño sino la
secuencia real de trabajo. Los pendientes formulados como «¿el origen provee X?» son **decisiones de
contrato**, no averiguaciones. Esto no invierte la dirección del dato: catálogo y usuarios siguen siendo
proyección de dato ajeno.

---

## Technical Context

**Project Type**: servicio backend multiproceso — API + worker + job de sincronización.

| Aspecto | Elección |
|---|---|
| Lenguaje | Python 3.11+ |
| API | FastAPI |
| Persistencia | PostgreSQL + **pgvector** |
| Caché | Redis (**solo** caché; nada de verdad exclusiva) |
| Mensajería | RabbitMQ |
| ORM / migraciones | SQLAlchemy + Alembic |
| Testing | pytest + **testcontainers** |
| Referencia funcional | `Prototipo-Referencia/` (`vectorizer.py`, `domain.py`, `cli_preferencias.py`) |

**Consumidor único de cara al producto**: `api-general`. El servicio **no** es alcanzable desde los
frontends (FR-008).

---

## Constitution Check

| Principio | Cómo lo satisface este plan | Riesgo residual |
|---|---|---|
| **I. Frontera de datos y ownership** (NN) | Catálogo y usuarios son proyección; se materializan, no se editan. Única excepción de autoría local: `user_declared_tags` (§2.14) | La excepción **debe seguir siendo una**: RD-75 fija que un segundo dato de autoría local exige componente propio |
| **II. Contratos como verdad externa** (NN) | CR-1…CR-18 en `data-model.md` §10; contract testing como gate de deploy | `api-general` incompleta: los contratos se están **definiendo**, no consumiendo |
| **III. Cómputo pesado fuera del request path** (NN) | Top-N materializado; popularidad materializada (FR-033a4); el endpoint de escritura tiene **prohibición explícita** de calcular (FR-089b) | Es el principio que más presión recibe; cada excepción se registró como tal |
| **IV. Pipeline unidireccional** | Data Transformer solo lee de `api-general`; sin escritura de vuelta | — |
| **V. Gobernanza del motor híbrido** | Configuración versionada, una sola versión activa por entorno, sin A/B en MVP | — |
| **VI. Testing obligatorio y contract testing** (NN) | pytest + testcontainers; contract tests bloquean el deploy | — |
| **VII. Observabilidad y resiliencia asíncrona** | Reintento con backoff exponencial (máx. 5) → DLQ; métricas de cuota, obsolescencia y sincronización | — |

**Resultado**: sin violaciones. Las dos excepciones existentes (escritura de declaración, cómputo en
carga de configuración) están **declaradas como excepciones**, con condición de revisión.

---

## Project Structure

```
specs/001-recomendaciones-precomputadas/
├── spec.md              # 152 FR · 27 SC · 29 clarificaciones · DEP-1…DEP-10
├── plan.md              # este archivo
├── data-model.md        # AUTORITATIVO · 16 tablas · RD-1…RD-80 · DI-1…DI-28 · CR-1…CR-18
├── tasks.md             # 50 tareas en 10 milestones
└── checklists/          # auditoría de calidad de requisitos (30/30)

src/
├── api/                 # FastAPI — lectura + endpoint de declaración (excepción FR-089)
├── engine/              # TF-IDF, coseno, k-vecinos, cross-boost, combinación lineal, MMR
├── postprocess/         # edad → exclusión → MMR (orden obligatorio)
├── worker/              # consumo de `recomendacion.actualizar`, idempotencia, recálculo
├── sync/                # Data Transformer
├── config/              # carga y validación estricta, cálculo de config_version
└── db/                  # modelos SQLAlchemy + migraciones Alembic
```

---

## 1. Arquitectura por componentes

| Componente | Responsabilidad | Restricción dominante |
|---|---|---|
| **API de lectura** | Sirve top-N materializado; aplica filtros obligatorios; recorta a `top_n` | No calcula (Principio III) |
| **API de escritura (declaración)** | **Única excepción**: persiste `user_declared_tags` | Valida y persiste; **no calcula** (FR-089b) |
| **Engine (librería)** | TF-IDF, coseno, k-vecinos, cross-boost, combinación lineal, MMR | Sin estado propio; determinista dada la configuración |
| **Worker** | Consume eventos, aplica idempotencia, dispara recálculo | Recálculo por umbral de interacciones (10) |
| **Data Transformer** | Sincroniza desde `api-general`; materializa perfiles, vectores, popularidad | Unidireccional; proyecta, no crea |
| **Procesos periódicos** | Purga de señales, recálculo de popularidad, recomposición de vocabulario | Operan sobre derivados; su error es reversible |

### Flujo de lectura (request path)

1. Autenticación por API key interna (FR-007).
2. Validación de `top_n` contra `[top_n_min, top_n_max]` = **`[10, 50]`** (FR-006a) — rechazo explícito
   fuera de rango, por **ambos** extremos.
3. Verificación de declaración de gustos (FR-088); sin ella, rechazo.
4. Lectura de caché Redis; ante miss, lectura de Postgres.
5. Filtros obligatorios **en orden**: edad → exclusión → MMR.
6. Recorte a `top_n` y marcado de naturaleza del resultado (FR-006).

### Flujo de recálculo (worker)

Evento → idempotencia por `origin_interaction_id` → persistencia de señal → conteo → si alcanza
`interaction_recalc_threshold` (**10**), recálculo del top-N → **invalidación de caché en el mismo acto**
(FR-080).

---

## 2. Modelo de datos y almacenamiento

### Vista de conjunto

Las 16 tablas viven en `data-model.md` §2, que es la fuente autoritativa. Resumen de zonas:

| Zona | Tablas | Naturaleza |
|---|---|---|
| **Proyección** (dato ajeno) | `users`, `items`, `tags`, `item_tags`, `tag_modules`, `vocab_versions`, `vocab_version_tags` | Materializado desde `api-general`; **regenerable** |
| **Derivada** (cómputo propio) | `item_vectors`, `user_profiles`, `item_popularity` | Recalculable desde lo anterior + señales |
| **Autoría local** | `user_signals`, `user_exclusions`, `user_declared_tags` | **No regenerable desde ningún origen** |
| **Operación** | `engine_config_versions`, `sync_runs`, `processed_events` | Metadatos |

### Lo no regenerable, y su consecuencia operativa

RD-71 obligó a corregir una afirmación que el plan anterior arrastraba: *«todo lo necesario para
recalcular vive en Postgres»* es cierto para lo proyectado y **falso** para lo propio.

| Entidad | Si se pierde |
|---|---|
| `user_signals` | Se pierde el historial; el filtrado colaborativo arranca de cero |
| `user_declared_tags` | **Hay que volver a preguntarle al usuario** |
| `user_exclusions` | **Los ítems rechazados reaparecen** |

El respaldo es responsabilidad **operativa**, no de diseño. Queda declarado, no resuelto (RD-71).

### Redis — 7 familias de claves

Caché exclusivamente. Dos familias principales:

| Clave | Contenido | TTL |
|---|---|---|
| `reco:v{cfg}:{user_id}:{module}` | JSON: ítems + score + rank + `config_version` + `computed_at` | `TTL_FRESH` |
| `reco:stale:v{cfg}:{user_id}:{module}` | Marca de resultado personalizado obsoleto disponible | — |

La segunda existe por FR-056a: ante un personalizado obsoleto se sirve el respaldo, **notificando** que
existe un personalizado anterior.

### Configuración versionada — inventario verificado

**Parámetros del motor** (`data-model.md` §4, dentro del repositorio, versionados):

| Parámetro | Valor | Origen |
|---|---|---|
| `alpha` / `beta` / `gamma` | 0,5 / 0,3 / 0,2 | Diseño del motor |
| `k` (vecinos) | 20 | Diseño del motor |
| `lambda_mmr` | 0,7 | Diseño del motor |
| `top_n_min` / `top_n_default` / `top_n_max` | **10 / 20 / 50** | RD-73, RD-78 |
| `peso_like` / consumo / `peso_dislike` | **1,0 / 0,3 / −1,0** | RD-73 (adoptados del prototipo) |
| `popularity_confidence_z` | **1,96** | RD-53 |
| `popularity_window_days` | a calibrar | RD-53 |
| `fallback_new_item_quota_ratio` | **0,20** | RD-77, RD-80 |
| `declared_tags_min` | **5** | RD-68 |
| `region_weight_factor` | **0,1** | RD-79 |
| `diversity_max_cluster_share` | a calibrar | — |
| Umbral de evidencia (promoción al conjunto general) | a calibrar | RD-67 |
| `age_rating_catalog` | `ATP` / `+13` / `+18` | RD-53 |

**Eliminados y por qué** — conviene tenerlos a la vista, porque su desaparición es tan informativa como
su existencia:

| Parámetro retirado | Motivo |
|---|---|
| ~~`fallback_new_item_slots`~~ | Reemplazado por el ratio (RD-77) |
| ~~`fallback_new_item_quota_min`~~ | Con `top_n ≥ 10` nunca gobernaría: *un parámetro que nunca gobierna miente sobre lo que hace* (RD-80) |
| ~~`fallback_bootstrap_min_items`~~ | Eliminado junto con el régimen de arranque (RD-70) |

**Validación al cargar**: `0 < fallback_new_item_quota_ratio < 1`;
`10 ≤ top_n_min ≤ top_n_default ≤ top_n_max`; `0 ≤ region_weight_factor < 1` — **inferior inclusivo**
(es el neutro, RD-76) y **superior estricto** (equivale al filtro duro que FR-081a prohíbe).

**Parámetros operativos** (fuera de `data-model.md`, RD-46): `signal_retention_days` = **18–24 meses**,
`sync_volume_delta_ratio` = **0,9**, `interaction_recalc_threshold` = **10**, retención de la marca de
idempotencia, TTLs de caché, umbrales de reintento.

> La distinción no es estética: los del motor entran en el **cálculo** de un derivado versionado (RD-13);
> los operativos no alteran ningún puntaje. `interaction_recalc_threshold` es el caso intermedio y va
> con los operativos: no altera el valor del top-N, solo **cuándo** se lo recomputa.

---

## 3. Contratos e interfaces

### 3.1 Lectura (expuesto a `api-general`)

`GET` de recomendaciones por usuario y módulo. Devuelve identificador, posición, score y
`config_version` por ítem (FR-004), más la marca temporal y la **naturaleza** del resultado (FR-006):
personalizada vigente · personalizada obsoleta · de respaldo no personalizada · vacía por falta de
candidatos · vacía por recálculo pendiente.

### 3.2 Escritura de declaración (excepción declarada)

`POST` de gustos declarados. **Confirmación síncrona** (FR-089a): asíncrona rechazaría al usuario por no
haber declarado lo que acaba de declarar. Valida el mínimo (FR-083), resuelve la herencia por tag
compartido (FR-085) y persiste. **Prohibido calcular** (FR-089b).

### 3.3 Evento consumido

`recomendacion.actualizar` desde RabbitMQ. Idempotencia por `origin_interaction_id`
(`NOT NULL UNIQUE`, DEP-8).

### 3.4 Política de errores

Rechazo explícito ante: `top_n` fuera de `[10, 50]` · ausencia de API key · falta de declaración de
gustos (FR-088) · payload inválido. Fallo transitorio (DB/Redis): reintento con backoff exponencial,
máx. 5 → DLQ.

### 3.5 Dependencias externas — **8 vigentes**

| ID | Qué se requiere de `api-general` | Estado |
|---|---|---|
| DEP-1 | Tipo de señal (like / dislike / consumo) por registro de actividad | Vigente |
| DEP-2 | Marca temporal por señal | Vigente |
| ~~DEP-3~~ | — | **Vacante a propósito** (identificador retirado, no se reutiliza) |
| DEP-4 | ~~Fuente de popularidad global por ítem~~ | **Resuelta**: se deriva localmente |
| DEP-5 | Fecha de nacimiento del usuario, obligatoria y no nula | Vigente |
| DEP-6 | Acuerdo sobre el conjunto de estados de respuesta | Vigente |
| DEP-7 | Tags temáticos **por ítem**, conjunto no vacío | Vigente |
| DEP-8 | Identificador propio de cada interacción, único y no reutilizado | Vigente |
| DEP-9 | Notificación de cada transición de estado como emisión propia, con identificador | Vigente |
| DEP-10 | **Vocabulario de tags normalizado del catálogo** | Vigente |

> **DEP-10 es la más severa del inventario.** Es la única dependencia cuyo incumplimiento deja al sistema
> **sin ningún usuario atendible**: sin vocabulario no hay declaración posible, y FR-088 rechaza todo.
> Se distingue de DEP-7, que es *por ítem*; DEP-10 es *sobre el conjunto*.

---

## 4. Plan de implementación por fases

| Fase | Milestones de `tasks.md` | Contenido | Gate de salida |
|---|---|---|---|
| **1 — Fundaciones y camino crítico** | M1, M4, M5 (parcial), M6 | Esquema, migraciones, consumo de eventos, idempotencia, recálculo, Data Transformer | Un usuario con señales obtiene un top-N materializado |
| **2 — Motor y post-procesamiento** | M2, M3 | TF-IDF, vecinos, cross-boost, combinación; edad → exclusión → MMR | Invariantes de seguridad verificados con tests |
| **3 — API y respaldo** | M7 | Lectura, declaración, cuota de novedades, estados de respuesta | Contract tests en verde |
| **4 — Observabilidad y cierre** | M8, M9, M10 | Métricas, salud, testing de integración, cierre | Definition of Done completa |

### Consistencia interna — verificada

- El orden edad → exclusión → MMR es **obligatorio** y está cubierto por M3.
- La invalidación de caché ocurre en el mismo acto que la actualización (FR-080): no hay camino por el
  que el resultado se actualice y la caché sobreviva.
- `origin_interaction_id` sostiene la idempotencia y es dependencia externa (DEP-8), de modo que M5 no
  puede cerrarse sin acuerdo de contrato.

### Funcionalidad clarificada **sin tarea asignada** — inconsistencia pendiente

**FR-088 rechaza toda solicitud de un usuario sin declaración de gustos, y la declaración no tiene tarea
asignada en `tasks.md`.** Con el estado actual del plan de tareas, Fase 1 produce un sistema que rechaza
al 100 % de sus usuarios. Requiere tarea nueva antes de que M7 se considere completable.

Lo mismo, en menor grado: siembra de vectores, purga de señales, supresión verificada, disparador por
conteo, ponderación regional y señal de obsoleto disponible carecen de tarea propia.

---

## 5. Plan de testing

| Nivel | Alcance | Herramienta |
|---|---|---|
| **Unitario** | Engine puro: TF-IDF, coseno, MMR, combinación lineal | pytest |
| **Invariantes** | DI-1…DI-28: filtro etario, exclusión, disjunción de conjuntos | pytest + fixtures |
| **Integración** | Postgres + Redis + RabbitMQ reales | testcontainers |
| **Contract** (**gate de deploy**) | Validación del payload contra CR-1…CR-18 | pytest |

**Casos que deben estar cubiertos explícitamente**: evento duplicado · payload inválido · `api-general`
caída durante la sincronización · Redis caído · broker caído · `top_n` fuera de rango por **ambos**
extremos · usuario sin declaración · cuota de novedades con conjunto emergente vacío.

**TDD selectivo**: obligatorio en invariantes de seguridad (edad, exclusión) y en el contrato; opcional
en el resto.

---

## 6. Observabilidad y operación

**Métricas mínimas**: proporción del respaldo servido que provino de la cuota (`fallback_new_item_share`,
FR-033a8) — distinguiendo cuota **disponible** de **efectivamente ocupada** — · tasa de resultados
obsoletos servidos · latencia del request path · profundidad de la cola y tamaño de la DLQ · resultado de
cada corrida de sincronización (`sync_runs`).

**Trazabilidad**: identificador de origen (`origin_interaction_id` en el worker), `user_id`, `module`,
`config_version`, `outcome`.

**Salud**: endpoint de estado que distingue *degradado* (Redis caído, se sirve desde Postgres) de
*caído* (Postgres inaccesible).

---

## 7. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| `api-general` incompleta bloquea la integración | Los contratos se **definen** acá (RD-47); el desarrollo local usa siembra sintética (patrón de `cli_preferencias.py`) |
| DEP-10 incumplida | Sin vocabulario no hay usuarios atendibles. **No hay mitigación técnica**: es acuerdo previo |
| La cuota de novedades nunca se llena | Métrica de FR-033a8 distingue cuota chica de umbral restrictivo |
| `v1` no observa la línea de base sin segmentación regional | Aceptado en RD-79: medir exige poner `region_weight_factor = 0` deliberadamente |
| Pérdida de Postgres | Tres entidades no regenerables (RD-71). Respaldo operativo, fuera del diseño |
| Erosión del Principio III por excepciones sucesivas | Cada excepción lleva condición de revisión; RD-75 fija que la segunda exige componente propio |

### Retirados por clarificación

Cold start sin solución (resuelto por declaración de gustos, RD-68/70) · régimen de arranque del conjunto
emergente (eliminado en RD-70) · popularidad como dependencia externa (DEP-4, resuelta).

---

## 8. Decisiones abiertas

**Ninguna bloqueante.** Los pendientes NC-1…NC-20 están **todos cerrados** (`data-model.md` §12).

Quedan **valores a calibrar**, que no son decisiones sino mediciones pendientes:
`popularity_window_days` · `diversity_max_cluster_share` · umbral de evidencia para la promoción al
conjunto general · `signal_retention_days` dentro del rango 18–24 meses.

> Los cuatro son configuración versionada y su error es **reversible**, salvo `signal_retention_days`,
> que puede acortarse pero **no alargarse** porque lo purgado no vuelve. Por eso su valor inicial debe
> ser conservador.

---

## Definition of Done (para pasar a `/speckit.tasks`)

- [x] Constitution Check sin violaciones no declaradas
- [x] Modelo de datos completo y autoritativo (`data-model.md`)
- [x] Contrato a `api-general` especificado (CR-1…CR-18)
- [x] Dependencias externas inventariadas (8 vigentes)
- [x] Pendientes de clarificación cerrados (NC-1…NC-20)
- [x] Parámetros de configuración con valor o con criterio de calibración
- [ ] **`tasks.md` actualizado**: encabezado desactualizado y funcionalidad sin tarea asignada
- [ ] **Incidencias de GitHub propagadas**

---

## Anexo A — Desfasajes corregidos en esta regeneración

| Afirmación del plan anterior | Estado real verificado |
|---|---|
| «FR-001→FR-071, 5 clarificaciones» | **152 FR, 29 clarificaciones** |
| «todo lo necesario para recalcular vive en Postgres» | **Falso** para las tres entidades de autoría local (RD-71) |
| 8 dependencias externas | **10 declaradas**, 8 vigentes, DEP-3 vacante |
| Sin endpoint de escritura | Existe como **excepción declarada** (FR-089) |
| `region_weight_factor` sin fijar | **0,1** en `v1` (RD-79) |
| Cuota de novedades como conteo fijo | **Proporción del 20 %** sin piso ni clamp (RD-80) |
| `top_n` sin cota inferior | Dominio **`[10, 50]`** (FR-006a, RD-78) |
| RD-1…RD-70 | **RD-1…RD-80** |

---

## Anexo B — Cobertura declarada

Las 7 historias de usuario están cubiertas por los 10 milestones de `tasks.md`. Los 27 criterios de éxito
tienen requisito funcional asociado. Los 32 invariantes de datos tienen verificación prevista en el nivel
correspondiente (esquema, carga de configuración o test).

**Excepción declarada**: DI-28 (mínimo de tags declarados) **no es verificable por esquema** — es el único
invariante que depende de validación en la capa de aplicación.

---

## Anexo C — Impacto sobre `tasks.md` e incidencias *(declarado, no ejecutado)*

**Tareas a actualizar**: T003, T004, T007, T012, T017, T022, T029, T031, T036, T038, T047, T050.

**Tareas nuevas requeridas**: endpoint y flujo de declaración de gustos · siembra de vectores · purga de
señales · verificación de supresión · disparador de recálculo por conteo · ponderación regional · señal de
resultado obsoleto disponible.

**Incidencias**: #3, #4, #7, #12, #17, #22, #29, #31, #36, #38, #47 y #50 requieren actualización; las
nuevas comienzan en **#61**.

> Propagación **pendiente de comando expreso**. Este anexo enumera el alcance; no lo ejecuta.
