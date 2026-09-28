# Checklist de calidad de requisitos — bloque de clarificación 2026-09-14

**Archivo**: `checklists/requirements-clarify-2026-09-14.md`
**Creado**: 2026-09-17 | **Audiencia**: autor de la spec | **Profundidad**: estándar
**Estado**: **cerrado** — **46/46 tildados** (2026-09-27, a pedido del autor), 0 bloqueantes 🔴 abiertos *(el encabezado decía «ningún ítem tildado», anterior al cierre del 2026-09-22; recontado 2026-09-27)*

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

- [x] **CHK031** 🔴 ¿Está especificado qué ocurre si el vocabulario del módulo ofrece **menos de cinco
  tags** elegibles? FR-083 exige un mínimo de cinco y FR-088 rechaza toda solicitud sin declaración; si el
  catálogo no alcanza para satisfacer el mínimo, ningún usuario de ese módulo es atendible y **no hay
  texto que indique cuál de las dos reglas cede**. [Gap: FR-083, FR-088, DEP-10]
  > ✅ **RESUELTO (2026-09-22)** — declarado como **supuesto** en `spec.md` §*Assumptions*, con el costo escrito sin atenuar; RD-82. No se agregó CR-19 ni validación de arranque: no se introduce camino de código para un caso que no se espera.

- [x] **CHK032** ¿El valor del mínimo está declarado como **configuración versionada** y no como constante
  del texto? Responde FR-083: `declared_tags_min`, valor inicial 5, con prohibición explícita de quedar
  implícito en el código. Verificar que `data-model.md` §4 lo liste con el mismo nombre y valor.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — `data-model.md` §4 lista `declared_tags_min` = 5 con el mismo nombre (RD-68).

- [x] **CHK033** ¿El **momento** de la declaración es inequívoco? FR-084 lo fija al primer ingreso al
  módulo y no al alta de la cuenta. Verificar que ningún otro requisito —en particular FR-079a, que
  enumera lo obligatorio del formulario de alta— dé a entender lo contrario.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — FR-079a enumera solo `birth_date` y `region`; RD-69 declara «FR-079a no se toca».

- [x] **CHK034** ¿Está resuelto sin ambigüedad qué pasa con un usuario **activo en un solo módulo**?
  FR-084 declara que la declaración de un módulo no es condición para operar en el otro. Verificar que
  FR-088 no lo contradiga al rechazar por ausencia de declaración sin acotar el rechazo al módulo pedido.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — FR-088 rechaza por **módulo**; T055: «declarado en uno y no en el otro → rechazo sólo en el segundo».

- [x] **CHK035** ¿La herencia entre módulos de FR-085 distingue con claridad **incorporarse al insumo** de
  **contar para el mínimo**? FR-085 lo enuncia: los tags compartidos se incorporan pero no cuentan para el
  mínimo de FR-083. Verificar que la distinción sea verificable con un caso concreto —usuario con 5 tags
  compartidos y 0 propios en el módulo nuevo— y que el resultado esperado sea deducible del texto.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — caso concreto fijado en T054 (5 heredados / 0 propios → rechazo) y RD-97 (la herencia es derivada, nunca persistida).

- [x] **CHK036** ¿Está definido qué es «vocabulario compartido» de forma comprobable? FR-085 remite a
  FR-010b y a `tag_modules`. Verificar que la pertenencia de un tag a más de un módulo sea consultable y
  que no dependa de un criterio no persistido.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — la pertenencia vive en `tag_modules` (`data-model.md` §2.12), persistida y consultable; «compartido» = pertenece a más de un módulo.

- [x] **CHK037** ¿La no caducidad de FR-086 es compatible con el efecto del feedback? FR-086 separa
  **peso** en el perfil de **pertenencia** a la declaración: un dislike reduce la contribución, no borra
  la declaración. Verificar que FR-087 —perfil derivado y reconstruible— no introduzca un camino por el
  que un peso nulo equivalga en la práctica a la eliminación del tag.
  > ⏳ **Revisado 2026-09-27: pendiente de decisión** — un dislike sobre todos los ítems de un tag declarado puede llevar su contribución a cero o por debajo (pesos con signo, RD-68) sin borrar la fila; si eso equivale en la práctica a eliminarlo es una decisión de producto.
  >
  > ✅ **Resuelto 2026-09-27 por decisión del autor** — FR-086b: los dislikes pueden llevar el peso de un tag declarado a cero o a negativo; la declaración no se borra y sigue contando para el mínimo (RD-109).

- [x] **CHK038** ¿Existe requisito que permita al usuario **modificar o retirar** su declaración? FR-086
  prohíbe que caduque o se elimine *por efecto del feedback*, lo cual no es lo mismo que prohibir el
  cambio deliberado. Si la edición está fuera de alcance, debe estar declarada como tal.
  [Gap: FR-086, FR-089]
  > ⏳ **Revisado 2026-09-27: pendiente de decisión** — no existe requisito de edición o retiro deliberado de la declaración; debe decidirse si entra o se declara fuera de alcance (condiciona RD-97).
  >
  > ✅ **Resuelto 2026-09-27 por decisión del autor** — FR-086a: la declaración es definitiva; el usuario no puede modificarla ni retirarla, y una segunda declaración del mismo módulo se rechaza (RD-109).

- [x] **CHK039** 🔴 ¿El rechazo de FR-088 y la precedencia de estados de FR-056 están libres de conflicto?
  FR-088 califica la ausencia de declaración como **precondición incumplida** y prohíbe expresamente
  crear un sexto estado. Verificar que ningún requisito de la familia FR-056 la trate como resultado de
  cálculo, y que DEP-6 —acuerdo sobre el conjunto de estados— refleje que este caso **no** amplía el
  conjunto.
  > ✅ **RESUELTO (2026-09-22)** — FR-056 acotado a solicitudes que superaron precondiciones; DEP-6 ampliada con FR-088.

- [x] **CHK040** ¿La excepción de FR-089 —endpoint de escritura en una API declarada de solo lectura—
  está acotada de forma verificable? Responde FR-089b: el endpoint valida, resuelve herencia y persiste,
  y tiene prohibido ejecutar el motor o cómputo proporcional al catálogo. Verificar que el límite sea
  auditable sin leer la implementación.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — FR-089b enumera las tres operaciones admitidas; T053 lo vuelve auditable con un test que falla si se invoca el motor.

- [x] **CHK041** ¿**FR-089b es verificable**, o solo enunciable? «MUST NOT ejecutar cómputo proporcional
  al catálogo» necesita un criterio observable —cota de latencia, ausencia de lectura sobre tablas
  derivadas, o equivalente— para poder fallar un test. Si no lo tiene, es una intención, no un requisito.
  [Gap: FR-089b]
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — criterio observable en T053: el test falla si el motor es invocado (ausencia de llamada, no latencia).

- [x] **CHK042** ¿La confirmación síncrona de FR-089a tiene justificación trazable y condición de
  revisión? FR-089a la funda en que una confirmación asíncrona haría que FR-088 rechazara al usuario por
  no haber declarado lo que acaba de declarar. Verificar que la dependencia entre ambos quede explícita en
  el texto y no solo en RD-75.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — la dependencia FR-089a ↔ FR-088 está en el texto de FR-089a, no solo en RD-75.

- [x] **CHK043** ¿La tabla `user_declared_tags` (§2.14) tiene política de borrado declarada en **ambas**
  claves foráneas? El modelo especifica `user_id` con `ON DELETE CASCADE` y `tag_name` con `ON DELETE
  RESTRICT`. Verificar que RESTRICT sobre el tag sea coherente con la recomposición de vocabulario: un
  tag retirado del catálogo con declaraciones vivas bloquearía la operación.
  > ✅ **Resuelto 2026-09-27** — la restricción no bloquea la recomposición: recomponer crea una versión nueva de vocabulario y no borra filas de `tags`; un tag declarado fuera del vocabulario vigente pesa 0 y la declaración sigue contando (`data-model.md` §2.14).

- [x] **CHK044** ¿DI-28 está declarado como invariante **no verificable por esquema**? El mínimo de cinco
  tags no es expresable como restricción de tabla. Verificar que la excepción esté escrita como tal y que
  se designe la capa responsable de sostenerlo.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — DI-28 declarado como excepción no verificable por esquema (`data-model.md` §2.14 y §6, `plan.md` Anexo B); lo sostienen la transacción de declaración y T017.

---

## B. Supresión y purga

*(FR-068 … FR-068d1 · FR-091 … FR-095)*

- [x] **CHK045** 🔴 ¿El orden **caché antes que origen** de FR-092 es inequívoco y está protegido contra
  la carrera que declara? FR-092 exige invalidar la caché antes de eliminar el dato de origen y verificar
  que no haya recálculo en curso. Verificar que el texto diga qué hacer **si lo hay**: esperar, abortar o
  suprimir de todos modos son tres comportamientos distintos y el requisito no elige.
  > ✅ **RESUELTO (2026-09-22)** — FR-092a: se **aborta** el recálculo mediante marca consultada **justo antes de escribir**; `data-model.md` §7.11 paso 2 corregido (decía «suprimir el bloqueo», que no detiene al worker que ya lo tomó). RD-82.

- [x] **CHK046** 🔴 ¿La verificación de FR-095 declara **qué se registra, quién lo observa y qué pasa si
  falla**? El texto responde dos de las tres: registra el resultado de consultar cada almacén —incluido el
  caso negativo— y trata como **no completada** toda supresión sin constancia registrada, con reintento.
  **No designa observador** ni criterio de escalamiento si el reintento tampoco deja constancia.
  [Gap parcial: FR-095]
  > ✅ **RESUELTO (2026-09-22)** — FR-095a: métrica con valor esperado 0, acción alerta y dueño; reintento acotado con escalamiento a estado **fallido visible**. RD-83.

- [x] **CHK047** ¿El alcance de la constancia de FR-095 está acotado para no reintroducir el dato
  suprimido? FR-095 lo acota: identificador y marca temporal, nada más. Verificar que ese alcance sea
  suficiente para auditar y que no se solape con la retención de señales de FR-068a.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — FR-095 acota la constancia a identificador y marca temporal.

- [x] **CHK048** ¿«Cada almacén de su alcance» de FR-095 es enumerable sin ambigüedad? El texto nombra
  tablas normalizadas y claves de caché de ámbito de usuario. Verificar contra `data-model.md` §2 y §3 que
  la enumeración sea cerrada y que ninguna de las 7 familias de claves Redis quede fuera por omisión.
  > ✅ **RESUELTO (2026-09-22)** — `data-model.md` §7.11 incorpora `user_declared_tags`: cinco tablas, no cuatro. RD-86.

- [x] **CHK049** ¿FR-093 cubre **toda versión de configuración**, incluidas las inactivas? El texto lo
  afirma. Verificar que sea consistente con el versionado de claves `reco:v{cfg}:…`: una supresión que
  recorra solo la versión activa dejaría residuo en las anteriores, que es exactamente el fallo que
  FR-094 manda tratar como fallo y no como éxito degradado.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — `data-model.md` §7.11 paso 1 invalida «para **toda** `config_version` y módulo»; T058 lo exige.

- [x] **CHK050** ¿La spec declara explícitamente **qué no se puede deshacer**? RD-71 identifica tres
  entidades no regenerables (`user_signals`, `user_declared_tags`, `user_exclusions`) y RD-53 registra que
  el horizonte de retención puede acortarse pero **no alargarse**. Verificar que esa irreversibilidad esté
  enunciada en `spec.md` y no solo en el registro de decisión. [Gap probable: FR-068a, FR-091]
  > ⚠️ **Revisado 2026-09-27, no se cumple** — la irreversibilidad consta en el registro de clarificación de `spec.md` (RD-71, horizonte que se acorta pero no se alarga), pero en ningún FR.
  >
  > ✅ **Resuelto 2026-09-27 por decisión del autor** — FR-068e declara la irreversibilidad como requisito: cinco tablas no recuperables y reducción de la retención con aprobación (RD-110).

- [x] **CHK051** ¿FR-068b es verificable al arrancar? Exige que el horizonte de retención sea
  **estrictamente mayor** que toda ventana operativa. Verificar que todas las ventanas involucradas
  —`popularity_window_days` entre ellas— estén enumeradas, ya que una ventana no listada haría la
  comprobación incompleta sin que nadie lo note.
  > ⚠️ **Revisado 2026-09-27, no se cumple** — FR-068b dice «en particular» y nombra dos ventanas; RD-46 identifica una tercera —la reentrega de RabbitMQ— que el requisito no enumera.
  >
  > ✅ **Resuelto 2026-09-27 por decisión del autor** — FR-068b enumera sus ventanas en lista cerrada —popularidad, idempotencia y reentrega del broker (`event_redelivery_window_hours`)— y T004 valida las tres (RD-110).

- [x] **CHK052** ¿FR-068d y FR-068d1 están libres de conflicto? FR-068d exige que la exclusión persista
  aunque su señal de origen se haya purgado; FR-068d1 expone cuántas exclusiones quedaron huérfanas como
  medida **informativa y sin umbral de alerta**. Verificar que la métrica no induzca una acción correctiva
  que FR-068d prohíbe.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — FR-068d1 prohíbe usarla para disparar acciones; T042 exige verificar que **no** tenga alerta.

---

## C. Segmentación regional

*(FR-079, FR-079a, FR-081, FR-081a, FR-081b, FR-090, FR-090a · `region_weight_factor`)*

- [x] **CHK053** 🔴 ¿Está especificado qué ocurre con usuarios **preexistentes sin región**? FR-079a
  obliga a recoger región y fecha de nacimiento en el formulario de alta, lo que gobierna las altas
  futuras. No hay texto que resuelva el estado de un usuario ya creado sin ese dato, ni si la migración lo
  rechaza, lo completa o lo deja inatendible. [Gap: FR-079, FR-079a, CR-1]
  > ✅ **RESUELTO (2026-09-22)** — `data-model.md` §7.5 extendida a `region` con contador propio, §4.3 corregida, y **DEP-11** declarada (backfill previo al despliegue). RD-85.

- [x] **CHK054** ¿La obligatoriedad de FR-079a está acoplada a su consecuencia? El texto la justifica: un
  alta sin ambos datos produce un usuario que el motor no puede atender, y ambos condicionan el rechazo en
  la ingesta (FR-079, CR-1). Verificar que CR-1 exija efectivamente ambos campos.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — `birth_date` la exige CR-1 y `region` la exige CR-5 (modificada por RD-52): entre ambas cláusulas cubren los dos campos.

- [x] **CHK055** 🔴 ¿La «degradación continua» de FR-081a tiene **criterio verificable**? El requisito
  exige que en una región poco poblada el término colaborativo siga produciendo resultado en lugar de
  quedarse sin insumo, y prohíbe que exista un valor del factor que anule el aporte ajeno. Verificar que
  exista un umbral observable —número mínimo de vecinos, cobertura mínima— con el que un test pueda
  distinguir «degradó» de «se apagó». Sin él, el requisito no es falsable. [Gap: FR-081a]
  > ✅ **RESUELTO (2026-09-22)** — FR-096: `collab_min_neighbors` = 10 en `data-model.md` §4. El criterio falsable es el tamaño del vecindario, no el dominio del factor. RD-84.

- [x] **CHK056** ¿El dominio de FR-081b y el valor inicial de FR-090a son coherentes? FR-081b fija
  `0 <= region_weight_factor < 1`, inclusivo abajo y estricto arriba; FR-090a fija el arranque en **0,1**,
  que cae dentro del dominio. Verificar que `data-model.md` §4 declare el mismo intervalo y el mismo
  valor, con el límite inferior **inclusivo** — excluirlo volvía irrepresentable el neutro (RD-76).
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — `data-model.md` §4 declara `0 <= region_weight_factor < 1`, límite inferior inclusivo, y el valor 0,1.

- [x] **CHK057** ¿La prohibición del filtro duro es irrepresentable y no solo desaconsejada? FR-081a la
  enuncia y FR-081b la traduce en el extremo superior estricto del dominio. Verificar que la restricción
  viva en la **validación de carga de configuración** y no en una convención.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — la restricción vive en la validación de carga (`data-model.md` §4) y en T004.

- [x] **CHK058** ¿FR-090 y FR-090a están libres de conflicto? FR-090 exige que la segmentación *pueda*
  desactivarse (`factor = 0`); FR-090a exige que `v1` arranque **activo** en 0,1 y prohíbe arrancar
  desactivado. Verificar que la distinción capacidad/prescripción sea explícita, ya que RD-74 había
  prescrito lo contrario y fue revertida por RD-79.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — FR-090a separa capacidad y prescripción de forma explícita («revierte la prescripción de RD-74… no revierte la capacidad»).

- [x] **CHK059** ¿El costo declarado en FR-090a tiene condición de revisión asociada? El texto admite que
  `v1` **no observa la línea de base sin segmentación** y que medirla exige poner el factor en 0
  deliberadamente. Verificar que esa acción quede asignada a alguien o a alguna fase, o declarada fuera de
  alcance.
  > ✅ **Resuelto 2026-09-27** — la medición de línea de base queda declarada **fuera del alcance del MVP** en FR-090a: evaluación offline que solo corre si se activa la condición de revisión de FR-081, con una versión de configuración nueva.

- [x] **CHK060** ¿El nombre `region_weight_factor` induce a error sobre lo que mide? RD-76 lo registra
  expresamente: el parámetro mide **intensidad de segmentación**, de modo que `0` es el neutro y el nombre
  «se lee al revés». Verificar que la semántica esté escrita **donde el parámetro se declara** y no solo
  en el registro de decisión.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — `data-model.md` §4 escribe la semántica y la advertencia «el nombre se lee al revés» donde declara el parámetro; FR-081b la repite.

---

## D. Invalidación y disparo de recálculo

*(FR-080, FR-080a)*

- [x] **CHK061** 🔴 ¿El «mismo acto» de FR-080 está definido de forma verificable? El requisito prohíbe
  que exista una vía por la que el resultado se actualice y la caché sobreviva, pero **no declara qué
  garantiza la atomicidad** entre dos almacenes distintos (Postgres y Redis), que no comparten
  transacción. Sin criterio —orden de operaciones, compensación ante fallo parcial— el requisito es una
  prohibición sin mecanismo. [Gap: FR-080]
  > ✅ **RESUELTO (2026-09-22)** — verificado que el top-N vive **solo en Redis**: FR-080b lo declara y FR-080c fija «Redis primero, siempre». RD-84 no aplica; ver RD-81…RD-86 y la sesión 2026-09-22 de `spec.md`.

- [x] **CHK062** ¿FR-080 y FR-092 son compatibles en el orden que imponen? FR-092 exige invalidar la
  caché **antes** del origen en la supresión; FR-080 exige simultaneidad en la actualización. Verificar
  que no se lean como reglas de orden contradictorias para el mismo par de almacenes.
  > ✅ **RESUELTO (2026-09-22)** — disuelto por FR-080c: la regla única de orden cubre actualización y supresión sin modificar FR-080 ni FR-092.

- [x] **CHK063** ¿El umbral de FR-080a está declarado como configuración versionada? El texto lo exige
  explícitamente, prohíbe que quede implícito en el código y fija el valor inicial en **10 interacciones**.
  Verificar que `data-model.md` §4 lo clasifique como **operativo** y no como parámetro del motor —RD-63 y
  RD-13 fundan esa clasificación en que no altera el valor del top-N, solo cuándo se recomputa—.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — `data-model.md` §4 lo clasifica como operativo: no altera el valor del top-N, solo cuándo se recomputa.

- [x] **CHK064** ¿El conteo de FR-080a tiene reglas completas? El texto fija que se lleva **por usuario** y
  que **se reinicia al recalcular**. Verificar que esté resuelto si el conteo es por módulo o global al
  usuario, dado que el resto del modelo está segmentado por módulo.
  > ⏳ **Revisado 2026-09-27: pendiente de decisión** — FR-080a fija el conteo «por usuario» pero no dice qué módulos recalcula al alcanzarlo, ni dónde vive el contador (ninguna entidad lo contiene).
  > 🔄 *Mismo día, tras las decisiones del autor*: **dónde vive** quedó resuelto por RD-104 (derivado de `user_signals`, no almacenado). Sigue abierto **por usuario o por (usuario, módulo)** y qué módulos recalcula.
  >
  > ✅ **Resuelto 2026-09-27 por decisión del autor** — conteo por (usuario, módulo), derivado de `user_signals`; alcanzar el umbral recalcula ese módulo y el opuesto solo si corresponde propagar (FR-080a, RD-104).

---

## E. Dependencias externas nuevas

*(DEP-7, DEP-8, DEP-9, DEP-10)*

- [x] **CHK065** ¿Las cuatro están declaradas como **bloqueantes** y no como supuestos? Las cuatro figuran
  en la tabla «Dependencias Externas Bloqueantes» de `spec.md`. Verificar que ninguna aparezca además como
  supuesto en otra sección, lo que debilitaría su carácter.
  > ⚠️ **Revisado 2026-09-27, no se cumple** — DEP-10 aparece además en *Assumptions* (mínimo de 5 tags, RD-82). Fue deliberado al cerrar CHK031, pero es exactamente lo que este ítem pide revisar.
  >
  > ✅ **Resuelto 2026-09-27 por decisión del autor** — el mínimo de tags elegibles pasó de *Assumptions* a DEP-10, con métrica `declarable_tags_total{module}` y alerta (RD-110).

- [x] **CHK066** ¿Cada una declara su **consecuencia de incumplimiento** en términos de comportamiento
  observable? Responden las cuatro: DEP-7 «el término `α = 0,5` no se degrada: no existe»; DEP-8 sostiene
  la idempotencia de ingesta; DEP-9 condiciona la emisión por transición; DEP-10 «sin él no hay de dónde
  elegir». Verificar que ninguna consecuencia esté formulada como riesgo genérico.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — las consecuencias de DEP-7…DEP-10 están formuladas como comportamiento observable en la tabla de `spec.md`.

- [x] **CHK067** 🔴 ¿DEP-10 está correctamente acoplada a FR-082 y FR-083? La tabla la vincula a FR-082,
  FR-083 y RD-68. Verificar que el acoplamiento sea de **vocabulario disponible**, no de tags por ítem
  —esa es DEP-7—, y que la distinción *por ítem* / *sobre el conjunto* quede escrita, ya que ambas
  podrían leerse como la misma exigencia.
  > ✅ **RESUELTO (2026-09-22)** — distinción *por ítem* / *sobre el conjunto* escrita en DEP-7 y DEP-10.

- [x] **CHK068** ¿DEP-10 declara su severidad diferencial? Es la única dependencia cuyo incumplimiento
  deja al sistema **sin ningún usuario atendible**, por encadenamiento con FR-088. Verificar que esa
  consecuencia esté en el texto de la dependencia y no solo en RD-72.
  > ✅ **RESUELTO (2026-09-22)** — separados los ejes de severidad: DEP-7 para el motor, DEP-10 para la cobertura de usuarios.

- [x] **CHK069** ¿DEP-9 distingue lo que el origen **puede** hacer de lo que **no puede**? El texto lo
  hace: el origen puede almacenar estado; lo que no puede es dejar una transición sin emitir o reemitirla
  bajo el identificador anterior. Verificar que sea consistente con FR-029e y FR-029e1.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — DEP-9 distingue «puede almacenar estado» de «no puede omitir la emisión»; coincide con FR-029e y FR-029e1.

- [x] **CHK070** ¿DEP-3 está declarada como **vacante a propósito**? El identificador fue retirado y no se
  reutiliza, por historial de colisiones. Verificar que la tabla lo indique explícitamente, de modo que un
  lector no lo interprete como omisión.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — la tabla de `spec.md` incluye desde el 2026-09-27 una fila `~~DEP-3~~` «vacante a propósito».

---

## F. Consistencia entre artefactos

- [x] **CHK071** 🔴 **Colisión de numeración FR-070.** El identificador designa **dos requisitos
  distintos**: el desempate entre ítems con idéntico score, y la familia de supresión FR-091…FR-095. Un
  lector que siga «FR-070» desde FR-093 llega al requisito equivocado. Verificar si se renumera la
  familia de supresión, se renumera el desempate, o se declara la homonimia — dado que el documento ya
  acumula tres incidentes de identificador reutilizado y mantiene DEP-3 vacante por esa razón.
  [Conflicto confirmado: `spec.md` línea ~560 vs ~930]
  > ✅ **RESUELTO (2026-09-22)** — renumerada la familia de supresión a FR-091…FR-095; RD-81. Identificadores viejos retirados y no reasignables.

- [x] **CHK072** ¿Todo FR nuevo tiene al menos un **SC que lo verifique**, o está declarado como no
  medible por diseño? Los criterios vigentes son SC-001…SC-027 y **ninguno se agregó durante la sesión del
  2026-09-14**, mientras el bloque FR-079…FR-090 sí. Verificar SC por SC cuáles cubren declaración de
  gustos, supresión verificada y segmentación regional; los que queden sin cobertura deben recibir SC o
  declararse no medibles. [Gap probable: FR-082…FR-090a]
  > ⏳ **Revisado 2026-09-27: pendiente de decisión** — ningún SC se agregó para FR-079…FR-096; hay que decidir si reciben SC o se declaran no medibles.
  >
  > ✅ **Resuelto 2026-09-27** — se agregan **SC-028…SC-031** (datos de alta, declaración, supresión, ponderación regional), atribuidos a T029, T053/T055, T059 y T061.

- [x] **CHK073** 🔴 **`data-model.md` declara un número de tablas inconsistente con las que enumera.** El
  documento afirma «§2 pasa a **15 tablas** — cifra final y única» y repite el 15 en la verificación
  entidad por entidad. La enumeración real son **16**: 14 subsecciones, donde §2.3 agrupa `tags` +
  `item_tags` y §2.13 agrupa `vocab_versions` + `vocab_version_tags`. La cifra quedó desactualizada al
  incorporarse §2.14 `user_declared_tags`. Verificar y corregir las tres menciones.
  [Desfasaje confirmado: `data-model.md`]
  > ✅ **RESUELTO (2026-09-22)** — corregida la única mención prescriptiva («cifra final y única») a **16 tablas**; las demás son registro histórico fechado y se conservan.

- [x] **CHK074** ¿`plan.md` refleja el estado vigente de los parámetros? Verificar que el inventario de
  configuración del plan coincida con `data-model.md` §4 en los valores fijados después del 2026-09-14
  —`top_n_min`/`top_n_default`/`top_n_max`, `fallback_new_item_quota_ratio`, `region_weight_factor`,
  pesos de señal— y que liste los parámetros **eliminados** como tales.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — tras el saneamiento del 2026-09-27, `plan.md` §2 lista los valores vigentes (incluidos `collab_min_neighbors` y `version_label`) y los parámetros eliminados con su motivo.

- [x] **CHK075** ¿La afirmación «todo lo necesario para recalcular vive en Postgres» fue retirada de todos
  los artefactos? RD-71 la declara **falsa** para las tres entidades de autoría local. Verificar que no
  sobreviva en `plan.md` ni en `tasks.md`.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — `plan.md` solo la conserva en el Anexo A como afirmación corregida («Falso»); `tasks.md` T003 habla de los **insumos**, que sí residen en Postgres.

- [x] **CHK076** ¿`tasks.md` cubre la funcionalidad que FR-088 vuelve bloqueante? El encabezado de
  `tasks.md` sigue declarando «FR-001→FR-071, 5 clarificaciones», y **la declaración de gustos no tiene
  tarea asignada** entre las 50 existentes. Con ese plan de tareas, la Fase 1 produce un sistema que
  rechaza al 100 % de sus usuarios. Verificar antes de dar por completable el milestone de API.
  > 🔎 **Verificado 2026-09-27** *(tildado 2026-09-27 a pedido del autor, tras reverificar la evidencia)* — T053, T054 y T055 cubren la declaración y el rechazo en Fase 1, y el encabezado de `tasks.md` está recontado.

---

## Cobertura declarada

**FR nuevos con ítem asignado**: FR-068a, FR-068b, FR-068d, FR-068d1, FR-091, FR-092, FR-093, FR-094,
FR-095, FR-079, FR-079a, FR-080, FR-080a, FR-081, FR-081a, FR-081b, FR-082, FR-083, FR-084, FR-085,
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

**Total**: 46 ítems (CHK031 … CHK076) · **10 marcados 🔴** · **46 tildados** (recontado 2026-09-27, tras las decisiones del autor)

**Los 10 bloqueantes**: CHK031, CHK039, CHK045, CHK046, CHK053, CHK055, CHK061, CHK067, CHK071, CHK073.
