# RecoMe · api-general Constitution# Constitution — `recome-api-general`



**Sistema:** RecoMe — hub de recomendaciones de películas y videojuegos.**Sistema:** RecoMe — hub de recomendaciones de películas y videojuegos

**Repo:** `api-general` (Java/Spring Boot) — API General, DB General (PostgreSQL: usuarios,**Repo:** `recome-api-general` (API General + DB General + DB Logs)

catálogo, actividad), DB Logs (Cassandra: eventos y trazas de alto volumen) y documentación de**Versión:** 1.0

contratos compartidos (OpenAPI + JSON Schema) del sistema completo.**Estado:** Vigente — cualquier propuesta de excepción a este documento requiere revisión explícita, no una decisión unilateral de este equipo.



> Este documento es la ley interna del repo. Ninguna decisión de diseño, por urgente o simple> Este documento es la ley interna de este repositorio. Ninguna decisión de diseño, por más

> que parezca, puede contradecirlo. Si la solución "más fácil" rompe un principio, la solución> simple o urgente que parezca, puede contradecir lo establecido acá. Si una solución "más

> está mal — no el principio.> fácil" implica romper uno de estos principios, la solución está mal — no el principio.



## Rol y Límites del Repo---



`api-general` es una de cuatro partes de RecoMe (junto a `recomendaciones`, `notificaciones` y## 0. Este repo no es un sistema aislado

`frontend`), cada una con equipo, base de datos y ciclo de deploy propios. Cumple tres roles no

negociables: **punto de entrada único** del sistema, **autoridad de identidad y autorización**`api-general` es **una de cuatro partes** de RecoMe. Los otros tres repos —

de usuarios finales, y **fuente única de verdad de los contratos compartidos**.`recomendaciones`, `notificaciones` y `frontend` — son mantenidos por otros equipos, con sus

propias bases de datos, sus propios ciclos de deploy y sus propias decisiones internas. Este

Lo que este repo **no** es: no calcula ni almacena perfiles de tags, vectores de similitud nirepo no tiene visibilidad ni control sobre lo que pasa *dentro* de esos repos, y ellos no

recomendaciones (eso es de `recomendaciones`); no hostea el broker de RabbitMQ ni eltienen visibilidad ni control sobre lo que pasa dentro de este.

almacenamiento de archivos/MinIO (eso es de `notificaciones`); no renderiza UI (eso es de

`frontend`).Todo lo que este repo necesita de otro repo se pide por un canal explícito y contractual

(REST u evento de RabbitMQ). Nunca por atajo.

## Core Principles

---

### I. Puerta de Entrada Única y Frontera de Datos (NO NEGOCIABLE)

## 1. Rol de este repo dentro de RecoMe

Frontend Usuario y Frontend Vendedor/Admin hablan **solo** con `api-general`. Ningún endpoint de

`recomendaciones` o `notificaciones` se expone, proxea de forma transparente ni publica hacia los`api-general` cumple tres roles no negociables en el sistema:

frontends, ni siquiera "temporalmente", "solo para un dashboard interno" o por presión de

deadline. Simétricamente, `api-general` es dueño exclusivo de DB General y DB Logs: ningún otro1. **Punto de entrada único del sistema.** Frontend Usuario y Frontend Vendedor/Admin (repo

repo se conecta a ellas, y este repo nunca abre conexión directa a la DB de `recomendaciones`   `frontend`) **solo** hablan con `api-general`. Ningún otro repo interno (`recomendaciones`,

(PostgreSQL+pgvector) ni a la DB Archivos (MinIO) de `notificaciones`. Todo dato ajeno se obtiene   `notificaciones`) es alcanzable directamente desde un frontend. Si un frontend necesita datos

por HTTP REST contra el repo dueño o por evento de RabbitMQ. Las migraciones y el esquema interno   de recomendaciones o necesita disparar una notificación o un reporte, la petición pasa por

de DB General y DB Logs son responsabilidad exclusiva de este repo y evolucionan libremente   `api-general`, que orquesta hacia el repo correspondiente.

mientras no rompan los contratos publicados; ningún repo externo puede asumir esa estructura más2. **Autenticación y autorización centralizada.** Este repo es el dueño de la identidad de

allá de lo que el contrato REST expone, y este repo no asume la estructura interna de bases   usuario y de las reglas de autorización del sistema. Ningún otro repo reimplementa o

ajenas.   duplica esta lógica.

3. **Fuente única de verdad de los contratos compartidos.** Este repo aloja y versiona:

### II. Custodia de los Contratos Compartidos (NO NEGOCIABLE)   - Las specs **OpenAPI** de todos los endpoints internos consumidos entre repos.

   - Los **JSON Schema** de todos los eventos de RabbitMQ del sistema.

Este repo aloja y versiona las specs **OpenAPI** de todos los endpoints internos consumidos entre

repos y los **JSON Schema** de todos los eventos de RabbitMQ del sistema — incluso de contratos   Esto aplica incluso para contratos cuya implementación *runtime* no vive acá (por ejemplo,

cuya implementación runtime no vive acá (el broker lo hostea `notificaciones`, pero el schema del   el broker de RabbitMQ lo hostea `notificaciones`, pero el schema del evento se documenta

evento se documenta acá) y de eventos que este repo ni publica ni consume. **Si un contrato no   acá). Si un contrato no está documentado en este repo, no es un contrato válido del sistema.

está documentado en este repo, no es un contrato válido del sistema.** Custodia no es propiedad:

`api-general` es el registro y el guardián del proceso, no el dueño unilateral del contenido.### Lo que este repo NO es

Ningún cambio de contrato puede mergearse acá por decisión exclusiva de este equipo, aunque este

repo sea quien publica el evento. Nombres de eventos y convenciones de API se definen una sola- No es el dueño de los datos de perfiles de tags, vectores de similitud ni del cálculo de

vez, acá, **antes** de implementarse en cualquier repo: nunca se implementa primero "para probar"  recomendaciones — eso vive y se calcula en `recomendaciones`.

y se documenta después.- No es el dueño de la infraestructura de mensajería (broker, definición base de

  exchanges/colas) — eso lo hostea `notificaciones`, aunque los *contratos* de los eventos que

### III. Versionado de Contratos y Compatibilidad Backwards (NO NEGOCIABLE)  viajan por ahí se documenten acá.

- No renderiza ni sirve UI — eso es responsabilidad de `frontend`.

Todo endpoint expuesto a otro repo tiene spec OpenAPI versionada. Los cambios **aditivos y- No genera ni almacena archivos exportables (reportes, adjuntos) — eso vive en `notificaciones`

compatibles** (campo opcional nuevo, endpoint nuevo, valor de enum nuevo tolerado por los  (DB Archivos en MinIO + webserver Nginx).

consumidores) pueden publicarse sobre la versión vigente. Todo cambio **breaking** (eliminar o

renombrar un campo, volver requerido un campo opcional, cambiar tipo o semántica, endurecer---

validaciones, cambiar códigos de estado o la forma de error) exige una **versión nueva y

explícita** del endpoint o del schema de evento: la versión anterior no se pisa ni se elimina sin## 2. Principios no negociables (heredados del sistema, no reabribles acá)

un **período de coexistencia acordado** con todos los consumidores conocidos, con fecha de

deprecación comunicada por escrito. Los schemas de evento evolucionan preferentemente de formaEstos principios gobiernan a los cuatro repos por igual. Este repo los implementa; no los

aditiva; un cambio incompatible implica un nombre/versión de evento nuevo y migración coordinadareinterpreta ni los relaja bajo ninguna circunstancia, incluyendo presión de deadline,

de publicadores y consumidores, nunca una mutación in-place del schema vigente. Todo contrato"total, es solo para una feature interna", o cualquier argumento de simplicidad.

publicado declara su versión y su estado (vigente / deprecado / retirado).

1. **Cero acceso directo a base de datos ajena.** `api-general` nunca se conecta directamente

### IV. Proceso y Autoridad de Aprobación de un Cambio de Contrato   a la DB de `recomendaciones` (PostgreSQL+pgvector) ni a la DB Archivos de `notificaciones`

   (MinIO), ni ningún otro repo se conecta directo a DB General o DB Logs. Toda esa

Un cambio de contrato compartido solo se mergea cuando se cumplen, **en este orden**:   comunicación es HTTP REST o evento de RabbitMQ.

1. Se actualiza la documentación del contrato (OpenAPI o JSON Schema) en este repo, incluyendo2. **`api-general` es la única puerta de entrada para los frontends.** No se expone ningún

   versión, motivo del cambio y clasificación compatible/breaking.   endpoint de `recomendaciones` o `notificaciones` directamente a `frontend`, ni siquiera

2. Se notifica explícitamente a **todos** los repos publicadores y consumidores afectados.   "temporalmente" o "solo para un dashboard interno".

3. Se obtiene **conformidad escrita de cada equipo consumidor afectado** antes de mergear, no3. **Los contratos de eventos son compartidos, no propiedad de quien los publica o consume.**

   después. El equipo de `api-general` aprueba la forma, la consistencia y el versionado del   `api-general` puede publicar (`recomendacion.actualizar`, `reporte.generar`,

   contrato, pero **no puede aprobar en nombre de un consumidor**: un breaking change sin   `notificacion.enviar`) y consumir (`reporte.listo`) eventos, pero ningún cambio a un schema

   conformidad de los consumidores queda bloqueado, sin excepción por urgencia.   de evento es una decisión unilateral de este equipo, aunque este repo sea quien lo publica.

4. Si es breaking, se acuerda período de coexistencia y plan de migración antes del merge.4. **Todo contrato REST expuesto a otro repo se documenta con OpenAPI en este repo**, y se

   versiona explícitamente si el cambio rompe compatibilidad. No se modifica de forma breaking

Clasificación obligatoria: un cambio es **interno** solo si no toca ningún endpoint documentado,   un endpoint consumido por otro repo sin coordinación previa.

ningún schema de evento, ni el comportamiento observable de un contrato publicado, ni las reglas5. **Autenticación servicio-a-servicio separada de la autenticación de usuario final.** Las

de autenticación servicio-a-servicio. Cualquier otra cosa **no es interna** y sigue el proceso de   llamadas internas que otros repos hacen contra `api-general` (p. ej. Data Transformer o

arriba. **Ante la duda, se trata como no-interno**: coordinar de más es más barato que romper un   Analytics) usan API key interna por entorno. Ningún endpoint interno queda expuesto sin

contrato en producción.   este control, incluso si "no tiene datos sensibles".

6. **Cada repo es dueño exclusivo de su propio esquema de datos.** Ningún otro repo puede

### V. Gobernanza de Autenticación y Autorización (NO NEGOCIABLE)   asumir la estructura interna de DB General o DB Logs más allá de lo que expone el contrato

   REST. Simétricamente, este repo no asume estructura interna de las bases de los otros repos.

Este repo es la única autoridad de identidad de usuario final y de las reglas de autorización del7. **Nombres de eventos y convenciones de API se definen una sola vez, acá, antes de

sistema; ningún otro repo reimplementa, duplica ni "cachea" esa lógica, y ningún repo confía en   implementarse en cualquier lado.** Si este equipo necesita un evento o endpoint nuevo que

un claim de usuario que no haya sido validado acá. Existen **dos planos de autenticación   afecta a otro repo, primero se define en la documentación de contratos de este repo y se

estrictamente separados**:   coordina con los equipos afectados — no se implementa primero "para probar" y se documenta

- **Usuario final** → credenciales/tokens emitidos y validados por `api-general`, con expiración,   después.

  rotación y revocación gestionadas acá. Autorización por roles/permisos evaluada en este repo

  antes de orquestar hacia otros servicios.Cualquier decisión de diseño interna a este repo que entre en conflicto con estos siete puntos

- **Servicio-a-servicio** → **API key interna por entorno**, distinta por ambiente y distinta de**no es una decisión válida**, sin importar cuánto simplifique el desarrollo a corto plazo.

  cualquier credencial de usuario. Toda llamada interna entrante (p. ej. Data Transformer de

  `recomendaciones`, Analytics de `frontend`) la exige, y toda llamada interna saliente la---

  presenta. **Ningún endpoint interno queda expuesto sin este control**, incluso si "no tiene

  datos sensibles".## 3. Stack tecnológico de este repo



Un token de usuario final nunca se reutiliza como credencial de servicio, ni viceversa. LosDecidido a nivel de sistema; no se reabre salvo justificación técnica fuerte y coordinación

secretos viven en configuración por entorno, nunca versionados ni logueados. Cambiar las reglas deexplícita con los otros tres equipos (un cambio acá puede tener impacto en cómo los demás

autenticación servicio-a-servicio es, por definición, un cambio de contrato (Principio IV).repos consumen este servicio).



### VI. Orquestación con Delegación Estricta| Componente | Tecnología |

|---|---|

`api-general` **orquesta**: autentica, autoriza, valida entrada, resuelve datos propios (usuarios,| API General | Java / Spring Boot |

catálogo, actividad), invoca a los servicios dueños de cada capacidad, compone la respuesta y| DB General | PostgreSQL (usuarios, catálogo, actividad) |

registra la traza. `api-general` **no ejecuta trabajo ajeno ni pesado**:| DB Logs | Cassandra (eventos y trazas de alto volumen) |

- Cálculo de scoring, similitud, perfiles de tags o diversificación → **delegado** a| Mensajería (cliente) | Cliente RabbitMQ compatible (broker hosteado por `notificaciones`) |

  `recomendaciones` (lectura vía REST de resultados precomputados; recálculo vía el evento| Documentación de contratos | OpenAPI (REST) + JSON Schema (eventos) |

  `recomendacion.actualizar`). Nunca se replica el motor acá.

- Envío de mails/push, generación y almacenamiento de reportes o archivos → **delegado** a**Por qué DB General es PostgreSQL y DB Logs es Cassandra**, y por qué son bases separadas:

  `notificaciones` vía eventos (`notificacion.enviar`, `reporte.generar`).usuarios/catálogo/actividad son datos transaccionales y relacionales; eventos y trazas son de

- Presentación y agregación analítica de cara al usuario → **delegado** a `frontend`/Analytics,alto volumen, append-heavy y no requieren las garantías transaccionales de Postgres. No se

  que consumen datos por REST de este repo.migra una a la otra, ni se fusionan, sin discusión explícita de arquitectura.



Ningún endpoint de cara al usuario dispara trabajo pesado o de larga duración de forma síncrona:---

se publica un evento y se responde con estado. Toda llamada saliente lleva timeout explícito,

manejo de fallo y degradación controlada — nunca resuelta accediendo a datos ajenos por otra vía.## 4. Comunicación saliente y entrante de este repo

Orquestar no habilita a asumir la estructura interna del servicio invocado más allá de su contrato.

### 4.1 REST — expuesto por este repo

### VII. Testing, Contract Testing y Observabilidad

- Todo endpoint que otro repo (`recomendaciones`, `notificaciones`, `frontend`/Analytics)

La principal superficie de riesgo de este repo es romper contratos de los que dependen otros tres  consuma de acá debe tener spec OpenAPI versionada en este repo.

equipos. Obligatorio antes de cualquier release:- Cambios breaking requieren nueva versión de endpoint (no se pisa la anterior sin período de

1. **Unitarios** de la lógica propia: autenticación, autorización, orquestación y reglas de  coexistencia coordinado con los consumidores conocidos).

   catálogo/actividad.- Todo acceso interno (no de usuario final) requiere la API key interna del entorno

2. **Integración contra DB General y DB Logs reales** (Postgres/Cassandra efímeros, no mockeados)  correspondiente.

   para validar migraciones y queries.

3. **Contract testing de todo endpoint expuesto** contra su spec OpenAPI publicada acá: cualquier### 4.2 REST — consumido por este repo

   divergencia entre implementación y spec es un bug bloqueante de release.

4. **Validación de schema de cada evento publicado** contra su JSON Schema, previa a la- Si `api-general` necesita datos o funcionalidad de `recomendaciones` o `notificaciones`,

   publicación en RabbitMQ.  lo hace exclusivamente contra los endpoints REST que esos repos expongan y documenten

5. **Validación de eventos consumidos**: ante payload que no matchea el schema, el consumidor  (documentación linkeada o replicada en este repo), nunca contra su base de datos.

   falla de forma explícita y detectable (nunca silenciosa), con dead-letter y alerta — es la- Cualquier suposición sobre la estructura interna de esos servicios más allá de lo que su

   señal temprana de que otro repo rompió un contrato.  contrato expone es una violación de este documento.

6. **Regresión de compatibilidad** al versionar: la versión anterior sigue funcionando durante

   todo el período de coexistencia acordado.### 4.3 RabbitMQ — eventos publicados por este repo

7. **Observabilidad**: logging estructurado con `correlation_id` propagado a cada llamada

   saliente y a cada evento publicado; métricas de latencia y error por endpoint, de éxito/falla| Evento | Consumidor | Notas |

   de publicación y consumo de eventos, y de intentos de autenticación fallidos. Nunca se loguean|---|---|---|

   credenciales, tokens ni API keys.| `recomendacion.actualizar` | Worker de `recomendaciones` | Dispara recálculo asíncrono; el cálculo pesado nunca ocurre en este repo ni en tiempo de request. |

| `reporte.generar` | Módulo de Reportes Exportables (`notificaciones`) | |

## Restricciones Técnicas| `notificacion.enviar` | Módulo de Notificaciones Push/Mail (`notificaciones`) | También puede ser publicado por otros módulos, no solo por este repo. |



| Componente | Tecnología |### 4.4 RabbitMQ — eventos consumidos por este repo

|---|---|

| API General | Java / Spring Boot || Evento | Publicador | Notas |

| DB General | PostgreSQL (usuarios, catálogo, actividad) ||---|---|---|

| DB Logs | Cassandra (eventos y trazas de alto volumen) || `reporte.listo` | Módulo de Reportes Exportables (`notificaciones`) | Este repo reacciona (p. ej. actualiza estado, notifica al usuario final vía sus propios canales) sin asumir estructura interna del módulo de reportes. |

| Mensajería (cliente) | RabbitMQ — broker hosteado por `notificaciones` |

| Contratos | OpenAPI (REST) + JSON Schema (eventos) |### 4.5 Reglas de contrato de eventos



DB General y DB Logs son bases separadas por diseño: usuarios/catálogo/actividad son datos- El **schema** (JSON Schema) de cada evento de la tabla anterior vive documentado en este

transaccionales y relacionales; eventos y trazas son append-heavy, de alto volumen y sin necesidad  repo, sin importar quién lo publica o consume.

de garantías transaccionales. No se fusionan ni se migra una a la otra sin discusión explícita de- Este repo puede publicar/consumir estos eventos, pero **no puede cambiar su schema

arquitectura entre los cuatro equipos.  unilateralmente**. Todo cambio de contrato de evento requiere:

  1. Actualizar la documentación del contrato en este repo.

**Eventos publicados:** `recomendacion.actualizar` (worker de `recomendaciones`),  2. Avisar explícitamente a todos los repos publicadores/consumidores del evento afectado.

`reporte.generar` y `notificacion.enviar` (`notificaciones`).  3. Obtener conformidad de esos equipos antes de mergear el cambio — no después.

**Eventos consumidos:** `reporte.listo` (`notificaciones`).- El broker en sí (deploy, exchanges/colas base) es infraestructura de `notificaciones`. Este

Un exchange/cola por tipo de evento. El broker en sí es infraestructura de `notificaciones`; este  repo no administra esa infraestructura, solo publica/consume contra ella como cliente.

repo actúa solo como cliente.

---

## Flujo de Desarrollo y Quality Gates

## 5. Qué se considera "cambio interno" y qué no

- Trabajo por PR con revisión; sin push directo a `main`. CI obligatorio (linters, unitarios,

  integración, contract tests); falla en CI bloquea el merge.Un cambio es **interno** (no requiere coordinación externa) si:

- Todo PR clasifica su cambio como interno / no-interno según el Principio IV y, si es- Solo afecta lógica, código o esquema de datos que ningún otro repo consume directa o

  no-interno, linkea la conformidad de los consumidores afectados.  indirectamente vía contrato.

- Todo cambio de esquema de DB General o DB Logs va con migración versionada y reversible.- No modifica ningún endpoint documentado en OpenAPI ni ningún schema de evento.

- Gate de constitución: un PR que viole los Principios I, II, III o V se rechaza; no existe- No cambia el comportamiento observable de un contrato ya publicado (aunque la

  excepción temporal.  implementación interna cambie).



### Resumen ejecutableUn cambio **no es interno**, y requiere coordinación explícita fuera de este repo, si:

- Modifica el request/response de un endpoint consumido por `recomendaciones`,

- ¿Leer o escribir directo en la base de otro repo? → **no**: REST o evento.  `notificaciones`, `frontend` o Analytics.

- ¿Un frontend necesita algo de `recomendaciones` o `notificaciones`? → pasa por `api-general`.- Modifica el schema, el nombre, o la semántica de cualquiera de los eventos listados en la

- ¿Se toca un endpoint o evento que otro repo consume? → no es interno: se coordina antes de mergear.  sección 4.

- ¿Evento o endpoint nuevo cross-repo? → se documenta acá primero, se implementa después.- Introduce un endpoint o evento nuevo que otro repo va a necesitar consumir.

- ¿Cálculo pesado o trabajo de otro dominio? → se delega, no se hace en el request path.- Cambia las reglas de autenticación servicio-a-servicio (API key interna).

- ¿Llamada interna entre repos? → API key interna del entorno, siempre.

Ante la duda, se trata como cambio no-interno. Es más barato coordinar de más que romper un

## Governancecontrato en producción.



Esta constitución es la autoridad máxima dentro de `api-general` y prevalece sobre cualquier---

práctica o preferencia individual. Queda subordinada a las reglas cross-repo de RecoMe: ante

conflicto, prevalece la regla cross-repo y el principio interno debe enmendarse. La custodia de## 6. Testing mínimo requerido

los contratos no otorga a este equipo poder unilateral sobre ellos (Principios II y IV).

Este repo no puede validar su corrección solo con tests unitarios internos, porque su

Enmiendas: se proponen por PR sobre este archivo, con justificación, análisis de impacto y plan desuperficie de riesgo principal es romper contratos que otros tres equipos dependen de leer.

migración cuando corresponda. Requieren aprobación del equipo del repo; si afectan contratos,

auth servicio-a-servicio o supuestos de otro repo, requieren además conformidad previa de los**Obligatorio antes de cualquier release:**

equipos impactados.

1. **Tests unitarios** de la lógica de negocio propia (auth, orquestación, reglas de

Versionado semántico de este documento:   catálogo/actividad).

- **MAJOR**: eliminación o redefinición incompatible de un principio o regla de gobernanza.2. **Tests de integración contra DB General y DB Logs** reales (o equivalentes de test:

- **MINOR**: principio o sección nueva, o expansión material de requisitos.   Postgres/Cassandra efímeros), no mockeadas, para validar migraciones y queries.

- **PATCH**: aclaraciones y correcciones sin cambio de obligaciones.3. **Contract testing de todo endpoint expuesto** contra su spec OpenAPI documentada en este

   repo — cualquier divergencia entre la implementación y la spec publicada es un bug de

Cumplimiento: cada revisión de PR verifica el alineamiento explícito con estos principios. Las   release, no un detalle menor.

violaciones detectadas en producción se tratan como incidentes con remediación priorizada.4. **Contract testing / validación de schema de cada evento publicado** (`recomendacion.actualizar`,

   `reporte.generar`, `notificacion.enviar`) contra el JSON Schema documentado, antes de

**Version**: 1.0.0 | **Ratified**: TODO(2026-9-7) | **Last Amended**: 2026-09-07   publicarlo a RabbitMQ.

5. **Validación de eventos consumidos** (`reporte.listo`): el consumidor debe fallar de forma
   explícita y detectable (no silenciosa) si el payload recibido no matchea el schema
   esperado — señal temprana de que otro repo rompió el contrato sin avisar.
6. **Tests de regresión de compatibilidad** al versionar un endpoint: la versión anterior
   sigue funcionando durante el período de coexistencia acordado con los consumidores.

Ningún release que rompa un contrato documentado (endpoint u evento) se mergea sin que el
punto 5 de la sección 4 (coordinación con los equipos afectados) esté cerrado.

---

## 7. Resumen ejecutable

- Si la solución implica leer o escribir directo en la base de otro repo → **no**, usar REST o evento.
- Si un frontend necesita algo de `recomendaciones` o `notificaciones` → pasa por `api-general`, nunca directo.
- Si se toca un endpoint u evento que otro repo consume → no es "interno", se coordina antes de mergear.
- Si se agrega un evento o endpoint nuevo cross-repo → se documenta acá primero, se implementa después.
- Si el cálculo es pesado → no vive en este repo en tiempo de request; se delega vía evento al worker correspondiente.
- Todo acceso interno entre repos → autenticado con API key de servicio, nunca abierto.
