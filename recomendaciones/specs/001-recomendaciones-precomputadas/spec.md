# Feature Specification: Servicio de Recomendaciones Híbridas Precomputadas (MVP)

**Feature Branch**: `001-recomendaciones-precomputadas`

**Created**: 2026-09-07

**Status**: Draft

**Input**: User description: "MVP end-to-end del repo `recomendaciones`: lectura de top-N precomputado, recálculo asíncrono vía `recomendacion.actualizar`, sincronización unidireccional desde `api-general`, motor híbrido (content-based + colaborativo + cross-module boost) y post-procesamiento obligatorio (edad, exclusión, MMR)."

## Clarifications

### Session 2026-09-07

- **Q**: ¿Cuál es la semántica exacta de la respuesta degradada ante cache miss (FR-034)? → **A**: Stale-while-revalidate con fallback a vacío. Si existe un top-N vencido para ese par (usuario, módulo), se sirve marcado explícitamente como obsoleto, junto con su marca temporal de cálculo y su versión de configuración. Si no existe ninguno, se responde un top-N vacío marcado como "recálculo pendiente". En ambos casos se señaliza el recálculo por vía asíncrona y nunca se calcula en línea. Un top-N obsoleto servido sigue estando sujeto a los filtros obligatorios vigentes al momento de servirlo.
- **Q**: ¿Qué alcance tiene el recálculo disparado por un `recomendacion.actualizar` (FR-010)? → **A**: Alcance condicional determinado por los tags del ítem de la actividad. El worker recalcula siempre el módulo de la actividad. Además recalcula el módulo opuesto **solo si** al menos uno de los tags del ítem pertenece al vocabulario de tags compartido entre módulos (es decir, un tag que también aparece en ítems del otro módulo), porque en ese caso la actividad altera el perfil de tags generales y con él el cross-module boost. Si ningún tag del ítem es compartido, el módulo opuesto no se recalcula. La condición la evalúa este repo con sus propios datos materializados; no requiere información adicional en el payload del evento ni cambio de contrato.
- **Q**: ¿Cómo se diferencian las señales de exclusión y su efecto sobre el scoring (FR-029)? → **A**: Dos planos separados. **Plano de exclusión**: like, dislike y visto/jugado excluyen todos al ítem del top-N; la exclusión por visto/jugado y por dislike es permanente, salvo que un like posterior sobre el mismo ítem revierta una exclusión originada en un dislike previo. **Plano de scoring**: solo like y dislike modifican el perfil de tags del usuario —el like refuerza los tags del ítem, el dislike los penaliza—; visto/jugado no altera el perfil, únicamente excluye. Ante señales contradictorias sobre un mismo ítem prevalece siempre la más reciente.
- **Q**: ¿Dónde vive la configuración del motor y qué ocurre al cambiar su versión (FR-025)? → **A**: Archivo de configuración versionado dentro del repo y desplegado junto con el código, con un identificador de versión único. Cambiarla requiere un PR y un nuevo despliegue, lo que la deja auditable y reproducible. Existe **una sola versión activa** por entorno en un momento dado (sin A/B testing en el MVP). Un cambio de versión **no** dispara invalidación ni recálculo masivo: los top-N existentes siguen siendo válidos y conviven etiquetados con su versión de origen hasta que un recálculo natural los reemplace.
- **Q**: ¿Qué se devuelve ante cold start puro, sin actividad alguna del usuario (US4, FR-033)? → **A**: Un top-N de respaldo basado en popularidad del módulo (ítems más likeados globalmente), **diversificado por MMR** para exponer variedad de clusters de tags y acelerar el aprendizaje sobre el usuario. Se precomputa de forma global por módulo, no por usuario, pero se personaliza al servirlo aplicando los filtros obligatorios del usuario concreto (edad y exclusión). Se marca explícitamente como resultado de respaldo, para distinguirlo de una recomendación personalizada.

## User Scenarios & Testing *(mandatory)*

> Nota de rol: el consumidor directo de este servicio es **siempre `api-general`**, nunca un
> frontend. Cuando se habla de "el usuario", se refiere al usuario final de RecoMe en cuyo nombre
> `api-general` realiza la consulta.

### User Story 1 - Lectura de recomendaciones precomputadas (Priority: P1)

`api-general` solicita el top-N de recomendaciones para un usuario y un módulo (`peliculas` o
`juegos`) y recibe una lista ordenada de ítems, cada uno con su score y la versión de
configuración del motor que lo generó. La respuesta se sirve exclusivamente desde resultados ya
calculados, con latencia acotada y estable.

**Why this priority**: Es la razón de existir del servicio. Sin esto, nada del resto entrega valor
observable. Puede demostrarse con datos precargados, sin que el worker ni el sincronizador existan
todavía.

**Independent Test**: Precargando manualmente un top-N para un usuario y módulo, se consulta la
operación de lectura y se verifica orden, score, versión de configuración, tamaño de página y
latencia.

**Acceptance Scenarios**:

1. **Given** un usuario con top-N precomputado vigente para `peliculas`, **When** `api-general`
   solicita sus recomendaciones, **Then** recibe la lista ordenada por score descendente, con score
   y versión de configuración por ítem, marcada como vigente, sin que el servicio ejecute cálculo
   alguno.
2. **Given** una solicitud con tamaño de página menor a la cantidad disponible, **When** se
   consulta, **Then** se devuelve exactamente ese tamaño respetando el orden y con información
   suficiente para pedir la página siguiente.
3. **Given** una solicitud con módulo inválido o tamaño de página fuera de los límites permitidos,
   **When** se consulta, **Then** el servicio la rechaza con un error de validación explícito y no
   devuelve resultados parciales.
4. **Given** una solicitud sin credencial de servicio válida, **When** se consulta, **Then** se
   rechaza sin exponer ningún dato de recomendaciones.
5. **Given** un catálogo de tamaño muy superior al de una prueba base, **When** se consulta,
   **Then** la latencia observada se mantiene dentro del mismo umbral (no crece con el catálogo).

---

### User Story 2 - Recálculo asíncrono al recibir `recomendacion.actualizar` (Priority: P1)

Cuando la actividad de un usuario cambia, `api-general` publica el evento
`recomendacion.actualizar`. El worker lo consume, recalcula el top-N del usuario para el o los
módulos afectados aplicando el motor híbrido y el post-procesamiento obligatorio, y deja el
resultado disponible para lectura.

**Why this priority**: Sin recálculo, el top-N nunca se actualiza ni se puede reconstruir tras una
pérdida de caché. Es la contraparte imprescindible de la Historia 1 y es testeable de forma aislada
verificando el estado precomputado resultante.

**Independent Test**: Publicando un evento válido contra un broker de prueba y verificando que el
top-N resultante quede almacenado, correctamente post-procesado y atribuible a una versión de
configuración.

**Acceptance Scenarios**:

1. **Given** un usuario con perfil de tags y actividad materializados, **When** llega un
   `recomendacion.actualizar` válido para ese usuario, **Then** el worker calcula el top-N, aplica
   edad → exclusión → MMR en ese orden y persiste el resultado con su versión de configuración y
   marca temporal.
2. **Given** el mismo evento entregado dos o más veces, **When** el worker lo procesa, **Then** el
   resultado final es idéntico al de un único procesamiento (idempotencia), sin duplicación ni
   corrupción del top-N.
3. **Given** un evento cuyo payload no cumple el JSON Schema documentado en `api-general`, **When**
   llega al worker, **Then** se rechaza de forma explícita y detectable, se envía a dead-letter y
   se registra el fallo, sin descartarlo en silencio ni bloquear la cola.
4. **Given** un evento para un usuario sin datos materializados, **When** se procesa, **Then** el
   worker resuelve el caso de cold start de forma documentada y deja un resultado válido
   (posiblemente vacío o basado solo en señales generales), sin fallar.
5. **Given** un fallo transitorio durante el recálculo, **When** ocurre, **Then** el evento se
   reintenta con backoff y, agotados los reintentos, va a dead-letter con la causa registrada.
6. **Given** un top-N obsoleto servido previamente por cache miss, **When** el recálculo señalizado
   se completa, **Then** el resultado pasa a estar vigente y las lecturas posteriores dejan de
   marcarse como obsoletas.
7. **Given** una actividad sobre un ítem cuyos tags incluyen al menos uno del vocabulario
   compartido entre módulos, **When** llega el evento, **Then** el worker recalcula el top-N de
   ambos módulos del usuario y registra el motivo de haber alcanzado el módulo opuesto.
8. **Given** una actividad sobre un ítem cuyos tags son todos exclusivos de su propio módulo,
   **When** llega el evento, **Then** el worker recalcula únicamente el top-N del módulo de la
   actividad, deja intacto el del módulo opuesto y registra el motivo de no haberlo alcanzado.
9. **Given** el mismo evento reprocesado, **When** el worker lo evalúa, **Then** toma la misma
   decisión sobre el módulo opuesto y produce el mismo resultado en ambos módulos.

---

### User Story 3 - Sincronización unidireccional de datos desde `api-general` (Priority: P2)

El Data Transformer lee usuarios, catálogo y actividad desde `api-general` vía REST autenticado con
la API key interna del entorno, y materializa en la DB Recomendaciones los perfiles de tags de
usuario y los vectores de tags de ítems que el motor necesita.

**Why this priority**: Alimenta al motor, pero puede sustituirse temporalmente por datos cargados a
mano para demostrar las historias P1. Es independientemente testeable observando el estado
materializado tras una corrida.

**Independent Test**: Ejecutando una corrida contra un doble de `api-general` y verificando el
contenido materializado, la idempotencia al repetir la corrida y la ausencia de escrituras hacia
recursos ajenos.

**Acceptance Scenarios**:

1. **Given** un conjunto de usuarios, ítems y actividad disponible en `api-general`, **When** corre
   el Data Transformer, **Then** quedan materializados los perfiles de tags de usuario y los
   vectores de tags de ítems, junto con la marca temporal de la sincronización.
2. **Given** una corrida previa exitosa, **When** se vuelve a ejecutar sobre los mismos datos,
   **Then** el estado resultante es equivalente (idempotencia) y no se generan duplicados.
3. **Given** que `api-general` no está disponible o responde con error durante la corrida, **When**
   ocurre, **Then** la corrida falla de forma controlada, deja el estado anterior íntegro y
   utilizable, registra el fallo y puede reintentarse sin intervención manual destructiva.
4. **Given** una corrida en curso, **When** se inspeccionan sus efectos, **Then** no existe ninguna
   escritura hacia `api-general` ni hacia ningún almacenamiento ajeno: el flujo es estrictamente de
   lectura externa y escritura local.
5. **Given** una discrepancia entre el dato local y el de `api-general`, **When** se detecta,
   **Then** prevalece el valor de `api-general` y el dato local se re-sincroniza.

---

### User Story 4 - Cold start cruzado entre módulos (Priority: P2)

Un usuario con historial únicamente en películas pide recomendaciones de juegos (o viceversa) y
recibe resultados relevantes gracias a la señal cruzada sobre su perfil de tags generales.

**Why this priority**: Es el diferencial funcional del producto, pero depende de que la lectura y
el recálculo básicos ya funcionen.

**Independent Test**: Con un usuario cuya actividad existe solo en un módulo, se verifica que el
top-N del otro módulo no sea vacío y que sus ítems compartan tags con el perfil general.

**Acceptance Scenarios**:

1. **Given** un usuario con actividad solo en `peliculas`, **When** se recalcula y se consulta su
   top-N de `juegos`, **Then** el resultado no es vacío y los ítems presentan afinidad de tags con
   su perfil general.
2. **Given** un usuario totalmente nuevo sin actividad en ningún módulo, **When** se consulta,
   **Then** recibe el top-N de respaldo del módulo —populares diversificados por MMR— marcado
   explícitamente como resultado no personalizado, sin error y sin violar ningún filtro obligatorio.
3. **Given** un usuario nuevo menor de edad, **When** recibe el top-N de respaldo, **Then** ningún
   ítem supera su `age_rating` permitido: el respaldo se filtra por las restricciones del usuario
   concreto antes de servirse.
4. **Given** el top-N de respaldo de un módulo, **When** se inspecciona su composición, **Then**
   presenta variedad de clusters de tags y no está dominado por un único género popular.
5. **Given** un usuario nuevo que registra su primera señal de preferencia, **When** se completa el
   recálculo, **Then** sus recomendaciones pasan a ser personalizadas y dejan de marcarse como
   respaldo.
6. **Given** una consulta que se resuelve con el top-N de respaldo, **When** se atiende, **Then** el
   servicio no ejecuta scoring, similitud ni diversificación durante el request: el respaldo ya
   estaba precomputado y solo se le aplican los filtros del usuario.

---

### User Story 5 - Garantía de filtros obligatorios (Priority: P1)

Ningún ítem que exceda el `age_rating` permitido para el usuario, ni ningún ítem ya visto, jugado o
dislikeado, puede aparecer en ninguna respuesta, en ninguna circunstancia.

**Why this priority**: Es un invariante de seguridad y corrección, no una funcionalidad opcional.
Una violación es un defecto crítico, incluso si el resto del sistema funciona.

**Independent Test**: Con usuarios de distintas edades y con historial de exclusión conocido, se
verifica exhaustivamente la ausencia de ítems prohibidos en el top-N, incluida la salida posterior
a la diversificación y las respuestas obsoletas.

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
5. **Given** un top-N obsoleto que se sirve por cache miss, **When** se emite la respuesta,
   **Then** sigue cumpliendo los filtros de edad y de exclusión vigentes: un resultado obsoleto
   nunca puede exponer un ítem que hoy sería prohibido.
6. **Given** un usuario que dislikeó un ítem, **When** se recalcula su top-N, **Then** ese ítem no
   aparece y los tags que lo caracterizan quedan penalizados en su perfil, reduciendo el score de
   otros ítems similares.
7. **Given** un usuario que likeó un ítem, **When** se recalcula su top-N, **Then** ese ítem no
   aparece (ya lo conoce) pero los tags que lo caracterizan quedan reforzados en su perfil,
   elevando el score de otros ítems similares.
8. **Given** un usuario que solo marcó un ítem como visto o jugado, sin like ni dislike, **When**
   se recalcula, **Then** el ítem queda excluido y su perfil de tags permanece sin cambios.
9. **Given** un ítem dislikeado y posteriormente likeado por el mismo usuario, **When** se
   recalcula, **Then** prevalece la señal más reciente: la penalización de tags se revierte por el
   refuerzo, y el ítem vuelve a ser elegible salvo que también haya sido consumido.

---

### User Story 6 - Comportamiento ante cache miss y pérdida de caché (Priority: P2)

Cuando el top-N vigente de un usuario no está disponible (expiración o pérdida total), el servicio
aplica una estrategia de *stale-while-revalidate*: sirve el último resultado conocido marcándolo
como obsoleto, o un resultado vacío marcado como pendiente si no existe ninguno, y en ambos casos
señaliza el recálculo por vía asíncrona, sin calcular en línea.

**Why this priority**: Define el comportamiento del sistema ante su modo de fallo más frecuente y
garantiza que la caché sea reconstruible.

**Independent Test**: Venciendo o vaciando la caché para un usuario y consultando, se verifica el
marcado de obsolescencia, la respuesta vacía cuando no hay histórico, la ausencia total de cómputo
pesado en el request y la señalización del recálculo.

**Acceptance Scenarios**:

1. **Given** un usuario cuyo top-N venció pero cuyo último resultado conocido aún se conserva,
   **When** `api-general` consulta, **Then** recibe ese resultado marcado explícitamente como
   obsoleto, con su marca temporal de cálculo y su versión de configuración, sin que el servicio
   ejecute scoring, similitud ni diversificación durante el request.
2. **Given** un usuario sin ningún top-N conocido (pérdida total o usuario nunca calculado),
   **When** consulta, **Then** recibe un top-N vacío marcado explícitamente como "recálculo
   pendiente", diferenciable de un top-N vacío por ausencia de candidatos válidos.
3. **Given** cualquiera de los dos casos anteriores, **When** se atiende la solicitud, **Then** el
   servicio señaliza el recálculo por vía asíncrona, con protección contra señalizaciones
   redundantes para el mismo usuario y módulo dentro de una ventana acordada.
4. **Given** una pérdida total de la caché, **When** se ejecuta la reconstrucción asíncrona,
   **Then** los top-N se regeneran sin pérdida de ningún dato autoritativo.
5. **Given** dos consultas consecutivas en el mismo estado de caché, **When** ocurren, **Then** la
   respuesta degradada es idéntica en ambos casos (determinismo).
6. **Given** un resultado servido como obsoleto, **When** `api-general` lo recibe, **Then** dispone
   de información suficiente (marca de obsolescencia y antigüedad) para decidir cómo presentarlo.

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
   ratio de aciertos/fallos de caché, la proporción de respuestas obsoletas y vacías-pendientes, y
   la latencia por endpoint.
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
  distinguible del vacío por "recálculo pendiente", nunca un error genérico ni un relleno con ítems
  que violen los filtros.
- **Usuario nuevo cuyos filtros vacían casi por completo el respaldo** (p. ej. menor de edad con un
  catálogo mayormente adulto): se devuelve lo que quede, aunque sea menos que el tamaño solicitado,
  sin completar con ítems no aptos.
- **Top-N de respaldo aún no precomputado** (arranque en frío del sistema, catálogo recién
  cargado): se responde como recálculo pendiente y se señaliza su generación, sin calcularlo en
  línea.
- **Catálogo sin suficientes likes para establecer popularidad**: el respaldo se construye con el
  criterio de desempate documentado y sigue siendo determinístico, sin quedar indefinido.
- **Usuario inexistente o desconocido para el servicio**: se responde de forma diferenciada del caso
  "usuario conocido sin resultados", sin filtrar información de existencia más allá de lo que el
  contrato con `api-general` autorice.
- **Empates de score**: el desempate es determinístico y documentado; dos ejecuciones idénticas
  producen exactamente el mismo orden.
- **Usuario sin vecinos similares**: la señal colaborativa aporta cero y el resultado se sostiene
  sobre las señales restantes, sin fallar ni redistribuir pesos de forma implícita.
- **Usuario que solo emitió dislikes**: su perfil de tags queda dominado por penalizaciones; el
  motor debe producir un resultado válido y no vacío por construcción, apoyándose en las señales
  restantes, sin invertir el sentido de la recomendación.
- **Like y dislike sobre el mismo ítem con la misma marca temporal**: el desempate es
  determinístico y documentado, nunca dependiente del orden de llegada de los eventos.
- **Ítem likeado que luego se dislikea**: prevalece el dislike por ser más reciente; el refuerzo de
  tags se convierte en penalización y el ítem permanece excluido.
- **Señal de preferencia sobre un ítem que ya no existe en el catálogo**: no rompe el cálculo del
  perfil y se ignora de forma registrada.
- **Ítem sin tags o con tags vacíos**: queda excluido de los candidatos de forma explícita en lugar
  de recibir un score indefinido.
- **`age_rating` ausente o desconocido en un ítem**: se trata como no apto por defecto (falla
  segura), nunca como apto.
- **Edad o fecha de nacimiento del usuario no disponible**: se aplica la restricción de edad más
  conservadora disponible; jamás se omite el filtro.
- **Top-N obsoleto cuyo conjunto de exclusión o cuya edad del usuario cambiaron desde el cálculo**:
  los filtros obligatorios se reevalúan sobre el resultado obsoleto antes de servirlo.
- **Top-N obsoleto extremadamente antiguo**: existe un límite de antigüedad más allá del cual el
  resultado deja de servirse y se responde como "recálculo pendiente".
- **Evento `recomendacion.actualizar` para un módulo desconocido**: se rechaza con dead-letter y no
  altera ningún top-N existente.
- **Ítem de la actividad sin tags o con tags desconocidos**: no se puede evaluar la condición de
  propagación; se recalcula únicamente el módulo de la actividad y se registra la limitación.
- **Tag que pasa a ser compartido al incorporarse un ítem nuevo del otro módulo**: la propagación
  aplica a partir de la siguiente sincronización que actualice el vocabulario compartido; los
  top-N previos se consideran vigentes hasta su próximo recálculo.
- **Recálculo del módulo opuesto que falla mientras el del módulo de la actividad tuvo éxito**: el
  éxito parcial se registra de forma diferenciada y el módulo fallido se reintenta sin invalidar el
  resultado ya persistido.
- **Ráfaga de eventos para el mismo usuario**: los recálculos se consolidan de modo que el resultado
  final refleje el estado más reciente sin trabajo redundante innecesario.
- **Avalancha de misses simultáneos tras una pérdida total de caché**: la señalización de recálculo
  se agrupa para no saturar el broker ni el worker.
- **Cambio de la versión de configuración del motor con top-N vigentes**: conviven resultados de
  distintas versiones, cada uno correctamente etiquetado, hasta que sean recalculados; no se
  invalida ni se recalcula nada de forma masiva.
- **Top-N etiquetado con una versión de configuración que ya no existe en el repo**: sigue
  sirviéndose tal cual, pero la discrepancia queda registrada para poder auditarla.
- **Despliegue con archivo de configuración ausente, malformado o con pesos inconsistentes**: el
  componente no arranca y lo señala explícitamente, en lugar de aplicar valores por defecto.
- **Rollback a una versión de configuración anterior**: es posible revirtiendo el cambio en el repo
  y desplegando; los top-N generados con la versión revertida siguen siendo válidos y distinguibles.
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
- **FR-006**: La respuesta MUST indicar la marca temporal del cálculo y su naturaleza (personalizada
  vigente, personalizada obsoleta, de respaldo no personalizada, vacía por falta de candidatos o
  vacía por recálculo pendiente), para que el consumidor pueda decidir cómo presentarla.
- **FR-007**: Toda solicitud entrante MUST autenticarse con la API key interna del entorno; sin ella
  MUST rechazarse sin exponer datos.
- **FR-008**: El servicio MUST NOT ser alcanzable directamente desde Frontend Usuario ni Frontend
  Vendedor/Admin: su único consumidor de cara al producto es `api-general`.

**Recálculo asíncrono**

- **FR-009**: El servicio MUST consumir el evento `recomendacion.actualizar` según el JSON Schema
  documentado en `api-general`, sin redefinirlo localmente.
- **FR-010**: El worker MUST recalcular el top-N del usuario para el módulo de la actividad
  indicada, aplicar el post-procesamiento obligatorio y persistir el resultado en la caché,
  dejándolo marcado como vigente.
- **FR-010a**: El worker MUST recalcular además el top-N del módulo opuesto cuando al menos uno de
  los tags del ítem de la actividad pertenezca al vocabulario de tags compartido entre módulos;
  cuando ninguno lo sea, MUST NOT recalcular el módulo opuesto.
- **FR-010b**: El vocabulario de tags compartido MUST derivarse de los datos ya materializados en la
  DB Recomendaciones (tags presentes en ítems de ambos módulos), sin requerir información adicional
  en el payload del evento ni modificación del contrato compartido.
- **FR-010c**: La decisión de recalcular o no el módulo opuesto MUST quedar registrada con su
  motivo, para poder auditar por qué un top-N no se actualizó tras una actividad.
- **FR-011**: El procesamiento del evento MUST ser idempotente: reprocesar el mismo evento MUST
  producir el mismo resultado final, incluida la decisión sobre el módulo opuesto.
- **FR-012**: Un evento cuyo payload no valide contra el schema MUST fallar de forma explícita y
  detectable, derivarse a dead-letter y registrarse; MUST NOT descartarse en silencio.
- **FR-013**: Los fallos transitorios MUST reintentarse con backoff y, agotados los reintentos,
  derivarse a dead-letter con la causa registrada.
- **FR-014**: El worker MUST etiquetar todo resultado persistido con la versión de configuración del
  motor utilizada y su marca temporal de cálculo.

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
- **FR-022a**: El perfil de tags del usuario MUST construirse únicamente a partir de señales
  explícitas de preferencia: los likes MUST reforzar los tags del ítem y los dislikes MUST
  penalizarlos, con magnitudes definidas en la configuración versionada del motor.
- **FR-022b**: El consumo (visto/jugado) MUST NOT modificar el perfil de tags del usuario: actúa
  exclusivamente sobre el conjunto de exclusión.
- **FR-022c**: El perfil resultante MUST permanecer en un rango acotado y numéricamente estable
  aunque un usuario acumule muchas señales negativas sobre un mismo tag.
- **FR-023**: La señal colaborativa MUST agregar ítems likeados por los k usuarios más similares al
  usuario objetivo.
- **FR-024**: La señal cross-module boost MUST derivarse del perfil de tags generales del usuario y
  aplicarse entre módulos (películas ↔ juegos) para atender el cold start cruzado.
- **FR-025**: Los pesos alpha/beta/gamma, el valor de k, las magnitudes de refuerzo/penalización y
  los parámetros de post-procesamiento MUST residir en un archivo de configuración versionado dentro
  del repo, identificado por una versión única, y MUST NOT estar embebidos como constantes en el
  código.
- **FR-025a**: La configuración MUST desplegarse junto con el código; modificarla MUST requerir un
  cambio revisable en el repo, de modo que toda variación quede auditable y reproducible.
- **FR-025b**: MUST existir exactamente una versión de configuración activa por entorno en un
  momento dado; el MVP MUST NOT admitir varias versiones activas simultáneas.
- **FR-025c**: Un cambio de versión de configuración MUST NOT invalidar ni recalcular masivamente
  los top-N existentes: estos MUST seguir sirviéndose, etiquetados con la versión que los generó,
  hasta que un recálculo natural los reemplace.
- **FR-025d**: La versión de configuración activa MUST ser consultable en tiempo de ejecución (por
  health check o métrica), para poder verificar qué configuración está produciendo los recálculos
  actuales.
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
- **FR-029a**: El conjunto de exclusión MUST incluir todo ítem sobre el que el usuario registró un
  like, un dislike o un consumo (visto/jugado); ninguno de ellos MUST aparecer en el top-N.
- **FR-029b**: La exclusión originada en un consumo (visto/jugado) MUST ser permanente y no
  reversible por señales posteriores.
- **FR-029c**: La exclusión originada en un dislike MUST ser permanente salvo que exista un like
  posterior sobre el mismo ítem, en cuyo caso la exclusión por dislike MUST considerarse revertida;
  el ítem permanece excluido si además fue consumido.
- **FR-029d**: Ante señales contradictorias sobre un mismo ítem, MUST prevalecer la más reciente
  según su marca temporal; el criterio de desempate MUST ser determinístico y documentado.
- **FR-030**: Un ítem cuyo `age_rating` sea desconocido o ausente MUST tratarse como no apto.
- **FR-031**: La diversificación MMR MUST NOT reintroducir ningún ítem previamente filtrado.
- **FR-032**: La diversificación MUST reducir la dominancia de un único cluster de tags en el top-N,
  según un criterio de diversidad medible y documentado.
- **FR-033**: Si tras los filtros no quedan candidatos válidos, el resultado MUST ser un top-N vacío
  explícito y distinguible del vacío por recálculo pendiente, nunca un relleno con ítems no aptos.
- **FR-033a**: MUST existir un top-N de respaldo por módulo, basado en la popularidad global de los
  ítems (volumen de likes), destinado a usuarios sin actividad suficiente para generar un perfil de
  tags.
- **FR-033b**: El top-N de respaldo MUST diversificarse por MMR sobre el espacio de tags, de modo
  que exponga distintos clusters en lugar de concentrarse en el género globalmente dominante.
- **FR-033c**: El top-N de respaldo MUST precomputarse de forma global por módulo mediante un
  proceso asíncrono, con su propia periodicidad de actualización, y MUST NOT calcularse por usuario
  ni durante un request.
- **FR-033d**: Al servirse a un usuario concreto, el top-N de respaldo MUST someterse a los filtros
  obligatorios de ese usuario (edad y exclusión). Este filtrado opera sobre un conjunto acotado y ya
  ordenado y NO constituye scoring, similitud ni diversificación, por lo que no contradice FR-003.
- **FR-033e**: Un top-N de respaldo servido MUST marcarse explícitamente como resultado no
  personalizado, distinguible de una recomendación personalizada, de un vacío por falta de
  candidatos y de un vacío por recálculo pendiente.
- **FR-033f**: Si tras aplicar los filtros del usuario el respaldo queda por debajo del tamaño
  solicitado, MUST devolverse lo disponible sin completar con ítems no aptos; el respaldo
  precomputado MUST dimensionarse con margen suficiente para absorber el filtrado habitual.
- **FR-033g**: En cuanto el usuario acumule actividad suficiente para generar un perfil de tags, sus
  recomendaciones MUST pasar a ser personalizadas y dejar de marcarse como respaldo.

**Cache miss y resiliencia**

- **FR-034**: Ante ausencia de un top-N vigente, el servicio MUST aplicar *stale-while-revalidate*:
  si conserva un resultado previo dentro del límite de antigüedad admitido, MUST servirlo marcado
  como obsoleto; en caso contrario MUST devolver un top-N vacío marcado como recálculo pendiente.
- **FR-035**: Ante cualquiera de esos dos casos, el servicio MUST señalizar el recálculo por vía
  asíncrona, con protección contra señalizaciones redundantes para el mismo usuario y módulo dentro
  de una ventana acordada.
- **FR-036**: Un resultado obsoleto MUST reevaluarse contra los filtros obligatorios vigentes antes
  de servirse; MUST NOT exponer ítems que hoy resulten no aptos.
- **FR-037**: MUST existir un límite máximo de antigüedad configurable más allá del cual un
  resultado obsoleto deja de servirse y se responde como recálculo pendiente.
- **FR-038**: La respuesta degradada MUST ser determinística: dos consultas consecutivas sobre el
  mismo estado de caché MUST producir la misma respuesta.
- **FR-039**: La caché MUST tratarse como almacenamiento derivado: su pérdida total MUST ser
  recuperable íntegramente mediante recálculo asíncrono, sin pérdida de datos autoritativos.
- **FR-040**: Toda llamada saliente a `api-general` MUST tener timeout explícito y comportamiento de
  fallo definido.
- **FR-041**: Ninguna estrategia de contingencia MUST habilitar acceso directo a bases de datos de
  otros repos ni exposición del servicio a los frontends.

**Observabilidad**

- **FR-042**: El servicio MUST exponer métricas de aciertos/fallos de caché, proporción de
  respuestas obsoletas y de recálculo pendiente, y latencia por endpoint.
- **FR-043**: El worker MUST exponer métricas de recálculos exitosos y fallidos, latencia de
  recálculo, profundidad de cola y mensajes derivados a dead-letter.
- **FR-044**: El Data Transformer MUST exponer métricas de éxito/falla por corrida, duración,
  volumen sincronizado y antigüedad de la última sincronización exitosa.
- **FR-045**: API, worker y Data Transformer MUST exponer health checks que reflejen el estado de
  sus dependencias críticas.
- **FR-046**: Todo registro MUST ser estructurado, incluir identificador de correlación y la versión
  de configuración cuando aplique, y MUST NOT contener credenciales ni datos sensibles.

**Contratos**

- **FR-047**: Todo endpoint expuesto hacia `api-general` y el schema del evento consumido MUST
  corresponder a los contratos documentados en `api-general`; esta feature MUST NOT definir ni
  modificar contratos compartidos por cuenta propia.
- **FR-048**: El servicio MUST validar automáticamente su conformidad con esos contratos antes de
  desplegar, de modo que una ruptura de compatibilidad se detecte antes de producción.

### Key Entities

- **Perfil de tags de usuario**: representación ponderada de las preferencias de un usuario sobre el
  vocabulario de tags; distingue el perfil por módulo del perfil general usado para la señal
  cruzada. Derivado de la actividad sincronizada; no es fuente de verdad.
- **Vector de tags de ítem**: representación de una película o juego en el espacio de tags, junto
  con su `age_rating` y el módulo al que pertenece.
- **Vocabulario de tags compartido**: subconjunto de tags que aparecen en ítems de ambos módulos
  (p. ej. terror, comedia, ciencia ficción). Determina qué actividades propagan su efecto al módulo
  opuesto y sostiene el cross-module boost. Se deriva de los datos materializados y se recalcula al
  sincronizar el catálogo.
- **Similitud entre usuarios**: relación de cercanía entre perfiles, usada para identificar a los k
  vecinos que alimentan la señal colaborativa.
- **Conjunto de exclusión del usuario**: ítems que nunca pueden aparecer en una recomendación,
  originados en un like, un dislike o un consumo (visto/jugado). Distingue el origen de cada
  exclusión, porque determina su reversibilidad: la de consumo es permanente y la de dislike puede
  revertirse por un like posterior.
- **Señal de preferencia**: registro de un like o un dislike del usuario sobre un ítem, con su marca
  temporal. Es la única fuente que modifica el perfil de tags (refuerzo o penalización); el consumo
  no lo hace.
- **Top-N precomputado**: lista ordenada de ítems recomendados para un par (usuario, módulo), con
  score por ítem, versión de configuración, marca temporal de cálculo y estado de frescura
  (vigente / obsoleto / recálculo pendiente).
- **Top-N de respaldo por módulo**: lista global de ítems populares (por volumen de likes)
  diversificada por MMR, precomputada de forma asíncrona por módulo y no por usuario. Se usa ante
  cold start puro y se filtra por las restricciones del usuario concreto al servirse.
- **Versión de configuración del motor**: identificador único de un conjunto concreto de pesos
  alpha/beta/gamma, valor de k, magnitudes de refuerzo/penalización y parámetros de
  post-procesamiento. Vive en un archivo versionado dentro del repo y se despliega con el código;
  hay una sola activa por entorno. Hace atribuible y reproducible cualquier resultado, y permite que
  convivan top-N generados por versiones distintas.
- **Registro de sincronización**: estado y resultado de cada corrida del Data Transformer, con su
  marca temporal, para poder evaluar la frescura de los datos materializados.
- **Evento de actualización**: solicitud asíncrona de recálculo para un usuario (y módulo), con su
  identificador único que habilita el procesamiento idempotente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: La latencia de la operación de lectura del top-N permanece dentro del mismo umbral
  acordado (p95) cuando el catálogo crece al menos 10× respecto de la línea base; la variación
  atribuible al tamaño del catálogo es inferior al 10 %.
- **SC-002**: **0 %** de ítems que violen el filtro de edad en cualquier respuesta emitida —vigente
  u obsoleta— medido sobre el 100 % de las respuestas de una batería de verificación con usuarios de
  todos los rangos etarios.
- **SC-003**: **0 %** de ítems pertenecientes al conjunto de exclusión del usuario en cualquier
  respuesta emitida, incluidas las respuestas obsoletas.
- **SC-004**: **100 %** de los top-N servidos incluyen una versión de configuración del motor
  identificable y un estado de frescura explícito.
- **SC-005**: Reprocesar el mismo evento `recomendacion.actualizar` produce un top-N idéntico
  (mismos ítems, mismo orden, mismos scores) en el **100 %** de los casos de prueba.
- **SC-006**: Re-ejecutar una corrida completa del Data Transformer sobre datos sin cambios deja un
  estado materializado equivalente en el **100 %** de los casos, sin duplicados.
- **SC-007**: El **100 %** de los eventos con payload inválido termina en dead-letter con causa
  registrada; **0 %** se descarta silenciosamente.
- **SC-008**: Tras un vaciado total de la caché, el **100 %** de los top-N afectados se reconstruye
  mediante recálculo asíncrono, sin pérdida de datos autoritativos.
- **SC-009**: **0 %** de los requests de lectura ejecutan operaciones de scoring, similitud o
  diversificación, verificable por instrumentación, incluidos los requests que resultan en cache
  miss.
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
- **SC-015**: Ante una ráfaga de misses del mismo par (usuario, módulo) dentro de la ventana de
  supresión, se emite **una sola** señal de recálculo.
- **SC-016**: El **100 %** de las actividades sobre ítems con al menos un tag compartido propaga el
  recálculo al módulo opuesto, y el **0 %** de las actividades sin tags compartidos lo hace,
  verificable sobre una batería de casos con vocabulario controlado.
- **SC-017**: El **100 %** de los recálculos registra si alcanzó al módulo opuesto y por qué motivo,
  permitiendo auditar cualquier top-N que no se haya actualizado tras una actividad.
- **SC-018**: **0 %** de ítems con like, dislike o consumo registrado aparece en el top-N del
  usuario, verificable sobre el 100 % de las respuestas de la batería de exclusión.
- **SC-019**: Registrar un dislike reduce de forma medible el score de los ítems que comparten sus
  tags, y registrar un like lo aumenta, en el **100 %** de los casos de prueba controlados; un
  consumo sin like ni dislike deja los scores del resto del catálogo sin variación.
- **SC-020**: Tras un like posterior a un dislike sobre el mismo ítem, el efecto sobre el perfil
  corresponde al de la señal más reciente en el **100 %** de los casos de prueba.
- **SC-021**: Re-ejecutar un recálculo con la misma entrada y la misma versión de configuración
  reproduce exactamente el mismo top-N en el **100 %** de los casos, condición necesaria para la
  evaluación offline exigida antes de cambiar los pesos.
- **SC-022**: Un cambio de versión de configuración provoca **0** invalidaciones masivas y **0**
  respuestas sin etiqueta de versión; el **100 %** de los top-N previos sigue siendo servible.
- **SC-023**: La versión de configuración activa es consultable en tiempo de ejecución el **100 %**
  del tiempo de operación de cada componente.
- **SC-024**: El **100 %** de los usuarios sin actividad recibe un top-N de respaldo no vacío en
  ambos módulos, salvo que sus propios filtros obligatorios agoten los candidatos disponibles.
- **SC-025**: El top-N de respaldo cumple el mismo umbral de diversidad exigido en SC-011: ningún
  cluster de tags supera el porcentaje máximo acordado.
- **SC-026**: **0 %** de los top-N de respaldo servidos contiene ítems que violen el filtro de edad
  o de exclusión del usuario que los recibe.
- **SC-027**: El **100 %** de las respuestas de respaldo se marca como no personalizada, siendo
  distinguible de una recomendación personalizada y de ambos tipos de resultado vacío.

## Assumptions

- El consumidor exclusivo de este servicio es `api-general`; ningún frontend lo consulta directa ni
  indirectamente sin pasar por él.
- El contrato del evento `recomendacion.actualizar` y los contratos REST relevantes ya existen o
  serán definidos y documentados en `api-general` antes de la implementación; esta feature los
  consume, no los define. La exposición del estado de frescura (vigente/obsoleto/pendiente) en la
  respuesta requiere coordinación con `api-general` por ser parte del contrato compartido.
- `api-general` expone endpoints internos suficientes para obtener usuarios, catálogo (con tags y
  `age_rating`) y actividad para la sincronización. La actividad MUST permitir distinguir el tipo de
  señal (like, dislike, visto/jugado) y su marca temporal, ya que de esa distinción dependen tanto
  la exclusión como el efecto sobre el perfil de tags; si el contrato actual no lo expone, es una
  necesidad a coordinar con `api-general` antes de implementar.
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
  la caché, límite máximo de antigüedad para servir resultados obsoletos, ventana de supresión de
  señales de recálculo, frecuencia de sincronización, tamaño y periodicidad de actualización del
  top-N de respaldo, umbral de actividad mínima para considerar a un usuario personalizable, y
  porcentaje máximo por cluster se acordarán durante la planificación: la spec fija que deben
  existir, ser configurables y ser medibles, no sus valores.
- El prototipo Python existente en la raíz del workspace es material de referencia del
  comportamiento esperado y no condiciona el diseño de la solución.
- El broker de RabbitMQ es provisto y operado por el repo `notificaciones`; esta feature actúa
  únicamente como cliente consumidor.
