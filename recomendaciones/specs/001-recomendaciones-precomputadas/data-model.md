# Modelo de Datos: Servicio de Recomendaciones Híbridas Precomputadas

**Feature**: 001-recomendaciones-precomputadas · **Fecha**: 2026-09-10 · **Estado**: refinamiento de [plan.md](./plan.md) §2

**Alcance**: formaliza la capa de datos que `plan.md` asume. **No modifica el alcance funcional
aprobado.** Toda entidad se remonta a un FR de [spec.md](./spec.md) o a un principio de la
[constitution v1.0.0](../../.specify/memory/constitution.md).

**Regla de lectura**: este documento especifica **qué datos existen y por qué**, no con qué ORM se
acceden. Los tipos son lógicos; su mapeo concreto es decisión de T003.

---

## 1. Separación de responsabilidades de almacenamiento

El principio que ordena todo el modelo: **ningún dato tiene dos fuentes de verdad**.

| Dato | Reside en | Justificación |
|---|---|---|
| Identidad del usuario, catálogo, actividad | **api-general** | Dato ajeno. Principio I: no se accede a su DB; se consume vía REST |
| Proyección local de usuario, ítem y señales | **DB Recomendaciones** | Materialización necesaria para que edad y exclusión se apliquen **íntegramente con datos locales**, sin llamada externa en el request path (FR-003) |
| Perfiles de tags, vectores de ítem | **DB Recomendaciones** | Estado derivado propio. Nadie más lo produce ni lo consume |
| Configuración del motor y su versión | **DB Recomendaciones** + repo | El archivo versionado vive en el repo (Q4); la tabla registra qué versiones existieron, para que un top-N viejo siga siendo interpretable |
| Exclusiones resueltas | **DB Recomendaciones** | Invariante de seguridad. No puede depender de un sistema que se puede caer (FR-050) |
| Idempotencia de eventos | **DB Recomendaciones** + Redis | Redis da velocidad; Postgres da durabilidad. Perder Redis no debe permitir reprocesar (INV-2) |
| Top-N precomputado, filtros calientes, respaldo | **Redis** | **Caché derivada y descartable.** Todo es recomputable desde Postgres |

> ⚠️ **Redis nunca es fuente de verdad.** Su pérdida total es un evento de rendimiento, no de
> integridad: `docs/runbook.md` + T022 describen la reconstrucción. Si algún dato dejara de ser
> recomputable desde Postgres, eso es un defecto de diseño, no una optimización.

**Frontera con `api-general`**: la proyección local es *solo lectura* y *desechable*. Se reconstruye
sincronizando. No se le agregan campos propios ni se edita: eso la convertiría en una segunda fuente
de verdad de un dato ajeno, violando el Principio I.

### 1.1 Zonas de datos y su regla de escritura

| Zona | Entidades | Escritor único | Reconstrucción |
|---|---|---|---|
| **Proyección local** (dato ajeno) | `users`, `items`, `tags`, `item_tags` | Data Transformer | Resincronizando desde `api-general` |
| **Derivados durables** (estado propio) | `item_vectors`, `user_profiles`, `user_exclusions`, **`item_popularity`** | Procesos propios (vectorizador, resolutor, batch de popularidad) | Recomputando desde señales y proyección |
| **Registro de hechos** | `user_signals`, `sync_runs`, `processed_events` | Ingesta / jobs | **No reconstruible.** Es el historial |
| **Configuración** | `engine_config_versions` | Loader | Desde el repo |
| **Caché** | Redis (§3) | Worker / batches | Desde Postgres |

> **Regla de escritor único**: cada fila tiene **un solo** proceso con autoridad para escribirla. La
> zona determina cuál. Esto no es una convención de código —que se olvida— sino un criterio de
> ubicación: si dos procesos necesitan escribir la misma fila, la fila está en la zona equivocada.

**RD-12 corrigió una violación de esta regla**: `like_count_window` vivía en `items` (proyección
local) pero lo escribía el batch de popularidad, no el Data Transformer. Dos escritores sobre la
misma fila, y una proyección que ya no era reconstruible sincronizando —la resincronización no
reponía ese valor—. La afirmación de desechabilidad de arriba **era falsa** mientras ese atributo
estuvo ahí. Reubicarlo la restituye.


---

## 2. Entidades persistentes en DB Recomendaciones

### 2.1 `users` — usuario materializado

**Propósito**: permitir el filtro de edad sin llamar a `api-general` en el request path (FR-003, FR-030).

> 🔄 **Revisado 2026-09-10 (RD-1)**: `birth_date` pasa a **obligatoria y confiable por contrato**.
> Desaparece el escenario de edad indeterminable y con él `age_resolution`. Ver §11.

| Atributo | Tipo | Nulo | **Naturaleza** | Notas |
|---|---|---|---|---|
| `id` | UUID | No | **Identidad** | **PK**. Identificador externo de `api-general`; no se genera acá |
| `birth_date` | date | **No** | **Funcional** | **Único insumo admitido** para la restricción etaria. Garantizada por contrato (CR-1) |
| `max_age_ordinal` | smallint | **No** | **Funcional** | **Única representación del permiso etario.** Derivado de `birth_date` vía config activa. Es el valor que se compara |
| `age_config_version` | text | **No** | **Integridad** | FK → `engine_config_versions`. Escala bajo la que se derivó el ordinal. Sin él, el ordinal es un número sin unidad (RD-5) |
| `age_derived_at` | timestamptz | **No** | **Auditoría (forense)** | Cuándo se derivó el ordinal. **Ningún componente lo lee, ninguna consulta lo filtra, ninguna métrica lo agrega** (RD-6) |
| `region` | char(2) | **Sí** | **Anticipación** | **ISO 3166-1 alfa-2**, mayúsculas. Sin consumo en esta feature (RD-4). `CHECK (region ~ '^[A-Z]{2}$')` |
| `synced_at` | timestamptz | No | **Operativo** | Marca de última sincronización |

**Clasificación por naturaleza** — determina qué está permitido hacer con cada atributo:

| Naturaleza | Definición | Regla |
|---|---|---|
| **Funcional** | Participa del cálculo o del filtrado | Puede leerse, indexarse y sostener invariantes |
| **Integridad** | Hace interpretable o verificable a un atributo funcional | Puede leerse en consultas de verificación y mantenimiento. No participa del resultado |
| **Auditoría (forense)** | Solo reconstruye la historia de un registro | ⛔ **Prohibido construir lógica funcional, consultas de selección o alertas sobre él.** Se lee en investigación, nunca en ejecución |
| **Anticipación** | Proyectado sin consumo actual | ⛔ Mismas prohibiciones que auditoría, más: no se indexa |
| **Operativo** | Sostiene mantenimiento de la proyección | Puede indexarse si hay consulta declarada |

> La categoría **auditoría** existe para que la prohibición sea explícita y revisable. Un atributo
> forense sin esa etiqueta es una invitación a que alguien, dentro de un año, escriba
> `WHERE age_derived_at < ...` creyendo que detecta algo. RD-6 documenta por qué eso sería un error.


**Índices**:

| Índice | Consulta que sirve |
|---|---|
| PK (`id`) | Lectura por usuario en el request path |
| `idx_users_birth_date (birth_date)` | **Cruce de umbral** (§7.5): `WHERE birth_date IN (:fechas_umbral)` — igualdad exacta sobre el puñado de fechas que hoy hacen cumplir años a un usuario |
| `idx_users_age_config_version (age_config_version) WHERE age_config_version <> :activa` | **Derivados bajo config obsoleta** (§7.5): parcial, normalmente vacío; se puebla solo tras un cambio de catálogo |
| `idx_users_synced_at (synced_at)` | Detección de proyecciones rancias |

> **`region` no se indexa.** No existe consulta que lo justifique: ningún componente la lee. Un índice
> es costo de escritura permanente al servicio de una lectura hipotética. Se añadirá cuando exista un
> requisito de segmentación regional que defina la consulta concreta — no antes.


**Integridad**:
- `birth_date NOT NULL`: el esquema hace **irrepresentable** un usuario sin fecha de nacimiento.
  No hay default: un usuario sin ella no se inserta (§7.5, política de ingesta).
- `max_age_ordinal NOT NULL` **sin default**: no existe el estado «materializado pero sin derivar».
- `age_config_version` es FK real: un ordinal siempre es interpretable, aun si la config cambió.
- `region` **admite nulo y su ausencia no tiene consecuencia alguna**. Asimetría deliberada con
  `birth_date`: esta última es obligatoria porque de ella depende un invariante de seguridad; la
  región no sostiene ningún invariante. Un usuario sin región recibe exactamente las mismas
  recomendaciones que uno con región — porque **ningún componente la lee** (§4.3).

**Consumidores por atributo** — qué se rompe si el atributo no existe:

| Atributo | Consumidores | Qué se rompe ante su ausencia |
|---|---|---|
| `birth_date` | §7.5 causa A (`WHERE birth_date IN (...)`) · derivación del ordinal · DI-2, DI-2a' | **Todo.** Sin el insumo no hay permiso etario |
| `max_age_ordinal` | §4.2 filtro · §3.2 snapshot · `filters:` (§3.1) · DI-2b, DI-2c | **El filtro.** Es el valor comparado |
| `age_config_version` | §7.5 causa B (`WHERE age_config_version <> :activa`) · índice parcial · §2.1 resolución de etiqueta legible · `filters:` · DI-2a', DI-2e · FK a `engine_config_versions` | **La interpretabilidad y la detección selectiva.** Ver RD-5 |
| `age_derived_at` | **Ninguno.** Se escribe en §7.5 y se declara en DI-2 como `NOT NULL`; nada lo lee | **Nada funcional.** Se pierde la capacidad de reconstruir *cuándo* se derivó un ordinal durante una investigación (RD-6) |
| `region` | **Ninguno** (§4.3) | Nada (RD-4) |
| `synced_at` | `idx_users_synced_at` · detección de proyección rancia (T031) | La detección de proyecciones desactualizadas |

Que `age_derived_at` sea la única fila con «ninguno» en ambas columnas es lo que motivó la auditoría
RD-6. La escritura en §7.5 no lo convierte en consumidor: escribir un valor que nadie lee no es uso.

**Una sola representación del permiso.** No se almacena la clasificación etaria legible: sería el
mismo hecho codificado dos veces, derivado del mismo mapeo, y ningún componente la consultaría
—el filtro opera solo sobre el ordinal (§4.2)—. Su único efecto sería habilitar un estado
inconsistente que el esquema no puede impedir. Cuando se necesita la etiqueta legible para
diagnóstico o soporte, se resuelve el ordinal contra `age_config_version` del propio registro, que
es exactamente el mapeo con el que se derivó. La traducción es siempre correcta y nunca ocurre en
el request path.

**Por qué se materializa el ordinal**: el filtro debe ser una **comparación ordinal indexable**
(§4). Calcular la edad desde `birth_date` en cada evaluación implicaría aritmética de fechas sobre
cada candidato, lo que impide usar índice y reintroduce cómputo donde FR-003 lo prohíbe. El costo es
la caducidad por paso del tiempo, que se resuelve en §7.5.

**Ciclo de vida**: creado/actualizado por el Data Transformer (T029). El ordinal se recalcula al
sincronizar, al cruzar un umbral etario y al cambiar el catálogo (§7.5). Nunca se borra por lógica de
negocio; si desaparece del origen, se marca vía `synced_at` rancio. `region` se repuebla en cada
sincronización; nunca se edita ni se enriquece localmente.

#### Por qué se incorpora `region` y se sigue rechazando NC-1

Ambos son atributos sin requisito funcional. Incorporar uno y rechazar el otro exige un criterio
verificable, no una preferencia. El criterio es:

> **¿El atributo tiene un valor de verdad determinable sin decidir funcionalidad?**

| | «Módulo de interés» (NC-1) | `region` |
|---|---|---|
| ¿Existe en el origen? | **No.** Es un concepto de producto que habría que crear | **Sí.** Dato de registro que `api-general` ya posee |
| ¿Tiene semántica definida sin decidir su uso? | **No.** ¿Declarado o inferido? ¿Uno o varios? ¿Con qué vigencia? Cada respuesta es una decisión de producto | **Sí.** «País del usuario según ISO 3166-1». No hay grado de libertad |
| ¿Se puede poblar hoy correctamente? | **No.** Sin definir su semántica, cualquier valor es arbitrario | **Sí.** Se copia del origen y se valida contra un estándar externo |
| Sin consumo, ¿qué es? | **Nada.** Un módulo de interés que nadie lee no significa nada: su significado *es* alterar la selección | **Un hecho verdadero sobre el usuario**, verificable con independencia de que alguien lo use |

La distinción es esa última fila. NC-1 sin consumo es un campo sin significado, y definirlo obliga a
inventar producto —eso sí es alcance nuevo—. `region` sin consumo sigue siendo un dato correcto o
incorrecto, contrastable contra el origen. Proyectarlo no decide nada sobre el motor.

**Costo asumido, declarado sin atenuantes**: un atributo que nadie lee es un atributo que puede
pudrirse en silencio, porque ninguna funcionalidad falla si está mal. La única defensa es la métrica
de §7.6, y es una defensa débil. Ver RD-4 para la alternativa descartada.

> ⚠️ **needs-clarification (NC-1)** — El brief menciona «módulo de interés» del usuario. **La spec no
> define tal atributo** y ningún FR lo requiere: las recomendaciones se piden por módulo en el
> request (FR-006). No lo incluyo. Si existe un requisito de producto no capturado, debe entrar por
> `/speckit.clarify`, no asumirse acá.

> ✅ **NC-3 resuelto**: `api-general` expone `birth_date`. No hay campo `age` ni doble formato.

---

### 2.2 `items` — ítem del catálogo materializado

**Propósito**: candidatos a recomendar, con la clasificación etaria necesaria para filtrar localmente.

> 🔄 **Revisado 2026-09-14 (RD-7..RD-11)**: se incorpora ciclo de vida del ítem. El modelo anterior
> no podía expresar «retirado», lo que permitía servir contenido ya no disponible. Ver §12.

| Atributo | Tipo | Nulo | **Naturaleza** | Notas |
|---|---|---|---|---|
| `id` | UUID | No | **Identidad** | **PK**. Identificador externo |
| `module` | enum(`peliculas`,`juegos`) | No | **Funcional** | Dimensión obligatoria. Sostiene `tags.is_shared` y con ello la señal cruzada (ver abajo) |
| `status` | enum(`available`,`retired`) | **No** | **Funcional** | **Default `available`.** Retiro **lógico**, nunca físico (RD-7) |
| `retired_at` | timestamptz | Sí | **Auditoría (forense)** | Cuándo se retiró. ⛔ No sostiene lógica: el filtro usa `status` |
| `min_age_ordinal` | smallint | **No** | **Funcional** | **Edad mínima requerida, en escala ordinal**. Valor comparado. Default = máximo de la escala |
| `age_config_version` | text | **No** | **Integridad** | FK → `engine_config_versions`. Escala bajo la que se derivó el ordinal (RD-5) |
| `age_rating` | enum | **No** | **Integridad** | **Dato de origen**, no derivado. Default = valor más restrictivo (FR-051). Permite re-derivar el ordinal ante cambio de catálogo |
| `age_rating_source` | enum(`declared`,`unknown_defaulted`) | No | **Auditoría (accionable)** | Excepción a la regla forense: sostiene una métrica de cobertura (§7.7, RD-9) |
| `synced_at` | timestamptz | No | **Operativo** | Última sincronización |

> 🔄 **`like_count_window` reubicado a `item_popularity` (§2.11, RD-12).** No provenía del origen:
> lo produce un proceso propio desde señales locales. Su presencia acá rompía la desechabilidad de
> la proyección y ponía dos procesos a escribir la misma fila.


Clasificación por naturaleza y sus reglas: §2.1. `retired_at` lleva la **prohibición expresa** de
sostener lógica funcional; `age_rating_source` es la **única excepción** documentada a esa regla
(RD-9), y lo es porque habilita una métrica accionable que ningún otro atributo puede producir.

**Sobre `module` — justificación principal.** No es solo una dimensión de partición del catálogo.
Un tag es `is_shared` (§2.3) **sí y solo si** aparece en ítems de **ambos** módulos, determinación
que exige conocer el módulo de cada ítem. Y `is_shared` es lo que habilita la propagación
cross-module de FR-010a, es decir el término γ del score (`γ·cross_module`, D4). **Sin `module` en
`items` no hay forma de saber qué tags son compartidos, y sin eso el tercer término del motor no
existe.** Esa es la justificación más fuerte del atributo, por encima del filtrado por módulo.

**Ningún atributo duplica información del origen.** `age_rating` es dato recibido y se conserva
porque permite re-derivar el ordinal ante un cambio de catálogo sin resincronizar (§4.1) — no es
descriptivo. `status` es estado propio de la proyección (RD-7). No se incorporan título, descripción,
género, duración ni fecha de publicación: son descriptivos, su autoridad es del origen, y ninguna
consulta declarada los requiere.

**Índices**:

| Índice | Consulta que sirve |
|---|---|
| PK (`id`) | Resolución de ítem |
| `idx_items_candidates (module, min_age_ordinal) WHERE status = 'available'` | **Selección de candidatos** del recálculo: prefiltrado ordinal ya restringido a vigentes. Parcial: los retirados no ocupan el índice. **También sirve al batch de respaldo** tras RD-12 |
| `idx_items_synced_at (synced_at)` | **Frescura del catálogo** (RD-11): `WHERE synced_at < :umbral` — detección económica de sincronización interrumpida, simétrica con `idx_users_synced_at` |

> El índice parcial **sobre `status = 'available'`** deja el predicado de vigencia en el índice, no
> en el código. Un desarrollador que olvide el `WHERE status` no obtiene un resultado silenciosamente
> incorrecto — obtiene un plan que no usa el índice, visible en review y en perfilado.


**Integridad**:
- `status` **NOT NULL con default `available`**. Asimetría deliberada con el fail-closed etario: el
  default permisivo es correcto acá porque el caso normal de alta es un ítem vigente, y el riesgo
  de un ítem retirado servido es de negocio, no de seguridad. El riesgo etario sí es de seguridad.
- `retired_at IS NOT NULL` ⟺ `status = 'retired'`. Verificable por `CHECK`.
- `min_age_ordinal` **NOT NULL con default = máximo ordinal**: un ítem sin derivar es representable
  pero inalcanzable para todo usuario. El fail-closed queda en el default del esquema.
- `age_rating` **NOT NULL con default no-apto**. Corrige P2 del prototipo a nivel de esquema.
- `age_rating` y `min_age_ordinal` derivan del mismo mapeo versionado; su consistencia se verifica
  por test (DI-2a'), no por constraint.
- `age_rating` restringido al catálogo de la configuración activa (FR-053).

**Consumidores de los atributos incorporados**:

| Atributo | Consumidores | Qué se rompe ante su ausencia |
|---|---|---|
| `status` | Selección de candidatos (T012) · batch de respaldo (T038) · guarda del request path (§4.4) · `retired:{module}` (§3.1) · DI-10 | **El defecto que motivó RD-7**: contenido retirado servible desde `fallback` y `reco:stale` |
| `retired_at` | **Ninguno.** Forense: reconstruir «¿desde cuándo dejó de estar disponible?» ante un reclamo | Nada funcional |
| `age_rating_source` | Métrica `catalog_unrated_ratio` (§7.7) | La única señal de cobertura degradada por fail-closed (RD-9) |

### 2.3 `tags` y `item_tags` — vocabulario y asignación

**Propósito**: sostener el espacio vectorial **único** de FR-010d.

**`tags`**

| Atributo | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | serial | No | **PK** |
| `name` | text | No | **UNIQUE**. Normalizado |
| `is_shared` | boolean | No | Aparece en ítems de **ambos** módulos. Deriva la propagación cross-module (FR-010a) |

**`item_tags`**

| Atributo | Tipo | Nulo | Notas |
|---|---|---|---|
| `item_id` | UUID | No | **PK compuesta**, FK → `items.id` ON DELETE CASCADE |
| `tag_id` | integer | No | **PK compuesta**, FK → `tags.id` |
| `weight` | real | No | Peso del tag en el ítem |

**Índices**: PK compuesta · `idx_item_tags_tag (tag_id)` para la búsqueda inversa.

> **Decisión**: `is_shared` es atributo de `tags`, no tabla aparte. La tabla `shared_tags` de
> `plan.md` §2 se **consolida acá**: era la misma información con una indirección extra, y un
> booleano no justifica una tabla. Impacto en T003 (ver §9).

---

### 2.4 `item_vectors` — representación vectorial del ítem

**Propósito**: señal content-based (FR-009) sin recomputar TF-IDF en cada recálculo.

| Atributo | Tipo | Nulo | Notas |
|---|---|---|---|
| `item_id` | UUID | No | **PK**, FK → `items.id` ON DELETE CASCADE |
| `vector` | vector(N) | No | Espacio **compartido** entre módulos (FR-010d) |
| `vocab_version` | text | **No** | Versión del vocabulario que lo generó (FR-010f) |
| `computed_at` | timestamptz | No | |

**Índices**: PK · `idx_item_vectors_vocab (vocab_version)` para la transición de T030 · índice
vectorial (ivfflat/hnsw) diferido a Fase 3.

**Integridad**: `vocab_version` **NOT NULL**. Comparar vectores de versiones distintas es error, no
resultado silencioso (FR-010f). El esquema no puede impedirlo solo, pero sí garantiza que el dato
para detectarlo siempre está.

---

### 2.5 `user_profiles` — perfil de tags por módulo y general

**Propósito**: señal content-based por módulo y **señal cross-module** (FR-024).

| Atributo | Tipo | Nulo | Notas |
|---|---|---|---|
| `user_id` | UUID | No | **PK compuesta**, FK → `users.id` ON DELETE CASCADE |
| `scope` | enum(`peliculas`,`juegos`,`general`) | No | **PK compuesta** |
| `vector` | vector(N) | No | L2-normalizado (FR-022c) |
| `vocab_version` | text | No | |
| `signal_count` | integer | No | Señales que lo formaron. Umbral de personalización (D6) |
| `computed_at` | timestamptz | No | |

**Integridad**: hasta tres filas por usuario. El perfil `general` **no** es un cuarto vector
independiente: agrega pesos por tag sobre ambos módulos y es lo que hace posible el cold start
cruzado (SC-010).

> **Decisión**: una sola tabla con `scope` discriminador, no tres tablas. El prototipo usa
> `UserMovieProfile` / `UserGameProfile` / `UserGeneralTagProfile` como clases distintas; a nivel de
> datos son la misma estructura y separarlas triplicaría las consultas del recálculo.

---

### 2.6 `user_signals` — registro de interacción

**Propósito**: base de perfiles y exclusiones. Materializa DEP-1 y DEP-2.

| Atributo | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | bigserial | No | **PK** |
| `user_id` | UUID | No | FK → `users.id` ON DELETE CASCADE |
| `item_id` | UUID | No | FK → `items.id` |
| `signal_type` | enum(`like`,`dislike`,`consumo`) | **No** | **Sin default.** FR-064 prohíbe inferirlo |
| `occurred_at` | timestamptz | **No** | Resuelve señales contradictorias (FR-029d) |
| `source` | enum(`sync`,`feedback_api`) | No | Origen: Data Transformer o endpoint propio |

**Índices**: PK · `idx_signals_user_item_time (user_id, item_id, occurred_at DESC)` — soporta
directamente «gana la más reciente» · `idx_signals_user_type (user_id, signal_type)`.

**Integridad**: `signal_type` y `occurred_at` **NOT NULL sin default**. Un evento sin tipo de señal
no es representable: va a DLQ (T023). El esquema hace cumplir FR-064.

**Regla de negocio (FR-022b, decisión Q3)**: `like` y `dislike` alimentan el perfil **y** excluyen;
`consumo` **solo excluye**, no altera el vector. Corrige P1 del prototipo, que le daba peso 0.3.

> ⚠️ **needs-clarification (NC-2)** — **Retención**. La spec no define cuánto se conservan las
> señales. Afecta el tamaño de la tabla y, por FR-033a1, qué ventana de popularidad es computable.
> No lo asumo: es decisión de producto con implicancias de privacidad.

---

### 2.7 `user_exclusions` — conjunto de exclusión resuelto

**Propósito**: aplicar el filtro de exclusión en tiempo acotado, sin recorrer el histórico de señales.

| Atributo | Tipo | Nulo | Notas |
|---|---|---|---|
| `user_id` | UUID | No | **PK compuesta**, FK → `users.id` ON DELETE CASCADE |
| `item_id` | UUID | No | **PK compuesta**, FK → `items.id` |
| `origin` | enum(`like`,`dislike`,`consumo`) | No | Señal que la produjo |
| `is_permanent` | boolean | No | `consumo` ⟹ `true`; `dislike` es revertible por like posterior |
| `resolved_at` | timestamptz | No | Trazabilidad de la resolución |

**Índices**: PK compuesta — cubre la consulta de pertenencia, que es la única que el request path
necesita (FR-033d).

**Integridad**: vista materializada de `user_signals` bajo «gana la más reciente». Su regeneración
es determinista y auditable: dadas las mismas señales, produce el mismo conjunto.

**Por qué es tabla y no cálculo al vuelo**: FR-050 exige rechazar la solicitud si el conjunto no está
disponible. Un conjunto que se calcula recorriendo señales sería cómputo en el request path (FR-003);
uno que solo vive en Redis violaría INV-2 al expirar. Debe ser durable y barato de leer.

---

### 2.8 `engine_config_versions` — configuración versionada del motor

**Propósito**: que un top-N generado hace un mes siga siendo interpretable (Q4, FR-025).

| Atributo | Tipo | Nulo | Notas |
|---|---|---|---|
| `config_version` | text | No | **PK**. Hash del archivo. **Inmutable** |
| `payload` | jsonb | No | Copia íntegra de la configuración |
| `activated_at` | timestamptz | No | |
| `deactivated_at` | timestamptz | Sí | `NULL` = versión activa |

**Integridad**:
- Índice parcial único sobre `deactivated_at IS NULL`: **a lo sumo una versión activa**.
- Las filas son **append-only**. Editar una versión existente rompería la trazabilidad de todo
  resultado que la referencie.

**Relación con el repo**: la fuente de verdad del *contenido* es `engine_config/vN.yaml`, versionado
en git (Q4). Esta tabla registra qué versiones **estuvieron activas y cuándo** — información que el
archivo no tiene y que hace falta para interpretar un resultado viejo.

---

### 2.9 `sync_runs` — metadatos del Data Transformer

**Propósito**: freshness observable (FR-040, T031).

| Atributo | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | bigserial | No | **PK** |
| `started_at` / `finished_at` | timestamptz | No / Sí | `finished_at` nulo ⟹ en curso o interrumpida |
| `status` | enum(`running`,`success`,`failed`) | No | |
| `entity_counts` | jsonb | Sí | Volumen por entidad |
| `failure_reason` | text | Sí | |

**Índices**: `idx_sync_runs_success (finished_at DESC) WHERE status='success'` — la métrica de
freshness es el **último éxito**, no el último intento (T031).

---

### 2.10 `processed_events` — idempotencia

**Propósito**: FR-011. Un evento reentregado no debe recomputar dos veces.

| Atributo | Tipo | Nulo | Notas |
|---|---|---|---|
| `event_id` | UUID | No | **PK**. Provisto por `api-general` (DEP-3) |
| `processed_at` | timestamptz | No | |
| `result` | enum(`recomputed`,`skipped_no_shared_tag`,`dlq`) | No | Auditoría de FR-010c |
| `expires_at` | timestamptz | No | Retención configurable (FR-068) |

**Índices**: PK — la única consulta es pertenencia por `event_id` · `idx_processed_expires
(expires_at)` para la purga.

**Integridad**: PK sobre `event_id` hace la doble inserción **estructuralmente imposible**, no
dependiente de una comprobación previa que podría tener carrera.

**Relación con Redis**: `dedupe:event:{event_id}` es la copia caliente. Perder Redis degrada latencia,
no corrección: la PK sigue rechazando el duplicado (INV-2). Tras `expires_at`, un duplicado tardío
debe poder reprocesarse sin corromper estado (FR-069) — de ahí que el recálculo sea convergente.

---

---

### 2.11 `item_popularity` — popularidad derivada por ventana

**Zona**: **datos derivados durables**, no proyección local. Es estado propio, producido por un
proceso propio desde señales locales. Nadie más lo produce ni lo consume (RD-12).

**Propósito**: sostener el conjunto de respaldo de FR-033a1 sin contaminar la proyección de catálogo.

| Atributo | Tipo | Nulo | **Naturaleza** | Notas |
|---|---|---|---|---|
| `item_id` | UUID | No | **Identidad** | **PK compuesta** con `config_version`. FK → `items.id` |
| `config_version` | text | No | **Identidad + Integridad** | **PK compuesta.** FK → `engine_config_versions`. Define `popularity_window_days`: **es la unidad de medida** del recuento (RD-13) |
| `like_count` | integer | **No** | **Funcional** | Señales positivas en la ventana. Default 0. Ver NC-7: **qué constituye popularidad no está definido** |
| `computed_at` | timestamptz | **No** | **Operativo** | Cuándo se calculó esta fila |

**Clave primaria `(item_id, config_version)`**: permite que convivan los recuentos de la ventana
saliente y la entrante durante una transición, sin que se pisen. Es lo que hace la transición
**aditiva**, igual que `config_version` en la clave de Redis (§4).

**Índices**:

| Índice | Consulta que sirve |
|---|---|
| PK `(item_id, config_version)` | Upsert del batch; reunión con `items` |
| `idx_popularity_ranking (config_version, like_count DESC)` | **Batch de respaldo** (T038): top por ventana activa, previo a la reunión con `items` para filtrar vigencia y módulo |

**Integridad**:
- `config_version` es FK real y **parte de la clave**: un recuento sin ventana declarada es
  irrepresentable. No hay «popularidad» a secas — hay «popularidad bajo esta ventana».
- `ON DELETE CASCADE` desde `items`: a diferencia de `user_signals`, esto **sí** es derivado
  descartable. Si el ítem desapareciera físicamente, su recuento no tiene sentido ni valor histórico.

**Ciclo de vida**: lo escribe **exclusivamente** el batch de popularidad. El Data Transformer no lo
toca. Las filas de versiones de config inactivas se purgan tras confirmar la transición.

**Consumidores**:

| Atributo | Consumidores | Qué se rompe ante su ausencia |
|---|---|---|
| `like_count` | Batch de respaldo T038 → `fallback:{module}` · desempate determinista (RD-10) | El conjunto de respaldo de FR-033a1 |
| `config_version` | Selección de la ventana activa · aislamiento durante transición · DI-12 | **La comparabilidad.** Recuentos de ventanas distintas mezclados sin señal |
| `computed_at` | `catalog_popularity_last_success_timestamp` (§7.7) · detección de filas no recalculadas | La observabilidad de un batch parcialmente fallido (RD-13) |

**Efecto de la reubicación sobre el batch de respaldo**: pasa de un índice parcial de una sola
pasada a **reunión con `items`** para filtrar `status='available'` y agrupar por `module`. Es el
costo declarado de RD-12. Es aceptable porque el batch corre **fuera del request path**, sobre un
catálogo acotado y con periodicidad de horas. Se verifica en T050 (perfilado de performance), no se
asume.

> **No se denormaliza `module` en esta tabla.** Sería duplicar un dato cuya autoridad es del origen,
> exactamente lo que las restricciones prohíben, y reintroduciría un estado inconsistente posible.
> El precio es la reunión; el beneficio es que la frontera de zonas queda limpia.



> **Asimetría deliberada con `users`**: un usuario sin `birth_date` **se rechaza** (el dato lo
> garantiza el contrato); un ítem sin clasificación **se acepta como no-apto**. La diferencia es que
> el catálogo es un origen de datos heterogéneo sobre el que no tenemos garantía contractual
> equivalente, y descartar ítems silenciosamente degradaría la cobertura sin señal.

**Disponibilidad regional: fuera de alcance (RD-4).** No se incorpora atributo equivalente a
`users.region`. La simetría sería aparente:

- La región del usuario es un **escalar** copiable; la disponibilidad regional de un ítem es un
  **conjunto** (`{AR, UY, ...}`), con vigencia temporal y a veces con ventanas por región. Proyectar
  eso son una tabla y un ciclo de vida, no una columna.
- Es un dato de **licenciamiento**, con consecuencias legales. Su autoridad reside en el catálogo,
  fuera de este repositorio. Materializar una copia sin consumirla crea una segunda representación
  de una obligación contractual que nadie valida — el peor caso de dato podrido.
- El argumento que justifica `users.region` (evitar una modificación futura del contrato compartido)
  **no aplica**: el contrato de disponibilidad regional no lo define este repositorio.

Si aparece un requisito de segmentación regional, la disponibilidad de ítems entra por
`/speckit.clarify` con su propia modelización. Registrado como **NC-6**.


---

---

## 3. Modelo de datos en Redis

> **Redis es caché derivada y descartable.** Todo lo de esta sección es reconstruible desde §2.

### 3.1 Esquema de claves

Convención: `{dominio}:{versión-config}:{identidad}:{dimensión}` — namespacing por prefijo, todas las
claves de recomendación llevan **usuario y módulo**.

| Clave | Estructura | TTL | Reconstrucción |
|---|---|---|---|
| `reco:v{cfg}:{user_id}:{module}` | JSON (§3.2) | `TTL_FRESH` (24 h) | Recálculo del worker |
| `reco:stale:v{cfg}:{user_id}:{module}` | JSON (§3.2) | `TTL_STALE` (7 d) | Copia del último vigente |
| `filters:{user_id}` | JSON: `max_age_ordinal` + `age_config_version` + set de exclusiones | `TTL_FILTERS` (1 h) | Desde `users` + `user_exclusions` |
| `fallback:{module}` | JSON (§3.2, sin `user_id`) | `TTL_FALLBACK` (6 h) | Batch T038 |
| `retired:{module}` | **Set** de `item_id` retirados | `TTL_FILTERS` (1 h) | Desde `items WHERE status='retired'` |
| `recompute:lock:{user_id}:{module}` | marca | `TTL_SUPPRESS` (5 min) | No requiere |
| `dedupe:event:{event_id}` | marca | `TTL_DEDUPE` (24 h) | Desde `processed_events` |

**`config_version` en la clave, no solo en el valor**: hace que resultados de versiones distintas
**coexistan sin colisionar**. Cambiar de configuración no requiere invalidación masiva — las claves
viejas expiran solas. Aplica a `reco:` **y** a `reco:stale:` (hallazgo F3).

**`TTL_FILTERS` es deliberadamente el más corto.** Corrige P4 del prototipo, donde `excl:` compartía
los 7 días de `reco:` (`cache_redis.py:33`): una exclusión vencida servía resultados sin filtrar.

### 3.2 Estructura del valor

```jsonc
{
  "schema_version": 1,
  "user_id": "...",           // ausente en fallback:
  "module": "peliculas",
  "config_version": "sha256:ab12...",   // obligatorio
  "vocab_version": "v3",
  "max_age_ordinal": 3,       // snapshot: ordinal del usuario al momento del cálculo
  "computed_at": "2026-09-10T12:00:00Z",
  "items": [
    { "item_id": "...", "rank": 1, "score": 0.87 }
  ]
}
```

**Atributos obligatorios por elemento**: `item_id`, `score`, `rank`. **Obligatorio por entrada**:
`config_version` — es lo que se propaga a la respuesta y hace trazable con qué pesos se generó (Q4).

**`max_age_ordinal` (snapshot etario)**: registra bajo qué permiso se filtró el resultado.
`fallback:` no lo lleva (no es por usuario); se filtra en el momento de servirse.

| Comparación al leer | Significado | Acción |
|---|---|---|
| `snapshot == usuario` | El resultado se calculó con el permiso vigente | Servir |
| `snapshot > usuario` | El permiso **se restringió** (corrección de datos). El resultado puede contener ítems ahora vedados | **Descartar como miss** + emitir recálculo. Nunca servir |
| `snapshot < usuario` | El usuario **creció** (§7.5). El resultado es seguro pero conservador | Servir + emitir recálculo asíncrono. No degrada seguridad |

La asimetría es intencional: el caso inseguro se descarta, el caso seguro-pero-subóptimo se sirve.
Esto hace que la caducidad por cumpleaños **no** produzca latencia ni indisponibilidad.

`schema_version` permite evolucionar el formato sin ambigüedad: una entrada con versión desconocida
se descarta como miss, no se interpreta a medias.

### 3.3 Reconstrucción total

Secuencia (T022), **nunca disparada por tráfico de lectura** (FR-066):

1. El servicio sigue respondiendo: `empty_pending` o `fallback` según precedencia (FR-056).
2. `fallback:{module}` se rehidrata desde la tabla de respaldo (D8) — sin recomputar.
3. El job de warm-up publica señales de recálculo **con límite de tasa**, priorizando usuarios activos.
4. `filters:` y `dedupe:` se repueblan por demanda desde Postgres.

Que la reconstrucción sea un proceso dedicado y no un efecto colateral del tráfico es lo que evita la
avalancha auto-infligida: N lecturas en miss no deben producir N recálculos.

---

## 4. Versionado de configuración del motor

**Contenido** (`engine_config/vN.yaml`): `alpha`, `beta`, `gamma` (pesos de señal, suma 1.0) ·
`k` (vecinos) · `lambda_mmr` (diversificación) · `top_n_default`, `top_n_max` · `peso_like`,
`peso_dislike` · `age_rating_catalog` (mapeo de clasificación etaria) ·
`popularity_window_days` · `diversity_max_cluster_share` · TTLs · umbrales de reintento.

> ⚠️ **`tiebreak_criteria` eliminado de la configuración (RD-10).** Declaraba configurable un
> criterio para el cual el modelo ofrece **una sola alternativa**: el recuento de popularidad
> (`item_popularity.like_count`). Cualquier
> otro valor —antigüedad, novedad, fecha de publicación— referencia atributos que `items` no tiene
> y que son descriptivos del origen, cuya incorporación las restricciones prohíben. Un parámetro
> con un único valor posible no es configuración: es una constante disfrazada, que sugiere una
> flexibilidad inexistente y falla en runtime si alguien la usa.
>
> El desempate queda **fijo y documentado**: a igual score, mayor `item_popularity.like_count`; si persiste
> el empate, orden lexicográfico por `id` — arbitrario pero **determinista**, que es lo que el
> invariante de reproducibilidad necesita. Si aparece un requisito de desempate por novedad, entra
> por `/speckit.clarify` junto con el atributo que lo sostenga.

### 4.1 `age_rating_catalog` — única fuente del mapeo ordinal

Es **la única** definición de la escala etaria en todo el sistema. Ningún componente puede tener
una tabla propia, un literal ni una traducción en tiempo de ejecución.

```yaml
age_rating_catalog:
  - { rating: ATP,  ordinal: 0, min_age: 0  }
  - { rating: "13", ordinal: 1, min_age: 13 }
  - { rating: "16", ordinal: 2, min_age: 16 }
  - { rating: "18", ordinal: 3, min_age: 18 }
```

- **Ordinal totalmente ordenado**: `ordinal` es único, contiguo y creciente con `min_age`.
  Verificable al cargar la config (falla el arranque si no).
- **Un solo mapeo, dos usos**: `min_age` deriva `users.max_age_ordinal` (el ordinal más alto cuyo
  `min_age` ≤ edad del usuario); `rating` deriva `items.min_age_ordinal`. Ambos lados hablan la
  misma escala **por construcción**, no por convención.
- **Asimetría de representación**: `users` guarda **solo** el ordinal (RD-2); `items` conserva
  además `age_rating`, porque allí es **dato recibido del origen**, no derivado — descartarlo
  perdería información que no podemos reconstruir.
- **Cambiar el catálogo es cambiar la versión de config**, y obliga a **recalcular todos los
  derivados** (`users.max_age_ordinal`, `items.min_age_ordinal`) antes de activar `vN+1`. Una
  activación con derivados a medio migrar mezclaría escalas: es la única falla capaz de romper el
  filtro sin que ningún componente tenga un bug.
- Los derivados guardan `age_config_version`: un valor cuya versión no es la activa **no se compara**
  (se trata como no derivado ⟹ no apto).

### 4.2 Regla de filtrado etario

> **El filtro de edad es, y solo es:** `item.min_age_ordinal <= user.max_age_ordinal`.

Ningún componente lee `birth_date`, calcula edades ni traduce `age_rating` en tiempo de ejecución.
La aritmética de fechas ocurre **una vez**, en la derivación (§7.5), nunca por candidato.

**Dónde se aplica** — reconciliación con FR-036/FR-049/T037:

| Momento | Qué corre | Fundamento |
|---|---|---|
| Recálculo asíncrono | Pipeline completo: scoring → **edad** → exclusión → MMR | FR-003: todo cómputo fuera del request path |
| Request path | **Solo** la comparación ordinal sobre la lista ya ordenada y acotada (≤ `top_n_max`) | FR-036 + FR-049: un resultado obsoleto o de respaldo **debe** reevaluarse contra los filtros vigentes antes de servirse |

Esto **no** contradice «el filtro se aplica en el recálculo»: el pipeline de selección es asíncrono.
Lo que permanece en el request path es una guarda de seguridad de costo O(n) sobre n ≤ 50, sin
similitud, sin recomputación, sin reordenamiento y sin diversificación (FR-033d). Eliminarla haría
servible un `reco:stale:` o un `fallback:` calculado bajo un permiso que ya no rige — exactamente el
fallo que FR-036 existe para impedir. La comparación ordinal es lo que vuelve esa guarda barata.

### 4.3 Frontera de responsabilidad de `region`

| Afirmación | Alcance |
|---|---|
| **Dato ajeno proyectado** | La fuente de verdad es `api-general`. Este repositorio guarda una copia de solo lectura (§1) |
| **No se edita ni se enriquece localmente** | Nada de inferencia por IP, por idioma ni por ningún otro medio. Inferirla la convertiría en dato propio y violaría el Principio I |
| **Sin consumo en esta feature** | Ni el motor, ni el post-procesamiento (scoring → edad → exclusión → MMR), ni el request path la leen |
| **Verificable** | Test: ninguna consulta de esos componentes referencia la columna. Es una aserción sobre el código, no una convención |

**Impacto sobre invariantes existentes: ninguno.** `region` es nulable, no participa de ninguna
derivación, no entra en ninguna clave y no tiene índice. Los invariantes etarios (DI-1, DI-2,
DI-2a'..DI-2e) y de exclusión (DI-3) dependen de `birth_date`, de los ordinales y de
`user_exclusions`; ninguno los toca. No se agrega invariante nuevo: **no hay nada que preservar**
sobre un atributo que nadie lee. Ese vacío es exactamente el costo declarado en §2.1.

**Ausencia de dimensión en la clave de caché.** El criterio que incorporó `module` y `config_version`
a la clave (§3.1) es: *una dimensión se agrega cuando resultados de valores distintos deben coexistir
sin colisionar*. Hoy la región no participa del cálculo, así que dos usuarios idénticos en todo salvo
la región obtienen **el mismo resultado**. Incorporarla multiplicaría las entradas por la cantidad de
regiones para almacenar copias idénticas — costo de memoria puro, sin ganancia.

Si mañana existiera segmentación regional, el cambio sería **aditivo y sin invalidación masiva**: la
segmentación llegaría acompañada de un cambio de configuración del motor, y `config_version` ya está
en la clave. Las entradas viejas quedarían en un espacio de nombres que nadie lee y expirarían solas
(§4, «no hay invalidación masiva»). Que la clave ya versione la configuración es lo que vuelve barato
este cambio futuro — no hace falta anticiparlo en la clave.

### 4.4 Regla de vigencia del ítem

> **Un ítem `retired` no se recomienda: ni se selecciona, ni se rankea, ni se sirve.**

Se aplica en **tres puntos**, y los tres son necesarios porque cubren caminos distintos:

| Punto | Momento | Mecanismo |
|---|---|---|
| Selección de candidatos | Recálculo asíncrono | `WHERE status = 'available'` vía `idx_items_candidates` |
| Construcción del respaldo | Batch T038 | Reunión con `item_popularity`, `WHERE status = 'available'` (RD-12) |
| **Guarda del request path** | Al servir | Diferencia contra el set `retired:{module}` |

**Decisión sobre el request path: se verifica** (RD-8). Las tres opciones evaluadas:

| Opción | Evaluación |
|---|---|
| **Verificar al servir** ✅ | Set membership sobre ≤ `top_n_max` (50) ítems contra un set de Redis. **Mismo orden de costo que el filtro de exclusión que T037 ya ejecuta** en esa ruta, y sobre la misma estructura de datos. No hay similitud, recomputación ni reordenamiento: FR-033d lo admite |
| Invalidación proactiva | Retirar un ítem popular obligaría a invalidar los resultados de **todos** los usuarios que lo tengan. Sin índice invertido ítem→usuarios, es un barrido de todo el espacio de claves. Se descarta por costo, no por corrección |
| Aceptar exposición acotada | La ventana es `TTL_STALE` = **7 días** (§3.2) más el TTL del respaldo. Siete días sirviendo contenido retirado no es una exposición «acotada» en ningún sentido útil |

**Por qué es aceptable en el request path**: la lista ya está ordenada y su tamaño está acotado por
diseño; la verificación es una diferencia de conjuntos, no un cálculo. La prohibición de FR-003
apunta al cómputo de recomendaciones, no a las guardas de corrección — que es exactamente la misma
distinción que ya resolvió FR-036 para el filtro etario (§4.2).

**Efecto sobre el resultado**: los ítems retirados se **eliminan** de la lista servida. Esto puede
devolver menos de `top_n` elementos; no se rellena con sustitutos, porque rellenar exigiría rankear
—cómputo prohibido—. Si la lista queda vacía, aplica la precedencia de FR-056 (`empty_no_candidates`).

**`retired:{module}` es una caché, no fuente de verdad.** Su ausencia en Redis es un miss que se
repuebla desde Postgres, igual que `filters:`. `TTL_FILTERS` corto (1 h) acota el rezago entre el
retiro y su efecto en la guarda.

**Identificador**: hash criptográfico del archivo. Determinista e **inmutable**: mismo contenido ⟹
mismo identificador, en cualquier máquina.

**Trazabilidad (FR-025, Q4)**: toda recomendación persistida y servida referencia su
`config_version`. Está en el valor de Redis (§3.2), en la clave (§3.1) y en la respuesta de la API.
Sin esto, «¿por qué el sistema recomendó esto?» es incontestable.

**Cambio de versión activa**:

| Paso | Efecto |
|---|---|
| Se activa `vN+1` | `deactivated_at` de `vN` deja de ser nulo; nueva fila activa |
| Claves `reco:v{N}` | Siguen existiendo; **ya no se leen** (la clave incorpora la versión) |
| Lecturas nuevas | Miss bajo `vN+1` → precedencia FR-056: respaldo o pendiente |
| Expiración | Las claves de `vN` se purgan solas por TTL |

**No hay invalidación masiva**, y esa es la ventaja de tener la versión en la clave: el cambio de
configuración es un no-evento operativo.

---

## 5. Diagrama entidad-relación

```mermaid
erDiagram
    users ||--o{ user_profiles   : "1..3 (scope)"
    users ||--o{ user_signals    : emite
    users ||--o{ user_exclusions : acumula
    items ||--o{ item_tags       : etiquetado
    items ||--|| item_vectors    : "1:1"
    items ||--o{ user_signals    : recibe
    items ||--o{ user_exclusions : excluido
    tags  ||--o{ item_tags       : asignado
    engine_config_versions ||--o{ user_profiles : "genera (config_version)"
    engine_config_versions ||--o{ users : "deriva ordinal etario"
    engine_config_versions ||--o{ items : "deriva ordinal etario"
    items ||--o{ item_popularity : "recuento por ventana"
    engine_config_versions ||--o{ item_popularity : "define la ventana"

    users {
        UUID id PK
        date birth_date "NOT NULL (CR-1), IDX cruce de umbral"
        smallint max_age_ordinal "NOT NULL, unica representacion del permiso"
        timestamptz age_derived_at "NOT NULL, observabilidad"
        text age_config_version FK
        char region "nullable, ISO 3166-1, sin consumo"
        timestamptz synced_at
    }
    items {
        UUID id PK
        enum module "peliculas|juegos"
        enum status "available|retired, default available"
        timestamptz retired_at "nullable, forense"
        enum age_rating "dato de origen, NOT NULL"
        smallint min_age_ordinal "NOT NULL, default max (no-apto)"
        text age_config_version FK
        enum age_rating_source
        timestamptz synced_at
    }
    item_popularity {
        UUID item_id PK "FK, CASCADE"
        text config_version PK "FK, unidad de medida"
        int like_count "NOT NULL default 0"
        timestamptz computed_at "NOT NULL"
    }
    tags {
        int id PK
        text name UK
        bool is_shared
    }
    item_tags {
        UUID item_id PK,FK
        int tag_id PK,FK
        real weight
    }
    item_vectors {
        UUID item_id PK,FK
        vector vector
        text vocab_version "NOT NULL"
    }
    user_profiles {
        UUID user_id PK,FK
        enum scope PK "peliculas|juegos|general"
        vector vector "L2-normalizado"
        text vocab_version
        int signal_count
    }
    user_signals {
        bigint id PK
        UUID user_id FK
        UUID item_id FK
        enum signal_type "NOT NULL, sin default"
        timestamptz occurred_at "NOT NULL"
        enum source
    }
    user_exclusions {
        UUID user_id PK,FK
        UUID item_id PK,FK
        enum origin
        bool is_permanent
    }
    engine_config_versions {
        text config_version PK "hash inmutable"
        jsonb payload
        timestamptz activated_at
        timestamptz deactivated_at "NULL = activa"
    }
    sync_runs {
        bigint id PK
        enum status
        timestamptz finished_at
    }
    processed_events {
        UUID event_id PK
        enum result
        timestamptz expires_at
    }
```

**Fronteras**:

| Zona | Entidades | Naturaleza |
|---|---|---|
| **Ajena** (`api-general`) | identidad, catálogo, actividad | Consumida vía REST. Nunca duplicada como verdad |
| **Proyección local** | `users`, `items`, `tags`, `item_tags`, `user_signals` | Materialización desechable de datos ajenos |
| **Derivada durable** | `item_vectors`, `user_profiles`, `user_exclusions` | Propia. Recomputable, pero persistida por costo |
| **Operativa** | `engine_config_versions`, `sync_runs`, `processed_events` | Propia. `processed_events` **no** es recomputable — es memoria de hechos |
| **Caché** | Todo Redis | Descartable |

> `sync_runs` y `processed_events` no tienen FK: son bitácoras, no participan del grafo relacional.

---

## 6. Invariantes de datos

| ID | Invariante | Verificación | Origen |
|---|---|---|---|
| **DI-1** | Ningún ítem se persiste ni se sirve sin clasificación etaria resuelta | `items.age_rating NOT NULL` + default no-apto. Test: insertar sin rating → default restrictivo, nunca permisivo | FR-051 |
| **DI-2** | Todo usuario materializado tiene `birth_date` y ordinal etario completo y vigente | `birth_date`, `max_age_ordinal`, `age_derived_at`, `age_config_version` todos `NOT NULL` sin default. Test: insertar sin `birth_date` → rechazo de la base | RD-1, CR-1 |
| ~~DI-2a~~ | ~~Consistencia `max_age_rating` ↔ `max_age_ordinal`~~ | **ELIMINADO (RD-2)**: verificaba la coherencia entre dos representaciones del mismo hecho. Al quedar una sola, el estado inconsistente es irrepresentable y el invariante queda sin objeto | — |
| **DI-2a'** | El ordinal de todo usuario corresponde a su `birth_date` bajo `age_config_version` | Test de propiedad: para toda fila, `max_age_ordinal` es el que el mapeo registrado asigna a esa fecha. Sustituye a DI-2a con un objeto real: la derivación, no la duplicación | §4.1 |
| **DI-2b** | Ningún resultado almacenado ni servido contiene un ítem con `min_age_ordinal > max_age_ordinal` del usuario | Test de invariante: recorrer `reco:*` y `reco:stale:*` y cruzar contra `users`. Intersección de violaciones = ∅ | §4.2 |
| **DI-2c** | Todo cambio de `max_age_ordinal` invalida los resultados precomputados de ese usuario | Test: alterar el ordinal → la lectura siguiente no sirve el resultado previo (descarte o recálculo según §3.2) | §3.2, §7.5 |
| **DI-2d** | No existe forma de desactivar, saltear ni relajar el filtro por configuración | Revisión + test: no hay flag, no hay rama condicional, no hay valor de config que lo evite. `age_rating_catalog` no admite un ordinal «comodín» | Principio de seguridad |
| **DI-2e** | Ningún usuario con `age_config_version` distinta de la activa se evalúa | Test: ordinal derivado bajo otro mapeo no es comparable. Consulta de §7.5 causa B como chequeo permanente | §4.1, §7.5 |
| **DI-3** | Ningún elemento del conjunto de exclusión aparece en un top-N almacenado | Test de invariante (T017): para todo `reco:*`, intersección con `user_exclusions` = ∅ | FR-050 |
| **DI-4** | Todo top-N almacenado referencia una `config_version` existente | Test de integridad: cada `config_version` de Redis existe en `engine_config_versions` | Q4, FR-025 |
| **DI-5** | La clave de recomendación distingue siempre el módulo | Test unitario del constructor de claves: no existe forma de generar una sin `module` | §3.1 |
| **DI-6** | El mismo `event_id` no se procesa dos veces | PK sobre `processed_events.event_id`. Test: 10 inserciones → 1 fila, 1 recálculo | FR-011 |
| **DI-7** | A lo sumo una configuración activa | Índice parcial único sobre `deactivated_at IS NULL` | FR-025 |
| **DI-8** | Ningún vector se compara con otro de distinta `vocab_version` | `vocab_version NOT NULL` + error explícito al comparar | FR-010f |
| **DI-9** | Edad y exclusión se resuelven **solo con datos locales** | Test: el request path no emite ninguna llamada a `api-general` | FR-003, INV-1 |
| **DI-10** | Ningún ítem `retired` se selecciona, rankea ni sirve | Test de invariante (T017): retirar un ítem presente en `reco:*` y en `fallback:*` → la lectura siguiente no lo contiene. Cubre los tres puntos de §4.4 | RD-7, FR nuevo |
| **DI-11** | El retiro de un ítem **no destruye** señales históricas | Test: retirar un ítem con señales → `user_signals` conserva las filas y los perfiles no cambian. El retiro es lógico | RD-7 |
| **DI-12** | El respaldo **nunca mezcla** recuentos de ventanas distintas | Test: poblar `item_popularity` con dos `config_version` → el batch usa solo la activa. La PK compuesta hace la mezcla detectable, y el `WHERE config_version = :activa` la hace imposible | RD-13 |
| **DI-13** | Cada fila tiene un **único proceso escritor**, determinado por su zona (§1.1) | Revisión + test: el Data Transformer no escribe `item_popularity`; el batch de popularidad no escribe `items`. Verificable por los módulos que importan cada repositorio | RD-12 |

**DI-1, DI-2 y DI-7 se cumplen en el esquema**, no en el código. Es la diferencia entre un invariante
que se puede violar por olvido y uno que la base rechaza.

DI-2 y DI-2a'..DI-2e son los invariantes etarios exigidos por RD-1, con la corrección de RD-2.
Nótese que **DI-2b es el único que no puede garantizarse en el esquema**: cruza Redis con Postgres.
Por eso es un test de invariante transversal (T017) y no una constraint — y por eso la guarda del
request path (§4.2) existe.

**Verificabilidad tras la auditoría RD-5/RD-6**: ningún atributo se eliminó, de modo que **ningún
invariante pierde su método de verificación**. DI-2 sigue exigiendo `age_derived_at NOT NULL`: es
una constraint de integridad sobre el registro de auditoría —si existe la fila, existe la marca—,
no una lógica funcional sobre su valor. Esa distinción es la que RD-6 preserva.

---

## 7. Ciclo de vida y consistencia

### 7.1 Escritura

```
api-general ──REST──> Data Transformer ──> users, items, tags, item_tags, user_signals
                                             │
                                             ├──> item_vectors    (TF-IDF, vocab compartido)
                                             ├──> user_profiles   (3 scopes)
                                             └──> user_exclusions (resolución de señales)

evento ──> Worker ──> processed_events (idempotencia)
                 └──> engine + post-proceso ──> reco:v{cfg}:{user}:{module}
                                                reco:stale:v{cfg}:...
```

### 7.2 Lectura y ausencia de resultado precomputado

Precedencia **estricta** de FR-056 — el orden importa y es lo que hace el comportamiento determinista:

| # | Condición | `result_type` |
|---|---|---|
| 1 | Recálculo en curso o sin datos suficientes | `empty_pending` |
| 2 | Candidatos agotados tras filtrar | `empty_no_candidates` |
| 3 | Sin top-N personalizado, hay respaldo | `fallback` |
| 4 | Vigente vencido, obsoleto disponible | `personalized_stale` |
| 5 | Top-N vigente | `personalized` |

**Nunca se devuelve vacío silencioso** — corrige la deuda del prototipo. Cada estado es distinguible
y accionable por el consumidor. **Redis caído ≠ miss**: es `503` con `Retry-After` (FR-065), nunca
un `200` engañoso.

### 7.3 Consistencia eventual

El sistema es **eventualmente consistente por diseño** (Principio III): el top-N refleja el estado
del perfil al momento del último recálculo.

| Ventana | Valor | Origen |
|---|---|---|
| Señal → top-N actualizado | segundos a minutos | Latencia del worker |
| Frescura aceptable | `TTL_FRESH` = 24 h | D5 |
| Obsolescencia máxima servible | `TTL_STALE` = 7 d | D5, Q1 |
| Antigüedad de la proyección | `sync_runs` + alerta | T031, T042 |

**Excepción sin ventana de tolerancia**: los invariantes de seguridad. Una exclusión registrada es
efectiva en la **siguiente lectura** —el filtro se aplica al servir, no solo al precomputar (FR-036)—
y por eso `TTL_FILTERS` es corto. Un top-N puede estar desactualizado; **nunca puede estar mal
filtrado**.

### 7.4 Migraciones

Regla: **expand → migrate → contract**. Nunca destructivo en un solo despliegue.

1. Agregar estructura nueva, nullable o con default seguro
2. Backfill idempotente y reanudable
3. Endurecer constraints
4. Eliminar lo viejo, en despliegue posterior

Toda migración tiene `downgrade` probado (T003). Un cambio de dimensionalidad del vector implica
`vocab_version` nueva: los vectores se recalculan **antes** de activarla (FR-010g), nunca conviven
mezclados.

### 7.5 Ingesta de usuarios y caducidad de los derivados etarios

**Política de ingesta (Data Transformer, T029)** — un usuario sin `birth_date` **no se inserta ni se
actualiza en modo degradado**:

| Paso | Acción |
|---|---|
| 1 | Se **rechaza** el registro. No hay inserción parcial ni fila con derivados por default |
| 2 | Se registra como **violación de contrato** (`WARN`), con `user_id` y `sync_run_id`, no como error de datos del usuario |
| 3 | El usuario queda **fuera del universo recomendable**: sin fila, no hay a quién recomendar. La ausencia es el fail-closed |
| 4 | Se incrementa `contract_violations_total{field="birth_date"}`, cuyo **valor esperado es 0**. Cualquier valor > 0 alerta: indica que `api-general` incumple CR-1 |
| 5 | `sync_runs.result` refleja el rechazo; la corrida no se marca exitosa en silencio |

Que la métrica tenga valor esperado cero es lo que la vuelve útil: no mide un fenómeno normal con
umbral arbitrario, mide un incumplimiento binario.

**Caducidad del ordinal.** Es el costo de materializarlo: `max_age_ordinal` es correcto *al momento
de derivarlo* y deja de serlo por **dos causas distintas**, que exigen consultas y respuestas
distintas.

#### Causa A — Cruce de umbral etario (paso del tiempo)

El usuario cumple la edad de un umbral del catálogo (13, 16, 18). Afecta a un conjunto **pequeño y
exactamente identificable** de usuarios por día.

**Criterio de selección** — no es un recorrido por antigüedad de derivación:

```sql
-- Para cada umbral U del catálogo activo, la fecha de nacimiento de quien
-- cumple exactamente U años hoy. Son tantas fechas como umbrales (3 o 4).
WHERE birth_date IN (:hoy - U1 años, :hoy - U2 años, ...)
```

Es **igualdad exacta** sobre un puñado de valores, resuelta por `idx_users_birth_date`. Buscar
«derivados antiguos» sería incorrecto además de caro: la antigüedad de la derivación no predice el
cruce de umbral —un usuario derivado hace un año puede seguir teniendo el ordinal correcto, y uno
derivado ayer puede cumplir años hoy—.

Acción: actualizar `max_age_ordinal` y `age_derived_at`; emitir evento de recálculo por usuario
(mismo camino que cualquier otra invalidación, con la idempotencia de `processed_events`).

| Parámetro | Valor | Fundamento |
|---|---|---|
| Frecuencia | **Diaria**, fuera de pico | Los umbrales son de granularidad diaria |
| Ventana máxima de caducidad aceptable | **24 h** | Cota superior del desfasaje |
| Dirección del desfasaje | **Siempre conservadora** | El ordinal viejo es *menor* que el correcto: el usuario ve **menos** contenido del que le corresponde. Nunca más |
| Métrica | `age_refresh_last_success_timestamp` | Ver §7.5.1 |

**La ventana de 24 h no es una ventana de riesgo de seguridad.** El paso del tiempo solo puede
volver a un usuario *más* permitido, jamás menos.

#### Causa B — Derivado bajo una versión de configuración distinta de la activa

Un cambio de `age_rating_catalog` reasigna la escala: los ordinales derivados con el mapeo anterior
**no son comparables** con los de ítems derivados con el nuevo. Es un caso categóricamente distinto
del anterior: afecta potencialmente a **toda** la tabla y no lo produce el paso del tiempo.

**Criterio de selección**: `WHERE age_config_version <> :version_activa`, resuelto por el índice
parcial `idx_users_age_config_version`. Normalmente el conjunto es **vacío**; se puebla solo tras
activar un catálogo nuevo.

Acción: recálculo masivo de `max_age_ordinal` (y de `items.min_age_ordinal`), **antes** de activar
`vN+1` (§4.1). Un usuario cuya `age_config_version` no es la activa tiene un ordinal no comparable:
no se lo evalúa contra ítems de la escala nueva.

> Esta consulta es también la **verificación** de que la migración de §4.1 terminó. Que sea barata y
> normalmente vacía la vuelve apta para ejecutarse como chequeo permanente, no solo durante el
> despliegue.

**`age_derived_at` no participa de ninguna de las dos consultas.** Causa A selecciona por igualdad
sobre `birth_date`; causa B por desigualdad sobre `age_config_version`. Es un atributo **forense**
(RD-6): se escribe, no se lee. Indexarlo habría sido optimizar una consulta que el proceso no
ejecuta (RD-3).

#### 7.5.1 Métricas de caducidad etaria

| Métrica | Umbral | Acción que dispara | Responsable |
|---|---|---|---|
| `age_refresh_last_success_timestamp` | **> 26 h** sin corrida exitosa | **Alerta.** Ejecutar el job manualmente; investigar la causa. Mientras no corra, los usuarios que cumplen años quedan sub-permitidos (degradación conservadora, no incidente de seguridad) | Guardia de plataforma |
| `age_stale_config_users_total` (filas con `age_config_version <> :activa`) | **> 0 fuera de una migración en curso** | **Alerta.** Ordinales no comparables en circulación. Completar el recálculo de §4.1 antes de que se evalúen | Guardia de plataforma |
| `age_threshold_crossings_total` | Sin umbral | **Ninguna.** Solo panel: dimensiona el trabajo diario del job | — |

Las dos primeras son accionables y **diferenciadas por causa**: la primera dice «el proceso no
corre», la segunda «la escala está mezclada». Son fallas distintas con remediaciones distintas, y
pueden ocurrir por separado.

> ⚠️ **Métrica eliminada: `age_ordinal_staleness_seconds`.** No era solo no accionable: **era
> incorrecta**. Se definía como el máximo de `now() - age_derived_at`, suponiendo que un valor alto
> indicaba atraso del job. No lo indica. `age_derived_at` solo se actualiza cuando el usuario cruza
> un umbral, de modo que un adulto de 40 años que nunca volverá a cruzar ninguno conserva la marca
> de su alta —años de antigüedad— aun con el job corriendo perfectamente. La métrica habría estado
> en rojo permanente desde el primer mes, por diseño.
>
> La sustituye `age_refresh_last_success_timestamp`, que mide lo que realmente importaba: **si el
> proceso corre**. Es telemetría del job, no un agregado sobre una columna de usuarios — y por eso
> no requiere leer `age_derived_at`.

**El caso inseguro no llega por ninguna de estas dos vías.** Que un permiso se **restrinja** —por
corrección de una fecha de nacimiento errónea— llega por sincronización (CR-4) y se propaga de
inmediato: la actualización de `users` invalida los resultados y, hasta que el recálculo ocurra, la
guarda del request path (§4.2) descarta el snapshot con ordinal mayor (§3.2).

### 7.6 Ingesta de `region`

Contrasta con la política de `birth_date` (§7.5) en todo salvo en la observabilidad:

| Situación | Comportamiento |
|---|---|
| Región presente y válida (ISO 3166-1 alfa-2) | Se persiste tal cual, en mayúsculas |
| **Región ausente** | Se persiste `NULL`. **El usuario se materializa normalmente** y es plenamente elegible para recibir recomendaciones |
| **Región fuera del dominio admitido** | Se persiste `NULL` (no el valor inválido: guardar basura validada es peor que no guardar). Se registra el valor rechazado en el log, no en la columna. El usuario se materializa normalmente |

**Ninguna de estas situaciones impide materializar al usuario ni afecta sus recomendaciones.** No
podría: nada las lee. Un `NULL` en `region` es indistinguible, para el motor, de cualquier valor.

**Observabilidad** — métrica deliberadamente **distinta** de la de campos obligatorios:

| Métrica | Valor esperado | Severidad | Significado |
|---|---|---|---|
| `contract_violations_total{field="birth_date"}` | **Exactamente 0** | Alerta | Incumplimiento de CR-1. Rompe el contrato y deja usuarios fuera del servicio |
| `projection_field_anomalies_total{field="region", reason="missing"\|"invalid"}` | **Bajo, no necesariamente 0** | Solo panel, sin alerta | Calidad de un dato sin consumo. No degrada nada hoy |

Confundirlas sería el error: alertar por región ausente entrenaría al equipo a ignorar alertas de una
familia que incluye violaciones reales de contrato. La métrica de región existe para que, **el día
que la región se consuma**, se sepa de antemano en qué estado está el dato — que es la única defensa
contra la degradación silenciosa que RD-4 declara como costo.

### 7.7 Ingesta y frescura del catálogo

**Retiro de ítems.** El origen comunica el retiro por CR-7. Cuando un ítem **desaparece del origen
sin señal explícita** (CR-8), la sincronización lo marca `status = 'retired'` — **nunca lo borra**:

- El borrado físico **fallaría** por la FK de `user_signals.item_id`, que deliberadamente no tiene
  `ON DELETE CASCADE` (§2.6), a diferencia de las tablas derivadas. Esa ausencia de cascade no es un
  olvido: es lo que protege el historial.
- Forzar el borrado en cascada **destruiría las señales** del usuario, degradando sus perfiles y
  vaciando su conjunto de exclusión — un ítem consumido volvería a ser recomendable si reingresara.

La desaparición silenciosa se trata como retiro porque es la interpretación **conservadora**: dejar
de recomendar algo que quizá siga disponible cuesta cobertura; seguir recomendando algo retirado
cuesta credibilidad y puede tener consecuencias contractuales del lado del catálogo.

**Métricas del catálogo**:

| Métrica | Umbral | Acción que dispara | Responsable |
|---|---|---|---|
| `catalog_sync_last_success_timestamp` | **> 26 h** | **Alerta.** Catálogo congelado: altas y retiros no se reflejan. Ejecutar sync, investigar | Guardia de plataforma |
| `catalog_popularity_last_success_timestamp` | **> 26 h** | **Alerta.** El respaldo sirve un ranking congelado (RD-11). Degradación silenciosa de la calidad del `fallback` | Guardia de plataforma |
| `catalog_unrated_ratio` = `age_rating_source='unknown_defaulted'` / total vigentes | **> 5 %** | **Alerta.** Esa fracción del catálogo es **inalcanzable para todo usuario** por el fail-closed etario. Escalar al proveedor del catálogo para que declare las clasificaciones faltantes (RD-9) | Dueño de producto |
| `catalog_retired_total` | Sin umbral | **Ninguna.** Panel: dimensiona el catálogo vigente vs. histórico | — |

**`catalog_unrated_ratio` es la única métrica de auditoría accionable del modelo**, y por eso
`age_rating_source` es la única excepción a la prohibición forense. La diferencia con
`age_derived_at` (RD-6) es concreta: allí el atributo no permitía construir ninguna pregunta
operativa; acá permite formular «¿qué porcentaje de mi catálogo nadie puede ver?», cuya respuesta
tiene un dueño y una acción. La degradación que mide es **silenciosa por naturaleza**: un ítem sin
clasificar no produce error, simplemente nunca aparece.

---

## 8. Correspondencia con el prototipo

| Prototipo | Entidad definitiva | Divergencia | Acción | Tarea |
|---|---|---|---|---|
| `Item` (`domain.py:18`) | `items` + `item_tags` | `tag_vector` embebido en el objeto | Separar a `item_vectors` con `vocab_version` | T003, T007 |
| `Movie` / `Game` | `items.module` | Subclases por módulo | Discriminador, no herencia: el módulo es dato | T003 |
| `User` (`domain.py:55`) | `users` | `.age` calculada al vuelo, por candidato | Materializar `max_age_ordinal`; la aritmética de fechas ocurre una vez (§7.5) | T003, T029 |
| `Feedback.WEIGHTS` (`domain.py:76`) | `user_signals` + config | **`consumo` pesa 0.3 sobre el perfil** | Solo excluye, no altera el vector (Q3) | T008 |
| `UserMovieProfile` / `UserGameProfile` / `UserGeneralTagProfile` | `user_profiles.scope` | Tres clases distintas | Una tabla, discriminador `scope` | T003 |
| `TfIdfVectorizer` (`vectorizer.py:44`) | `item_vectors` | **Vocabulario independiente por módulo** | Espacio único compartido (FR-010d) | T007, T030 |
| `AGE_RATING_MIN` (`orchestration.py:19`) | `age_rating_catalog` en config | **Constante en código; `.get(rating, 0)` fail-open** | Externalizar a config con ordinal; desconocido ⟹ ordinal máximo (no apto) | T004, T013 |
| `ExclusionSet` (`orchestration.py:102`) | `user_exclusions` | Estado interno accedido desde el batch | Tabla + interfaz pública de pertenencia | T014 |
| `RedisCache` (`cache_redis.py:67`) | §3 | **`DEFAULT_TTL` 7 d compartido; sin `config_version`** | TTLs diferenciados; versión en clave y valor | T018, T019 |
| `reco:{user}:{module}` (`cache_redis.py:103`) | `reco:v{cfg}:{user}:{module}` | **El módulo ya está**; falta `config_version` | Agregar versión al namespace | T018 |
| `excl:{user}:{module}` (`cache_redis.py:107`) | `filters:{user_id}` | Mismo TTL que `reco:` | `TTL_FILTERS` estrictamente menor | T018 |
| — | `sync_runs` | **Entidad ausente** | Crear: freshness observable | T003, T031 |
| — | `processed_events` | **Entidad ausente** | Crear: idempotencia durable | T003, T024 |
| — | `engine_config_versions` | **Entidad ausente** | Crear: trazabilidad de Q4 | T003, T004 |

> **Corrección al brief**: se pedía resolver «ausencia de la dimensión de módulo en la clave». El
> prototipo **sí** la incluye (`cache_redis.py:103`). La ausencia real es la de `config_version`.
> No se documenta una divergencia inexistente.

---

## 9. Impactos sobre `spec.md`, `plan.md`, `tasks.md` e issues

### 9.1 `spec.md`

| FR | Acción | Detalle |
|---|---|---|
| **FR-030** | ✏️ Reescribir | El filtro se resuelve por comparación ordinal local, no por «edad del usuario» genérica |
| **FR-052** | ⚠️ **Obsoleto en su forma actual** | «Si la edad no puede determinarse ⟹ restricción máxima» pierde referente: el caso es **irrepresentable** (DI-2). Reemplazar por: *un usuario sin `birth_date` MUST ser rechazado en ingesta y MUST NOT existir en el universo recomendable* |
| **FR-051** | ✅ Se mantiene | Aplica a **ítems**, donde el fail-closed por default sigue siendo necesario |
| **FR-036 / FR-049 / FR-033d** | ✅ Sin cambio | La guarda ordinal del request path los satisface (§4.2). **No se debilitan** |
| **FR-053** | ✏️ Precisar | El catálogo etario debe definir ordinal único, contiguo y monótono (§4.1) |
| **DEP-5** | ⚠️ Endurecer | De «edad o fecha de nacimiento» a **`birth_date` obligatoria, no nula y confiable**. Pasa de dependencia informativa a **requisito contractual duro** (CR-1) |
| **Nuevo FR** | ➕ Crear | Caducidad de derivados etarios: ventana máxima 24 h, proceso periódico, dirección conservadora (§7.5) |
| **`region`** | ⭕ **Sin impacto** | No corresponde FR alguno: no habilita comportamiento observable. Un FR describiría un requisito inexistente. Solo se refleja en DEP/contratos como CR-5/CR-6 |

**⚠️ Impacto funcional de RD-7 — requiere FR nuevos.** A diferencia de todo lo anterior en este
documento, el ciclo de vida del ítem **cambia el comportamiento observable del sistema** y no puede
resolverse solo en el modelo de datos:

| FR | Acción | Enunciado propuesto |
|---|---|---|
| **FR-072** | ➕ **Crear** | Un ítem retirado del catálogo **MUST NOT** ser recomendado: ni seleccionado como candidato, ni incluido en el conjunto de respaldo, ni servido desde un resultado precomputado o degradado |
| **FR-073** | ➕ **Crear** | El retiro **MUST** ser lógico. Las señales históricas del usuario sobre un ítem retirado **MUST** conservarse y seguir alimentando su perfil y su conjunto de exclusión |
| **FR-074** | ➕ **Crear** | Un ítem que desaparece del origen sin señal explícita **MUST** tratarse como retirado. La sincronización **MUST** abortar sin marcar retiros si no puede confirmar que el listado recibido es completo (CR-9) |
| **FR-075** | ➕ **Crear** | Si tras excluir ítems retirados el resultado queda por debajo de `top_n`, **MUST** servirse la lista reducida. **MUST NOT** rellenarse con sustitutos, por requerir cómputo prohibido (FR-003) |
| **FR-033a1** | ⚠️ **Modificar** | El respaldo por popularidad **MUST** construirse solo sobre ítems vigentes |
| **FR-036** | ✏️ Precisar | La reevaluación de un resultado obsoleto **MUST** incluir la vigencia del ítem, además de la edad |
| **FR-025** | ✏️ Precisar | `tiebreak_criteria` deja de ser parámetro configurable (RD-10). El desempate es fijo y determinista |
| **DEP** | ➕ Crear | **DEP-7**: estado de disponibilidad del ítem y garantía de completitud del listado (CR-7, CR-8, CR-9) |

> **Estos FR deben entrar por `/speckit.specify` o `/speckit.clarify`**, no darse por aprobados
> porque estén escritos acá. El modelo de datos los anticipa; no los autoriza. FR-074 en particular
> tiene una consecuencia de producto —qué hacer ante un origen que responde parcialmente— que
> excede lo técnico.

### 9.2 `plan.md`

§2 ya delega en este documento. Agregar a la lista de componentes el job `age_threshold_refresh`
(Fase 1: sin él, DI-2c se degrada con el tiempo). Cerrar la referencia a resolución de edad en D-items.

### 9.3 `tasks.md`

| Tarea | Acción | Detalle |
|---|---|---|
| **T003** | ⚠️ Modificar | `users`: `birth_date NOT NULL`, `max_age_ordinal`, `age_derived_at`, `age_config_version`. **Sin `max_age_rating`** (RD-2) ni `age_resolution`. Índices `idx_users_birth_date` e `idx_users_age_config_version` (parcial) — **no** `idx_users_age_staleness` (RD-3). `items`: `min_age_ordinal`; conserva `age_rating`. Índices de `items` definidos por RD-7 (ver abajo) |
| **T004** | ⚠️ Modificar | Validar `age_rating_catalog` al cargar: ordinal único, contiguo, monótono con `min_age`. Falla el arranque si no |
| **T013** | ⚠️ Modificar | El filtro es **solo** `min_age_ordinal <= max_age_ordinal`. TDD: el test rojo debe incluir el caso fail-open del prototipo |
| **T017** | ⚠️ Modificar | Cubrir DI-2, DI-2a', DI-2b, DI-2c, DI-2d, **DI-2e**. **No** implementar DI-2a (eliminado por RD-2) |
| **T029** | ⚠️ Modificar | Política de rechazo + `contract_violations_total` con valor esperado 0. Deriva solo el ordinal |
| **T031** | ✏️ Precisar | Exponer `age_refresh_last_success_timestamp`, `age_stale_config_users_total` y `age_threshold_crossings_total` (§7.5.1). **No** exponer `age_ordinal_staleness_seconds`: eliminada por incorrecta (RD-6) |
| **T037** | ✏️ Precisar | La guarda del request path es comparación ordinal. **No se elimina** |
| **T042** | ⚠️ **Modificar** | Alertas: `contract_violations_total > 0`; **`age_refresh_last_success_timestamp > 26 h`**; `age_stale_config_users_total > 0` fuera de migración. Cada una con su acción y responsable (§7.5.1). La alerta sobre `age_ordinal_staleness_seconds` **no debe implementarse** — habría quedado en rojo permanente |
| **T047** | ⚠️ Modificar | Documentar CR-1..CR-4 en `docs/contracts/required-fields.md` |
| **T051** | ➕ **Crear** | Job `age_threshold_refresh`, con **dos criterios de selección separados** (§7.5 causa A por igualdad sobre fechas de umbral; causa B por config no activa). Emite `age_refresh_last_success_timestamp`. Fase 1. Depende de T003, T004 |

**Impacto de la auditoría RD-5/RD-6 sobre el backlog.** Ningún atributo se elimina ⟹ T003 no cambia
por este motivo. El impacto real está en **observabilidad**:

| Tarea | Acción | Detalle |
|---|---|---|
| **T031** | ⚠️ Modificar | Sustituir la métrica incorrecta por las tres de §7.5.1 |
| **T042** | ⚠️ Modificar | Reemplazar la alerta de `age_ordinal_staleness_seconds` por la de liveness del job. **Es la corrección más importante de esta auditoría**: la alerta original habría disparado permanentemente, y una alerta que siempre suena es peor que ninguna — enseña a ignorar la familia entera, que incluye violaciones de contrato |
| **T051** | ✏️ Precisar | Emitir la métrica de liveness al completar cada corrida |
| **T003** | ⭕ Sin cambio adicional | La clasificación por naturaleza (§2.1) es documental; no altera el DDL |

**Issues**: **#31, #42, #51** a modificar — los tres ya figuraban en la lista previa. **Ningún issue
nuevo, ninguno se cierra.**

**Impacto de la auditoría de catálogo (RD-7..RD-11).** Es el de mayor alcance del documento: es el
único que **agrega funcionalidad**.

| Tarea | Acción | Detalle |
|---|---|---|
| **T003** | ⚠️ Modificar | `items`: `status`, `retired_at`, `CHECK` de coherencia. Índice parcial `idx_items_candidates` (reemplaza a los totales) + `idx_items_synced_at` |
| **T004** | ⚠️ Modificar | **Eliminar `tiebreak_criteria`** del esquema de configuración (RD-10). El loader debe rechazar el parámetro si aparece |
| **T012** | ⚠️ Modificar | Selección de candidatos restringida a `status='available'` |
| **T017** | ⚠️ Modificar | Añadir DI-10 y DI-11 |
| **T018** | ⚠️ Modificar | Clave `retired:{module}` con `TTL_FILTERS` |
| **T029** | ⚠️ Modificar | Retiro por CR-7; desaparición → retiro (CR-8); **abortar sin marcar retiros si no hay confirmación de completitud (CR-9)**. Emitir `catalog_sync_last_success_timestamp` |
| **T031** | ⚠️ Modificar | Añadir `catalog_unrated_ratio`, `catalog_retired_total`, las dos de liveness |
| **T037** | ⚠️ **Modificar** | **Guarda de vigencia** en el request path (§4.4), además de la etaria. Lista reducida sin relleno (FR-075) |
| **T038** | ⚠️ Modificar | Respaldo solo sobre vigentes. Emitir `catalog_popularity_last_success_timestamp` |
| **T042** | ⚠️ Modificar | Alertas de §7.7 con umbral, acción y responsable |
| **T047** | ⚠️ Modificar | Documentar CR-7, CR-8, **CR-9** |
| **T052** | ➕ **Crear** | Tests de ciclo de vida del ítem: retiro lógico preserva señales (DI-11), retirado no servible por ninguno de los tres caminos (DI-10), sync parcial no retira (CR-9). Fase 1 |

**Sobre `plan.md`**: §2 delega en este documento, pero la lista de componentes debe incorporar la
guarda de vigencia en el request path. D-items sin cambio.

**Issues**: **#3, #4, #12, #17, #18, #29, #31, #37, #38, #42, #47** a modificar; **dos issues nuevos**
(T051 → #61, T052 → #62). **Ninguno se cierra por obsolescencia** — ni siquiera el de
`tiebreak_criteria`, porque T004 existe por el loader completo, no por ese parámetro.

> ⚠️ **Estos cambios no deben aplicarse al backlog hasta que los FR-072..FR-075 se aprueben.**
> Modificar T037 para filtrar por vigencia es implementar un requisito que todavía no existe en
> `spec.md`. La secuencia correcta es: aprobar los FR, después propagar.

**Impacto de la auditoría de popularidad (RD-12, RD-13, NC-7).**

| Tarea | Acción | Detalle |
|---|---|---|
| **T003** | ⚠️ Modificar | **Tabla `item_popularity`** con PK compuesta `(item_id, config_version)`, FK con CASCADE desde `items`, `idx_popularity_ranking`. Quitar `like_count_window` de `items`. Pasa a **12 tablas** |
| **T038** | ⚠️ **Modificar** | Batch con **reunión** `item_popularity × items`, filtrando `status='available'` y `config_version = :activa`. **Bloqueado por NC-7**: la definición de popularidad determina qué se calcula |
| **T017** | ⚠️ Modificar | Añadir DI-12 y DI-13 |
| **T029** | ✏️ Precisar | El Data Transformer **no escribe** `item_popularity` (DI-13) |
| **T050** | ⚠️ Modificar | Perfilar la reunión del batch: es el costo declarado de RD-12 y no debe asumirse resuelto |
| **T031** | ✏️ Precisar | `catalog_popularity_last_success_timestamp` desde el batch; `computed_at` permite detectar fallo **parcial** |

**Sobre `spec.md`**: **FR-033a1** debe precisarse con la definición que resuelva NC-7 — hoy dice
«por popularidad» sin definirla, lo que la vuelve no verificable. No corresponde FR nuevo por la
reubicación: es estructura interna, sin comportamiento observable.

**Sobre `plan.md`**: §2 lista las tablas; pasa a 12. La zona de datos de §1.1 debería reflejarse en
la descripción de componentes.

**Issues**: **#3, #17, #29, #31, #38, #50** a modificar. **Ninguno nuevo, ninguno se cierra.**

---

### Verificación de coherencia de esta auditoría

| Criterio previo | ¿Se respeta? | Cómo |
|---|---|---|
| RD-5: conservar la versión de config como unidad de medida | ✅ | RD-13 aplica el mismo argumento al mismo tipo de defecto. Difiere solo en que acá va **en la clave**, porque se requiere convivencia durante la transición |
| RD-11: descartar la marca temporal por fila | ⚠️ **Revisado** | El argumento (replicar un valor idéntico en millones de filas) valía para `items`; no vale para `item_popularity`, cuya existencia entera **es** el resultado del batch. Documentado en RD-11 |
| «Nada sin consumo entra al modelo» | ✅ | Se **rechaza** incorporar `dislike_count` y `consumo_count` por anticipación, y se explicita por qué la excepción de RD-4 no aplica: no hay costo de contrato compartido |
| No duplicar datos del origen | ✅ | No se denormaliza `module` en `item_popularity`, aun al precio de la reunión |
| Clasificación por zonas verdadera para toda entidad | ✅ | §1.1 revisada entidad por entidad. `item_popularity` era la única mal ubicada |
| Sin cómputo en el request path | ✅ | La reunión ocurre en el batch (T038) |
| Desempate determinista | ✅ | RD-10 intacto, con la referencia actualizada |

**Impacto de `region` (RD-4) sobre el backlog: mínimo y sin funcionalidad.**

| Tarea | Acción | Detalle |
|---|---|---|
| **T003** | ✏️ Precisar | Columna `region char(2) NULL` con `CHECK (region ~ '^[A-Z]{2}$')`. **Sin índice** |
| **T029** | ✏️ Precisar | Mapear `region` desde el origen; `NULL` ante ausencia o valor fuera de dominio; `projection_field_anomalies_total` (§7.6) |
| **T031** | ✏️ Precisar | Exponer la métrica **en panel, sin alerta** — distinta de `contract_violations_total` |
| **T047** | ✏️ Precisar | Documentar CR-5 y CR-6 |

**Ninguna tarea nueva, ningún issue nuevo, ninguna estimación cambia.** `region` no habilita
funcionalidad: no hay lógica que implementar, ni test de comportamiento que escribir más allá de la
validación de dominio en T029 y la aserción de §4.3 (que ningún componente la lee). No genera épica
ni criterio de aceptación funcional. Es una columna, un mapeo y una métrica.

**Ninguna tarea se cierra por obsolescencia.** Todas se refinan.

### 9.4 Issues de GitHub

| Issue | Acción |
|---|---|
| #3, #4, #13, #17, #29, #47 | ⚠️ **Modificar** cuerpo (criterios de aceptación afectados) |
| #31, #37, #42 | ✏️ **Precisar** (agregar criterio) |
| **nuevo #51+** | ➕ **Crear** issue de T051, milestone Fase 1, épica de datos |
| — | ✅ **Ninguno se cierra** |

> Los issues afectados por `region` (#3, #29, #31, #47) ya figuran arriba por las correcciones
> etarias. **`region` no agrega ningún issue a la lista**: se absorbe en cambios ya necesarios.

> ⚠️ La numeración issue↔tarea (`TXXX`→`#XXX`) se rompe con T051, porque #51–#60 ya son épicas. El
> issue nuevo tomará #61. Conviene anotarlo en `tasks.md` para no reintroducir la suposición.

---

## 10. Contrato requerido a `api-general`

Este repositorio tiene **prioridad de definición** sobre el modelo de datos; `api-general` se acopla.

| ID | Requisito | Consecuencia del incumplimiento |
|---|---|---|
| **CR-1** | El usuario expone **`birth_date`** (`date`, ISO 8601), **obligatoria y no nula** | El usuario se rechaza en ingesta y no recibe recomendaciones |
| **CR-2** | `birth_date` es **confiable**: validada en origen, no derivada ni estimada | Un dato erróneo produce un permiso etario erróneo. Es la fuente única |
| **CR-3** | No se expone campo `age` ni escalar equivalente | Un segundo formato reintroduce la resolución ambigua que RD-1 elimina |
| **CR-4** | Toda corrección de `birth_date` genera evento de sincronización | Sin él, un permiso restringido tarda hasta el próximo sync completo |
| **CR-5** | El usuario expone **`region`** como código **ISO 3166-1 alfa-2** en mayúsculas. **Best-effort**: puede venir ausente o nula | **NO se rechaza al usuario.** Se persiste `NULL` y se materializa igual (§7.6). Solo se contabiliza en `projection_field_anomalies_total` |
| **CR-6** | Toda corrección de `region` se refleja en la siguiente sincronización | Ninguna. No requiere evento dedicado ni invalidación de caché: nada consume el valor (§4.3). Se corrige solo por el sync periódico |
| **CR-7** | El catálogo expone el **estado de disponibilidad** del ítem, y comunica el retiro de forma explícita | Sin él, el retiro solo se detecta por desaparición (CR-8), con el rezago del sync completo |
| **CR-8** | Un ítem que **desaparece** del catálogo se interpreta como retirado | Si la desaparición fuera un defecto de paginación o un error transitorio del origen, se retirarían ítems vigentes. Mitigación: CR-9 |
| **CR-9** | La respuesta del catálogo permite distinguir un **listado completo** de uno parcial o fallido | **Crítico.** Sin esto, una respuesta truncada retiraría masivamente ítems vigentes. La sincronización **MUST** abortar sin marcar retiros si no puede confirmar completitud |

**Sobre el nivel de garantía de CR-5**: es el único requisito de la serie que **no** es exigible. Se
pide el estándar de codificación, no la presencia del dato. Exigir presencia sería incoherente:
no podemos convertir en bloqueante un campo que no usamos. Si `api-general` no puede emitir ISO
3166-1, es preferible que **no emita nada** a que emita texto libre — un `NULL` es honesto, un
`"Buenos Aires"` en un campo declarado ISO es una mentira que alguien creerá más adelante.

A documentar en `docs/contracts/required-fields.md` (T047) y a reflejar en la constitution de
`api-general` como cambio de contrato que requiere aprobación.

---

## 11. Registro de decisión

### RD-1 — `birth_date` obligatoria; filtro etario por comparación ordinal

**Contexto**: el modelo original admitía `birth_date` nula, un campo `age` alternativo y un atributo
de auditoría `age_resolution` con fail-closed sobre `undetermined` (FR-052).

**Decisión**: `birth_date` obligatoria y no nula como único insumo. Derivar `max_age_ordinal` y
comparar ordinales. Eliminar `age_resolution`.

**Fundamento**:
1. `age_resolution` audita un estado que ya no puede ocurrir. Un atributo cuyo dominio útil es vacío
   es ruido, y peor: **sugiere que el caso es manejable**, invitando a código que lo maneje.
2. La comparación ordinal es indexable; la comparación por enum requiere traducir en tiempo de
   ejecución, que es exactamente donde vivía el bug fail-open del prototipo (`.get(rating, 0)`).
3. Con un solo insumo obligatorio, el fail-closed se mueve del código al esquema: no hay rama que
   olvidar.

### Alternativa descartada — `birth_date` opcional + `age_resolution` + fail-closed

**En qué consistía**: aceptar usuarios sin fecha de nacimiento, registrar la procedencia de la
resolución, y aplicar la restricción máxima cuando fuera indeterminable.

**Por qué se descarta**: dado que `api-general` se acopla a este modelo, aceptar el dato ausente
sería tolerar voluntariamente una degradación evitable. Introduce un estado (`undetermined`) que
debe manejarse en cada punto de decisión, y un usuario permanentemente limitado al contenido más
restrictivo sin señal accionable — un fallo silencioso disfrazado de comportamiento seguro.

**Ventaja real que se resigna**: robustez ante un origen de datos incompleto. La alternativa degrada;
esta decisión rechaza. Rechazar es más visible, pero deja usuarios sin servicio.

**Condición bajo la cual debe reconsiderarse** — cualquiera de estas la reactiva:

1. `api-general` deja de poder garantizar CR-1 (p. ej. registro social sin fecha de nacimiento, o
   requisito legal de que el campo sea opcional).
2. Aparece un **segundo consumidor** del contrato con garantías distintas, de modo que este
   repositorio pierde la prioridad de definición.
3. `contract_violations_total{field="birth_date"}` deja de ser cero de forma sostenida y el origen
   no puede corregirse: la realidad contradice al contrato, y el modelo debe seguir a la realidad.

En cualquiera de los tres casos, la reversión es aditiva: relajar `NOT NULL`, reintroducir el
atributo de procedencia y hacer que `max_age_ordinal` tome el máximo del catálogo ante ausencia.
La escala ordinal **no** cambia — solo el modo de poblarla.

---

### RD-2 — Ordinal como única representación del permiso etario del usuario

**Contexto**: RD-1 introdujo `max_age_ordinal` **junto a** `max_age_rating`. Ambos codificaban el
mismo hecho, derivaban del mismo mapeo y ninguna consulta leía el enumerado: §4.2 establece que el
filtro opera solo sobre el ordinal y que ningún componente traduce clasificaciones en runtime.

**Decisión**: eliminar `max_age_rating` de `users`. Conservar solo `max_age_ordinal`.

**Fundamento**: el propio documento admitía que la consistencia entre ambos «se verifica por test,
no por constraint — la base no conoce el mapeo». Esa admisión es el argumento: la duplicación
**crea** un estado inconsistente posible que sin ella no existiría, y traslada al test la carga de
detectarlo. Un invariante que solo hace falta porque duplicamos un dato es un costo autoinfligido.

**Qué se pierde**: legibilidad directa en inspección de la tabla. Se recupera resolviendo el ordinal
contra `age_config_version` del propio registro — traducción siempre correcta, porque usa el mapeo
con el que se derivó, y nunca en el request path.

**No aplica a `items`**: ahí `age_rating` es dato recibido del origen, no derivado. Eliminarlo
perdería información irreconstruible y borraría la trazabilidad de `age_rating_source`.

**Invariante eliminado**: DI-2a queda sin objeto. Se sustituye por DI-2a', que verifica lo que sí
importa —que el ordinal corresponda a la fecha de nacimiento bajo el mapeo registrado—.

**Reconsiderar si**: apareciera un consumidor que requiera la etiqueta legible en caliente y con
volumen tal que la resolución contra la config resulte costosa. Sería entonces una **caché** de
presentación explícita, no un atributo del modelo.

---

### RD-3 — Índice orientado a la consulta de cruce de umbral

**Contexto**: RD-1 definió `idx_users_age_staleness (age_derived_at, birth_date)` para detectar
derivados caducados.

**Decisión**: reemplazarlo por `idx_users_birth_date (birth_date)` y un índice parcial sobre
`age_config_version`. Reclasificar `age_derived_at` como atributo de observabilidad.

**Fundamento**: el índice servía a una consulta que el proceso no ejecuta. El refresco no busca
*derivados antiguos* sino *usuarios que cruzan un umbral hoy*, lo cual es igualdad exacta sobre
tantas fechas como umbrales tenga el catálogo. La antigüedad de la derivación **no predice** el
cruce: un usuario derivado hace un año puede tener el ordinal correcto y uno derivado ayer puede
cumplir años hoy. Liderar el índice por `age_derived_at` habría forzado un recorrido por rango
seguido de descarte, sobre toda la tabla.

**Corolario**: al separar las consultas se hizo visible que hay **dos causas** de caducidad con
respuestas distintas —cruce de umbral (incremental, diario, seguro) y cambio de catálogo (masivo,
bloqueante de la activación)—. La formulación anterior las confundía en un solo barrido. La segunda
queda cubierta por `idx_users_age_config_version`, índice parcial normalmente vacío que sirve además
como verificación permanente de que la migración de §4.1 terminó (DI-2e).

---

### RD-4 — `region` como anticipación de contrato, sin consumo funcional

**Contexto**: ningún FR de `spec.md` exige recomendaciones regionales. El atributo no habilita
funcionalidad en esta feature.

**Decisión**: incorporar `users.region` (`char(2)`, ISO 3166-1 alfa-2, nulable, sin índice, sin
dimensión de clave). **No** incorporar disponibilidad regional en `items`.

**Fundamento**:
1. **La asimetría de costo de cambio.** Agregar una columna a una tabla propia es una migración
   local. Agregar un campo al contrato compartido requiere coordinación con `api-general`, cambio
   de versión de contrato y aprobación según su constitution. Definirlo ahora, mientras este
   repositorio tiene prioridad de definición y el contrato aún no está congelado, cuesta casi nada;
   hacerlo después cuesta una negociación entre repositorios.
2. **No es alcance nuevo** según el criterio verificable de §2.1: `region` tiene valor de verdad
   determinable sin decidir funcionalidad, a diferencia de NC-1.
3. **No compromete nada.** Nulable, sin índice, sin clave, sin invariante, sin lectura.

**Costo asumido, sin atenuar**: se persiste un dato que nadie valida por uso. Ninguna funcionalidad
falla si está mal, así que su degradación es silenciosa por construcción. Añade una columna al
esquema, al mapeo del Data Transformer y a la superficie de privacidad (NC-5) a cambio de un
beneficio íntegramente futuro y condicional. Si la segmentación regional nunca llega, esto fue
trabajo neto perdido y un campo que confundirá a quien lea la tabla en dos años.

**Alternativa descartada — diferir hasta que exista requisito funcional**

*En qué consistía*: no tocar el modelo ni el contrato; incorporar región cuando un FR la exija,
junto con su índice, su semántica de uso y su dimensión de clave.

*Qué la hace atractiva*: es el criterio que este documento aplicó a NC-1 y a la disponibilidad
regional de ítems. Evita el dato podrido y mantiene la regla «nada entra al modelo sin consumo».

*Qué se resigna al no diferirla*: la coherencia perfecta de ese criterio. Se admite acá una
excepción fundada en el costo de cambio del contrato, no en necesidad técnica. **Es la parte más
débil de esta decisión** y conviene que quede escrita así.

*Qué se resignaría al diferirla*: una modificación posterior del contrato compartido, con
coordinación entre dos repositorios y sus ciclos de aprobación — precisamente lo que la prioridad
de definición actual permite evitar.

**Condición de revisión** — cualquiera reabre la decisión:
1. Pasan **dos ciclos de planificación** sin que aparezca un requisito de segmentación regional:
   el beneficio esperado no se materializó y la columna debería eliminarse.
2. `projection_field_anomalies_total{field="region"}` es alto y sostenido: el origen no puede
   proveer el dato con calidad, y anticipar el contrato no compró nada.
3. Se determina que la región es dato personal con obligaciones de minimización (NC-5): entonces
   persistir sin consumo pasa de costo menor a **incumplimiento**, y la columna se elimina.
4. Aparece el requisito funcional: la decisión se cierra y `region` deja de ser anticipación —
   entran índice, dimensión de clave si corresponde (§4.3) y NC-6 para ítems.

---

### RD-5 — `age_config_version` se conserva: es condición de interpretabilidad

**Auditoría**: ¿es necesario, dado que el ordinal es derivable de `birth_date` + config activa?

**Sí, y por dos razones independientes**, cada una suficiente:

**1. Sin él, el ordinal es un número sin unidad.** Un `3` significa «18+» bajo un catálogo y podría
significar «16+» bajo otro con más niveles. La derivabilidad *futura* no rescata al valor *ya
almacenado*: derivarlo de nuevo con la config activa da el valor correcto de hoy, pero no dice bajo
qué escala se escribió el que está guardado — que es justo lo que hace falta para saber si es
comparable. El atributo no duplica información del ordinal: **le aporta la unidad de medida**.

**2. Es el único mecanismo de detección selectiva.** Sin él, identificar registros derivados bajo
una escala obsoleta exige recalcular el padrón completo y comparar — O(n) sobre toda la tabla, ante
cada cambio de catálogo. Con él es una desigualdad sobre un índice parcial normalmente vacío.

**Verificación exigida, punto por punto**:

| Requisito | Estado | Dónde |
|---|---|---|
| Consulta de detección declarada explícitamente | ✅ | §7.5 causa B: `WHERE age_config_version <> :version_activa` |
| El proceso lo usa efectivamente | ✅ | §7.5 causa B es criterio de selección, no comentario |
| Índice que la sirve | ✅ | `idx_users_age_config_version`, parcial (§2.1) |
| Integridad referencial definida | ✅ | FK → `engine_config_versions` (§2.1, ERD §5) |
| Impide el ordinal huérfano de escala | ✅ | `NOT NULL` + FK: no hay fila con ordinal y sin escala, ni con escala inexistente |
| Invariantes que dependen de él | ✅ | DI-2, DI-2a', DI-2e |

**Contraste con RD-2**: allí se eliminó `max_age_rating` porque **codificaba el mismo hecho** que el
ordinal y habilitaba un estado inconsistente. `age_config_version` codifica un hecho **distinto**
—bajo qué escala— que ningún otro atributo contiene. El criterio es el mismo; el resultado difiere
porque los casos difieren.

**Decisión**: conservar. Clasificado como atributo de **integridad**.

---

### RD-6 — `age_derived_at` se conserva solo como atributo forense

**Auditoría**: sus consumidores eran (a) la escritura en §7.5, (b) su mención en DI-2 como
`NOT NULL`, y (c) la métrica `age_ordinal_staleness_seconds`. Ninguna consulta de caducidad lo
utiliza como criterio de selección: causa A resuelve por igualdad sobre `birth_date`, causa B por
desigualdad sobre `age_config_version`.

**Hallazgo sobre (c)**: la métrica no solo no era accionable — **era incorrecta**. Medía el máximo de
`now() - age_derived_at` como proxy del atraso del job, pero la marca solo se actualiza al cruzar un
umbral. Un usuario adulto que ya no cruzará ninguno conserva la marca de su alta indefinidamente,
con el job funcionando. La métrica habría estado en rojo permanente por construcción. Eliminada y
sustituida por telemetría del job (§7.5.1), que no lee esta columna.

**Con (c) eliminada, el atributo queda sin ningún consumidor de lectura.**

**Decisión: conservar, con justificación exclusivamente forense.** No habilita ninguna decisión
operativa: todas las que importan están cubiertas por las dos métricas de §7.5.1. Su único valor es
la investigación posterior a un incidente de filtrado etario, donde la pregunta «¿cuándo se calculó
este permiso?» no tiene otra respuesta posible — ningún otro atributo la contiene, y `synced_at`
no sirve porque la derivación y la sincronización no ocurren juntas (causa A actualiza el ordinal
sin que haya sync).

**Prohibición expresa**: ⛔ no construir sobre él consultas de selección, alertas ni lógica
funcional. Su clasificación en la tabla de §2.1 hace la prohibición revisable en code review.

**Alternativa descartada — eliminar el atributo**

*A favor*: es el criterio que este documento aplicó en RD-2 (atributo redundante) y al rechazar NC-1
(sin requisito funcional). Cero consumidores de lectura es el caso más claro de «no debería estar».

*Por qué no se aplica el precedente*: los precedentes eliminaban atributos por razones que acá no
concurren. RD-2 eliminó un **duplicado** que creaba un estado inconsistente posible;
`age_derived_at` no duplica nada ni puede contradecir a ningún otro atributo. NC-1 se rechazó por
**carecer de valor de verdad** sin decidir producto; este tiene un valor de verdad objetivo y
verificable. El criterio real que unifica los tres casos no es «¿lo lee alguien?» sino **«¿aporta un
hecho propio, verdadero y no contenido en otro atributo?»** — y acá la respuesta es sí.

*Qué se resigna al no eliminarlo*: la regla simple «nada sin consumo entra al modelo». Se admite una
segunda excepción tras RD-4, lo cual erosiona esa regla. La diferencia con `region` es que este
atributo **sí tiene una función declarada** —forense— mientras que `region` no tiene ninguna hoy.

*Qué se resignaría al eliminarlo*: la reconstrucción de incidentes de filtrado etario. Dado que el
filtro etario es el invariante de seguridad central de esta feature, perder la capacidad de auditar
*cuándo* se calculó un permiso, para ahorrar ocho bytes por usuario, es un mal negocio.

**Condición de revisión**:
1. Si aparece cualquier consulta, alerta o lógica que lo lea: la clasificación forense se violó.
   Revisar si el uso es legítimo —y reclasificar— o si es el error que la prohibición anticipa.
2. Si una auditoría de privacidad determina que es dato de comportamiento sujeto a minimización
   (misma familia que NC-5), se elimina: no hay finalidad funcional que oponer.

---

### RD-7 — Ciclo de vida del ítem: retiro lógico

**Hallazgo**: el modelo no podía expresar «este ítem ya no está disponible». Consecuencia concreta:
un ítem retirado seguía siendo servible desde `fallback:` (el contador de popularidad no distingue
vigencia) y desde `reco:stale:` (hasta 7 días). Ninguna guarda lo detectaba: la del request path
solo verificaba edad, y el filtro de exclusión se define sobre señales del usuario, no sobre estado
del ítem. **Era un defecto funcional, no una omisión de modelado.**

**Decisión**: `status enum(available, retired)` con default `available`, más `retired_at` forense.
Retiro **lógico**. Aplicado en tres puntos (§4.4) y respaldado por índices parciales.

**Por qué lógico y no físico**: el borrado físico fallaría por la FK de `user_signals.item_id`, que
no tiene cascade —a diferencia de las tablas derivadas—. Y forzarlo destruiría el historial que
alimenta perfiles y exclusiones: un ítem ya consumido volvería a ser recomendable si reingresara al
catálogo. La asimetría de cascade en el esquema ya expresaba esta decisión; RD-7 la hace explícita.

**Alternativa descartada — borrado físico con cascade a señales**: más simple de implementar y evita
una condición en cada consulta. Se resigna la integridad del historial del usuario, que es
irrecuperable: las señales no se pueden reconstruir desde ninguna fuente. Se descarta.

**Revisión**: si `catalog_retired_total` creciera hasta degradar el rendimiento de los índices
parciales, correspondería archivar ítems retirados sin señales asociadas — nunca los que las tengan.

---

### RD-8 — Verificar vigencia en el request path

**Decisión**: se verifica al servir, contra el set `retired:{module}`.

**Fundamento**: es una diferencia de conjuntos sobre ≤ 50 ítems ya ordenados —**el mismo orden de
costo y la misma estructura de datos que el filtro de exclusión que T037 ya ejecuta** en esa ruta—.
FR-033d admite explícitamente operaciones acotadas sin similitud, recomputación ni reordenamiento.

**Alternativas descartadas**:

*Invalidación proactiva*: correcta, pero retirar un ítem popular exigiría invalidar los resultados de
todos los usuarios que lo contengan, y sin índice invertido ítem→usuarios eso es un barrido del
espacio de claves. Se descarta por costo. **Reconsiderar si** el volumen de retiros fuera bajo y
predecible, y existiera ese índice.

*Aceptar exposición acotada*: la ventana real sería `TTL_STALE` (7 días) más el TTL del respaldo.
No es acotada en ningún sentido operativo útil. Se descarta.

**Costo asumido**: la respuesta puede contener menos de `top_n` elementos, porque no se rellena con
sustitutos —rellenar exigiría rankear, que sí está prohibido en esa ruta—. Es una degradación
visible y honesta, preferible a servir contenido inexistente.

---

### RD-9 — `age_rating_source`: auditoría **accionable**, excepción a la regla forense

**Decisión**: conservar, y **sí habilita una métrica accionable**: `catalog_unrated_ratio` (§7.7),
umbral 5 %, acción «escalar al proveedor del catálogo», responsable dueño de producto.

**Por qué difiere de RD-6**: allí `age_derived_at` no permitía formular ninguna pregunta operativa
—su valor alto era esperable y no indicaba falla—. Acá la pregunta es «¿qué porcentaje del catálogo
es inalcanzable para todos los usuarios?», tiene respuesta numérica, dueño y remediación. La
degradación que mide es **silenciosa por construcción**: un ítem sin clasificar no genera error,
simplemente nunca aparece en ninguna recomendación. Sin esta métrica, nadie se entera.

El criterio se mantiene intacto —toda métrica debe ser accionable—; lo que cambia es que acá se
cumple. La prohibición de lógica funcional sigue vigente: `age_rating_source` **no** filtra ni
pondera. El filtro usa `min_age_ordinal`.

---

### RD-10 — `tiebreak_criteria` eliminado de la configuración

**Hallazgo**: parámetro configurable con **un solo valor posible**. Los demás candidatos razonables
—antigüedad, novedad, fecha de publicación— requieren atributos descriptivos cuya autoridad es del
origen y cuya incorporación está explícitamente prohibida.

**Decisión**: eliminarlo. Desempate **fijo**: mayor `item_popularity.like_count`; ante empate
persistente, orden lexicográfico por `id`.

**Fundamento**: un parámetro con una sola alternativa no es configuración, es una constante que
aparenta flexibilidad. El daño concreto es que invita a configurar un valor que no existe, fallando
en runtime o —peor— siendo ignorado en silencio.

**Por qué el desempate por `id` es aceptable**: es arbitrario pero **determinista**, que es la
propiedad que importa. Dos ejecuciones con el mismo estado producen el mismo orden; sin eso, los
tests de reproducibilidad no son escribibles.

**Alternativa descartada — incorporar `published_at` para sostener el parámetro**: haría honesta la
configuración, pero introduce un atributo descriptivo del origen sin requisito funcional que lo
pida. Es exactamente lo que NC-1 y las restricciones rechazan. **Reconsiderar si** aparece un
requisito de desempate o ponderación por novedad — entraría por `/speckit.clarify` con el atributo.

---

### RD-11 — Frescura del contador de popularidad: telemetría, no atributo

**Hallazgo**: `like_count_window` no registra cuándo se calculó, y `synced_at` no lo suple: la
sincronización del catálogo y el recálculo de popularidad no son solidarios. Si el proceso de
popularidad se interrumpe, el respaldo sirve un ranking congelado sin señal alguna.

**Decisión**: **telemetría del proceso** (`catalog_popularity_last_success_timestamp`, §7.7), no un
atributo `popularity_computed_at` en `items`.

**Fundamento — mismo criterio que RD-6**: la pregunta operativa es «¿corre el proceso?», que es una
propiedad **del proceso**, no de cada fila. Un atributo por ítem replicaría el mismo valor millones
de veces y obligaría a agregarlo para responder algo que el job puede emitir directamente. Es
además la lección de la métrica incorrecta que RD-6 eliminó: medir frescura por agregación sobre una
columna de entidades es frágil, porque el valor depende de cuándo se tocó cada fila y no de si el
proceso funciona.

**Alternativa descartada — `popularity_computed_at` por ítem**: permitiría detectar ítems
individuales no recalculados, útil si el proceso fuera incremental y pudiera fallar parcialmente.
**Reconsiderar si** el recálculo deja de ser un batch total y pasa a ser incremental por ítem.

**Hallazgo 5 resuelto en la misma dirección, pero al revés**: sí se incorpora
`idx_items_synced_at`, simétrico con `idx_users_synced_at`. La diferencia con el caso anterior es
que acá la consulta es *por fila* —«¿qué ítems no se sincronizan desde hace X?»— y sirve para
distinguir un sync globalmente caído de uno que omite un subconjunto. Esa distinción no la puede
dar la telemetría del job.

> 🔄 **RD-11 revisado por RD-13.** Su argumento contra `popularity_computed_at` era que replicaría
> un valor idéntico en cada fila de una tabla de millones. Ese argumento **era correcto para
> `items`** —donde la mayoría de las filas no tienen nada que ver con popularidad— y **deja de
> serlo** en `item_popularity`, cuya existencia entera es el resultado de ese batch. Ahí
> `computed_at` no es un agregado forzado sino un atributo natural de la fila, y permite algo que la
> telemetría del job no puede: detectar un batch **parcialmente** fallido, donde el job reportó
> éxito pero un subconjunto de ítems no se recalculó. La telemetría del job se conserva; el
> atributo la complementa. Es la misma distinción que ya llevó a conservar `idx_items_synced_at`
> pese a existir telemetría de sync.

---

### RD-12 — `like_count_window` reubicado a `item_popularity`

**Hallazgo**: el atributo vivía en `items`, declarada **proyección local** —desechable y
reconstruible sincronizando—, pero no provenía del origen: lo producía un proceso propio desde
señales locales. Dos consecuencias, ambas reales:

1. **Dos escritores sobre la misma fila.** El Data Transformer escribía la proyección y el batch de
   popularidad escribía esa columna. Nada estructural impedía que un `UPDATE` de sincronización
   pisara el recuento; solo lo evitaba la disciplina de escribir columnas explícitas en el `UPSERT`.
   **Mitigación por convención de código, no por estructura** — y las convenciones se olvidan.
2. **La desechabilidad era falsa.** §1 afirmaba que la proyección se reconstruye sincronizando. No
   era cierto: la resincronización no repone el recuento. Una restauración desde el origen habría
   dejado el respaldo en cero sin que nada lo señalara.

**Decisión**: reubicar a `item_popularity` (§2.11), zona de **derivados durables**. Se agrega §1.1
con las zonas y la **regla de escritor único**, y DI-13 para verificarla.

**Fundamento**: el criterio de ubicación no es «¿sobre qué entidad habla el dato?» sino **«¿quién lo
produce y cómo se reconstruye?»**. La popularidad habla de un ítem pero es estado propio, igual que
`item_vectors` —que nadie propuso meter en `items` pese a ser 1:1 con él—. La inconsistencia estaba
en tratar dos derivados del mismo tipo de forma distinta.

**Costo asumido**: el batch de respaldo pierde el índice parcial de una sola pasada y pasa a
requerir una **reunión** con `items` para filtrar vigencia y agrupar por módulo. Es aceptable porque
corre fuera del request path, sobre catálogo acotado, con periodicidad de horas — y queda a
verificar en T050, no asumido.

**Alternativa descartada — conservar en `items` y corregir la afirmación de §1**: habría sido más
barato, y honesto en el sentido de que la documentación describiría la realidad. Se resigna la
propiedad de desechabilidad de la proyección, que es una garantía operativa concreta: poder truncar
y resincronizar el catálogo ante una corrupción, sin perder nada. Cambiar la definición para que
encaje con el modelo, en lugar de corregir el modelo, es debilitar un principio para evitar una
migración. Se descarta.

**Condición de revisión**: si el perfilado de T050 mostrara que la reunión domina el tiempo del
batch y no se resuelve con índices, correspondería evaluar una vista materializada — **no** volver
a mezclar zonas.

---

### RD-13 — `config_version` como unidad de medida del recuento

**Hallazgo**: el recuento se calcula sobre `popularity_window_days`, parámetro de la configuración
versionada. Dos valores calculados bajo ventanas distintas **no son comparables**, y el modelo no
registraba bajo cuál se había calculado cada uno. Durante una transición de ventana, el respaldo
podía mezclar escalas sin señal alguna: un ítem recalculado bajo 30 días compitiendo contra uno
todavía bajo 7.

**Decisión**: `config_version` como **parte de la clave primaria** de `item_popularity`, no como
mero atributo. Más `computed_at`.

**Fundamento — es exactamente el criterio de RD-5**, aplicado al mismo tipo de defecto: *la
derivabilidad futura no rescata al valor ya almacenado*. Recalcular la popularidad hoy da el valor
correcto de hoy, pero no dice bajo qué ventana se calculó el que está guardado — que es justo lo
necesario para saber si es comparable. El atributo **no duplica información: aporta la unidad de
medida**. Un `like_count = 40` sin ventana declarada es un número sin sentido.

**Por qué en la clave y no como columna**: en `users`, `age_config_version` es columna porque el
usuario tiene **un** ordinal vigente. Acá se necesita que **convivan** los recuentos de la ventana
saliente y la entrante durante la transición, para que el batch pueda seguir sirviendo el respaldo
con la ventana activa mientras se calcula la nueva. La clave compuesta hace la transición
**aditiva**, igual que `config_version` en la clave de Redis (§4): sin invalidación masiva, con las
filas viejas purgables tras confirmar.

**Alternativa descartada — recalcular todo el padrón antes de activar la config nueva**, como se
hace con los ordinales etarios (§4.1). Es correcta y más simple. Se descarta porque las escalas
etarias **deben** migrarse en bloque —mezclarlas rompe un invariante de seguridad— mientras que
mezclar ventanas de popularidad solo degrada la calidad del respaldo. Bloquear la activación de una
configuración por un recálculo de popularidad sería tratar un problema de calidad con la severidad
de uno de seguridad.

**Condición de revisión**: si las transiciones de ventana resultaran tan infrecuentes que la
convivencia no aporte, simplificar a columna + recálculo en bloque.

---

## 12. Pendientes de clarificación

| ID | Ambigüedad | Por qué no lo asumo | Bloquea |
|---|---|---|---|
| **NC-1** | «Módulo de interés» del usuario | Ningún FR lo requiere; las recomendaciones se piden por módulo en el request (FR-006). Agregarlo sería alcance nuevo | No. `users` está completa sin él |
| **NC-2** | Retención de `user_signals` | Decisión de producto con implicancias de privacidad. Afecta el tamaño de la tabla y la ventana de FR-033a1 | No a Fase 1. Sí antes de producción |
| **NC-3** | ~~Formato de la edad~~ | ✅ **Cerrado por RD-1**: `birth_date` obligatoria, único formato admitido (CR-1, CR-3) | — |
| **NC-4** | Umbrales del `age_rating_catalog` (¿ATP/13/16/18?) | El esquema es agnóstico, pero los valores concretos son decisión de producto/legal | No a T003. Sí a T004 |
| **NC-5** | ¿`region` es dato personal sujeto a minimización? | Misma familia que NC-2. Un dato de ubicación **persistido sin consumo** es el caso más difícil de justificar ante un principio de minimización: no hay finalidad que invocar. No decido esto solo | No a T003. **Sí antes de producción**, y condiciona RD-4 |
| **NC-6** | Disponibilidad regional de ítems | Fuera de alcance por RD-4 (§2.2): es dato de licenciamiento, conjunto no escalar, con autoridad fuera de este repositorio | No. Entra por `/speckit.clarify` si aparece segmentación regional |
| **NC-7** | **¿Qué constituye «popularidad»?** | Decisión de producto, no técnica. Ver abajo | No a T003. **Sí a T038** |

#### NC-7 — Definición de popularidad

`spec.md` no define qué es popularidad; FR-033a1 solo dice que el respaldo se construye por
popularidad. El modelo implementa hoy **recuento bruto de señales positivas**, que es una decisión
tomada por omisión, no deliberada. Las alternativas producen ordenamientos radicalmente distintos:

| Definición | Efecto | Atributos que exige |
|---|---|---|
| **Recuento bruto de positivas** (actual) | Encabeza el respaldo con ítems **polarizantes**: un ítem con 1000 likes y 900 dislikes supera a uno con 800 likes y 5 dislikes | `like_count` |
| **Diferencia** (positivas − negativas) | Penaliza la polarización, pero sigue dominada por el volumen | `like_count`, `dislike_count` |
| **Proporción** (positivas / total) | Encabeza con ítems de **muy pocas señales**: 3 likes y 0 dislikes da 100 % | `like_count`, `dislike_count` |
| **Estimador con corrección de muestra pequeña** (p. ej. límite inferior de un intervalo de confianza) | Corrige ambos sesgos | `like_count`, `dislike_count` |

**Ninguna es derivable de las otras sin conservar sus componentes**: de la proporción no se recupera
el volumen, del recuento bruto no se recupera la proporción. Por eso la decisión condiciona el
modelo y no puede posponerse hasta la implementación de T038.

**Consideración adicional para producto**: las señales de `consumo` **no** alteran el perfil del
usuario (Q3, FR-022b) porque no expresan preferencia. Pero sí son **evidencia legítima de
popularidad** —alguien lo vio o lo jugó— y hoy no participan del cálculo. Que se excluyan de una
dimensión no implica que deban excluirse de la otra; conviene decidirlo explícitamente.

> **No se incorporan `dislike_count` ni `consumo_count` por anticipación.** Serían atributos sin
> consumo, y **la excepción admitida en RD-4 para `region` no aplica acá**: allí la justificación
> era el costo de modificar el contrato compartido con `api-general`, que exige coordinación entre
> repositorios y aprobación. Estos son **datos propios**, derivables de `user_signals` —que ya los
> registra— mediante una migración local de bajo costo. Sin ese costo asimétrico, no hay excepción
> que invocar y rige la regla general: nada sin consumo entra al modelo.


Ninguno bloquea T003. NC-2, NC-4 y **NC-5** deberían cerrarse antes de Fase 2.
**NC-7 bloquea T038** y debería cerrarse antes: implementar el respaldo exige saber qué se ordena.

> **NC-5 tiene prioridad sobre los demás** porque puede revertir RD-4. Es el único pendiente capaz
> de convertir una decisión aplicada en un cambio a deshacer.



---

<sub>Refinamiento de `plan.md` §2 · Trazable a spec.md FR-001→FR-071 y constitution v1.0.0 · Prototipo consultado como referencia (no normativo)</sub>
