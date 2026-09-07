# Feature Specification: Servicio de Recomendaciones Híbridas Precomputadas (MVP)# Feature Specification: [FEATURE NAME]



**Feature Branch**: `001-recomendaciones-precomputadas`**Feature Branch**: `[###-feature-name]`



**Created**: 2026-09-07**Created**: [DATE]



**Status**: Draft**Status**: Draft



**Input**: User description: "MVP end-to-end del repo `recomendaciones`: lectura de top-N precomputado, recálculo asíncrono vía `recomendacion.actualizar`, sincronización unidireccional desde `api-general`, motor híbrido (content-based + colaborativo + cross-module boost) y post-procesamiento obligatorio (edad, exclusión, MMR)."**Input**: User description: "$ARGUMENTS"



## User Scenarios & Testing *(mandatory)*## User Scenarios & Testing *(mandatory)*



> Nota de rol: el consumidor directo de este servicio es **siempre `api-general`**, nunca un<!--

> frontend. Cuando se habla de "el usuario", se refiere al usuario final de RecoMe en cuyo nombre  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.

> `api-general` realiza la consulta.  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,

  you should still have a viable MVP (Minimum Viable Product) that delivers value.

### User Story 1 - Lectura de recomendaciones precomputadas (Priority: P1)

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.

`api-general` solicita el top-N de recomendaciones para un usuario y un módulo (`peliculas` o  Think of each story as a standalone slice of functionality that can be:

`juegos`) y recibe una lista ordenada de ítems, cada uno con su score y la versión de  - Developed independently

configuración del motor que lo generó. La respuesta se sirve exclusivamente desde resultados ya  - Tested independently

calculados, con latencia acotada y estable.  - Deployed independently

  - Demonstrated to users independently

**Why this priority**: Es la razón de existir del servicio. Sin esto, nada del resto entrega valor-->

observable. Puede demostrarse con datos precargados, sin que el worker ni el sincronizador existan

todavía.### User Story 1 - [Brief Title] (Priority: P1)



**Independent Test**: Precargando manualmente un top-N para un usuario y módulo, se consulta la[Describe this user journey in plain language]

operación de lectura y se verifica orden, score, versión de configuración, tamaño de página y

latencia.**Why this priority**: [Explain the value and why it has this priority level]



**Acceptance Scenarios**:**Independent Test**: [Describe how this can be tested independently - e.g., "Can be fully tested by [specific action] and delivers [specific value]"]



1. **Given** un usuario con top-N precomputado disponible para `peliculas`, **When** `api-general`**Acceptance Scenarios**:

   solicita sus recomendaciones, **Then** recibe la lista ordenada por score descendente, con score

   y versión de configuración por ítem, sin que el servicio ejecute cálculo alguno.1. **Given** [initial state], **When** [action], **Then** [expected outcome]

2. **Given** una solicitud con tamaño de página menor a la cantidad disponible, **When** se2. **Given** [initial state], **When** [action], **Then** [expected outcome]

   consulta, **Then** se devuelve exactamente ese tamaño respetando el orden y con información

   suficiente para pedir la página siguiente.---

3. **Given** una solicitud con módulo inválido o tamaño de página fuera de los límites permitidos,

   **When** se consulta, **Then** el servicio la rechaza con un error de validación explícito y no### User Story 2 - [Brief Title] (Priority: P2)

   devuelve resultados parciales.

4. **Given** una solicitud sin credencial de servicio válida, **When** se consulta, **Then** se[Describe this user journey in plain language]

   rechaza sin exponer ningún dato de recomendaciones.

5. **Given** un catálogo de tamaño muy superior al de una prueba base, **When** se consulta,**Why this priority**: [Explain the value and why it has this priority level]

   **Then** la latencia observada se mantiene dentro del mismo umbral (no crece con el catálogo).

**Independent Test**: [Describe how this can be tested independently]

---

**Acceptance Scenarios**:

### User Story 2 - Recálculo asíncrono al recibir `recomendacion.actualizar` (Priority: P1)

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

Cuando la actividad de un usuario cambia, `api-general` publica el evento

`recomendacion.actualizar`. El worker lo consume, recalcula el top-N del usuario para el o los---

módulos afectados aplicando el motor híbrido y el post-procesamiento obligatorio, y deja el

resultado disponible para lectura.### User Story 3 - [Brief Title] (Priority: P3)



**Why this priority**: Sin recálculo, el top-N nunca se actualiza ni se puede reconstruir tras una[Describe this user journey in plain language]

pérdida de caché. Es la contraparte imprescindible de la Historia 1 y es testeable de forma aislada

verificando el estado precomputado resultante.**Why this priority**: [Explain the value and why it has this priority level]



**Independent Test**: Publicando un evento válido contra un broker de prueba y verificando que el**Independent Test**: [Describe how this can be tested independently]

top-N resultante quede almacenado, correctamente post-procesado y atribuible a una versión de

configuración.**Acceptance Scenarios**:



**Acceptance Scenarios**:1. **Given** [initial state], **When** [action], **Then** [expected outcome]



1. **Given** un usuario con perfil de tags y actividad materializados, **When** llega un---

   `recomendacion.actualizar` válido para ese usuario, **Then** el worker calcula el top-N, aplica

   edad → exclusión → MMR en ese orden y persiste el resultado con su versión de configuración y[Add more user stories as needed, each with an assigned priority]

   marca temporal.

2. **Given** el mismo evento entregado dos o más veces, **When** el worker lo procesa, **Then** el### Edge Cases

   resultado final es idéntico al de un único procesamiento (idempotencia), sin duplicación ni

   corrupción del top-N.<!--

3. **Given** un evento cuyo payload no cumple el JSON Schema documentado en `api-general`, **When**  ACTION REQUIRED: The content in this section represents placeholders.

   llega al worker, **Then** se rechaza de forma explícita y detectable, se envía a dead-letter y  Fill them out with the right edge cases.

   se registra el fallo, sin descartarlo en silencio ni bloquear la cola.-->

4. **Given** un evento para un usuario sin datos materializados, **When** se procesa, **Then** el

   worker resuelve el caso de cold start de forma documentada y deja un resultado válido- What happens when [boundary condition]?

   (posiblemente vacío o basado solo en señales generales), sin fallar.- How does system handle [error scenario]?

5. **Given** un fallo transitorio durante el recálculo, **When** ocurre, **Then** el evento se

   reintenta con backoff y, agotados los reintentos, va a dead-letter con la causa registrada.## Requirements *(mandatory)*



---<!--

  ACTION REQUIRED: The content in this section represents placeholders.

### User Story 3 - Sincronización unidireccional de datos desde `api-general` (Priority: P2)  Fill them out with the right functional requirements.

-->

El Data Transformer lee usuarios, catálogo y actividad desde `api-general` vía REST autenticado con

la API key interna del entorno, y materializa en la DB Recomendaciones los perfiles de tags de### Functional Requirements

usuario y los vectores de tags de ítems que el motor necesita.

- **FR-001**: System MUST [specific capability, e.g., "allow users to create accounts"]

**Why this priority**: Alimenta al motor, pero puede sustituirse temporalmente por datos cargados a- **FR-002**: System MUST [specific capability, e.g., "validate email addresses"]

mano para demostrar las historias P1. Es independientemente testeable observando el estado- **FR-003**: Users MUST be able to [key interaction, e.g., "reset their password"]

materializado tras una corrida.- **FR-004**: System MUST [data requirement, e.g., "persist user preferences"]

- **FR-005**: System MUST [behavior, e.g., "log all security events"]

**Independent Test**: Ejecutando una corrida contra un doble de `api-general` y verificando el

contenido materializado, la idempotencia al repetir la corrida y la ausencia de escrituras hacia*Example of marking unclear requirements:*

recursos ajenos.

- **FR-006**: System MUST authenticate users via [NEEDS CLARIFICATION: auth method not specified - email/password, SSO, OAuth?]

**Acceptance Scenarios**:- **FR-007**: System MUST retain user data for [NEEDS CLARIFICATION: retention period not specified]



1. **Given** un conjunto de usuarios, ítems y actividad disponible en `api-general`, **When** corre### Key Entities *(include if feature involves data)*

   el Data Transformer, **Then** quedan materializados los perfiles de tags de usuario y los

   vectores de tags de ítems, junto con la marca temporal de la sincronización.- **[Entity 1]**: [What it represents, key attributes without implementation]

2. **Given** una corrida previa exitosa, **When** se vuelve a ejecutar sobre los mismos datos,- **[Entity 2]**: [What it represents, relationships to other entities]

   **Then** el estado resultante es equivalente (idempotencia) y no se generan duplicados.

3. **Given** que `api-general` no está disponible o responde con error durante la corrida, **When**## Success Criteria *(mandatory)*

   ocurre, **Then** la corrida falla de forma controlada, deja el estado anterior íntegro y

   utilizable, registra el fallo y puede reintentarse sin intervención manual destructiva.<!--

4. **Given** una corrida en curso, **When** se inspeccionan sus efectos, **Then** no existe ninguna  ACTION REQUIRED: Define measurable success criteria.

   escritura hacia `api-general` ni hacia ningún almacenamiento ajeno: el flujo es estrictamente de  These must be technology-agnostic and measurable.

   lectura externa y escritura local.-->

5. **Given** una discrepancia entre el dato local y el de `api-general`, **When** se detecta,

   **Then** prevalece el valor de `api-general` y el dato local se re-sincroniza.### Measurable Outcomes



---- **SC-001**: [Measurable metric, e.g., "Users can complete account creation in under 2 minutes"]

- **SC-002**: [Measurable metric, e.g., "System handles 1000 concurrent users without degradation"]

### User Story 4 - Cold start cruzado entre módulos (Priority: P2)- **SC-003**: [User satisfaction metric, e.g., "90% of users successfully complete primary task on first attempt"]

- **SC-004**: [Business metric, e.g., "Reduce support tickets related to [X] by 50%"]

Un usuario con historial únicamente en películas pide recomendaciones de juegos (o viceversa) y

recibe resultados relevantes gracias a la señal cruzada sobre su perfil de tags generales.## Assumptions



**Why this priority**: Es el diferencial funcional del producto, pero depende de que la lectura y<!--

el recálculo básicos ya funcionen.  ACTION REQUIRED: The content in this section represents placeholders.

  Fill them out with the right assumptions based on reasonable defaults

**Independent Test**: Con un usuario cuya actividad existe solo en un módulo, se verifica que el  chosen when the feature description did not specify certain details.

top-N del otro módulo no sea vacío y que sus ítems compartan tags con el perfil general.-->



**Acceptance Scenarios**:- [Assumption about target users, e.g., "Users have stable internet connectivity"]

- [Assumption about scope boundaries, e.g., "Mobile support is out of scope for v1"]

1. **Given** un usuario con actividad solo en `peliculas`, **When** se recalcula y se consulta su- [Assumption about data/environment, e.g., "Existing authentication system will be reused"]

   top-N de `juegos`, **Then** el resultado no es vacío y los ítems presentan afinidad de tags con- [Dependency on existing system/service, e.g., "Requires access to the existing user profile API"]

   su perfil general.
2. **Given** un usuario totalmente nuevo sin actividad en ningún módulo, **When** se consulta,
   **Then** el servicio devuelve un resultado documentado y determinístico para cold start puro,
   sin error inesperado y sin violar ningún filtro obligatorio.

---

### User Story 5 - Garantía de filtros obligatorios (Priority: P1)

Ningún ítem que exceda el `age_rating` permitido para el usuario, ni ningún ítem ya visto, jugado o
dislikeado, puede aparecer en ninguna respuesta, en ninguna circunstancia.

**Why this priority**: Es un invariante de seguridad y corrección, no una funcionalidad opcional.
Una violación es un defecto crítico, incluso si el resto del sistema funciona.

**Independent Test**: Con usuarios de distintas edades y con historial de exclusión conocido, se
verifica exhaustivamente la ausencia de ítems prohibidos en el top-N, incluida la salida posterior
a la diversificación.

**Acceptance Scenarios**:

1. **Given** un usuario menor de edad, **When** se recalcula y se consulta su top-N, **Then**
   ningún ítem supera su `age_rating` permitido, ni antes ni después de la diversificación.
2. **Given** un usuario con ítems ya vistos, jugados o dislikeados, **When** se consulta su top-N,
   **Then** ninguno de esos ítems aparece.
3. **Given** un conjunto de candidatos donde la diversificación tendería a incorporar un ítem
   filtrado, **When** se aplica MMR, **Then** ese ítem sigue excluido: MMR nunca reintroduce un
   ítem previamente filtrado.
4. **Given** una configuración que intentara desactivar el filtro de edad o el de exclusión,
   **When** se carga, **Then** se rechaza como configuración inválida.

---

### User Story 6 - Comportamiento ante cache miss y pérdida de caché (Priority: P2)

Cuando el top-N de un usuario no está disponible en la caché (expiración o pérdida total), el
servicio responde de forma degradada, determinística y documentada, y señaliza el recálculo por vía
asíncrona, sin calcular en línea.

**Why this priority**: Define el comportamiento del sistema ante su modo de fallo más frecuente y
garantiza que la caché sea reconstruible.

**Independent Test**: Vaciando la caché para un usuario y consultando, se verifica la respuesta
degradada, la ausencia total de cómputo pesado en el request y la señalización del recálculo.

**Acceptance Scenarios**:

1. **Given** un usuario sin top-N en caché, **When** `api-general` consulta, **Then** recibe una
   respuesta degradada documentada y explícitamente identificable como tal, sin que el servicio
   ejecute scoring, similitud ni diversificación durante el request.
2. **Given** el mismo miss, **When** se atiende, **Then** el servicio señaliza el recálculo por vía
   asíncrona, con protección contra la avalancha de señales repetidas para el mismo usuario y
   módulo.
3. **Given** una pérdida total de la caché, **When** se ejecuta el proceso de reconstrucción
   asíncrona, **Then** los top-N se regeneran sin pérdida de ningún dato autoritativo.
4. **Given** dos misses consecutivos del mismo usuario y módulo, **When** ocurren, **Then** la
   respuesta degradada es idéntica en ambos casos (determinismo).

---

### User Story 7 - Observabilidad y estado de salud (Priority: P3)

El equipo puede saber, sin inspección manual, si las recomendaciones se están sirviendo, si los
recálculos se completan y qué tan fresca está la última sincronización.

**Why this priority**: Imprescindible para operar, pero no bloquea la demostración funcional del
MVP.

**Independent Test**: Consultando los health checks y las métricas expuestas tras ejercitar
lecturas, recálculos exitosos y fallidos, y una corrida de sincronización.

**Acceptance Scenarios**:

1. **Given** tráfico de lectura, **When** se consultan las métricas, **Then** están disponibles el
   ratio de aciertos/fallos de caché y la latencia por endpoint.
2. **Given** recálculos exitosos y fallidos, **When** se consultan las métricas, **Then** ambos
   conteos, la latencia de recálculo y el volumen enviado a dead-letter son visibles.
3. **Given** una sincronización completada, **When** se consulta, **Then** la antigüedad de la
   última sincronización exitosa está expuesta como métrica.
4. **Given** cada componente (API, worker, Data Transformer), **When** se consulta su health check,
   **Then** reporta su estado y el de sus dependencias críticas.
5. **Given** cualquier registro emitido, **When** se inspecciona, **Then** contiene identificador de
   correlación y no contiene credenciales ni datos sensibles.

---

### Edge Cases

- **Catálogo sin candidatos válidos tras los filtros**: el top-N resultante es vacío y explícito,
  nunca un error genérico ni un relleno con ítems que violen los filtros.
- **Usuario inexistente o desconocido para el servicio**: se responde de forma diferenciada del caso
  "usuario conocido sin resultados", sin filtrar información de existencia más allá de lo que el
  contrato con `api-general` autorice.
- **Empates de score**: el desempate es determinístico y documentado; dos ejecuciones idénticas
  producen exactamente el mismo orden.
- **Usuario sin vecinos similares**: la señal colaborativa aporta cero y el resultado se sostiene
  sobre las señales restantes, sin fallar ni redistribuir pesos de forma implícita.
- **Ítem sin tags o con tags vacíos**: queda excluido de los candidatos de forma explícita en lugar
  de recibir un score indefinido.
- **`age_rating` ausente o desconocido en un ítem**: se trata como no apto por defecto (falla
  segura), nunca como apto.
- **Edad o fecha de nacimiento del usuario no disponible**: se aplica la restricción de edad más
  conservadora disponible; jamás se omite el filtro.
- **Evento `recomendacion.actualizar` para un módulo desconocido**: se rechaza con dead-letter y no
  altera ningún top-N existente.
- **Ráfaga de eventos para el mismo usuario**: los recálculos se consolidan de modo que el resultado
  final refleje el estado más reciente sin trabajo redundante innecesario.
- **Cambio de la versión de configuración del motor con top-N vigentes**: conviven resultados de
  distintas versiones, cada uno correctamente etiquetado, hasta que sean recalculados.
- **Sincronización parcial interrumpida**: no deja el estado materializado en una condición
  inconsistente que el motor pueda leer como válida.
- **Broker de RabbitMQ no disponible**: la lectura de recomendaciones sigue funcionando sobre lo ya
  precomputado; la señalización de recálculo se degrada de forma controlada y registrada.

## Requirements *(mandatory)*

### Functional Requirements

**Lectura de recomendaciones**

- **FR-001**: El servicio MUST exponer una operación de solo lectura que devuelva el top-N de
  recomendaciones para un usuario y un módulo (`peliculas` | `juegos`).
- **FR-002**: El servicio MUST servir esa operación exclusivamente desde resultados previamente
  calculados y almacenados en caché.
- **FR-003**: El servicio MUST NOT ejecutar, durante un request, cálculo de scoring, similitud,
  agregación colaborativa, cross-module boost ni diversificación, ni de forma síncrona ni diferida
  dentro del ciclo del request.
- **FR-004**: Cada ítem devuelto MUST incluir su identificador, su posición en el ranking, su score
  y la versión de configuración del motor que lo generó.
- **FR-005**: La operación MUST admitir tamaño de resultado configurable y paginación, con límites
  máximos validados; una solicitud fuera de esos límites MUST rechazarse con error explícito.
- **FR-006**: La respuesta MUST indicar la marca temporal del cálculo, para que el consumidor pueda
  evaluar su frescura.
- **FR-007**: Toda solicitud entrante MUST autenticarse con la API key interna del entorno; sin ella
  MUST rechazarse sin exponer datos.
- **FR-008**: El servicio MUST NOT ser alcanzable directamente desde Frontend Usuario ni Frontend
  Vendedor/Admin: su único consumidor de cara al producto es `api-general`.

**Recálculo asíncrono**

- **FR-009**: El servicio MUST consumir el evento `recomendacion.actualizar` según el JSON Schema
  documentado en `api-general`, sin redefinirlo localmente.
- **FR-010**: El worker MUST recalcular el top-N del usuario y módulo indicados, aplicar el
  post-procesamiento obligatorio y persistir el resultado en la caché.
- **FR-011**: El procesamiento del evento MUST ser idempotente: reprocesar el mismo evento MUST
  producir el mismo resultado final.
- **FR-012**: Un evento cuyo payload no valide contra el schema MUST fallar de forma explícita y
  detectable, derivarse a dead-letter y registrarse; MUST NOT descartarse en silencio.
- **FR-013**: Los fallos transitorios MUST reintentarse con backoff y, agotados los reintentos,
  derivarse a dead-letter con la causa registrada.
- **FR-014**: El worker MUST etiquetar todo resultado persistido con la versión de configuración del
  motor utilizada.

**Sincronización de datos**

- **FR-015**: El Data Transformer MUST obtener usuarios, catálogo y actividad únicamente desde
  `api-general` vía REST, autenticado con la API key interna del entorno.
- **FR-016**: El Data Transformer MUST materializar los perfiles de tags de usuario y los vectores
  de tags de ítems en la DB Recomendaciones.
- **FR-017**: El Data Transformer MUST NOT escribir en la base de datos ni en ningún almacenamiento
  de otro repo, ni invocar operaciones que muten estado de usuario o catálogo en `api-general`.
- **FR-018**: La sincronización MUST ser idempotente y re-ejecutable sin corromper el estado.
- **FR-019**: Ante indisponibilidad o error de `api-general`, la corrida MUST fallar de forma
  controlada dejando el estado previo íntegro y utilizable.
- **FR-020**: Ante discrepancia de datos, la autoridad MUST ser siempre `api-general`; los datos
  locales son una proyección derivada y desechable.

**Motor híbrido**

- **FR-021**: El score de un ítem candidato MUST resultar de la combinación lineal de tres señales
  con pesos alpha (content-based), beta (colaborativo) y gamma (cross-module boost).
- **FR-022**: La señal content-based MUST basarse en la similitud coseno entre el vector TF-IDF del
  perfil de tags del usuario y el vector de tags del ítem.
- **FR-023**: La señal colaborativa MUST agregar ítems likeados por los k usuarios más similares al
  usuario objetivo.
- **FR-024**: La señal cross-module boost MUST derivarse del perfil de tags generales del usuario y
  aplicarse entre módulos (películas ↔ juegos) para atender el cold start cruzado.
- **FR-025**: Los pesos alpha/beta/gamma, el valor de k y los parámetros de post-procesamiento MUST
  residir en configuración versionada e identificable, y MUST NOT estar embebidos como constantes en
  el código.
- **FR-026**: El cálculo MUST ser determinístico: la misma entrada y la misma versión de
  configuración MUST producir el mismo top-N, incluido el criterio de desempate.
- **FR-027**: Toda configuración del motor MUST validarse al cargarse; una configuración inválida
  MUST impedir el arranque o el recálculo en lugar de aplicar valores por defecto silenciosos.

**Post-procesamiento obligatorio**

- **FR-028**: El post-procesamiento MUST ejecutarse siempre en este orden: (1) filtro de edad por
  `age_rating`, (2) filtro de exclusión de ítems vistos/jugados/dislikeados, (3) diversificación por
  MMR.
- **FR-029**: El filtro de edad y el filtro de exclusión MUST ser invariantes no desactivables: no
  existe configuración, bandera ni excepción de rendimiento que los omita.
- **FR-030**: Un ítem cuyo `age_rating` sea desconocido o ausente MUST tratarse como no apto.
- **FR-031**: La diversificación MMR MUST NOT reintroducir ningún ítem previamente filtrado.
- **FR-032**: La diversificación MUST reducir la dominancia de un único cluster de tags en el top-N,
  según un criterio de diversidad medible y documentado.
- **FR-033**: Si tras los filtros no quedan candidatos válidos, el resultado MUST ser un top-N vacío
  explícito, nunca un relleno con ítems no aptos.

**Cache miss y resiliencia**

- **FR-034**: Ante ausencia del top-N en caché, el servicio MUST devolver una respuesta degradada
  determinística, documentada y explícitamente identificable como tal.
- **FR-035**: Ante un miss, el servicio MUST señalizar el recálculo por vía asíncrona, con
  protección contra señalizaciones redundantes para el mismo usuario y módulo.
- **FR-036**: La caché MUST tratarse como almacenamiento derivado: su pérdida total MUST ser
  recuperable íntegramente mediante recálculo asíncrono, sin pérdida de datos autoritativos.
- **FR-037**: Toda llamada saliente a `api-general` MUST tener timeout explícito y comportamiento de
  fallo definido.
- **FR-038**: Ninguna estrategia de contingencia MUST habilitar acceso directo a bases de datos de
  otros repos ni exposición del servicio a los frontends.

**Observabilidad**

- **FR-039**: El servicio MUST exponer métricas de aciertos/fallos de caché y latencia por endpoint.
- **FR-040**: El worker MUST exponer métricas de recálculos exitosos y fallidos, latencia de
  recálculo, profundidad de cola y mensajes derivados a dead-letter.
- **FR-041**: El Data Transformer MUST exponer métricas de éxito/falla por corrida, duración,
  volumen sincronizado y antigüedad de la última sincronización exitosa.
- **FR-042**: API, worker y Data Transformer MUST exponer health checks que reflejen el estado de
  sus dependencias críticas.
- **FR-043**: Todo registro MUST ser estructurado, incluir identificador de correlación y la versión
  de configuración cuando aplique, y MUST NOT contener credenciales ni datos sensibles.

**Contratos**

- **FR-044**: Todo endpoint expuesto hacia `api-general` y el schema del evento consumido MUST
  corresponder a los contratos documentados en `api-general`; esta feature MUST NOT definir ni
  modificar contratos compartidos por cuenta propia.
- **FR-045**: El servicio MUST validar automáticamente su conformidad con esos contratos antes de
  desplegar, de modo que una ruptura de compatibilidad se detecte antes de producción.

### Key Entities

- **Perfil de tags de usuario**: representación ponderada de las preferencias de un usuario sobre el
  vocabulario de tags; distingue el perfil por módulo del perfil general usado para la señal
  cruzada. Derivado de la actividad sincronizada; no es fuente de verdad.
- **Vector de tags de ítem**: representación de una película o juego en el espacio de tags, junto
  con su `age_rating` y el módulo al que pertenece.
- **Similitud entre usuarios**: relación de cercanía entre perfiles, usada para identificar a los k
  vecinos que alimentan la señal colaborativa.
- **Conjunto de exclusión del usuario**: ítems vistos, jugados o dislikeados que nunca pueden
  aparecer en una recomendación.
- **Top-N precomputado**: lista ordenada de ítems recomendados para un par (usuario, módulo), con
  score por ítem, versión de configuración y marca temporal de cálculo.
- **Versión de configuración del motor**: identificador de un conjunto concreto de pesos
  alpha/beta/gamma, valor de k y parámetros de post-procesamiento, que hace atribuible y
  reproducible cualquier resultado.
- **Registro de sincronización**: estado y resultado de cada corrida del Data Transformer, con su
  marca temporal, para poder evaluar la frescura de los datos materializados.
- **Evento de actualización**: solicitud asíncrona de recálculo para un usuario (y módulo), con su
  identificador único que habilita el procesamiento idempotente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: La latencia de la operación de lectura del top-N permanece dentro del mismo umbral
  acordado (p95) cuando el catálogo crece al menos 10× respecto de la línea base; la variación
  atribuible al tamaño del catálogo es inferior al 10 %.
- **SC-002**: **0 %** de ítems que violen el filtro de edad en cualquier respuesta emitida, medido
  sobre el 100 % de las respuestas de una batería de verificación con usuarios de todos los rangos
  etarios.
- **SC-003**: **0 %** de ítems pertenecientes al conjunto de exclusión del usuario en cualquier
  respuesta emitida.
- **SC-004**: **100 %** de los top-N servidos incluyen una versión de configuración del motor
  identificable y resoluble a una configuración concreta.
- **SC-005**: Reprocesar el mismo evento `recomendacion.actualizar` produce un top-N idéntico
  (mismos ítems, mismo orden, mismos scores) en el **100 %** de los casos de prueba.
- **SC-006**: Re-ejecutar una corrida completa del Data Transformer sobre datos sin cambios deja un
  estado materializado equivalente en el **100 %** de los casos, sin duplicados.
- **SC-007**: El **100 %** de los eventos con payload inválido termina en dead-letter con causa
  registrada; **0 %** se descarta silenciosamente.
- **SC-008**: Tras un vaciado total de la caché, el **100 %** de los top-N afectados se reconstruye
  mediante recálculo asíncrono, sin pérdida de datos autoritativos.
- **SC-009**: **0 %** de los requests de lectura ejecutan operaciones de scoring, similitud o
  diversificación, verificable por instrumentación.
- **SC-010**: Para usuarios con actividad en un solo módulo, al menos el 90 % obtiene un top-N no
  vacío en el módulo opuesto (efectividad del cold start cruzado).
- **SC-011**: Ningún top-N de tamaño N concentra más de un porcentaje máximo acordado de ítems
  provenientes de un mismo cluster de tags, verificable con la métrica de diversidad definida.
- **SC-012**: **0** conexiones directas a bases de datos de otros repos y **0** rutas de acceso desde
  los frontends, verificable por revisión de configuración de red y dependencias.
- **SC-013**: El **100 %** de los endpoints expuestos y del evento consumido pasa la validación
  automatizada contra los contratos documentados en `api-general` antes de cada despliegue.
- **SC-014**: La antigüedad de la última sincronización exitosa está disponible como métrica el
  **100 %** del tiempo de operación del servicio.

## Assumptions

- El consumidor exclusivo de este servicio es `api-general`; ningún frontend lo consulta directa ni
  indirectamente sin pasar por él.
- El contrato del evento `recomendacion.actualizar` y los contratos REST relevantes ya existen o
  serán definidos y documentados en `api-general` antes de la implementación; esta feature los
  consume, no los define.
- `api-general` expone endpoints internos suficientes para obtener usuarios, catálogo (con tags y
  `age_rating`) y actividad (vistos, jugados, likes, dislikes) para la sincronización.
- La API key interna por entorno ya está definida a nivel de sistema y es provista por configuración
  de entorno.
- El vocabulario de tags es compartido entre módulos, lo que hace posible la señal cruzada
  películas ↔ juegos.
- La edad o fecha de nacimiento del usuario es obtenible desde `api-general`; cuando no lo sea, se
  aplica la política conservadora descrita en los edge cases.
- El MVP usa TF-IDF y similitud coseno; no se entrenan modelos de deep learning ni embeddings
  aprendidos.
- Los valores concretos de N por defecto, tamaño máximo de página, umbral de latencia p95, valor de
  k, pesos iniciales alpha/beta/gamma, parámetro de compensación de MMR, política de expiración de
  la caché, frecuencia de sincronización y porcentaje máximo por cluster se acordarán durante la
  planificación: la spec fija que deben existir, ser configurables y ser medibles, no sus valores.
- El prototipo Python existente en la raíz del workspace es material de referencia del
  comportamiento esperado y no condiciona el diseño de la solución.
- El broker de RabbitMQ es provisto y operado por el repo `notificaciones`; esta feature actúa
  únicamente como cliente consumidor.
