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

| Magnitud | Valor | Fuente | Comando de verificación |
|---|---|---|---|
| Requisitos funcionales | **167** definidos · **92** bases | `spec.md` | `grep -oE '^- \*\*FR-[0-9]{3}[a-z0-9]*\*\*' spec.md \| sort -u \| wc -l` (bases: mismo patrón hasta `FR-[0-9]{3}`) |
| Criterios de éxito | **31** (`SC-001`…`SC-031`; SC-028…SC-031 agregados el 2026-09-27, CHK072) | `spec.md` | `grep -oE 'SC-[0-9]{3}' spec.md \| sort -u \| wc -l` |
| Entradas de clarificación | **53**, en **6 sesiones** (2026-09-07, 2026-09-14, tres del 2026-09-22 y las decisiones del autor del 2026-09-27), más el registro de saneamiento del 2026-09-27, que no abre preguntas | `spec.md` | `grep -c '^- \*\*Q' spec.md` |
| Dependencias externas | **12 declaradas**: **10 vigentes**, 1 resuelta (`DEP-4`) y `DEP-3` **vacante a propósito**. `DEP-12` (evento de baja) se agregó el 2026-09-27 (RD-101) | `spec.md` | `grep -oE 'DEP-[0-9]+' spec.md \| sort -u` |
| Registros de decisión | **RD-1 … RD-110** (110; RD-94…RD-97 del saneamiento y RD-98…RD-110 de las decisiones del autor, ambos del 2026-09-27) | `data-model.md` §11 | `grep -c '^### RD-' data-model.md` |
| Invariantes de datos | **34** (`DI-1`…`DI-29` más `DI-2a'`…`DI-2e`; `DI-2a` eliminado) | `data-model.md` §6 | `grep -oE "^\| \*\*DI-[0-9a-z']+\*\*" data-model.md \| sort -u \| wc -l` |
| Cláusulas de contrato a `api-general` | **19 declaradas**, **17 vigentes** (`CR-13` y `CR-14` eliminadas por RD-50; `CR-19` agregada por RD-101) | `data-model.md` §10 | `grep -oE '^\| \*\*CR-[0-9]+\*\*' data-model.md \| sort -u` |
| Tablas en PostgreSQL | **18**, agrupadas en 16 subsecciones | `data-model.md` §2 | inspección de §2 |
| Familias de claves Redis | **8** (la octava, `recompute:requests`, por RD-100) | `data-model.md` §3 | inspección de §3 |
| Historias de usuario | **7** (US1…US7) | `spec.md` | inspección |
| Tareas | **64 activas** (T001…T065) y **T036 retirada** (RD-95) | `tasks.md` | `grep -cE '^### T0[0-9]{2} ' tasks.md` |
| Checklist de contratos | **30/30** tildados — cerrado | `checklists/requirements-contracts.md` | `grep -c '^- \[x\]'` |
| Checklist de clarificación | **46/46** tildados — cerrado el 2026-09-27 | `checklists/requirements-clarify-2026-09-14.md` | `grep -c '^- \[x\]'` |

> **Tabla recontada el 2026-09-22 y de nuevo el 2026-09-27** (FR: el conteo anterior, 158, medía menciones con otra expresión; 161 son definiciones; invariantes: 33, no 32). Cada cifra tiene al lado el comando que la produce, de modo que
> verificarla cuesta un `grep` y no una lectura. La versión anterior estaba fechada solo de forma
> implícita y por eso **parecía vigente estando vencida en siete de sus doce filas** — un recuento
> sin fecha no envejece a la vista, que es la forma más eficiente de volverse falso sin que nadie lo
> note.

---

## Summary

Servicio de recomendaciones **híbridas y precomputadas** para RecoMe. Expone una API de lectura que sirve
top-N ya calculados; un worker asíncrono recalcula al recibir eventos de actividad; un Data Transformer
sincroniza **unidireccionalmente** desde `api-general` y materializa la proyección del catálogo, los usuarios y la actividad. Los **derivados** —vectores, vocabulario, popularidad— los producen procesos propios, no el sincronizador (DI-13).

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
| Mensajería | RabbitMQ (eventos entre repositorios, solo consumo) · Redis Streams (`recompute:requests`, coordinación interna, RD-100) |
| ORM / migraciones | SQLAlchemy + Alembic |
| Testing | pytest + **testcontainers** |
| Dependencias principales ⁽ʳ⁾ | pydantic v2 (validación/contratos), numpy/scipy o pandas + scikit-learn (TF-IDF, coseno, MMR), `redis-py`, `aio-pika` (RabbitMQ), `httpx` (REST saliente con timeouts) |
| Plataforma ⁽ʳ⁾ | Linux, contenedores; tres procesos desplegables independientes (API, worker, Data Transformer) más jobs periódicos |
| Objetivos de rendimiento ⁽ʳ⁾ | Lectura p95 **constante e independiente del catálogo**, objetivo inicial **≤ 50 ms** p95 en la API (excluida la red); recálculo de un usuario ≤ 2 s p95. **Confirmado como umbral de SC-001 el 2026-09-27 (RD-105)** |
| Escala ⁽ʳ⁾ | MVP de decenas de miles de usuarios y catálogo del orden de 10⁴–10⁵ ítems por módulo |
| Referencia funcional | `Prototipo-Referencia/` (`vectorizer.py`, `domain.py`, `cli_preferencias.py`) |

⁽ʳ⁾ *Restaurado el 2026-09-27 desde `.plan-2026-09-07.bak`: la regeneración del 2026-09-17 omitió estas
filas sin que ninguna decisión posterior las revocara. En particular, SC-001 perdió su único ancla
numérica («umbral acordado»).*

**Consumidor único de cara al producto**: `api-general`. El servicio **no** es alcanzable desde los
frontends (FR-008).

---

## Constitution Check

| Principio | Cómo lo satisface este plan | Riesgo residual |
|---|---|---|
| **I. Frontera de datos y ownership** (NN) | Catálogo, usuarios y actividad son proyección; se materializan, no se editan. La actividad entra **solo** por sincronización o por el evento `recomendacion.actualizar` (RD-95: se retiró el endpoint propio de feedback). Única excepción de autoría local: `user_declared_tags` (§2.14) | La excepción **debe seguir siendo una**: RD-75 fija que un segundo dato de autoría local exige componente propio |
| **II. Contratos como verdad externa** (NN) | CR-1…CR-18 en `data-model.md` §10; contratos propios **definidos primero** y publicados en `api-general` antes de implementar (T049); contract testing como gate de deploy | `api-general` incompleta: los contratos se están **definiendo**, no consumiendo. La señalización de recálculo propia (FR-035) usa un Stream de Redis interno (RD-100), que **no** es contrato entre repositorios. El evento de baja de cuenta (CR-19, DEP-12) **sí** lo es y debe definirse primero en `api-general` |
| **III. Cómputo pesado fuera del request path** (NN) | Top-N materializado; popularidad materializada (FR-033a4); el camino normal de lectura solo lee Redis, con Postgres únicamente como respaldo degradado ante miss (RD-96); el endpoint de escritura tiene **prohibición explícita** de calcular (FR-089b) | **Tensión resuelta por enmienda** (constitución **v1.1.0**, RD-98): el Principio III declara ahora la escritura de declaración como su **única excepción**, con los límites de FR-089b. Pendiente la aprobación de la enmienda por PR (Governance) |
| **IV. Pipeline unidireccional** | Data Transformer solo lee de `api-general`; sin escritura de vuelta | — |
| **V. Gobernanza del motor híbrido** | Configuración versionada, una sola versión activa por entorno, sin A/B en MVP | — |
| **VI. Testing obligatorio y contract testing** (NN) | pytest + testcontainers; contract tests bloquean el deploy | — |
| **VII. Observabilidad y resiliencia asíncrona** | Reintento con backoff exponencial (máx. 5) → DLQ; métricas de cuota, obsolescencia y sincronización | — |

**Resultado** *(revisado 2026-09-27)*: **sin violaciones, condicionado a la aprobación de la enmienda
v1.1.0**. La tensión que registraba esta sección —la escritura de declaración frente al Principio III—
se resolvió enmendando el principio (RD-98), que era la única vía: la constitución prevalece sobre la
spec y una excepción al principio exige enmendarlo (Governance). La otra excepción, el cómputo en la
carga de configuración, no toca el request path.

---

## Project Structure

```
specs/001-recomendaciones-precomputadas/
├── spec.md              # requisitos, criterios de éxito, clarificaciones, DEP-1…DEP-12 (ver inventario)
├── plan.md              # este archivo
├── data-model.md        # AUTORITATIVO · 18 tablas · RD-1…RD-110 · DI-1…DI-29 · CR-1…CR-19
├── tasks.md             # backlog T001…T065 (T036 retirada) en 11 milestones
├── contracts/           # OpenAPI + JSON Schema — producido por T049 (contract-first)
└── checklists/          # auditoría de calidad de requisitos (2 checklists)

src/recomendaciones/     # mismo árbol que tasks.md T001, que es el que manda
├── api/                 # FastAPI — lectura + endpoint de declaración (excepción FR-089); api/services/
├── engine/              # funciones puras: TF-IDF, coseno, k-vecinos, cross-boost, combinación, postprocess.py (edad → exclusión → MMR → cuota)
├── config/              # carga y validación estricta, cálculo de config_version, engine_config/vN.yaml
├── worker/              # consumo de `recomendacion.actualizar`, de `recompute:requests` y del evento de baja; idempotencia, señal, recálculo, supresión
├── transformer/         # Data Transformer: cliente REST de solo lectura, materialización, vocabulario
├── batch/               # procesos periódicos: respaldo, popularidad, purga, refresco etario, warm-up
├── storage/             # db/ (SQLAlchemy, repositorios, resolutor de exclusiones) y cache/ (claves, TTL)
├── observability/       # logging JSON, métricas, health
└── shared/              # dominio y errores tipados
migrations/              # Alembic
```

> *Árbol corregido el 2026-09-27: el anterior (`postprocess/`, `sync/`, `db/` en la raíz) no coincidía
> con el de T001 —del que dependen las rutas de todas las tareas— ni con el plan original.*

---

## 1. Arquitectura por componentes

| Componente | Responsabilidad | Restricción dominante |
|---|---|---|
| **API de lectura** | Sirve top-N materializado; aplica filtros obligatorios; recorta a `top_n` | No calcula (Principio III) |
| **API de escritura (declaración)** | **Única excepción**: persiste `user_declared_tags` | Valida y persiste; **no calcula** (FR-089b) |
| **Engine (librería)** | TF-IDF, coseno, k-vecinos, cross-boost, combinación lineal, MMR | Sin estado propio; determinista dada la configuración |
| **Worker** | Consume eventos, aplica idempotencia, **persiste la señal del evento** y su exclusión (RD-95, RD-96), dispara recálculo | Recálculo por umbral de interacciones (10) |
| **Data Transformer** | Sincroniza desde `api-general`: usuarios, catálogo y actividad (T029) | Unidireccional; proyecta, no crea. **No escribe `item_popularity`, `tag_modules` ni `vocab_*`** (DI-13) |
| **Procesos periódicos** | Purga de señales (T057), recálculo de popularidad (T063), vocabulario y **reconciliación de vectores** (T030), refresco de umbrales etarios (T051) | Operan sobre derivados; su error es reversible. Son los **únicos** escritores de sus tablas |

### Flujo de lectura (request path)

1. Autenticación por API key interna (FR-007).
2. Validación de `top_n` contra `[top_n_min, top_n_max]` = **`[10, 50]`** (FR-006a) — rechazo explícito
   fuera de rango, por **ambos** extremos.
3. Lectura de `filters:{user_id}` (edad, exclusiones y módulos declarados, RD-96); ante **miss de esa
   clave**, repoblado por lectura acotada de Postgres —respaldo degradado sobre datos materializados que
   el Principio III admite—. Redis **caído** (no miss) → `503` con `Retry-After` (FR-065).
4. Verificación de declaración de gustos en el módulo (FR-088); sin ella, rechazo como precondición
   incumplida, antes de toda precedencia de estados.
5. Lectura del resultado desde Redis: `reco:` vigente —bajo la versión activa y, ante miss, bajo las
   **versiones legibles** con igual catálogo etario (RD-103)—; si no hay, **respaldo** (`fallback:`) con
   la señal de FR-056a si existe `reco:stale:`; si no, `reco:stale:` dentro del límite; si no, vacío
   pendiente. Todo miss de resultado escribe una solicitud en `recompute:requests` con supresión por
   `recompute:lock` (FR-034, FR-035, RD-100). **Un miss de resultado nunca consulta Postgres.** Con
   `prefer=stale`, el obsoleto dentro del límite precede al respaldo (FR-056a, RD-107); sin el
   parámetro, el respaldo lleva `stale_available: true` cuando existe ese obsoleto.
6. **Guardas** sobre la lista ya ordenada y acotada (≤ `top_n_max`): comparación ordinal de edad,
   pertenencia a exclusiones y diferencia contra `retired:{module}` (`data-model.md` §4.2, §4.4).
   **Sin MMR, sin similitud, sin reordenamiento** (FR-033d): la diversificación ya ocurrió en el
   recálculo.
7. Recorte a `top_n` y marcado de naturaleza del resultado, evaluado **después** de las guardas
   (FR-006, FR-056, RD-42).

> *Flujo corregido el 2026-09-27: decía «ante miss, lectura de Postgres» y aplicaba «edad → exclusión
> → MMR» en el request path. Ambas cosas contradecían FR-003, FR-033d, FR-065, FR-080b y
> `data-model.md` §4.2/§7.2, que este plan declara autoritativo.*

### Flujo de recálculo (worker)

Evento → idempotencia **de evento** por `event_id` (`processed_events`) → persistencia de la señal con
idempotencia **de señal** por `origin_interaction_id` (DI-21) → resolutor de exclusiones e
invalidación de `filters:{user_id}` (RD-96) → conteo → si alcanza `interaction_recalc_threshold`
(**10**), reconstrucción del perfil y recálculo del top-N → **invalidación de caché en el mismo acto**
(FR-080, Redis primero por FR-080c). Son dos niveles de idempotencia distintos (`data-model.md`
§7.10); la versión anterior de este flujo los confundía en uno. El conteo es una consulta sobre
`user_signals` desde el último cálculo, no un contador almacenado (RD-104).

El worker consume además **`recompute:requests`** (miss, declaración, warm-up, refresco etario; RD-100),
que recalcula sin pasar por el conteo, y el **evento de baja de cuenta** (CR-19), que ejecuta la
supresión de `data-model.md` §7.11 (RD-101). El post-proceso termina con la **cuota de novedades** en
posiciones reservadas (FR-028 paso 4, RD-102).

---

## 2. Modelo de datos y almacenamiento

### Vista de conjunto

Las 18 tablas viven en `data-model.md` §2, que es la fuente autoritativa. Resumen de zonas:

| Zona | Tablas | Naturaleza |
|---|---|---|
| **Proyección** (dato ajeno) | `users`, `items`, `tags`, `item_tags` | Materializado desde `api-general`; **regenerable** |
| **Derivada** (cómputo propio) | `item_vectors`, `user_profiles`, `item_popularity`, `tag_modules`, `vocab_versions`, `vocab_version_tags`, `user_exclusions` ⁽¹⁾ | Recalculable desde lo anterior + señales |
| **Registro de hechos** | `user_signals`, `user_exclusions` ⁽¹⁾, `sync_runs`, `processed_events`, **`user_suppressions`**, **`item_promotions`** | **No regenerable**: es el historial. Las dos últimas, de RD-101 y RD-102 |
| **Dato de origen local** | `user_declared_tags` | **No regenerable desde ningún origen** |
| **Configuración** | `engine_config_versions` | Versionada en el repo, registrada en la base |

⁽¹⁾ Zona mixta (RD-29). *Tabla alineada el 2026-09-27 con `data-model.md` §1.1, que es la normativa:
la anterior ubicaba `tag_modules` y `vocab_*` en proyección —contra DI-13, que prohíbe al Data
Transformer escribirlas— y mezclaba señales con autoría local.*

### Lo no regenerable, y su consecuencia operativa

RD-71 obligó a corregir una afirmación que el plan anterior arrastraba: *«todo lo necesario para
recalcular vive en Postgres»* es cierto para lo proyectado y **falso** para lo propio.

| Entidad | Si se pierde |
|---|---|
| `user_signals` | Se pierde el historial; el filtrado colaborativo arranca de cero |
| `user_declared_tags` | **Hay que volver a preguntarle al usuario** |
| `user_exclusions` | **Los ítems rechazados reaparecen** |
| `user_suppressions` | Se pierde la constancia de las supresiones **y la lápida**: un usuario suprimido que el origen todavía liste se rematerializa |
| `item_promotions` | Ítems ya promovidos vuelven al conjunto emergente si su evidencia cayó (FR-033a6e) |

El respaldo es responsabilidad **operativa**, no de diseño. Queda declarado, no resuelto (RD-71).

### Redis — 8 familias de claves

Caché exclusivamente. Dos familias principales:

| Clave | Contenido | TTL |
|---|---|---|
| `reco:v{cfg}:{user_id}:{module}` | JSON: ítems + score + rank + `config_version` + `computed_at` | `TTL_FRESH` |
| `reco:stale:v{cfg}:{user_id}:{module}` | Marca de resultado personalizado obsoleto disponible | — |

La segunda existe por FR-056a: ante un personalizado obsoleto se sirve el respaldo, **notificando** que
existe un personalizado anterior. La octava familia, `recompute:requests`, es un **Stream** de
solicitudes de recálculo sin TTL y con `MAXLEN` (RD-100); el inventario completo está en `data-model.md`
§3.1.

### Configuración versionada — inventario verificado

**Parámetros del motor** (`data-model.md` §4, dentro del repositorio, versionados):

| Parámetro | Valor | Origen |
|---|---|---|
| `alpha` / `beta` / `gamma` | 0,5 / 0,3 / 0,2 | Diseño del motor |
| `k` (vecinos) | 20 | Diseño del motor |
| `lambda_mmr` | 0,7 | Diseño del motor |
| `top_n_min` / `top_n_default` / `top_n_max` | **10 / 20 / 50** | RD-73, RD-78 |
| `peso_like` / `peso_dislike` | **1,0 / −1,0** | RD-73. **Sin peso de consumo**: el 0,3 que RD-73 adoptaba del prototipo contradecía FR-022b y se eliminó (RD-99) |
| `collab_min_neighbors` | **10** | RD-84, FR-096 |
| `version_label` | distinto en cada archivo | RD-94 (hace posible el rollback hacia adelante) |
| `popularity_confidence_z` | **1,96** | RD-53 |
| `popularity_window_days` | **90** | RD-53, RD-108 |
| `fallback_new_item_quota_ratio` | **0,20** — cuota del **top-N personalizado** (el prefijo es histórico) | RD-77, RD-80, RD-102 |
| `declared_tags_min` | **5** | RD-68 |
| `region_weight_factor` | **0,1** | RD-79 |
| `diversity_max_cluster_share` | **0,4**, cluster = tag principal del ítem, aplicado como tope en la selección | FR-071a, RD-108 |
| `emergent_evidence_threshold` (promoción al conjunto general) | **20** | RD-67, RD-102, RD-108 |
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
`sync_volume_delta_ratio` = **0,9**, `interaction_recalc_threshold` = **10**, `recompute_requests_maxlen`
= **100 000** (RD-100, RD-108), `event_redelivery_window_hours` (RD-110, copiado del broker), retención de la marca de idempotencia, TTLs de caché, umbrales de reintento.

> La distinción no es estética: los del motor entran en el **cálculo** de un derivado versionado (RD-13);
> los operativos no alteran ningún puntaje. `interaction_recalc_threshold` es el caso intermedio y va
> con los operativos: no altera el valor del top-N, solo **cuándo** se lo recomputa.

---

## 3. Contratos e interfaces

### 3.1 Lectura (expuesto a `api-general`)

`GET` de recomendaciones por usuario y módulo, con **`top_n`** como único parámetro de tamaño y **sin
paginación** (FR-005, RD-107). Devuelve identificador, posición, score y `config_version` por ítem
(FR-004), más la marca temporal y la **naturaleza** del resultado (FR-006): personalizada vigente ·
personalizada obsoleta · de respaldo no personalizada · vacía por falta de candidatos · vacía por
recálculo pendiente. Cuando sirve respaldo existiendo un personalizado obsoleto, marca
**`stale_available: true`**; el cliente puede pedir ese obsoleto con **`prefer=stale`** (FR-056a).

### 3.2 Escritura de declaración (excepción declarada)

`POST` de gustos declarados. **Confirmación síncrona** (FR-089a): asíncrona rechazaría al usuario por no
haber declarado lo que acaba de declarar. Valida el mínimo (FR-083), resuelve la herencia por tag
compartido (FR-085) y persiste. **Prohibido calcular** (FR-089b).

### 3.3 Eventos consumidos

`recomendacion.actualizar` desde RabbitMQ. Dos niveles de idempotencia: **de evento** por `event_id`
(`processed_events`, FR-011) y **de señal** por `origin_interaction_id` (`NOT NULL UNIQUE`, DEP-8,
FR-011a), que por eso es campo obligatorio del evento (FR-061).

**Baja de cuenta** (CR-19, DEP-12; nombre propuesto `usuario.eliminado`): dispara la supresión (FR-091a),
con idempotencia por `event_id`. **Su contrato no existe todavía**: debe definirse primero en
`api-general` (Principio II, RD-101).

### 3.4 Política de errores

Rechazo explícito ante: `top_n` fuera de `[10, 50]` · ausencia de API key · falta de declaración de
gustos (FR-088) · payload inválido. Fallo transitorio (DB/Redis): reintento con backoff exponencial,
máx. 5 → DLQ.

### 3.5 Dependencias externas — **12 declaradas, 10 vigentes** *(recontado 2026-09-27)*

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
| DEP-11 | **Backfill de `region` en usuarios preexistentes**, por `api-general`, antes del despliegue | Vigente |
| DEP-12 | **Notificación de baja de cuenta** como evento propio (CR-19) | Vigente — **sin contrato aún** (RD-101) |

> **DEP-10 es la más severa del inventario.** Es la única dependencia cuyo incumplimiento deja al sistema
> **sin ningún usuario atendible**: sin vocabulario no hay declaración posible, y FR-088 rechaza todo.
> Se distingue de DEP-7, que es *por ítem*; DEP-10 es *sobre el conjunto*.

---

## 4. Plan de implementación por fases

La asignación **autoritativa** por tarea está en `tasks.md` («Asignación de fases»); esta tabla la
resume y no la sustituye.

| Fase | Tareas (`tasks.md`) | Contenido | Gate de salida |
|---|---|---|---|
| **1 — Vertical slice** | T001–T024, T027–T030, T033–T035, T037, T038, **T049**, T053–T055, T063, **T064** | Esquema, configuración, motor y post-proceso (test-first), caché, worker con persistencia de señal, Data Transformer y vectores, contratos, lectura, declaración, respaldo | Un usuario declarado obtiene un top-N materializado end-to-end; US1, US2, US5 |
| **2 — Robustez operativa** | T025, T026, T031, T032, T039–T042, T046, T051, T052, T056, T057, T060–T062, **T065** | Reintentos y DLQ, freshness, observabilidad, alertas, refresco etario, ciclo de vida del ítem, purga, umbral de recálculo, ponderación regional, cuota de novedades en el personalizado | Sobrevive a fallos; US3, US4, US6, US7 |
| **3 — Optimización y cierre** | T043–T045, T047, T048, T050, T058, T059 | Contract testing en CI, casos críticos, CI con gates, carga, supresión verificada | Definition of Done completa |

> *Tabla corregida el 2026-09-27: tenía cuatro fases que no coincidían con las tres de `tasks.md` y
> ubicaba el motor en la Fase 2 mientras el gate de la Fase 1 exigía un top-N calculado.*

### Consistencia interna — verificada

- El orden edad → exclusión → MMR → cuota es **obligatorio** y está cubierto por M3 y T065.
- La invalidación de caché ocurre en el mismo acto que la actualización (FR-080): no hay camino por el
  que el resultado se actualice y la caché sobreviva.
- `origin_interaction_id` sostiene la idempotencia y es dependencia externa (DEP-8), de modo que M5 no
  puede cerrarse sin acuerdo de contrato.

### Funcionalidad clarificada **sin tarea asignada** — inconsistencia pendiente

> ✅ **RESUELTA el 2026-09-22.** Se conserva como registro de una inconsistencia real —el plan
> advertía que Fase 1 produciría un sistema que rechaza al 100 % de sus usuarios— y de qué la
> resolvió.

**El aviso decía**: «FR-088 rechaza toda solicitud de un usuario sin declaración de gustos, y la
declaración no tiene tarea asignada en `tasks.md`». Era exacto cuando se escribió.

**Qué lo resolvió**: la actualización delta de `tasks.md` del 2026-09-17 creó **T053** (endpoint de
declaración), **T054** (herencia entre módulos) y **T055** (rechazo por módulo sin declaración). El
camino completo tiene tarea: escribir la declaración, heredar sin que cuente para el mínimo, y
rechazar antes de la precedencia de estados.

**Estado del resto del párrafo, verificado una por una el 2026-09-22**:

| Funcionalidad que el aviso listaba | Estado |
|---|---|
| Purga de señales | ✅ **T057** |
| Supresión verificada | ✅ **T058** (aborto del recálculo) y **T059** (verificación y observador) |
| Disparador por conteo | ✅ **T060** |
| Ponderación regional | ✅ **T061** |
| Señal de obsoleto disponible | ✅ **T062** |
| **Siembra de vectores** | ✅ **Cerrado el 2026-09-22 sin crear tarea**: se extendió **T030**. El agujero era **mayor que la siembra** — ver nota abajo |

**Sobre la siembra de vectores — cerrado el 2026-09-22, y era peor de lo declarado.**

El pendiente se enunció como «falta el poblado inicial de `item_vectors`». La auditoría de la cadena
de escritura mostró que el arranque era solo **el caso visible** de un defecto permanente: T030 se
disparaba **únicamente al cambiar el hash del vocabulario**, y ese hash es función del conjunto de
**tags**, no de ítems. Por lo tanto **todo ítem nuevo cuyos tags ya existieran quedaba sin vector de
forma indefinida**, con el catálogo en régimen normal y sin que nada fallara.

**Qué lo cerró**: T030 pasó de «transición entre versiones» a **vocabulario y reconciliación de
vectores**. Tras cada sincronización, todo ítem vigente con tags y sin vector recibe uno; el arranque
desde vacío es el caso degenerado del mismo procedimiento, no un camino aparte. No se creó tarea
nueva: `data-model.md` ya situaba ambas responsabilidades en ese job.

**No hay pendientes en esta sección.**

---

## 5. Plan de testing

| Nivel | Alcance | Herramienta |
|---|---|---|
| **Unitario** | Engine puro: TF-IDF, coseno, MMR, combinación lineal | pytest |
| **Invariantes** | DI-1…DI-29: filtro etario, exclusión, disjunción de conjuntos, lápida de supresión | pytest + fixtures |
| **Integración** | Postgres + Redis + RabbitMQ reales | testcontainers |
| **Contract** (**gate de deploy**) | Validación del payload contra CR-1…CR-19 | pytest |

**Casos que deben estar cubiertos explícitamente**: evento duplicado · payload inválido · `api-general`
caída durante la sincronización · Redis caído · broker caído · `top_n` fuera de rango por **ambos**
extremos · usuario sin declaración · cuota de novedades con conjunto emergente vacío · usuario suprimido
que el origen sigue listando · cambio de versión con y sin cambio del catálogo etario.

**TDD en toda tarea de producción** *(desde el 2026-09-27, decisión del autor)*: el test precede a la
implementación en toda tarea que produce código; quedan exentas solo las que **son** tests, documentos o
configuración de CI (lista en `tasks.md`, *Política TDD*). Antes: «TDD selectivo, obligatorio en
invariantes de seguridad y en el contrato; opcional en el resto».

---

## 6. Observabilidad y operación

**Métricas mínimas**: proporción del top-N personalizado servido que provino de la cuota
(`fallback_new_item_share`, nombre histórico, FR-033a8, RD-102) — distinguiendo cuota **disponible** de **efectivamente ocupada** — · tasa de resultados
obsoletos servidos · latencia del request path · profundidad de la cola y tamaño de la DLQ · longitud y pendientes de `recompute:requests` · resultado de
cada corrida de sincronización (`sync_runs`).

**Trazabilidad**: identificador de origen (`origin_interaction_id` en el worker), `user_id`, `module`,
`config_version`, `outcome`.

**Salud**: `liveness` (el proceso vive, sin dependencias), `readiness` (dependencias críticas: Redis
para la API; Redis, Postgres y broker para el worker; Postgres para el Data Transformer) y exposición
de la `config_version` activa (T041). **Redis caído no es un modo degradado de servicio**: la API
responde `503` con `Retry-After` y **nunca** sirve desde Postgres (FR-065, T021). *(Corregido el
2026-09-27: decía «degradado: Redis caído, se sirve desde Postgres», lo que FR-065 prohíbe.)*

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

Los pendientes de clarificación NC-1…NC-20 están **todos cerrados** (`data-model.md` §12). El
saneamiento del 2026-09-27 encontró **conflictos entre textos ya decididos**; el autor los resolvió el
mismo día:

| Conflicto | Textos en tensión | Resolución | Tareas |
|---|---|---|---|
| Escritura de declaración en una API «estrictamente de solo lectura» | FR-089 ↔ constitución, Principio III | ✅ Constitución **v1.1.0**, única excepción (RD-98). **Falta aprobar la enmienda por PR** | T053 |
| Peso del consumo en el perfil | RD-73, T004 ↔ FR-022b, US5-8, SC-019, T008 | ✅ Se elimina el peso (RD-99) | T004, T008 |
| Canal de la señalización de recálculo propia | FR-035, FR-089b, T020, T022, T051 ↔ Principio II | ✅ Stream de Redis interno `recompute:requests` (RD-100) | T018, T020, T022, T027, T051, T053 |
| Disparo de la supresión y dónde vive su estado | FR-091…FR-095 sin origen ni entidad | ✅ Evento de baja (CR-19, DEP-12) y `user_suppressions` (RD-101). **Falta el contrato en `api-general`** | T003, T029, T058, T059 |
| Orden por afinidad y cuota por solicitud en un respaldo global; pertenencia derivada vs. promoción definitiva | FR-033a6f1, FR-033a6a ↔ FR-033c, FR-033d; FR-033a6c ↔ FR-033a6e | ✅ Cuota en el top-N personalizado; `item_promotions` (RD-102) | T038, T063, T065 |
| Convivencia de versiones de configuración | FR-025c, SC-022 ↔ `data-model.md` §2.8 | ✅ Se leen versiones con igual catálogo etario (RD-103) | T018, T020 |
| Contador de FR-080a sin entidad | FR-080a ↔ modelo de datos | ✅ Derivado de `user_signals`, por (usuario, módulo) (RD-104) | T003, T060 |
| IDF, vecinos no positivos, umbral de SC-001 | T007, T010, SC-001 sin valor | ✅ RD-105 | T007, T010, T050 |
| «Likes suficientes» sin umbral | FR-033a2 ↔ SC-024, edge cases | ✅ Sin umbral: sin evidencia se ordena por desempate (RD-106) | T038 |
| Forma del contrato de lectura y del obsoleto «consultable» | FR-005, FR-056a | ✅ Solo `top_n`; `stale_available` + `prefer=stale` (RD-107) | T033, T049, T062 |
| Valores sin fijar; D3 | FR-071, §4 | ✅ RD-108 | T004, T010, T015, T063 |
| Edición de la declaración; dislikes sobre tags declarados | CHK037, CHK038 | ✅ Definitiva; el peso puede anularse (RD-109) | T053 |
| Irreversibilidad sin FR; ventanas de FR-068b abiertas; DEP-10 como supuesto | CHK050, CHK051, CHK065 | ✅ FR-068e, lista cerrada, DEP-10 con métrica (RD-110) | T004, T030, T042 |

**Siguen abiertos**: ninguna decisión de diseño. CHK072 se cerró agregando SC-028…SC-031.

**Valores a calibrar**, que no son decisiones sino mediciones pendientes: frecuencia de sincronización ·
periodicidad del respaldo · `event_redelivery_window_hours` (se copia del broker de `notificaciones`) ·
`signal_retention_days` dentro del rango 18–24 meses.

> Todos son configuración versionada u operativa y su error es **reversible**, salvo
> `signal_retention_days`, que puede acortarse pero **no alargarse** porque lo purgado no vuelve. Por eso
> su valor inicial debe ser conservador.

---

## Definition of Done (para pasar a `/speckit.tasks`)

- [x] Constitution Check sin violaciones no declaradas
- [x] Modelo de datos completo y autoritativo (`data-model.md`)
- [x] Contrato a `api-general` especificado (CR-1…CR-19; CR-19 agregada el 2026-09-27)
- [x] Dependencias externas inventariadas (**12 declaradas, 10 vigentes**; `DEP-4` resuelta, `DEP-3` vacante)
- [x] Pendientes de clarificación cerrados (NC-1…NC-20)
- [x] Parámetros de configuración con valor o con criterio de calibración
- [x] **`tasks.md` actualizado** — ejecutado el 2026-09-17 (delta de encabezado, T003, T004, T017,
      T042, T047 y doce tareas nuevas) y el 2026-09-22 (`T052` creada, seis tareas desbloqueadas,
      27/27 criterios de éxito atribuidos). Coherente con el Anexo C de este mismo archivo, que ya
      lo declaraba ejecutado mientras este ítem seguía sin tildar — **contradicción interna
      resuelta el 2026-09-22**
- [x] **Incidencias de GitHub propagadas** — ejecutado el 2026-09-27 con `publish_issues.py` y
      `link_and_epics.py`: #1–#50 actualizados, T051–T065 creados como **#61–#75** en el milestone M11,
      épico de M11 en **#76**, dependencias enlazadas por número y **#36 cerrado como no planeado**
      (T036 retirada). *(Hasta esa fecha el ítem seguía sin tildar porque el Anexo C solo declaraba el
      impacto.)*

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

## Anexo C — Impacto sobre `tasks.md` e incidencias *(tasks.md ejecutado; incidencias declaradas)*

**Estado**: `tasks.md` se actualizó en **dos pases** —2026-09-17 y 2026-09-22—. La propagación a
GitHub sigue **declarada y no ejecutada**.

**Segundo pase, 2026-09-22 — levantamiento del bloqueo del ciclo de vida del ítem**:
- **T052 creada** en el identificador que la sección de bloqueo mantuvo reservado doce días.
- **Seis tareas desbloqueadas y modificadas**: T012, T017, T018, T029, T037, T038.
- **27/27 criterios de éxito atribuidos** a la tarea que los verifica (antes eran 4). *(Desde el
  2026-09-27: **31/31**; SC-028 → T029, SC-029 → T053 y T055, SC-030 → T059, SC-031 → T061.)*
- **Tres FR nuevos citados** donde faltaban: FR-084 en T053, FR-086 en T054, FR-091 en T058/T059.
- La sección «Tareas bloqueadas» pasó a ser **registro histórico de un bloqueo levantado**.
- Total del backlog: **63 tareas**.

**Tercer pase, 2026-09-22 — auditoría de la cadena de popularidad y de la escritura de vectores**:
- **T029**: eliminado su criterio sobre popularidad — violaba **DI-13** («el Data Transformer no
  escribe `item_popularity`»). Reemplazado por un criterio **negativo y verificable**. Es la
  **tercera vez** que un derivado se aloja en la zona de proyección (RD-12, RD-14, y esta).
- **T063 produce / T038 consume**: reparto explícito. T038 pasa a **leer** `item_popularity`,
  ordenar por `popularity_score` —no por `like_count`— y recibe el criterio de **cuota** que estaba
  en T063. **T063 se movió a Fase 1**, arrastrada por la dependencia de T038 (hallazgo F2).
- **T030** extendida a **reconciliación de vectores**: cierra un agujero por el que todo ítem nuevo
  con tags preexistentes quedaba sin vector de forma permanente.
- **Tabla de fases completada T001–T063**, con fundamento por tarea.
- **`data-model.md` §2.4** precisado: el escritor único de `item_vectors` es T030; T007 es una
  función pura y no escribe.
- **Corrección F9 — `T028`, `T029` y `T030` se mueven a Fase 1.** `item_vectors` tenía un único
  escritor (T030) en Fase 2, mientras `T009` la leía desde Fase 1 y `T012` dependía de T009. Con la
  tabla vacía, `α = 0,5` aportaba cero **y el pipeline corría sin fallar**: sin excepción, sin test
  rojo y sin alerta, produciendo recomendaciones plausibles con medio motor apagado. La cadena
  arrastra —T030 ← T029 ← T028—, de modo que los tres pasan. **T031** (freshness) y **T032**
  (`api-general` caído) quedan en Fase 2: Fase 1 necesita que la sincronización *funcione*, Fase 2
  que *sobreviva a que falle*.
  **Costo declarado**: Fase 1 deja de ser un slice mínimo y absorbe el Data Transformer completo,
  con él la dependencia de `api-general`, que está **incompleta** (RD-47).

**Tareas actualizadas** (hecho): T003 (16 tablas de `data-model.md` §2, no 10 de `plan.md`), T004
(inventario completo de §4 y rechazo de `tiebreak_criteria`), T017 (32 invariantes, DI-28 con test
propio), T042 (alerta de liveness en reemplazo de la métrica de antigüedad), T047 (DEP-1…DEP-11 y
CR-1…CR-18), más la cabecera (fuentes de verdad y conteos).

**Tareas nuevas creadas** (hecho): T051 · T053 · T054 · T055 · T056 · T057 · T058 · T059 · T060 ·
T061 · T062 · T063, más **T052**. Total del backlog: **63 tareas**.

**Bloqueado, no omitido** *(registro del primer pase, 2026-09-17 — **ya no vigente**: el segundo pase
del 2026-09-22 creó T052 y modificó las seis tareas, ver arriba)*: T052 (ciclo de vida del ítem) **no se creó**, y T012, T018, T029, T037,
T038 y T017 no se modificaron en ese aspecto, porque dependen de **FR-072…FR-075, que no existen en
`spec.md`** — `data-model.md` §9 los propone y advierte que «no deben aplicarse al backlog hasta que
se aprueben». La numeración salta de T051 a T053 y el hueco se deja declarado.

**Incidencias** *(declarado, no ejecutado)*: #3, #4, #17, #42 y #47 requieren actualización de
cuerpo; las nuevas van de **#61 a #72** (T051→#61, T053→#62, …), con la salvedad de que la
correspondencia `TXXX`→`#XXX` no se sostiene porque #51–#60 ya son épicas.

**Componentes con proceso periódico** — verificado que la lista los incluye: refresco de derivados
etarios (T051), purga de señales (T057) y recálculo de popularidad por ventana (T063).

> Propagación **pendiente de comando expreso**. Este anexo enumera el alcance; no lo ejecuta.
