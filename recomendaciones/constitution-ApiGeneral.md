<!-- Copia de referencia de la constitution de api-general (fuente: repo api-general), ratificada v1.0.0.
     Reconstruida el 2026-09-27: el archivo original estaba entrelazado línea a línea con el borrador
     previo (ver constitution-ApiGeneral.borrador-previo.md). Contenido sin cambios. -->

# RecoMe · api-general Constitution

**Sistema:** RecoMe — hub de recomendaciones de películas y videojuegos.
**Repo:** `api-general` (Java/Spring Boot) — API General, DB General (PostgreSQL: usuarios,
catálogo, actividad), DB Logs (Cassandra: eventos y trazas de alto volumen) y documentación de
contratos compartidos (OpenAPI + JSON Schema) del sistema completo.

> Este documento es la ley interna del repo. Ninguna decisión de diseño, por urgente o simple
> que parezca, puede contradecirlo. Si la solución "más fácil" rompe un principio, la solución
> está mal — no el principio.

## Rol y Límites del Repo

`api-general` es una de cuatro partes de RecoMe (junto a `recomendaciones`, `notificaciones` y
`frontend`), cada una con equipo, base de datos y ciclo de deploy propios. Cumple tres roles no
negociables: **punto de entrada único** del sistema, **autoridad de identidad y autorización**
de usuarios finales, y **fuente única de verdad de los contratos compartidos**.

Lo que este repo **no** es: no calcula ni almacena perfiles de tags, vectores de similitud ni
recomendaciones (eso es de `recomendaciones`); no hostea el broker de RabbitMQ ni el
almacenamiento de archivos/MinIO (eso es de `notificaciones`); no renderiza UI (eso es de
`frontend`).

## Core Principles

### I. Puerta de Entrada Única y Frontera de Datos (NO NEGOCIABLE)

Frontend Usuario y Frontend Vendedor/Admin hablan **solo** con `api-general`. Ningún endpoint de
`recomendaciones` o `notificaciones` se expone, proxea de forma transparente ni publica hacia los
frontends, ni siquiera "temporalmente", "solo para un dashboard interno" o por presión de
deadline. Simétricamente, `api-general` es dueño exclusivo de DB General y DB Logs: ningún otro
repo se conecta a ellas, y este repo nunca abre conexión directa a la DB de `recomendaciones`
(PostgreSQL+pgvector) ni a la DB Archivos (MinIO) de `notificaciones`. Todo dato ajeno se obtiene
por HTTP REST contra el repo dueño o por evento de RabbitMQ. Las migraciones y el esquema interno
de DB General y DB Logs son responsabilidad exclusiva de este repo y evolucionan libremente
mientras no rompan los contratos publicados; ningún repo externo puede asumir esa estructura más
allá de lo que el contrato REST expone, y este repo no asume la estructura interna de bases
ajenas.

### II. Custodia de los Contratos Compartidos (NO NEGOCIABLE)

Este repo aloja y versiona las specs **OpenAPI** de todos los endpoints internos consumidos entre
repos y los **JSON Schema** de todos los eventos de RabbitMQ del sistema — incluso de contratos
cuya implementación runtime no vive acá (el broker lo hostea `notificaciones`, pero el schema del
evento se documenta acá) y de eventos que este repo ni publica ni consume. **Si un contrato no
está documentado en este repo, no es un contrato válido del sistema.** Custodia no es propiedad:
`api-general` es el registro y el guardián del proceso, no el dueño unilateral del contenido.
Ningún cambio de contrato puede mergearse acá por decisión exclusiva de este equipo, aunque este
repo sea quien publica el evento. Nombres de eventos y convenciones de API se definen una sola
vez, acá, **antes** de implementarse en cualquier repo: nunca se implementa primero "para probar"
y se documenta después.

### III. Versionado de Contratos y Compatibilidad Backwards (NO NEGOCIABLE)

Todo endpoint expuesto a otro repo tiene spec OpenAPI versionada. Los cambios **aditivos y
compatibles** (campo opcional nuevo, endpoint nuevo, valor de enum nuevo tolerado por los
consumidores) pueden publicarse sobre la versión vigente. Todo cambio **breaking** (eliminar o
renombrar un campo, volver requerido un campo opcional, cambiar tipo o semántica, endurecer
validaciones, cambiar códigos de estado o la forma de error) exige una **versión nueva y
explícita** del endpoint o del schema de evento: la versión anterior no se pisa ni se elimina sin
un **período de coexistencia acordado** con todos los consumidores conocidos, con fecha de
deprecación comunicada por escrito. Los schemas de evento evolucionan preferentemente de forma
aditiva; un cambio incompatible implica un nombre/versión de evento nuevo y migración coordinada
de publicadores y consumidores, nunca una mutación in-place del schema vigente. Todo contrato
publicado declara su versión y su estado (vigente / deprecado / retirado).

### IV. Proceso y Autoridad de Aprobación de un Cambio de Contrato

Un cambio de contrato compartido solo se mergea cuando se cumplen, **en este orden**:
1. Se actualiza la documentación del contrato (OpenAPI o JSON Schema) en este repo, incluyendo
   versión, motivo del cambio y clasificación compatible/breaking.
2. Se notifica explícitamente a **todos** los repos publicadores y consumidores afectados.
3. Se obtiene **conformidad escrita de cada equipo consumidor afectado** antes de mergear, no
   después. El equipo de `api-general` aprueba la forma, la consistencia y el versionado del
   contrato, pero **no puede aprobar en nombre de un consumidor**: un breaking change sin
   conformidad de los consumidores queda bloqueado, sin excepción por urgencia.
4. Si es breaking, se acuerda período de coexistencia y plan de migración antes del merge.

Clasificación obligatoria: un cambio es **interno** solo si no toca ningún endpoint documentado,
ningún schema de evento, ni el comportamiento observable de un contrato publicado, ni las reglas
de autenticación servicio-a-servicio. Cualquier otra cosa **no es interna** y sigue el proceso de
arriba. **Ante la duda, se trata como no-interno**: coordinar de más es más barato que romper un
contrato en producción.

### V. Gobernanza de Autenticación y Autorización (NO NEGOCIABLE)

Este repo es la única autoridad de identidad de usuario final y de las reglas de autorización del
sistema; ningún otro repo reimplementa, duplica ni "cachea" esa lógica, y ningún repo confía en
un claim de usuario que no haya sido validado acá. Existen **dos planos de autenticación
estrictamente separados**:
- **Usuario final** → credenciales/tokens emitidos y validados por `api-general`, con expiración,
  rotación y revocación gestionadas acá. Autorización por roles/permisos evaluada en este repo
  antes de orquestar hacia otros servicios.
- **Servicio-a-servicio** → **API key interna por entorno**, distinta por ambiente y distinta de
  cualquier credencial de usuario. Toda llamada interna entrante (p. ej. Data Transformer de
  `recomendaciones`, Analytics de `frontend`) la exige, y toda llamada interna saliente la
  presenta. **Ningún endpoint interno queda expuesto sin este control**, incluso si "no tiene
  datos sensibles".

Un token de usuario final nunca se reutiliza como credencial de servicio, ni viceversa. Los
secretos viven en configuración por entorno, nunca versionados ni logueados. Cambiar las reglas de
autenticación servicio-a-servicio es, por definición, un cambio de contrato (Principio IV).

### VI. Orquestación con Delegación Estricta

`api-general` **orquesta**: autentica, autoriza, valida entrada, resuelve datos propios (usuarios,
catálogo, actividad), invoca a los servicios dueños de cada capacidad, compone la respuesta y
registra la traza. `api-general` **no ejecuta trabajo ajeno ni pesado**:
- Cálculo de scoring, similitud, perfiles de tags o diversificación → **delegado** a
  `recomendaciones` (lectura vía REST de resultados precomputados; recálculo vía el evento
  `recomendacion.actualizar`). Nunca se replica el motor acá.
- Envío de mails/push, generación y almacenamiento de reportes o archivos → **delegado** a
  `notificaciones` vía eventos (`notificacion.enviar`, `reporte.generar`).
- Presentación y agregación analítica de cara al usuario → **delegado** a `frontend`/Analytics,
  que consumen datos por REST de este repo.

Ningún endpoint de cara al usuario dispara trabajo pesado o de larga duración de forma síncrona:
se publica un evento y se responde con estado. Toda llamada saliente lleva timeout explícito,
manejo de fallo y degradación controlada — nunca resuelta accediendo a datos ajenos por otra vía.
Orquestar no habilita a asumir la estructura interna del servicio invocado más allá de su contrato.

### VII. Testing, Contract Testing y Observabilidad

La principal superficie de riesgo de este repo es romper contratos de los que dependen otros tres
equipos. Obligatorio antes de cualquier release:
1. **Unitarios** de la lógica propia: autenticación, autorización, orquestación y reglas de
   catálogo/actividad.
2. **Integración contra DB General y DB Logs reales** (Postgres/Cassandra efímeros, no mockeados)
   para validar migraciones y queries.
3. **Contract testing de todo endpoint expuesto** contra su spec OpenAPI publicada acá: cualquier
   divergencia entre implementación y spec es un bug bloqueante de release.
4. **Validación de schema de cada evento publicado** contra su JSON Schema, previa a la
   publicación en RabbitMQ.
5. **Validación de eventos consumidos**: ante payload que no matchea el schema, el consumidor
   falla de forma explícita y detectable (nunca silenciosa), con dead-letter y alerta — es la
   señal temprana de que otro repo rompió un contrato.
6. **Regresión de compatibilidad** al versionar: la versión anterior sigue funcionando durante
   todo el período de coexistencia acordado.
7. **Observabilidad**: logging estructurado con `correlation_id` propagado a cada llamada
   saliente y a cada evento publicado; métricas de latencia y error por endpoint, de éxito/falla
   de publicación y consumo de eventos, y de intentos de autenticación fallidos. Nunca se loguean
   credenciales, tokens ni API keys.

## Restricciones Técnicas

| Componente | Tecnología |
|---|---|
| API General | Java / Spring Boot |
| DB General | PostgreSQL (usuarios, catálogo, actividad) |
| DB Logs | Cassandra (eventos y trazas de alto volumen) |
| Mensajería (cliente) | RabbitMQ — broker hosteado por `notificaciones` |
| Contratos | OpenAPI (REST) + JSON Schema (eventos) |

DB General y DB Logs son bases separadas por diseño: usuarios/catálogo/actividad son datos
transaccionales y relacionales; eventos y trazas son append-heavy, de alto volumen y sin necesidad
de garantías transaccionales. No se fusionan ni se migra una a la otra sin discusión explícita de
arquitectura entre los cuatro equipos.

**Eventos publicados:** `recomendacion.actualizar` (worker de `recomendaciones`),
`reporte.generar` y `notificacion.enviar` (`notificaciones`).
**Eventos consumidos:** `reporte.listo` (`notificaciones`).
Un exchange/cola por tipo de evento. El broker en sí es infraestructura de `notificaciones`; este
repo actúa solo como cliente.

## Flujo de Desarrollo y Quality Gates

- Trabajo por PR con revisión; sin push directo a `main`. CI obligatorio (linters, unitarios,
  integración, contract tests); falla en CI bloquea el merge.
- Todo PR clasifica su cambio como interno / no-interno según el Principio IV y, si es
  no-interno, linkea la conformidad de los consumidores afectados.
- Todo cambio de esquema de DB General o DB Logs va con migración versionada y reversible.
- Gate de constitución: un PR que viole los Principios I, II, III o V se rechaza; no existe
  excepción temporal.

### Resumen ejecutable

- ¿Leer o escribir directo en la base de otro repo? → **no**: REST o evento.
- ¿Un frontend necesita algo de `recomendaciones` o `notificaciones`? → pasa por `api-general`.
- ¿Se toca un endpoint o evento que otro repo consume? → no es interno: se coordina antes de mergear.
- ¿Evento o endpoint nuevo cross-repo? → se documenta acá primero, se implementa después.
- ¿Cálculo pesado o trabajo de otro dominio? → se delega, no se hace en el request path.
- ¿Llamada interna entre repos? → API key interna del entorno, siempre.

## Governance

Esta constitución es la autoridad máxima dentro de `api-general` y prevalece sobre cualquier
práctica o preferencia individual. Queda subordinada a las reglas cross-repo de RecoMe: ante
conflicto, prevalece la regla cross-repo y el principio interno debe enmendarse. La custodia de
los contratos no otorga a este equipo poder unilateral sobre ellos (Principios II y IV).

Enmiendas: se proponen por PR sobre este archivo, con justificación, análisis de impacto y plan de
migración cuando corresponda. Requieren aprobación del equipo del repo; si afectan contratos,
auth servicio-a-servicio o supuestos de otro repo, requieren además conformidad previa de los
equipos impactados.

Versionado semántico de este documento:
- **MAJOR**: eliminación o redefinición incompatible de un principio o regla de gobernanza.
- **MINOR**: principio o sección nueva, o expansión material de requisitos.
- **PATCH**: aclaraciones y correcciones sin cambio de obligaciones.

Cumplimiento: cada revisión de PR verifica el alineamiento explícito con estos principios. Las
violaciones detectadas en producción se tratan como incidentes con remediación priorizada.

**Version**: 1.0.0 | **Ratified**: TODO(2026-9-7) | **Last Amended**: 2026-09-07
