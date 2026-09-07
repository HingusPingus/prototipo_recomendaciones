# Implementation Plan: Servicio de Recomendaciones Híbridas Precomputadas (MVP)

**Branch**: `001-recomendaciones-precomputadas` | **Date**: 2026-09-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-recomendaciones-precomputadas/spec.md` (48+ FR, 27 SC, 5 clarificaciones)

## Summary

Servicio de recomendaciones híbridas para RecoMe, alcanzable únicamente desde `api-general`. La API
sirve top-N estrictamente desde caché; todo el cómputo (TF-IDF, coseno, colaborativo, cross-module
boost, MMR) ocurre en un worker asíncrono disparado por `recomendacion.actualizar`. Un Data
Transformer sincroniza unidireccionalmente desde `api-general` y materializa perfiles y vectores en
la DB Recomendaciones. Los filtros de edad y exclusión son invariantes de seguridad aplicados tanto
en el recálculo como en la salida.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: FastAPI (API), pydantic v2 (validación/contratos), pandas + scikit-learn o
numpy/scipy (TF-IDF, coseno, MMR), SQLAlchemy + Alembic (DB y migraciones), `redis-py` (caché),
`pika`/`aio-pika` (RabbitMQ), `httpx` (REST saliente con timeouts)

**Storage**: PostgreSQL + pgvector (fuente derivada, autoritativa dentro del repo), Redis (caché,
no fuente de verdad)

**Testing**: pytest, `testcontainers` (Postgres/Redis/RabbitMQ efímeros), `schemathesis` o validación
directa contra OpenAPI/JSON Schema de `api-general` para contract testing

**Target Platform**: Linux, contenedores; tres procesos desplegables independientes

**Project Type**: Servicio backend multi-proceso (API + worker + job de sincronización)

**Performance Goals**: lectura p95 constante e independiente del catálogo (objetivo inicial ≤ 50 ms
p95 en API, excluida la red); recálculo de un usuario ≤ 2 s p95

**Constraints**: cero cómputo pesado en request path; Redis reconstruible por completo; sin acceso a
DB ajenas; no expuesto a frontends

**Scale/Scope**: MVP de decenas de miles de usuarios y catálogo de orden 10⁴–10⁵ ítems por módulo

## Constitution Check

*GATE: verificado antes de Phase 0 y re-verificado tras el diseño de Phase 1.*

| Principio | Cómo lo cumple el plan | Estado |
|---|---|---|
| I — Frontera de datos y ownership | Único cliente de Postgres/Redis propios; salida solo por HTTP a `api-general`; sin drivers de DB ajenas en dependencias; servicio en red interna, no publicado | ✅ |
| II — Contratos externos | OpenAPI y JSON Schema se consumen desde `api-general`; se versionan como artefactos derivados en `contracts/`; contract tests bloqueantes en CI | ✅ (con 2 dependencias externas abiertas, ver §8) |
| III — Cómputo fuera del request | API solo `GET` sobre Redis; el filtrado del respaldo es O(N) sobre lista corta ya ordenada; test de instrumentación que falla si se invoca el módulo de scoring desde el proceso API | ✅ |
| IV — Sincronización unidireccional | Data Transformer con cliente HTTP de solo lectura; sin credenciales de escritura; API key interna por entorno | ✅ |
| V — Motor gobernado | `engine_config/vN.yaml` versionado en repo, hash de contenido como `config_version`, validación al cargar, evaluación offline reproducible por PR | ✅ |
| VI — Testing y contract testing | Unit determinista del motor, integración con contenedores, contract tests contra `api-general` como gate de deploy | ✅ |
| VII — Observabilidad y resiliencia | Métricas Prometheus por componente, logging JSON con `correlation_id`, health/ready/live, DLQ y backoff | ✅ |

**Resultado**: sin violaciones. No se requiere Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-recomendaciones-precomputadas/
├── plan.md              # Este archivo
├── spec.md              # Especificación clarificada
├── research.md          # Phase 0: decisiones técnicas y alternativas
├── data-model.md        # Phase 1: entidades, tablas, claves Redis
├── quickstart.md        # Phase 1: levantar el stack local
├── contracts/           # Phase 1: OpenAPI propio + copias derivadas de api-general
└── tasks.md             # Phase 2: generado por /speckit.tasks
```

### Source Code (repository root)

```text
src/recomendaciones/
├── api/                     # FastAPI: routers, dependencias, esquemas de respuesta
│   ├── routes/
│   ├── deps.py              # auth por API key interna, cliente Redis
│   └── schemas.py
├── engine/                  # Motor puro, sin I/O — importable solo por worker/batch
│   ├── content.py           # TF-IDF + coseno
│   ├── collaborative.py     # k vecinos
│   ├── cross_module.py      # cross-module boost
│   ├── scoring.py           # combinación alpha/beta/gamma
│   └── postprocess.py       # edad → exclusión → MMR
├── config/
│   ├── loader.py            # validación estricta, cálculo de config_version
│   └── engine_config/       # v1.yaml, v2.yaml ... (versionado en repo)
├── worker/                  # Consumidor de recomendacion.actualizar
│   ├── consumer.py
│   ├── handler.py           # idempotencia, propagación cross-module
│   └── dlq.py
├── transformer/             # Data Transformer
│   ├── client.py            # httpx read-only hacia api-general
│   └── pipeline.py          # materialización idempotente
├── batch/
│   └── fallback.py          # top-N de respaldo por módulo (populares + MMR)
├── storage/
│   ├── db/                  # SQLAlchemy models, repositorios
│   └── cache/               # claves, serialización, TTL
├── observability/           # logging JSON, métricas, health checks
└── shared/                  # dominio, errores, tipos

migrations/                  # Alembic
tests/
├── unit/                    # engine, config, claves de caché
├── integration/             # Postgres, Redis, RabbitMQ (testcontainers)
├── contract/                # OpenAPI propio + schema del evento
└── invariants/              # edad y exclusión: batería exhaustiva
```

**Structure Decision**: monorepo de un solo paquete con tres entrypoints (`api`, `worker`,
`transformer`) más un job batch. `engine/` es una librería pura sin I/O, lo que hace triviales los
tests deterministas y permite una regla de arquitectura verificable: **el proceso API no importa
`engine/`**.

---

## 1. Arquitectura por componentes

| Componente | Responsabilidad | Prohibiciones explícitas |
|---|---|---|
| **API de lectura** (FastAPI) | Autenticar API key interna, validar params, leer Redis, aplicar filtros de salida, marcar naturaleza de la respuesta | No importa `engine/`; no consulta Postgres en el camino normal; no publica eventos salvo la señal de recálculo |
| **Worker de recálculo** | Consumir `recomendacion.actualizar`, validar schema, resolver idempotencia, ejecutar motor + post-proceso, escribir Redis, decidir propagación cross-module | No expone HTTP; no llama a `api-general`; no escribe fuera de su propia DB/caché |
| **Data Transformer** | Leer usuarios/catálogo/actividad de `api-general`, materializar perfiles, vectores, exclusiones y vocabulario compartido | Cliente HTTP de solo lectura; sin verbos de mutación; sin acceso a DB ajenas |
| **Batch de respaldo** | Precomputar top-N de populares por módulo, diversificado por MMR | No personaliza por usuario |
| **Engine (librería)** | TF-IDF, coseno, k-vecinos, cross-boost, combinación lineal, post-proceso | Funciones puras: sin red, sin DB, sin reloj implícito |

### Flujo de lectura (request path)

```
api-general --(API key)--> API
                            ├─ HIT vigente        → top-N personalizado
                            ├─ HIT vencido        → re-filtra edad/exclusión → "obsoleto" + señal recálculo
                            ├─ MISS + sin perfil  → respaldo del módulo → re-filtra → "no personalizado"
                            └─ MISS total         → vacío "pendiente" + señal recálculo (con supresión)
```

El re-filtrado de salida es una intersección de conjuntos sobre ≤ N ítems: no es scoring y por eso
no vulnera FR-003. Los conjuntos de exclusión y la edad se leen de una clave Redis propia y liviana,
no de Postgres.

### Flujo de recálculo (worker)

```
evento → validar schema → dedupe por event_id → cargar perfil/candidatos de Postgres
       → scoring híbrido → edad → exclusión → MMR → escribir Redis (vigente + config_version)
       → ¿algún tag ∈ vocabulario compartido? → sí: repetir para el módulo opuesto
```

---

## 2. Modelo de datos y almacenamiento

### PostgreSQL + pgvector (estado derivado y duradero)

| Tabla | Contenido | Notas |
|---|---|---|
| `users` | id, edad/`max_age_rating`, marca de sincronización | Proyección de `api-general` |
| `items` | id, módulo, `age_rating`, popularidad (nº de likes) | `age_rating` NOT NULL con default no-apto |
| `item_tags` | item_id, tag_id, peso | |
| `item_vectors` | item_id, `vector` (pgvector), `vocab_version` | Recalculado al sincronizar catálogo |
| `user_profiles` | user_id, módulo (`peliculas`/`juegos`/`general`), `vector` | Tres filas por usuario |
| `user_signals` | user_id, item_id, tipo (like/dislike/consumo), `occurred_at` | Base de exclusión y de perfil |
| `user_exclusions` | user_id, item_id, origen, `is_active` | Vista materializada de la resolución de señales |
| `shared_tags` | tag_id | Vocabulario compartido; recalculado por sincronización |
| `sync_runs` | id, inicio, fin, estado, volumen | Para métrica de *freshness* |
| `processed_events` | `event_id`, procesado_en | Idempotencia del worker (TTL de retención) |

**Regla de exclusión**: `user_exclusions` se deriva de `user_signals` aplicando "gana la señal más
reciente"; un consumo genera exclusión permanente, un dislike genera exclusión revertible por like
posterior.

### Redis (caché, nunca fuente de verdad)

| Clave | Valor | TTL |
|---|---|---|
| `reco:v{cfg}:{user_id}:{module}` | JSON: ítems + score + rank + `config_version` + `computed_at` | `TTL_FRESH` (ej. 24 h) |
| `reco:stale:{user_id}:{module}` | Copia del último resultado conocido | `TTL_STALE` (ej. 7 d) |
| `filters:{user_id}` | `max_age_rating` + set de exclusiones | `TTL_FILTERS` (ej. 1 h) |
| `fallback:{module}` | Top-N de respaldo diversificado | `TTL_FALLBACK` (ej. 6 h) |
| `recompute:lock:{user_id}:{module}` | Marca de supresión de señales | `TTL_SUPPRESS` (ej. 5 min) |
| `dedupe:event:{event_id}` | Marca de evento procesado | `TTL_DEDUPE` (ej. 24 h) |

**Invalidación / regeneración**: no hay invalidación masiva. Al vencer `TTL_FRESH` la entrada pasa a
servirse como obsoleta desde `reco:stale` hasta `TTL_STALE`; superado ese límite se responde
"pendiente". La pérdida total de Redis es recuperable: todo lo necesario para recalcular vive en
Postgres. La reconstrucción se hace por un job de *warm-up* que publica señales de recálculo con
límite de tasa, no en línea.

**Trazabilidad**: `config_version` es el hash del archivo de configuración activo y forma parte de
la clave, lo que hace que resultados de versiones distintas convivan sin colisionar. El campo se
propaga a la respuesta por ítem.

### Versionado de configuración

`src/recomendaciones/config/engine_config/vN.yaml` contiene `alpha`, `beta`, `gamma`, `k`,
`lambda_mmr`, `peso_like`, `peso_dislike`, `top_n_default`, `top_n_max`. El loader valida rangos y
que `alpha+beta+gamma≈1`, rechaza la desactivación de filtros obligatorios y expone
`config_version` por `/health` y como métrica.

---

## 3. Contratos e interfaces

### 3.1 Lectura (expuesto a `api-general`)

```
GET /internal/v1/recommendations/{user_id}?module=peliculas&limit=20&cursor=...
Header: X-Internal-API-Key
```

Respuesta:

```jsonc
{
  "user_id": "...", "module": "peliculas",
  "result_type": "personalized|personalized_stale|fallback|empty_no_candidates|empty_pending",
  "computed_at": "2026-09-07T12:00:00Z",
  "config_version": "sha256:ab12...",
  "items": [{"item_id": "...", "rank": 1, "score": 0.87}],
  "next_cursor": null
}
```

`result_type` cubre los cinco estados de FR-006. Errores: `401` sin API key, `422` params inválidos,
`503` con `Retry-After` si Redis está caído.

### 3.2 Evento consumido

`recomendacion.actualizar` — schema propiedad de `api-general`. Campos mínimos requeridos:
`event_id`, `user_id`, `module`, `item_id`, `signal_type`, `occurred_at`.

Política de errores:

| Situación | Acción |
|---|---|
| Payload inválido | Rechazo inmediato → DLQ, sin reintento, log con causa |
| Módulo desconocido | DLQ, no altera ningún top-N |
| `event_id` ya procesado | ACK sin recomputar (idempotencia) |
| Fallo transitorio (DB/Redis) | Reintento con backoff exponencial, máx. 5 → DLQ |
| Fallo solo en módulo opuesto | Se conserva el resultado del módulo principal; se reencola solo el opuesto |

### 3.3 Contratos internos

`engine/` expone funciones puras con tipos explícitos (`score_candidates`, `apply_postprocess`);
`storage/` expone repositorios; ninguna capa superior conoce el detalle de Redis o SQL. Regla
verificada por test: `api/` no importa `engine/`.

---

## 4. Plan de implementación por fases

| Fase | Objetivo | Cambios principales | Riesgos | Criterios de aceptación |
|---|---|---|---|---|
| **1 — Vertical slice** | Servir top-N precomputado end-to-end | Esquema DB + migraciones; `engine/` completo con post-proceso; worker consumiendo el evento; API de lectura cache-first; config v1; unit tests del motor | Contrato del evento aún no cerrado con `api-general`; datos de actividad sin tipo de señal | US1 y US2 demostrables; SC-002/003 (0 % violaciones de filtros); SC-005 (idempotencia básica); SC-009 (sin cómputo en request) |
| **2 — Robustez operativa** | Que sobreviva a fallos reales | Data Transformer completo; idempotencia por `event_id` + DLQ + backoff; stale-while-revalidate con supresión; batch de respaldo; métricas, health checks y logging estructurado; contract testing en CI | Avalancha de recálculos tras pérdida de caché; drift de contratos | US3/US4/US6/US7; SC-006/007/008/015; SC-013 (contract tests bloqueantes); SC-024/026/027 |
| **3 — Optimización y endurecimiento** | Rendimiento y gobernanza | Índices pgvector y tuning de consultas; propagación cross-module condicional afinada; consolidación de ráfagas; job de warm-up con límite de tasa; harness de evaluación offline reproducible; alertas | Regresión de calidad al tocar pesos; costo del recálculo doble | SC-001 (latencia estable a 10× catálogo); SC-010/011 (cold start cruzado y diversidad); SC-016/017; SC-021 (reproducibilidad exacta) |

---

## 5. Plan de testing

**Unit** (`tests/unit/`, sin I/O, semilla fija): TF-IDF y coseno; agregación de k vecinos; cross-module
boost; combinación alpha/beta/gamma; desempate determinista; cada regla de post-proceso; loader de
configuración (rechaza inválidas y config que desactive filtros); resolución de señales
like/dislike/consumo y reversión por like posterior.

**Integración** (`testcontainers`): repositorios contra Postgres real y migraciones aplicadas;
serialización, TTL y transición vigente→obsoleto→pendiente en Redis; worker punta a punta contra
RabbitMQ real, incluyendo DLQ y reintentos; Data Transformer contra un doble de `api-general`,
verificando idempotencia y **cero escrituras externas**.

**Contract** (gate de deploy): validación del payload consumido contra el JSON Schema de
`api-general`; validación de la respuesta de lectura contra el OpenAPI publicado; test de
compatibilidad que falla si un campo requerido desaparece.

**Invariantes** (`tests/invariants/`, batería exhaustiva y property-based): ningún ítem sobre
`age_rating` en ninguna de las cinco `result_type`; ningún ítem excluido en ninguna respuesta; MMR
nunca reintroduce un filtrado; `age_rating` nulo tratado como no apto; edad desconocida → política
conservadora.

**Casos críticos exigidos**: menor de edad; exclusión activa; cache miss con y sin histórico;
evento duplicado; payload inválido; `api-general` caído durante sync; Redis caído; broker caído
(la lectura debe seguir funcionando); catálogo sin candidatos válidos.

**Arquitectura**: test que falla si `api/` importa `engine/` o si el proceso API abre conexión a una
DB ajena.

---

## 6. Observabilidad y operación

**Métricas** (Prometheus): `reco_cache_hits_total{result_type}`, `reco_request_duration_seconds`
(histograma por endpoint), `reco_recompute_total{status,module}`,
`reco_recompute_duration_seconds`, `reco_dlq_messages_total{reason}`, `reco_queue_depth`,
`reco_sync_last_success_timestamp` (para *freshness*), `reco_sync_duration_seconds`,
`reco_cross_module_propagation_total{propagated}`, `reco_active_config_version` (gauge etiquetado).

**Logging**: JSON estructurado con `timestamp`, `level`, `correlation_id` (propagado desde el header
de `api-general` y desde `event_id` en el worker), `user_id`, `module`, `config_version`, `outcome`.
Prohibido loguear API keys o payloads completos.

**Health checks** por servicio: `/health/live` (proceso vivo), `/health/ready` (dependencias
críticas: Redis para la API; Redis+DB+broker para el worker; DB para el transformer),
`/health/info` (versión de config activa y de build).

**Alertas iniciales sugeridas**:

| Alerta | Umbral inicial | Severidad |
|---|---|---|
| Tasa de fallo de recálculo | > 5 % en 10 min | crítica |
| Mensajes en DLQ | > 0 en 5 min | alta |
| Freshness de sincronización | > 2× la periodicidad configurada | alta |
| Cache hit ratio | < 80 % en 30 min | media |
| Latencia p95 de lectura | > 100 ms en 10 min | media |
| Profundidad de cola | creciente 15 min seguidos | media |

---

## 7. Riesgos y mitigaciones

| Riesgo | Impacto | Probabilidad | Mitigación |
|---|---|---|---|
| **Drift de contratos** con `api-general` | Alto | Media | Contract tests bloqueantes en CI; copias derivadas versionadas en `contracts/`; alerta ante fallo de validación de evento |
| **Inconsistencia temporal**: top-N obsoleto con exclusiones nuevas | Alto (seguridad) | Alta | Re-filtrado obligatorio de edad y exclusión en la salida (FR-036), no solo en el recálculo |
| **Replay masivo de eventos** | Medio | Media | Dedupe por `event_id` en Redis + `processed_events`; operaciones de escritura idempotentes |
| **Pérdida total de caché** → avalancha | Alto | Baja | Job de warm-up con límite de tasa; supresión de señales por ventana; degradación a respaldo mientras se reconstruye |
| **Recálculo doble por cross-module** encarece el worker | Medio | Alta | Propagación condicional por vocabulario compartido; métrica de tasa de propagación; consolidación de ráfagas en Fase 3 |
| **Actividad sin tipo de señal** en `api-general` | Alto (bloqueante) | Media | Escalar ya en Fase 1; plan B: derivar exclusión sin ajustar perfil, degradando calidad de forma explícita |
| **Cold start del respaldo** en catálogo nuevo | Bajo | Media | Desempate documentado por criterio secundario; responder "pendiente" si aún no existe |
| **Regresión de calidad** al mover pesos | Medio | Media | Evaluación offline reproducible obligatoria por PR (Principio V); `config_version` en cada resultado |

---

## 8. Decisiones abiertas

| # | Decisión | Opciones | Trade-off | **Recomendación** |
|---|---|---|---|---|
| D1 | Tipo de señal en el contrato de actividad de `api-general` | (a) exponerlo; (b) derivarlo localmente | (b) rompe el modelo de perfil acordado en clarify | **(a)**, escalar de inmediato: es bloqueante de Fase 1 |
| D2 | `result_type` en el contrato de respuesta | (a) enum explícito; (b) flags booleanos | El enum es más claro y extensible | **(a)**, coordinar con `api-general` |
| D3 | Cómputo de vecinos colaborativos | (a) online en cada recálculo; (b) matriz de similitud precalculada en batch | (a) es simple pero O(usuarios) por evento | **(b)** en Fase 3; (a) en Fase 1 con k y muestra acotados |
| D4 | Valores iniciales | α=0.5, β=0.3, γ=0.2, k=20, λ_MMR=0.7 | Sin datos aún | Adoptar como `v1.yaml` y ajustar con evaluación offline en Fase 3 |
| D5 | TTLs | `FRESH` 24 h, `STALE` 7 d, `FILTERS` 1 h, `FALLBACK` 6 h | Frescura vs. carga del worker | Adoptar como defaults configurables y revisar con datos reales |
| D6 | Umbral de personalización | (a) ≥1 señal; (b) ≥3 señales | (a) personaliza antes pero con perfil pobre | **(b)**, mejor calidad percibida al salir del respaldo |
| D7 | Publicación de la señal de recálculo desde la API | (a) publicar a RabbitMQ; (b) tabla outbox | (a) acopla la API al broker | **(a)** con *fire-and-forget* y fallo silencioso registrado; la lectura nunca debe fallar por el broker |
| D8 | Almacenamiento del respaldo | (a) solo Redis; (b) Redis + tabla | (a) se pierde con la caché | **(b)**, permite rehidratar sin recomputar |

---

## Definition of Done (para pasar a `/speckit.tasks`)

- [ ] D1 y D2 escalados al equipo de `api-general` y con respuesta registrada
- [ ] `research.md` con las decisiones D3–D8 resueltas y justificadas
- [ ] `data-model.md` con tablas, índices, claves Redis y TTLs finales
- [ ] `contracts/` con el OpenAPI del endpoint de lectura y la copia derivada del JSON Schema del evento
- [ ] `quickstart.md` con el stack local reproducible (Postgres+pgvector, Redis, RabbitMQ)
- [ ] `engine_config/v1.yaml` con los valores de D4 y su validación
- [ ] Estructura de directorios creada, con la regla "API no importa engine" verificable
- [ ] Constitution Check re-verificado tras el diseño: sin violaciones
- [ ] Cada FR de la spec mapeado a al menos una fase del plan
- [ ] Cada SC de la spec mapeado a al menos un test planificado
- [ ] Riesgos con dueño asignado
