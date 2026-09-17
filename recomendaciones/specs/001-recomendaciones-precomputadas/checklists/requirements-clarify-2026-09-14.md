# Checklist de calidad de requisitos — bloque de clarificación 2026-09-14

**Archivo**: `checklists/requirements-clarify-2026-09-14.md`
**Creado**: 2026-09-17 | **Audiencia**: autor de la spec | **Profundidad**: estándar
**Estado**: abierto para revisión — **ningún ítem tildado**

---

## Alcance y relación con el checklist existente

Este checklist es **complementario, no sustituto**, de `requirements-contracts.md` (2026-09-08, 30/30
resueltos). Aquellos 30 ítems siguen vigentes y **no se re-auditan acá**.

`requirements-contracts.md` cita como requisito más alto FR-071. Después de esa fecha ocurrió la sesión
de clarificación del 2026-09-14 y el modelo de datos cerró hasta RD-80. El bloque de requisitos base
FR-079 → FR-090 —más los sufijos de FR-068 y FR-070 que la misma sesión reescribió— **nunca pasó por una
auditoría de calidad de requisitos**. Eso es lo que se cubre acá.

**Qué se audita**: si el texto del requisito es inequívoco, verificable, completo y libre de conflicto con
otro texto. **Qué no se audita**: la implementación, que no existe.

🔴 = sin resolver, la feature queda **no implementable o insegura**.

---

## A. Declaración de gustos del usuario

*(FR-082 … FR-089b · `data-model.md` §2.14 `user_declared_tags` · RD-68, RD-69, RD-70)*

- [ ] **CHK031** 🔴 ¿Está especificado qué ocurre si el vocabulario del módulo ofrece **menos de cinco
  tags** elegibles? FR-083 exige un mínimo de cinco y FR-088 rechaza toda solicitud sin declaración; si el
  catálogo no alcanza para satisfacer el mínimo, ningún usuario de ese módulo es atendible y **no hay
  texto que indique cuál de las dos reglas cede**. [Gap: FR-083, FR-088, DEP-10]

- [ ] **CHK032** ¿El valor del mínimo está declarado como **configuración versionada** y no como constante
  del texto? Responde FR-083: `declared_tags_min`, valor inicial 5, con prohibición explícita de quedar
  implícito en el código. Verificar que `data-model.md` §4 lo liste con el mismo nombre y valor.

- [ ] **CHK033** ¿El **momento** de la declaración es inequívoco? FR-084 lo fija al primer ingreso al
  módulo y no al alta de la cuenta. Verificar que ningún otro requisito —en particular FR-079a, que
  enumera lo obligatorio del formulario de alta— dé a entender lo contrario.

- [ ] **CHK034** ¿Está resuelto sin ambigüedad qué pasa con un usuario **activo en un solo módulo**?
  FR-084 declara que la declaración de un módulo no es condición para operar en el otro. Verificar que
  FR-088 no lo contradiga al rechazar por ausencia de declaración sin acotar el rechazo al módulo pedido.

- [ ] **CHK035** ¿La herencia entre módulos de FR-085 distingue con claridad **incorporarse al insumo** de
  **contar para el mínimo**? FR-085 lo enuncia: los tags compartidos se incorporan pero no cuentan para el
  mínimo de FR-083. Verificar que la distinción sea verificable con un caso concreto —usuario con 5 tags
  compartidos y 0 propios en el módulo nuevo— y que el resultado esperado sea deducible del texto.

- [ ] **CHK036** ¿Está definido qué es «vocabulario compartido» de forma comprobable? FR-085 remite a
  FR-010b y a `tag_modules`. Verificar que la pertenencia de un tag a más de un módulo sea consultable y
  que no dependa de un criterio no persistido.

- [ ] **CHK037** ¿La no caducidad de FR-086 es compatible con el efecto del feedback? FR-086 separa
  **peso** en el perfil de **pertenencia** a la declaración: un dislike reduce la contribución, no borra
  la declaración. Verificar que FR-087 —perfil derivado y reconstruible— no introduzca un camino por el
  que un peso nulo equivalga en la práctica a la eliminación del tag.

- [ ] **CHK038** ¿Existe requisito que permita al usuario **modificar o retirar** su declaración? FR-086
  prohíbe que caduque o se elimine *por efecto del feedback*, lo cual no es lo mismo que prohibir el
  cambio deliberado. Si la edición está fuera de alcance, debe estar declarada como tal.
  [Gap: FR-086, FR-089]

- [ ] **CHK039** 🔴 ¿El rechazo de FR-088 y la precedencia de estados de FR-056 están libres de conflicto?
  FR-088 califica la ausencia de declaración como **precondición incumplida** y prohíbe expresamente
  crear un sexto estado. Verificar que ningún requisito de la familia FR-056 la trate como resultado de
  cálculo, y que DEP-6 —acuerdo sobre el conjunto de estados— refleje que este caso **no** amplía el
  conjunto.

- [ ] **CHK040** ¿La excepción de FR-089 —endpoint de escritura en una API declarada de solo lectura—
  está acotada de forma verificable? Responde FR-089b: el endpoint valida, resuelve herencia y persiste,
  y tiene prohibido ejecutar el motor o cómputo proporcional al catálogo. Verificar que el límite sea
  auditable sin leer la implementación.

- [ ] **CHK041** ¿**FR-089b es verificable**, o solo enunciable? «MUST NOT ejecutar cómputo proporcional
  al catálogo» necesita un criterio observable —cota de latencia, ausencia de lectura sobre tablas
  derivadas, o equivalente— para poder fallar un test. Si no lo tiene, es una intención, no un requisito.
  [Gap: FR-089b]

- [ ] **CHK042** ¿La confirmación síncrona de FR-089a tiene justificación trazable y condición de
  revisión? FR-089a la funda en que una confirmación asíncrona haría que FR-088 rechazara al usuario por
  no haber declarado lo que acaba de declarar. Verificar que la dependencia entre ambos quede explícita en
  el texto y no solo en RD-75.

- [ ] **CHK043** ¿La tabla `user_declared_tags` (§2.14) tiene política de borrado declarada en **ambas**
  claves foráneas? El modelo especifica `user_id` con `ON DELETE CASCADE` y `tag_name` con `ON DELETE
  RESTRICT`. Verificar que RESTRICT sobre el tag sea coherente con la recomposición de vocabulario: un
  tag retirado del catálogo con declaraciones vivas bloquearía la operación.

- [ ] **CHK044** ¿DI-28 está declarado como invariante **no verificable por esquema**? El mínimo de cinco
  tags no es expresable como restricción de tabla. Verificar que la excepción esté escrita como tal y que
  se designe la capa responsable de sostenerlo.

---

## B. Supresión y purga

*(FR-068 … FR-068d1 · FR-070a … FR-070e)*

- [ ] **CHK045** 🔴 ¿El orden **caché antes que origen** de FR-070b es inequívoco y está protegido contra
  la carrera que declara? FR-070b exige invalidar la caché antes de eliminar el dato de origen y verificar
  que no haya recálculo en curso. Verificar que el texto diga qué hacer **si lo hay**: esperar, abortar o
  suprimir de todos modos son tres comportamientos distintos y el requisito no elige.

- [ ] **CHK046** 🔴 ¿La verificación de FR-070e declara **qué se registra, quién lo observa y qué pasa si
  falla**? El texto responde dos de las tres: registra el resultado de consultar cada almacén —incluido el
  caso negativo— y trata como **no completada** toda supresión sin constancia registrada, con reintento.
  **No designa observador** ni criterio de escalamiento si el reintento tampoco deja constancia.
  [Gap parcial: FR-070e]

- [ ] **CHK047** ¿El alcance de la constancia de FR-070e está acotado para no reintroducir el dato
  suprimido? FR-070e lo acota: identificador y marca temporal, nada más. Verificar que ese alcance sea
  suficiente para auditar y que no se solape con la retención de señales de FR-068a.

- [ ] **CHK048** ¿«Cada almacén de su alcance» de FR-070e es enumerable sin ambigüedad? El texto nombra
  tablas normalizadas y claves de caché de ámbito de usuario. Verificar contra `data-model.md` §2 y §3 que
  la enumeración sea cerrada y que ninguna de las 7 familias de claves Redis quede fuera por omisión.

- [ ] **CHK049** ¿FR-070c cubre **toda versión de configuración**, incluidas las inactivas? El texto lo
  afirma. Verificar que sea consistente con el versionado de claves `reco:v{cfg}:…`: una supresión que
  recorra solo la versión activa dejaría residuo en las anteriores, que es exactamente el fallo que
  FR-070d manda tratar como fallo y no como éxito degradado.

- [ ] **CHK050** ¿La spec declara explícitamente **qué no se puede deshacer**? RD-71 identifica tres
  entidades no regenerables (`user_signals`, `user_declared_tags`, `user_exclusions`) y RD-53 registra que
  el horizonte de retención puede acortarse pero **no alargarse**. Verificar que esa irreversibilidad esté
  enunciada en `spec.md` y no solo en el registro de decisión. [Gap probable: FR-068a, FR-070a]

- [ ] **CHK051** ¿FR-068b es verificable al arrancar? Exige que el horizonte de retención sea
  **estrictamente mayor** que toda ventana operativa. Verificar que todas las ventanas involucradas
  —`popularity_window_days` entre ellas— estén enumeradas, ya que una ventana no listada haría la
  comprobación incompleta sin que nadie lo note.

- [ ] **CHK052** ¿FR-068d y FR-068d1 están libres de conflicto? FR-068d exige que la exclusión persista
  aunque su señal de origen se haya purgado; FR-068d1 expone cuántas exclusiones quedaron huérfanas como
  medida **informativa y sin umbral de alerta**. Verificar que la métrica no induzca una acción correctiva
  que FR-068d prohíbe.

---

## C. Segmentación regional

*(FR-079, FR-079a, FR-081, FR-081a, FR-081b, FR-090, FR-090a · `region_weight_factor`)*

- [ ] **CHK053** 🔴 ¿Está especificado qué ocurre con usuarios **preexistentes sin región**? FR-079a
  obliga a recoger región y fecha de nacimiento en el formulario de alta, lo que gobierna las altas
  futuras. No hay texto que resuelva el estado de un usuario ya creado sin ese dato, ni si la migración lo
  rechaza, lo completa o lo deja inatendible. [Gap: FR-079, FR-079a, CR-1]

- [ ] **CHK054** ¿La obligatoriedad de FR-079a está acoplada a su consecuencia? El texto la justifica: un
  alta sin ambos datos produce un usuario que el motor no puede atender, y ambos condicionan el rechazo en
  la ingesta (FR-079, CR-1). Verificar que CR-1 exija efectivamente ambos campos.

- [ ] **CHK055** 🔴 ¿La «degradación continua» de FR-081a tiene **criterio verificable**? El requisito
  exige que en una región poco poblada el término colaborativo siga produciendo resultado en lugar de
  quedarse sin insumo, y prohíbe que exista un valor del factor que anule el aporte ajeno. Verificar que
  exista un umbral observable —número mínimo de vecinos, cobertura mínima— con el que un test pueda
  distinguir «degradó» de «se apagó». Sin él, el requisito no es falsable. [Gap: FR-081a]

- [ ] **CHK056** ¿El dominio de FR-081b y el valor inicial de FR-090a son coherentes? FR-081b fija
  `0 <= region_weight_factor < 1`, inclusivo abajo y estricto arriba; FR-090a fija el arranque en **0,1**,
  que cae dentro del dominio. Verificar que `data-model.md` §4 declare el mismo intervalo y el mismo
  valor, con el límite inferior **inclusivo** — excluirlo volvía irrepresentable el neutro (RD-76).

- [ ] **CHK057** ¿La prohibición del filtro duro es irrepresentable y no solo desaconsejada? FR-081a la
  enuncia y FR-081b la traduce en el extremo superior estricto del dominio. Verificar que la restricción
  viva en la **validación de carga de configuración** y no en una convención.

- [ ] **CHK058** ¿FR-090 y FR-090a están libres de conflicto? FR-090 exige que la segmentación *pueda*
  desactivarse (`factor = 0`); FR-090a exige que `v1` arranque **activo** en 0,1 y prohíbe arrancar
  desactivado. Verificar que la distinción capacidad/prescripción sea explícita, ya que RD-74 había
  prescrito lo contrario y fue revertida por RD-79.

- [ ] **CHK059** ¿El costo declarado en FR-090a tiene condición de revisión asociada? El texto admite que
  `v1` **no observa la línea de base sin segmentación** y que medirla exige poner el factor en 0
  deliberadamente. Verificar que esa acción quede asignada a alguien o a alguna fase, o declarada fuera de
  alcance.

- [ ] **CHK060** ¿El nombre `region_weight_factor` induce a error sobre lo que mide? RD-76 lo registra
  expresamente: el parámetro mide **intensidad de segmentación**, de modo que `0` es el neutro y el nombre
  «se lee al revés». Verificar que la semántica esté escrita **donde el parámetro se declara** y no solo
  en el registro de decisión.

---

## D. Invalidación y disparo de recálculo

*(FR-080, FR-080a)*

- [ ] **CHK061** 🔴 ¿El «mismo acto» de FR-080 está definido de forma verificable? El requisito prohíbe
  que exista una vía por la que el resultado se actualice y la caché sobreviva, pero **no declara qué
  garantiza la atomicidad** entre dos almacenes distintos (Postgres y Redis), que no comparten
  transacción. Sin criterio —orden de operaciones, compensación ante fallo parcial— el requisito es una
  prohibición sin mecanismo. [Gap: FR-080]

- [ ] **CHK062** ¿FR-080 y FR-070b son compatibles en el orden que imponen? FR-070b exige invalidar la
  caché **antes** del origen en la supresión; FR-080 exige simultaneidad en la actualización. Verificar
  que no se lean como reglas de orden contradictorias para el mismo par de almacenes.

- [ ] **CHK063** ¿El umbral de FR-080a está declarado como configuración versionada? El texto lo exige
  explícitamente, prohíbe que quede implícito en el código y fija el valor inicial en **10 interacciones**.
  Verificar que `data-model.md` §4 lo clasifique como **operativo** y no como parámetro del motor —RD-63 y
  RD-13 fundan esa clasificación en que no altera el valor del top-N, solo cuándo se recomputa—.

- [ ] **CHK064** ¿El conteo de FR-080a tiene reglas completas? El texto fija que se lleva **por usuario** y
  que **se reinicia al recalcular**. Verificar que esté resuelto si el conteo es por módulo o global al
  usuario, dado que el resto del modelo está segmentado por módulo.

---

## E. Dependencias externas nuevas

*(DEP-7, DEP-8, DEP-9, DEP-10)*

- [ ] **CHK065** ¿Las cuatro están declaradas como **bloqueantes** y no como supuestos? Las cuatro figuran
  en la tabla «Dependencias Externas Bloqueantes» de `spec.md`. Verificar que ninguna aparezca además como
  supuesto en otra sección, lo que debilitaría su carácter.

- [ ] **CHK066** ¿Cada una declara su **consecuencia de incumplimiento** en términos de comportamiento
  observable? Responden las cuatro: DEP-7 «el término `α = 0,5` no se degrada: no existe»; DEP-8 sostiene
  la idempotencia de ingesta; DEP-9 condiciona la emisión por transición; DEP-10 «sin él no hay de dónde
  elegir». Verificar que ninguna consecuencia esté formulada como riesgo genérico.

- [ ] **CHK067** 🔴 ¿DEP-10 está correctamente acoplada a FR-082 y FR-083? La tabla la vincula a FR-082,
  FR-083 y RD-68. Verificar que el acoplamiento sea de **vocabulario disponible**, no de tags por ítem
  —esa es DEP-7—, y que la distinción *por ítem* / *sobre el conjunto* quede escrita, ya que ambas
  podrían leerse como la misma exigencia.

- [ ] **CHK068** ¿DEP-10 declara su severidad diferencial? Es la única dependencia cuyo incumplimiento
  deja al sistema **sin ningún usuario atendible**, por encadenamiento con FR-088. Verificar que esa
  consecuencia esté en el texto de la dependencia y no solo en RD-72.

- [ ] **CHK069** ¿DEP-9 distingue lo que el origen **puede** hacer de lo que **no puede**? El texto lo
  hace: el origen puede almacenar estado; lo que no puede es dejar una transición sin emitir o reemitirla
  bajo el identificador anterior. Verificar que sea consistente con FR-029e y FR-029e1.

- [ ] **CHK070** ¿DEP-3 está declarada como **vacante a propósito**? El identificador fue retirado y no se
  reutiliza, por historial de colisiones. Verificar que la tabla lo indique explícitamente, de modo que un
  lector no lo interprete como omisión.

---

## F. Consistencia entre artefactos

- [ ] **CHK071** 🔴 **Colisión de numeración FR-070.** El identificador designa **dos requisitos
  distintos**: el desempate entre ítems con idéntico score, y la familia de supresión FR-070a…FR-070e. Un
  lector que siga «FR-070» desde FR-070c llega al requisito equivocado. Verificar si se renumera la
  familia de supresión, se renumera el desempate, o se declara la homonimia — dado que el documento ya
  acumula tres incidentes de identificador reutilizado y mantiene DEP-3 vacante por esa razón.
  [Conflicto confirmado: `spec.md` línea ~560 vs ~930]

- [ ] **CHK072** ¿Todo FR nuevo tiene al menos un **SC que lo verifique**, o está declarado como no
  medible por diseño? Los criterios vigentes son SC-001…SC-027 y **ninguno se agregó durante la sesión del
  2026-09-14**, mientras el bloque FR-079…FR-090 sí. Verificar SC por SC cuáles cubren declaración de
  gustos, supresión verificada y segmentación regional; los que queden sin cobertura deben recibir SC o
  declararse no medibles. [Gap probable: FR-082…FR-090a]

- [ ] **CHK073** 🔴 **`data-model.md` declara un número de tablas inconsistente con las que enumera.** El
  documento afirma «§2 pasa a **15 tablas** — cifra final y única» y repite el 15 en la verificación
  entidad por entidad. La enumeración real son **16**: 14 subsecciones, donde §2.3 agrupa `tags` +
  `item_tags` y §2.13 agrupa `vocab_versions` + `vocab_version_tags`. La cifra quedó desactualizada al
  incorporarse §2.14 `user_declared_tags`. Verificar y corregir las tres menciones.
  [Desfasaje confirmado: `data-model.md`]

- [ ] **CHK074** ¿`plan.md` refleja el estado vigente de los parámetros? Verificar que el inventario de
  configuración del plan coincida con `data-model.md` §4 en los valores fijados después del 2026-09-14
  —`top_n_min`/`top_n_default`/`top_n_max`, `fallback_new_item_quota_ratio`, `region_weight_factor`,
  pesos de señal— y que liste los parámetros **eliminados** como tales.

- [ ] **CHK075** ¿La afirmación «todo lo necesario para recalcular vive en Postgres» fue retirada de todos
  los artefactos? RD-71 la declara **falsa** para las tres entidades de autoría local. Verificar que no
  sobreviva en `plan.md` ni en `tasks.md`.

- [ ] **CHK076** ¿`tasks.md` cubre la funcionalidad que FR-088 vuelve bloqueante? El encabezado de
  `tasks.md` sigue declarando «FR-001→FR-071, 5 clarificaciones», y **la declaración de gustos no tiene
  tarea asignada** entre las 50 existentes. Con ese plan de tareas, la Fase 1 produce un sistema que
  rechaza al 100 % de sus usuarios. Verificar antes de dar por completable el milestone de API.

---

## Cobertura declarada

**FR nuevos con ítem asignado**: FR-068a, FR-068b, FR-068d, FR-068d1, FR-070a, FR-070b, FR-070c, FR-070d,
FR-070e, FR-079, FR-079a, FR-080, FR-080a, FR-081, FR-081a, FR-081b, FR-082, FR-083, FR-084, FR-085,
FR-086, FR-087, FR-088, FR-089, FR-089a, FR-089b, FR-090, FR-090a.

**FR nuevos SIN ítem propio, y por qué**:

| Requisito | Motivo de la exclusión |
|---|---|
| FR-068 (enunciado general) | Es el encabezado de la familia; su contenido se audita en los sufijos FR-068a…FR-068d1 (CHK051, CHK052) |
| FR-068c | Verificación previa a la purga de una señal de consumo. Cubierto indirectamente por CHK051 (ventanas) y CHK052 (exclusiones huérfanas); no se le asignó ítem propio por no haber cambiado su comportamiento en la sesión del 2026-09-14 |
| FR-029e, FR-029e1 | Reformulados en la sesión, pero pertenecen a la disciplina de emisión de señales, no a las cinco áreas del alcance pedido. Solo se los cita como referencia cruzada en CHK069 |
| FR-033a6 … FR-033a8 | Cuota de novedades. Cambiaron **después** del 2026-09-14 (RD-77, RD-78, RD-80) y no forman parte del bloque que este checklist audita. **Requieren checklist propio** |
| FR-006a | `top_n_min`. Introducido por RD-78, posterior a la sesión auditada. Misma observación |
| FR-021b, FR-022c, FR-056a | Revisados en la sesión pero ya cubiertos por ítems vigentes de `requirements-contracts.md` |

**Declaración de límite**: este checklist audita el bloque **FR-079 → FR-090a** más los sufijos de FR-068
y FR-070 reescritos el 2026-09-14. **No cubre** las decisiones RD-77 a RD-80 (cuota proporcional, cota
inferior de `top_n`, eliminación del piso), que son posteriores y quedan sin auditoría de requisitos.

**Hallazgos confirmados durante la redacción** —verificados contra el texto, no supuestos—: la colisión
FR-070 (CHK071), el desfasaje del conteo de tablas (CHK073) y la ausencia de SC nuevos para el bloque
completo (CHK072).

---

**Total**: 46 ítems (CHK031 … CHK076) · **10 marcados 🔴** · **0 tildados**

**Los 10 bloqueantes**: CHK031, CHK039, CHK045, CHK046, CHK053, CHK055, CHK061, CHK067, CHK071, CHK073.
