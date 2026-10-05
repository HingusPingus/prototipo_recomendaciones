<!--
Sync Impact Report
- Version change: 1.1.1 → 1.2.0 (MINOR: excepción acotada de lectura en el Principio III y nombre del
  evento consumido; ningún principio se elimina ni se redefine de forma incompatible).
- Modified principles:
  - III. Cómputo Pesado Fuera del Request Path — se agrega la única excepción de lectura fuera de
    Redis: la consulta de la constancia de recepción de una baja por su identificador de evento
    (FR-095c de la feature 001), una fila por clave y sin datos del usuario. La de escritura no cambia.
  - Alcance, I, II, III y VI: el evento consumido se nombra `recomendacion.actualizar.v3`, el contrato
    que publica api-general (RD-116 de la feature 001). Sin cambio de obligaciones: es el mismo evento
    de actualización, en su versión vigente.
- Added sections: ninguna. Removed sections: ninguna.
- Templates: plan-template.md, spec-template.md y tasks-template.md no citan estos principios por
  texto; sin cambios necesarios.
- Follow-up TODOs: ninguno.
- Motivo: api-general implementó el checkpoint de entrega del evento de baja (su commit 9137825), que
  consulta la recepción en este repositorio; responder exige leer Postgres desde la API (RD-115, RD-117).

Historial previo — 1.1.0 → 1.1.1 (PATCH: aclaración de redacción, sin cambio de obligaciones).
- Modified principles:
  - III. Cómputo Pesado Fuera del Request Path — «todo recálculo ocurre exclusivamente en el worker
    asíncrono disparado por `recomendacion.actualizar`» se leía como si ese evento fuera el único
    disparador, lo que contradecía la señalización ante miss que el mismo principio exige y la
    coordinación interna que Restricciones Técnicas ya admitía. La frase ahora nombra ambos
    disparadores. La obligación sustantiva —el recálculo ocurre solo en el worker— no cambia.
- Restricciones Técnicas: el ejemplo de coordinación interna se completa con los emisores reales
  (API ante miss o declaración; procesos batch que invalidan antes de emitir) y se explicita por qué
  todos cumplen la condición de autorreparación.
- Templates: sin cambios necesarios (no citan este texto).
- Follow-up TODOs: ninguno.
- Motivo: hallazgo CA1 de /speckit-analyze (2026-09-28).

Historial previo — 1.0.0 → 1.1.0 (MINOR: excepción acotada al Principio III y aclaración en
  Restricciones Técnicas; ningún principio se elimina ni se redefine de forma incompatible).
- Modified principles:
  - III. Cómputo Pesado Fuera del Request Path — se agrega la única excepción de escritura: el
    registro de la declaración de gustos (FR-089 de la feature 001), sin cómputo.
- Added sections: ninguna. Restricciones Técnicas y de Seguridad suma una aclaración sobre la
  coordinación interna entre procesos del repo.
- Removed sections: ninguna.
- Templates: plan-template.md, spec-template.md y tasks-template.md no referencian estos
  principios por texto; sin cambios necesarios.
- Follow-up TODOs: ninguno. RATIFICATION_DATE se fija en 2026-09-07, fecha del commit 1826b12
  («ratificar recomendaciones constitución v1.0.0»); era TODO(2026-09-07). La corrección viaja dentro
  de esa misma enmienda en lugar de abrir un PATCH aparte.
- Motivo: la spec de la feature 001 declaraba una excepción de escritura que la constitución no
  admitía (tensión detectada en el saneamiento del 2026-09-27).
-->

# RecoMe · Recomendaciones Constitution

Repositorio: `recomendaciones` (GitHub: `prototipo_recomendaciones`).
Alcance: API Recomendaciones (Python/FastAPI), DB Recomendaciones (PostgreSQL + pgvector),
caché Redis, Data Transformer (Python/pandas) y worker asíncrono consumidor de
`recomendacion.actualizar.v3`. Este documento gobierna solo este repo y queda siempre subordinado
a las reglas cross-repo del sistema RecoMe.

## Core Principles

### I. Frontera de Datos y Ownership Exclusivo (NO NEGOCIABLE)

Este repo es dueño exclusivo de la DB Recomendaciones (PostgreSQL + pgvector) y de la caché
Redis: ningún otro repo del sistema puede conectarse a ellas de forma directa, ni en lectura ni
en escritura, bajo ninguna justificación de performance, urgencia o simplicidad. Cualquier dato
que otro repo necesite de acá se expone únicamente vía REST documentado o vía eventos de
RabbitMQ. Simétricamente, `recomendaciones` NUNCA abre conexión directa a la DB General
(PostgreSQL) ni a la DB Logs (Cassandra) de api-general: todo acceso a datos ajenos ocurre por
REST contra api-general o por el evento `recomendacion.actualizar.v3`. Las migraciones y el
esquema de la DB Recomendaciones son responsabilidad exclusiva de este repo y pueden evolucionar
libremente mientras no rompan los contratos publicados; ningún repo externo puede asumir esa
estructura interna. Este repo tampoco es accesible directamente desde Frontend Usuario ni
Frontend Vendedor/Admin: api-general es la única puerta de entrada del sistema, y la topología
de red debe hacer cumplir esa restricción.

### II. Contratos Compartidos como Fuente Externa de Verdad (NO NEGOCIABLE)

El JSON Schema del evento `recomendacion.actualizar.v3` y el OpenAPI de todo endpoint que este
repo expone hacia api-general o consume de él viven documentados en api-general, que es la
fuente única de verdad. Este repo mantiene copias solo como artefactos derivados de
verificación, nunca como definición autoritativa. Cambiar el nombre, la forma, la semántica o
la versión de un contrato compartido NO es un "cambio interno": requiere (a) actualizar la
documentación de contratos en api-general, (b) avisar y coordinar con todos los repos
publicadores/consumidores afectados, y (c) versionar explícitamente el endpoint si el cambio
rompe compatibilidad — todo ANTES de mergear acá. Ningún principio, excepción o hotfix habilita
redefinir unilateralmente un evento o endpoint compartido desde este repo. Si `recomendaciones`
necesita un evento o endpoint nuevo que afecte a otro repo, se define primero en la
documentación de api-general y recién después se implementa. Las convenciones de nombres de
eventos y de API son del sistema, no del repo.

### III. Cómputo Pesado Fuera del Request Path (NO NEGOCIABLE)

La API de Recomendaciones es estrictamente de solo lectura sobre resultados precomputados —con las
dos excepciones acotadas que cierran este principio, una de escritura y una de lectura—: en
tiempo de request lee el top-N por usuario y por módulo (películas/juegos) desde Redis y nada
más. Ningún endpoint puede disparar —ni sincrónicamente, ni "en background del request"— cálculo
de scoring híbrido, TF-IDF, similitud coseno, vecinos colaborativos, cross-module boost ni
diversificación MMR. Todo recálculo ocurre exclusivamente en el worker asíncrono —disparado por
`recomendacion.actualizar.v3` o por las solicitudes internas de recálculo que admiten las Restricciones
Técnicas—, que deja el resultado ya post-procesado en Redis. Un miss de caché
se responde de forma degradada y determinística (fallback documentado sobre datos ya
materializados, respuesta vacía o error controlado) y, si corresponde, señaliza el recálculo por
vía asíncrona: jamás se resuelve calculando en línea. Objetivo explícito: latencia constante e
independiente del tamaño del catálogo.

**Única excepción de escritura (desde v1.1.0)**: la API expone un endpoint para registrar la
declaración de gustos del usuario por módulo, el único dato cuya autoridad nace en este repositorio
y que ningún otro componente puede escribir. Esa escritura MUST limitarse a validar la declaración,
resolver lo que se hereda entre módulos y persistirla, con confirmación síncrona; MUST NOT ejecutar
el motor ni ningún cómputo proporcional al catálogo, y MUST delegar el recálculo a la vía
asíncrona. La excepción no se extiende por analogía: cualquier otra escritura, o un segundo dato de
autoría local, exige un componente propio o una nueva enmienda.

**Única excepción de lectura fuera de Redis (desde v1.2.0)**: la API expone una consulta de la
constancia de recepción de un evento de baja de cuenta, por el identificador de ese evento, para que
api-general verifique que la baja llegó a este repositorio (checkpoint de entrega acordado entre
repos). Esa consulta MUST leer como máximo una fila por clave de las constancias de supresión, sin
cómputo ni lectura proporcional a ningún volumen; MUST NOT devolver datos del usuario; y no depende
de Redis. Como la de escritura, esta excepción no se extiende por analogía: cualquier otra lectura
fuera de Redis exige una nueva enmienda.

### IV. Pipeline de Sincronización Unidireccional

El Data Transformer solo lee de api-general vía REST, autenticado con la API key interna de
servicio del entorno correspondiente (distinta de la autenticación de usuarios finales), y
escribe únicamente en la DB Recomendaciones. Está prohibido que escriba en la DB General, en la
DB Logs o en cualquier almacenamiento de otro repo, y está prohibido que invoque endpoints de
api-general que muten estado de usuario o catálogo. Los datos de usuario, catálogo y actividad
replicados acá son una proyección derivada y desechable: la autoridad es siempre de api-general
y, ante discrepancia, gana api-general y se re-sincroniza. La sincronización debe ser
idempotente y re-ejecutable sin corromper el estado. Ningún componente interno queda expuesto
sin el control de API key interna, y las credenciales se gestionan por entorno, nunca
hardcodeadas ni versionadas.

### V. Gobernanza del Motor Híbrido de Recomendación

Los pesos alpha/beta/gamma de la combinación lineal (content-based, colaborativo, cross-module
boost), el algoritmo de scoring y las reglas de post-procesamiento obligatorio —filtro de edad
por `age_rating`, filtro de exclusión de ítems vistos/jugados/dislikeados y diversificación
MMR— son configuración gobernada, no constantes sueltas en el código. Todo cambio requiere:
(a) valores parametrizados y versionados fuera de la lógica, (b) justificación escrita, (c)
evaluación offline reproducible (dataset o fixture fijo, semilla fija, métricas comparadas
contra la configuración vigente) adjunta al PR, y (d) aprobación explícita antes del deploy a
producción. El filtro de edad y el filtro de exclusión son invariantes de seguridad y
corrección: no pueden desactivarse, saltearse ni volverse opcionales por performance, y MMR no
puede reintroducir ítems previamente filtrados. Todo top-N publicado en Redis debe ser
atribuible a una versión identificable de la configuración del motor.

### VI. Testing Obligatorio y Contract Testing (NO NEGOCIABLE)

Mínimos exigidos para mergear:
- **Unitarios de scoring**: cobertura de TF-IDF/similitud coseno, agregación de los k vecinos
  colaborativos, cross-module boost, combinación alpha/beta/gamma y cada regla de
  post-procesamiento (edad, exclusión, MMR), incluyendo casos borde: perfil vacío, cold start,
  cold start cruzado, empates de score y catálogo sin candidatos válidos. Deterministas, sin
  red ni dependencias externas.
- **Integración del worker**: consumo real de `recomendacion.actualizar.v3` contra un broker de
  prueba, verificando idempotencia ante duplicados, manejo de mensajes inválidos,
  reintentos/dead-letter y escritura correcta del top-N precomputado en Redis.
- **Integración del Data Transformer**: sincronización contra un doble de api-general,
  verificando autenticación por API key interna, idempotencia y ausencia total de escrituras
  hacia recursos ajenos.
- **Contract testing**: validación automatizada de los payloads consumidos/publicados contra el
  JSON Schema de `recomendacion.actualizar.v3`, y de requests/responses contra los OpenAPI
  documentados en api-general. Corre en CI y su falla bloquea el deploy: una ruptura de
  compatibilidad debe detectarse acá, nunca en producción.
- **API**: tests que verifiquen que ningún endpoint ejecuta cómputo pesado ni accede a fuentes
  de datos ajenas (Principios I y III).

### VII. Observabilidad y Resiliencia Asíncrona

Worker y Data Transformer son procesos desacoplados sin respuesta síncrona al usuario, por lo
que su estado debe ser observable sin inspección manual. Requisitos mínimos:
- **Logging estructurado** (JSON) con nivel, timestamp, `correlation_id`/`event_id`, `user_id`
  cuando aplique, versión de configuración del motor y resultado (éxito/falla con causa). Sin
  datos sensibles ni credenciales en logs.
- **Métricas del worker**: recálculos exitosos y fallidos, latencia de recomputo (p50/p95),
  profundidad de cola y mensajes derivados a dead-letter.
- **Métricas del Data Transformer**: éxito/falla por corrida, duración, volumen sincronizado y
  antigüedad (freshness) de la última sincronización exitosa.
- **Métricas de la API**: latencia por endpoint, hit/miss ratio de Redis y tasa de respuestas
  degradadas por miss.
- **Resiliencia**: reintentos con backoff y dead-letter para eventos fallidos, timeouts
  explícitos en toda llamada REST a api-general, y degradación controlada ante indisponibilidad
  de api-general o del broker — nunca resuelta accediendo a datos ajenos por otra vía.
- **Health checks** para API, worker y Data Transformer, con alertas ante falla sostenida de
  recálculo o de sincronización.

## Restricciones Técnicas y de Seguridad

- Stack fijo: API en Python/FastAPI, persistencia en PostgreSQL + pgvector, caché en Redis,
  transformación en Python/pandas, mensajería vía RabbitMQ (broker hosteado por el repo
  `notificaciones`, contratos documentados en api-general).
- Un exchange/cola por tipo de evento; el worker no consume eventos ajenos a su responsabilidad.
- Todo evento que cruce la frontera del repo viaja por RabbitMQ y tiene contrato en api-general. La
  coordinación **interna** entre procesos de este repo —las solicitudes de recálculo que la API
  emite ante un miss o una declaración, y las que emiten los procesos batch del repo tras invalidar la
  entrada afectada— puede apoyarse en Redis, siempre que sean indicaciones reconstruibles cuya
  pérdida se recupere sola (un miss posterior vuelve a emitirlas): no es mensajería entre repos ni
  convierte a Redis en fuente de verdad.
- Toda llamada REST saliente hacia api-general usa la API key interna del entorno; la
  autenticación/autorización de usuarios finales es responsabilidad de api-general y no se
  reimplementa acá.
- La API de Recomendaciones no se publica a internet ni a los frontends: su superficie de red es
  alcanzable únicamente por api-general y componentes internos autorizados.
- Redis es caché, no fuente de verdad: su pérdida total debe ser recuperable mediante recálculo
  asíncrono, sin pérdida de datos autoritativos.
- Configuración y secretos por variables de entorno, distintos por entorno, nunca versionados.

## Flujo de Desarrollo y Quality Gates

- Trabajo por PR con revisión; sin push directo a `main`.
- CI obligatorio: linters, tests unitarios, tests de integración y contract tests. Falla en CI
  bloquea el merge.
- Gate de constitución: todo PR declara qué principios toca y justifica cualquier complejidad
  añadida. Un PR que viole los Principios I, II, III o VI se rechaza; no existe excepción
  temporal.
- Todo PR que toque un contrato compartido debe linkear el PR/documento correspondiente en
  api-general, ya coordinado con los repos afectados.
- Todo PR que toque el motor híbrido adjunta justificación y resultados de la evaluación offline
  reproducible (Principio V).
- Cambios de esquema de la DB Recomendaciones van siempre con migración versionada y reversible.

## Governance

Esta constitución es la autoridad máxima dentro del repo `recomendaciones` y prevalece sobre
cualquier práctica, convención o preferencia individual. A su vez, queda subordinada a las
reglas cross-repo de RecoMe: ante conflicto entre un principio interno y una regla cross-repo
(ownership de datos, api-general como única puerta de entrada, contratos compartidos
documentados en api-general, API key interna de servicio), prevalece la regla cross-repo y el
principio interno debe enmendarse.

Enmiendas: se proponen por PR sobre este archivo, con justificación, análisis de impacto sobre
plantillas y flujos dependientes, y plan de migración cuando corresponda. Requieren aprobación
del equipo del repo; si afectan contratos o supuestos de otro repo, requieren además
coordinación previa con api-general y con los repos impactados.

Versionado semántico de este documento:
- **MAJOR**: eliminación o redefinición incompatible de un principio o de una regla de
  gobernanza.
- **MINOR**: incorporación de un principio o sección nueva, o expansión material de requisitos.
- **PATCH**: aclaraciones, redacción o correcciones sin cambio de obligaciones.

Cumplimiento: cada revisión de PR verifica explícitamente el alineamiento con estos principios.
Las violaciones detectadas en producción se tratan como incidentes y requieren remediación
priorizada. La guía operativa del día a día vive en el README del repo y en la documentación de
contratos de api-general.

**Version**: 1.2.0 | **Ratified**: 2026-09-07 | **Last Amended**: 2026-10-05
