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

### Session 2026-09-14

- **Q**: ¿Qué constituye «popularidad» para el conjunto de respaldo (FR-033a1)? → **A**: **Límite inferior del intervalo de confianza de Wilson** sobre la proporción de señales positivas. Se descartan el recuento bruto —que encabeza con ítems polarizantes—, la diferencia —dominada por el volumen— y la proporción cruda —que encabeza con ítems de muy pocas señales—. La definición exige persistir el numerador y el denominador —`like_count` y `engaged_user_count`, precisados en Q7—, y **agrega un parámetro nuevo a la configuración del motor**: `popularity_confidence_z`, el nivel de confianza del estimador. El puntaje se **materializa** en `item_popularity.popularity_score`: no se calcula al servir ni al ordenar. Con cero señales el puntaje es `0`. Cambiar `popularity_confidence_z` obliga a recalcular el puntaje de todo el catálogo, pero **no** a recorrer el historial de señales, porque los recuentos quedan persistidos. El desempate a igual score pasa a ser por `popularity_score`.
- **Q**: ¿Participan las señales de consumo del cálculo de popularidad? → **A**: **Sí, en el denominador y no en el numerador**. El puntaje mide *«de quienes interactuaron con el ítem, qué proporción lo likeó»*. No contradice FR-022b: el consumo sigue sin expresar preferencia, pero sí constituye la oportunidad de expresarla. **El denominador cuenta usuarios distintos, no señales**: sumar los recuentos por tipo contaría dos veces a quien consumió y además likeó —un ítem unánimemente likeado puntuaría como si la mitad lo hubiera rechazado, y el sesgo castigaría más a los ítems mejores—. Se persisten numerador y denominador; **no** se persiste un recuento de dislikes ni de consumos por separado, porque ninguna consulta los necesita. Costo aceptado: esta definición penaliza a los ítems recién ingresados, que acumulan consumos antes que likes; queda registrado como pendiente de revisión con una métrica asociada, sin corregirlo por anticipación.
- **Q**: ¿Cuál es la política de retención de las señales de actividad (NC-2)? → **A**: **Purga por antigüedad con horizonte largo**, declarado como parámetro de configuración. Se descarta la retención indefinida —que deja al sistema sin mecanismo de supresión y resuelve la primera obligación legal de borrado con una operación manual en producción— y se descarta la purga de horizonte corto, que erosiona la evidencia del filtrado colaborativo, única dimensión donde conservar historial mejora efectivamente el motor. La popularidad **no se ve afectada** mientras el horizonte supere su ventana, porque el puntaje solo considera señales dentro de ella. Lo que se pierde es la **verificabilidad** de las exclusiones permanentes, no las exclusiones mismas: ya están materializadas, y la reconstrucción sobre ellas es aditiva. **No se fija el número**: es empírico y depende del aporte del historial antiguo al filtrado colaborativo, que no es medible antes de tener tráfico. Se registra que el horizonte **puede acortarse más adelante pero no alargarse**, porque lo purgado no vuelve; por eso el valor inicial debe ser conservador.

- **Q**: ¿De dónde proviene la escala de clasificación etaria (NC-4)? → **A**: **Catálogo propio de RecoMe**, de tres niveles (`ATP`, `+13`, `+18`), definido en este repositorio. Lo decide el dato: `api-general` ya emite un vocabulario propio y único para ambos módulos, y mapear a estándares externos exigiría **dos vocabularios** —cine y videojuegos usan sistemas distintos—, lo que rompe la escala ordinal única o convierte el permiso etario del usuario en un valor por módulo; ambas modifican el esquema. Se descartan también la edad mínima numérica —elimina la escala ordinal que evita aritmética en runtime— y la escala binaria —hace irrepresentable toda gradación futura sin migración—. **Costo aceptado**: los umbrales no tienen respaldo normativo externo que invocar. Revisable si surge una obligación legal o una expansión a jurisdicciones con normativa propia.
- **Nota de autoridad**: `api-general` está incompleta y a la espera de este modelo. La prioridad de definición de este repositorio deja de ser una postura de diseño y pasa a ser la secuencia real de trabajo: los pendientes formulados como «¿el origen provee X?» son en realidad **decisiones de contrato**, no averiguaciones. Esto **no** invierte la dirección del dato: el catálogo y los usuarios siguen siendo proyección de dato ajeno.

- **Q**: El catálogo de origen no tiene clasificación temática. ¿Cómo se resuelve el insumo del término content-based? → **A**: **Se especifica desde este repositorio** (CR-16, DEP-7): el catálogo debe exponer un conjunto no vacío de tags por ítem. Se descartan derivarlos localmente de la descripción —nos volvería productores de dato ajeno, con procesamiento de lenguaje fuera de alcance—, reponderar el motor a `α = 0` —elimina la recomendación por contenido y deja sin sustento a `γ` y al MMR— y curar tags propios. **`weight` se elimina**: exigir un peso por asignación obligaría al origen a inventar un número sin criterio editorial, y la ponderación real ya existe y es propia (TF-IDF). La pertenencia queda binaria.

- **Q**: ¿Las interacciones son eventos inmutables o el estado vigente del vínculo usuario-ítem (NC-16), y se exige un identificador propio de interacción (NC-11)? → **A**: **Eventos inmutables con identificador propio del origen** (DEP-8, DEP-9). El identificador pasa a ser la **clave natural** —en restricción de unicidad, no en la clave primaria, que sigue siendo interna—. Sustituye a la combinación de cuatro atributos, que dependía de que la marca temporal fuera estable ante reentrega: esa garantía se **elimina del contrato** porque pedía al origen certeza sobre *cuándo ocurrió algo*, dato que una corrección o un ajuste de reloj alteran sin mala fe, y cuyo incumplimiento era **indetectable** desde este lado. El identificador es administrativo: el origen lo controla por completo. Se descartan espejar el estado —vacía de contenido a las decisiones de popularidad y retención— y derivar el historial comparando sincronizaciones, que volvería la marca temporal una hora de *detección*. **Costos aceptados**: aparece un índice que la clave anterior cubría de forma incidental; el empate temporal deja de ser anómalo y el desempate por identidad interna pasa a ser el mecanismo general; y el riesgo se traslada a la **reutilización** de identificadores, que se prohíbe explícitamente pero no es cero.

- **Q**: ¿Existe obligación de supresión de datos personales, y sigue justificada `region` sin consumidor (NC-5, NC-10)? → **A**: **Sí, existe**: un usuario puede eliminar su cuenta. La eliminación en cascada desde el usuario **se confirma** —la alternativa exigiría un borrado manual ordenado, que falla en silencio y de forma parcial, el peor resultado en esta operación—. **No contradice la permanencia de las exclusiones**: ese invariante prohíbe vaciar y reconstruir el conjunto, no eliminar al sujeto entero; si no sobrevive el usuario, no hay sujeto sobre el cual el invariante pueda ser falso. **El hallazgo real es la caché**: cuatro claves de alcance de usuario no participan de la cascada y sobreviven hasta siete días, de modo que se exige invalidación explícita (FR-070a..d). En cuanto a `region`: **recibe consumidor** —segmentación geográfica del término colaborativo— y deja de ser una excepción por anticipación. La columna no cambia; cambia su naturaleza. La pregunta de minimización se reformula de «dato sin finalidad» a «finalidad proporcionada». Quedan abiertas tres consecuencias que antes no existían: refuerzo de burbuja geográfica, tratamiento de la región ausente —degradar a vecindario global, nunca excluir— y la forma de incorporarla al cálculo.

- **Q**: ¿Cómo se trata la región ausente ahora que segmenta el vecindario colaborativo? → **A**: **No se trata: deja de ser representable.** La región pasa a obligatoria y se solicita al crear la cuenta. Admitir el valor ausente obligaría a **cada consulta** del término colaborativo a decidir qué hacer con él, que es la clase de fail-open silencioso ya eliminado para la edad y para la clasificación etaria. **Es la decisión opuesta a la registrada poco antes** —degradar a vecindario global—, y el cambio de premisa la justifica: degradar era correcto para un dato opcional. **Costo aceptado**: el rechazo es más severo de lo que el motor necesita, porque el conjunto de respaldo no depende de la región; y a diferencia de la edad, es un dato que la persona declara sobre sí misma, de modo que quien prefiera no informarlo queda fuera del producto. Se descarta un valor centinela por reintroducir el mismo problema con otro nombre, pero queda registrado como la primera corrección a evaluar si el rechazo resulta excesivo.
- **Q**: ¿Cómo se aprueba el lote de requisitos pendientes? → **A**: **Separando por impacto, no por familia**: aprobación en bloque de los que solo precisan redacción, y revisión individual de los que cambian comportamiento observable. El corte temático mezclaría en un mismo lote precisiones inocuas con cambios en lo que el usuario ve. Se **elimina FR-052 en su forma anterior** —«si la edad no puede determinarse, aplicar restricción máxima»—, que perdió referente al volverse la fecha de nacimiento obligatoria y no nula: el caso es irrepresentable, y un requisito sobre un caso imposible es una instrucción que nadie puede cumplir ni verificar. El identificador **no se reutiliza**: FR-052 queda **retirado y libre**, y la obligatoriedad de la región toma un identificador nuevo (FR-079). Reasignarlo habría hecho que toda referencia previa —en tareas, incidencias o historial— apuntara en silencio a un requisito distinto, que es uno de los tres modos de falla recurrentes registrados.

- **Q**: ¿Qué valores toman el nivel de confianza de la popularidad y el horizonte de retención de señales? → **A**: **1,96** (95 %, convención habitual) y **18–24 meses** respectivamente. El primero exige que un ítem acumule decenas de señales antes de competir con uno establecido; el costo declarado es que **agrava el sesgo contra ítems recién ingresados**, y bajarlo es la corrección más barata si eso resulta un problema. El segundo cubre más de un ciclo estacional completo, en línea con la instrucción de errar por exceso: lo purgado no vuelve. Se fija un **rango y no un valor exacto** porque la diferencia entre 18 y 24 meses no tiene consecuencia observable, y precisar más sería falsa exactitud. Queda abierto qué ceremonia debe requerir una **reducción** del horizonte, dado que subirlo es inocuo y bajarlo destruye datos de forma irreversible, y ambas operaciones son indistinguibles en un archivo de configuración.
- **Q**: ¿Qué umbral debe abortar una sincronización por volumen anómalo? → **A**: **0,9** — una corrida cuyo conteo sea menor al 90 % de la última exitosa se descarta sin marcar retiros. **No está calibrado**, y se adopta igual: esperar datos reales dejaría sin guarda justamente el período de mayor riesgo, cuando el origen está recién construido. El umbral falla hacia el lado barato —entre congelar el catálogo y vaciarlo, elige congelarlo—, porque un ítem ausente del catálogo se interpreta como retirado y una respuesta parcial admitida provocaría el retiro masivo de ítems vigentes. Si aparecieran cargas masivas legítimas, el ratio **no es la guarda adecuada** y debería sustituirse por un tope absoluto de retiros por corrida.

- **Q**: Revisión individual de los requisitos que cambian comportamiento observable (estrategia C de Q13). → **A**: **(1)** `region` y `birth_date` son ambas obligatorias y se recogen en el formulario de alta (FR-079a, RD-61). **(2)** Un ítem sin tags **se rechaza**: no es recomendable con este motor (FR-021b reescrito, RD-60; cierra NC-9). **(3)** La verificación de supresión pasa a requisito ejecutable y registrado (FR-070e, RD-59). **(4)** La exclusión **persiste aunque su señal de origen se haya purgado**; `user_exclusions` es derivado con vida propia y la reconstrucción deja de ser requisito (FR-068d reescrito, FR-068d1 informativa sin umbral, RD-58). **(5)** La inmutabilidad es obligación **local**: el origen puede guardar estado, este repositorio traduce a historial; sobrevive la exigencia de identificador **por emisión** (FR-029e reformulado, FR-029e1, DEP-9 y CR-18 reformulados, RD-55). **(6)** El sesgo del respaldo contra ítems nuevos se difiere a NC-13. **(7)** La caché se invalida en el mismo acto del recálculo, y el recálculo se dispara por conteo de interacciones configurable (FR-080, FR-080a, RD-57; abre NC-19 por el valor). **(8)** Se sirve respaldo **avisando** que hay un personalizado obsoleto consultable; la precedencia de FR-056 no cambia y la señal es distinta del estado (FR-056a, RD-56). **(9)** El vocabulario compartido derivado de datos materializados se acepta como está.

- **Q**: Cierre de los cuatro pendientes restantes: protección de ítems nuevos (NC-13), región en el motor (NC-17 a+c), umbral de recálculo (NC-19) y disponibilidad regional de ítems (NC-6). → **A**: **NC-13**: **cuota reservada** en el respaldo (`fallback_new_item_share`, FR-033a6..a8), máximo y no mínimo, **sin alterar el puntaje** — se descartan ventana de gracia y piso artificial porque contaminan la medición (RD-65; abre NC-20 por el valor). **NC-17**: **ponderación blanda**, nunca filtro duro, con prohibición explícita del valor que lo emularía (FR-081, FR-081a, RD-64) — la burbuja geográfica no se elimina, se vuelve graduable. **NC-19**: **10 interacciones**, etiquetado como punto de partida y no como medición; admisible sin datos porque es configuración versionada y su error es reversible (RD-63). **NC-6**: **fuera de alcance por decisión explícita** — si entrara, entraría como restricción de cumplimiento con catálogo versionado propio, como el filtro etario, no como columna de `items` (RD-62).

- **Q**: ¿Qué valor toma la cuota de novedades en el respaldo (NC-20, parte)? → **A**: **3 posiciones reservadas**. Expresada en **posiciones absolutas y no en proporción** (FR-033a6a): `top_n` es variable por solicitud, de modo que una fracción daría una cantidad distinta de novedades en cada respuesta y redondearía a cero en los `top_n` bajos, apagando la protección justo donde cada posición pesa más. Se valida al arrancar que `fallback_new_item_slots < top_n_default`, estricto (FR-033a6b). RD-66. **NC-20 permanece abierto solo por el umbral de evidencia**, sin el cual la cuota no es operable.

- **Q**: ¿Cómo se determina qué ítems ocupan la cuota de novedades (NC-20)? → **A**: **Dos conjuntos disjuntos** (FR-033a6c): todo ítem entra al **emergente** y pasa al **general** al alcanzar el umbral de evidencia. El emergente se ordena por **criterio propio, no por Wilson** (FR-033a6d): entre ítems de poca evidencia, Wilson ordena por anchura del intervalo, es decir otra vez por evidencia. Dos reglas que la propuesta no contemplaba y que la ventana móvil de FR-033a1 hace necesarias: la promoción es **definitiva** (FR-033a6e) —la evidencia puede *bajar*, y sin esto un ítem viejo sin tracción competiría por las posiciones de novedad— y la salida del régimen de arranque es **monótona** (FR-033a6g). **Régimen de arranque**: con el conjunto general por debajo de `fallback_bootstrap_min_items` = **1000**, el respaldo se sirve íntegramente desde el emergente y la cuota no se aplica (FR-033a6f), con el régimen activo expuesto como observable. RD-67. **NC-20 queda abierto solo por el umbral y el criterio de orden**.

- **Q**: ¿Cómo se resuelve el arranque en frío del conjunto emergente (NC-20)? → **A**: **no se resuelve en el catálogo sino en el usuario**. Se incorpora `user_declared_tags` (§2.14): el usuario declara **mínimo 5 tags por módulo** (FR-082, FR-083), **al ingresar por primera vez a ese módulo y no al crear la cuenta** (FR-084) — FR-079a no se toca. Al declarar en el segundo módulo, los tags compartidos del primero se **heredan sin volver a pedirse**, pero **no cuentan para el mínimo**, que mide elección deliberada (FR-085). El perfil usa **TF-IDF con pesos con signo** como el prototipo de referencia —los componentes pueden ser negativos y ponderan por IDF—, es **derivado y reconstruible**, nunca incremental (FR-087), y se siembra por feedback sintético que **no se persiste en `user_signals`**. Los gustos **no caducan**: el feedback modula el peso del tag, no su pertenencia (FR-086). Consecuencia: **se eliminan FR-033a6f y FR-033a6g** (régimen de arranque y su trinquete) y el emergente se ordena por **afinidad con el perfil**, con prohibición explícita de aleatoriedad (FR-033a6f1/f2). La cuota de 3 posiciones y la partición en dos conjuntos **se conservan**: el ítem nuevo compite bien en α pero sigue en desventaja en β y en el respaldo. Una solicitud sin declaración se rechaza como **precondición incumplida**, no como sexto estado de FR-056 (FR-088). RD-68, RD-69, RD-70. **NC-20 cerrado; no queda ningún pendiente abierto.**

- **Q**: La declaración de gustos (FR-082…FR-088) no tiene componente que la escriba: la API solo lee, el Data Transformer proyecta dato ajeno y el worker consume eventos. ¿Quién persiste `user_declared_tags`? → **A**: **Un endpoint de escritura en esta API, como excepción declarada** (FR-089, RD-75). Es el único dato cuya autoridad nace en este repositorio, de modo que la regla «la API solo lee» no tiene a quién delegarlo. La confirmación es **síncrona** (FR-089a): si fuera asíncrona, FR-088 rechazaría al usuario por no haber declarado lo que acaba de declarar. El endpoint **no calcula**: solo persiste (FR-089b) — la excepción cubre la escritura, no el cómputo, y así no erosiona el Principio III. Se descartan el evento por RabbitMQ (no puede confirmar), el Data Transformer (contradice RD-68, proyecta dato ajeno) y guardarlo en `api-general` (contradice RD-47). **Condición de revisión**: un segundo dato de autoría local exige componente de escritura propio, porque una excepción con dos casos deja de ser excepción.

- **Q**: ¿Se amplía el alcance de lo recuperable ante pérdida de Postgres? → **A**: **No. Lo especificado hasta aquí como recuperable lo es; lo que no, no** (RD-71). La decisión no cambia nada del sistema, pero **obliga a corregir una afirmación falsa** que venía arrastrándose: «todo lo necesario para recalcular vive en Postgres» es cierto para lo proyectado, no para lo propio. Tres entidades no son regenerables desde ningún origen — `user_signals` (se pierde el historial), `user_declared_tags` (**hay que volver a preguntarle al usuario**) y `user_exclusions` (**los ítems rechazados reaparecen**) —. Queda declarado, no resuelto: el respaldo es responsabilidad operativa, no de diseño.

- **Q**: ¿Con qué valor arranca `region_weight_factor` (RD-64)? → **A**: **Con su valor neutro, segmentación regional desactivada en `v1`** (FR-090, RD-74). La activación posterior es un cambio ordinario de configuración, no de esquema — de ahí que se adopte *neutro* y no *ausente* —. `region` **sigue siendo `NOT NULL` al alta** de todas formas: es un dato fácil de pedir en el momento del registro e imposible de recuperar retroactivamente. Consecuencia sobre RD-64: su validación debe admitir el neutro explícitamente, además de seguir rechazando el extremo que equivale a un filtro duro.

- **Q**: Los tags de los ítems se originan fuera (por ejemplo, una API de Steam). ¿Constituye eso una dependencia externa? → **A**: **Sí: se registra DEP-10** (RD-72). Se distingue de DEP-7, que es *por ítem* («todo ítem trae al menos un tag»): DEP-10 es *sobre el conjunto* — el vocabulario normalizado del que se nutren tanto `item_tags` como la declaración del usuario —. Su incumplimiento es el más severo del inventario: es la única dependencia externa cuya falta deja al sistema **sin ningún usuario atendible**, porque sin vocabulario no hay declaración posible y FR-088 rechaza todo. **DEP-3 no se reutiliza**: queda vacante a propósito.

- **Q**: ¿Qué valores concretos toman las ponderaciones de señal y el tamaño del resultado? → **A**: **Se adoptan los del prototipo y un `top_n_default` concreto** (RD-73): `peso_like = 1,0`, consumo `= 0,3`, `peso_dislike = −1,0`, `top_n_default = 20`. El tamaño no es arbitrario: RD-66 ya razonaba sobre «`top_n_default` en el orden de 20» al fijar la cuota de tres posiciones, de modo que esto **confirma un supuesto que ya estaba operando sin estar escrito**. Queda registrado el riesgo de orden: la cuota se fijó antes que el tamaño del resultado sobre el que se calcula, y si `top_n_default` bajara, tres posiciones dejarían de ser una minoría del top.

- **Q**: ¿Qué valor concreto deja a la ponderación regional sin efecto, y en qué forma se expresa la cuota de novedades? → **A**: **(1)** `region_weight_factor` se define como **intensidad de la segmentación** —misma región pesa `1`, otra región pesa `1 − factor`—, de modo que **el neutro es `0`** (FR-081b, RD-76). Esto **corrige un defecto, no aclara una redacción**: §4 validaba `0 < factor < 1` estricto en ambos extremos, lo que hacía **irrepresentable** el arranque neutro que RD-74 ordenaba; la configuración de `v1` no habría podido cargarse. El límite inferior pasa a inclusivo; el superior sigue estricto. Costo aceptado: con esta semántica **el nombre se lee al revés** de lo que mide. **(2)** La cuota vuelve a ser **proporcional con piso**: `fallback_new_item_quota_ratio` = **0,20** y `fallback_new_item_quota_min` = **1**, calculada sobre el `top_n` **de cada solicitud** (FR-033a6a, RD-77). Revierte RD-66 y reinstala su alternativa descartada: RD-66 corrigió el modo de falla de la fracción en los `top_n` bajos **sin mirar el simétrico** —un absoluto de 3 se diluye al 6 % en un `top_n` de 50—; la fracción con piso cubre ambos extremos. Con `top_n_default` = 20 la cuota pasa de **3 a 4** posiciones. `top_n = 1` da cuota **0** por clamp. Los nombres **no reutilizan** `fallback_new_item_share`, que sigue siendo la métrica observada (FR-033a8).

- **Q**: ¿Con qué intensidad arranca la ponderación regional y cómo se garantizan 3 posiciones de cuota en todos los casos? → **A**: **(1)** `region_weight_factor` = **0,1** en `v1` (FR-090a, RD-79): segmentación **activa con intensidad mínima**, el aporte extrarregional pesa 0,9. **Revierte la prescripción de RD-74** —que mandaba arrancar en `0`— pero **no su capacidad**: el `0` sigue siendo representable y sigue siendo el neutro, de modo que la corrección de RD-76 no queda sin uso. Fundamento: con `0`, el camino de segmentación nunca se ejecuta en producción y se estrenaría el día que alguien cambie el valor, sobre tráfico real. Costo aceptado: **`v1` nunca observa la línea de base sin segmentación**, y la condición de revisión de RD-64 pasa a exigir poner el factor en `0` deliberadamente para medir. **(2)** `top_n_min` = **10** (FR-006a) y `fallback_new_item_quota_min` = **3** (RD-78), acoplados: el piso de `1` de RD-77 no era el deseable sino el único **seguro** mientras `top_n` no tenía cota inferior. Acotar `top_n` elimina la colisión, vuelve **redundante** el clamp `top_n − 1` en todo el dominio admisible y hace **irrepresentable** el caso degenerado `top_n = 1`. Consecuencia que no es «20 % siempre»: el piso gobierna en `top_n` ∈ [10, 14], donde la cuota **excede** la proporción configurada —3 de 10 es **30 %**—; el 20 % describe el comportamiento desde `top_n` = 15, que incluye el defecto de 20. Dominio de `top_n` = **`[10, 50]`**.

- **Q**: ¿El 20 % puro contradice algún requisito vigente? Si no, rige solo; si sí, la cuota es 3 en todos los casos. → **A**: **No contradice nada, de modo que rige el 20 % solo** (RD-80). Verificado punto por punto: el riesgo de redondeo a cero que el piso cubría ya es **irrepresentable** con `top_n_min` = 10 —`floor(10 × 0,20)` = 2—; `cuota < top_n` se cumple con margen; y **ningún requisito exige un 3**, que provenía de RD-66 (revertido) y de RD-78 (piso, no derivación). Consecuencia: **`fallback_new_item_quota_min` se elimina**, no se baja a `1`, porque con `top_n ≥ 10` jamás gobernaría — el mismo criterio con que RD-77 descartó el redondeo hacia arriba: *un parámetro que nunca gobierna miente sobre lo que hace*. **El clamp `top_n − 1` también se quita** de la fórmula y la garantía vuelve a la validación de arranque, donde es verificable una vez en lugar de ejecutarse en cada solicitud para no hacer nada. Fórmula vigente: `cuota = floor(top_n × ratio)`. **Costo aceptado**: se pierde la garantía de 3 posiciones — en `top_n` ∈ [10, 14] la cuota es **2** —, que es precisamente lo que la instrucción puso en la balanza. **`top_n_min` = 10 permanece**: su segundo fundamento (evitar el apagado por redondeo) es independiente del piso y sobrevive a su eliminación.

## Dependencias Externas Bloqueantes

> Estas dependencias son responsabilidad de `api-general`. Mientras no estén confirmadas, la feature
> **no es implementable**: no se trata de supuestos operativos sino de precondiciones. Ver FR-061 a
> FR-064.

| # | Dependencia | Requisitos que la necesitan | Consecuencia si no se cumple |
|---|---|---|---|
| DEP-1 | Tipo de señal (like / dislike / consumo) por registro de actividad | FR-022a, FR-022b, FR-029a-d, FR-062 | El perfil de tags no puede construirse; la señal content-based queda sin insumo confiable |
| DEP-2 | Marca temporal por señal de actividad | FR-029d, FR-062 | No puede resolverse el conflicto entre señales contradictorias |
| DEP-8 | **Identificador propio de cada interacción**, único y no reutilizado | FR-011, FR-069, DI-21 | **Sostiene la idempotencia de ingesta.** Sin él, una reentrega con marca temporal alterada entra como interacción nueva: no viola ninguna restricción y el síntoma aparece después como popularidad inflada sin causa aparente |
| DEP-9 | **Notificación de cada transición de estado como emisión propia**, con identificador nuevo. El origen **puede** almacenar estado; lo que no puede es dejar una transición sin emitir o reemitirla bajo el identificador anterior | FR-029d, FR-029e, FR-068a, y toda la temporalidad del motor | Este repositorio recibiría estado y no historial. La ventana de popularidad pierde sentido, el filtrado colaborativo pierde temporalidad y la purga se deshace en cada sincronización |
| DEP-4 | ~~Fuente de popularidad global por ítem~~ — **resuelto**: se deriva del volumen de likes propio (FR-033a). No es dependencia externa. | FR-033a | — |
| DEP-7 | **Tags temáticos por ítem**, conjunto no vacío | FR-022a, FR-026, FR-032, y todo el término content-based | **El más grave de la tabla.** Sin tags el término `α = 0,5` no se degrada: no existe. También quedan sin sustento el cruce entre módulos (`γ`) y la diversificación MMR, que mide diversidad **sobre clusters de tags**. Faltaba en esta tabla: DEP-1 lo daba por supuesto |
| DEP-5 | **Fecha de nacimiento** del usuario, obligatoria y no nula | FR-030, FR-051 | **El usuario se rechaza en la ingesta** y no recibe recomendaciones. Ya no existe el modo degradado de «restricción máxima»: la fecha es condición de admisión (CR-1) |
| DEP-6 | Acuerdo sobre el conjunto de estados de respuesta | FR-006, FR-056, FR-057 | El contrato de lectura no puede cerrarse |
| DEP-10 | **Vocabulario de tags normalizado del catálogo**, del que se ofrecen las opciones de declaración | FR-082, FR-083, RD-68 | **Sin él no hay de dónde elegir**: la declaración no puede presentarse y, por FR-088, ningún usuario nuevo puede recibir recomendaciones. Los tags se originan en APIs externas (Steam y equivalentes) y llegan normalizados vía `api-general`: la normalización **no ocurre acá**, y una variación en su criterio cambia el conjunto elegible sin aviso. Es dependencia de **disponibilidad y estabilidad**, no de construcción — el catálogo ya existe poblado. **No se reutiliza DEP-3**, vacante |

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
- **FR-006a**: El tamaño de resultado solicitado MUST estar comprendido en `[top_n_min, top_n_max]`, con
  **`top_n_min` = 10**, y toda solicitud por debajo del mínimo MUST rechazarse con error explícito, igual
  que las que exceden el máximo (FR-005). El mínimo MUST declararse como requisito del contrato y MUST
  NOT quedar implícito en un valor de configuración: es una restricción sobre el consumidor —`api-general`
  no puede pedir un top de 3— y existe para que la cuota de novedades (FR-033a6) **no se apague por
  redondeo**: sin cota inferior, un `top_n` de 1 a 4 daría cuota `0`. Ese fundamento es independiente del
  piso que RD-78 había introducido y **sobrevive a su eliminación** en RD-80.
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
- **FR-010d**: El vocabulario de tags MUST ser **único y compartido por ambos módulos**: la
  representación vectorial de un ítem de películas y la de un ítem de juegos MUST vivir en el mismo
  espacio, de modo que la similitud entre ellos sea una operación definida. MUST NOT construirse un
  espacio vectorial independiente por módulo.
- **FR-010e**: El vocabulario compartido MUST ser un **artefacto versionado propiedad de este
  repositorio**, derivado del catálogo ya sincronizado. MUST NOT ser un contrato compartido ni
  requerir aprobación de `api-general`, dado que es un detalle interno del motor y no cruza la
  frontera del servicio.
- **FR-010f**: Toda representación vectorial persistida MUST registrar la versión de vocabulario con
  la que fue generada. Vectores generados con versiones distintas MUST NOT compararse entre sí.
- **FR-010g**: MUST estar definido en configuración versionada el criterio de regeneración del
  vocabulario y el procedimiento de transición, que MUST recalcular las representaciones afectadas
  antes de que la nueva versión pase a estar vigente. Un vocabulario desactualizado MUST degradar
  únicamente la calidad de las recomendaciones, nunca su corrección ni los invariantes obligatorios.
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
- **FR-029b1**: La permanencia de una exclusión MUST ser independiente de la retención de la señal
  que la originó. Purgar la señal MUST NOT hacer reaparecer el ítem. En consecuencia, la exclusión
  MUST estar materializada y toda reconstrucción de derivados sobre ella MUST ser aditiva: ningún
  procedimiento de recálculo MUST vaciar el conjunto de exclusiones para reconstruirlo desde las
  señales vivas.
- **FR-029c**: La exclusión originada en un dislike MUST ser permanente salvo que exista un like
  posterior sobre el mismo ítem, en cuyo caso la exclusión por dislike MUST considerarse revertida;
  el ítem permanece excluido si además fue consumido.
- **FR-029d**: Ante señales contradictorias sobre un mismo ítem, MUST prevalecer la más reciente
  según su marca temporal; el criterio de desempate MUST ser determinístico y documentado.
- **FR-011a**: La deduplicación de interacciones MUST apoyarse en el **identificador provisto por el
  origen**, no en una combinación de atributos descriptivos. Una interacción reentregada MUST NOT
  producir un segundo registro **aunque su marca temporal difiera**.
- **FR-011b**: El identificador del origen MUST NOT usarse como clave primaria interna. La identidad
  interna de un registro MUST permanecer bajo control de este servicio.
- **FR-079**: La región del usuario MUST ser obligatoria y no nula, y MUST recogerse al crear la
  cuenta. Un usuario sin región válida MUST rechazarse en la ingesta; MUST NOT persistirse con un
  valor ausente ni con un centinela, porque ambos trasladarían la decisión a cada consulta que la
  utilice.
- **FR-079a**: La fecha de nacimiento y la región MUST recogerse **ambas en el formulario de alta**
  de la aplicación web, y ambas MUST ser de respuesta obligatoria. Las dos condicionan el rechazo en
  la ingesta (FR-079, CR-1), de modo que un alta que omita cualquiera de ellas produce un usuario que
  el motor no puede atender. El formulario MUST NOT permitir completar el alta sin ambas.
- **FR-070a**: La supresión de un usuario a pedido MUST eliminar **todos** los datos de su alcance,
  incluidos los almacenados en caché. MUST NOT considerarse suprimido un dato cuya eliminación se
  delegue en el vencimiento de su tiempo de vida.
- **FR-070b**: La supresión MUST invalidar la caché **antes** de eliminar el dato de origen, y MUST
  verificar que no haya un recálculo en curso para ese usuario. Un recálculo iniciado antes de la
  supresión MUST NOT poder reescribir datos ya eliminados.
- **FR-070c**: La supresión MUST alcanzar a **toda** versión de configuración y a todos los módulos,
  no solo a los activos.
- **FR-070d**: El sistema MUST verificar la ausencia efectiva de datos tras la supresión y MUST
  señalar todo residuo. Una supresión parcial MUST tratarse como fallo, no como éxito degradado.
- **FR-070e**: La verificación de FR-070d MUST ser una comprobación **ejecutable y registrada**: tras
  cada supresión, el sistema MUST consultar cada almacén de su alcance —tablas normalizadas y claves
  de caché de ámbito de usuario— y MUST dejar constancia del resultado, incluido el caso negativo.
  Una supresión cuya verificación no se haya registrado MUST tratarse como **no completada** y MUST
  reintentarse. La constancia MUST NOT contener datos del usuario suprimido más allá de su
  identificador y la marca temporal.
- **FR-029e**: Las señales MUST almacenarse **en este repositorio** como hechos inmutables. Una
  transición de estado MUST registrarse como un hecho nuevo y MUST NOT modificar ni reemplazar el
  registro anterior. La obligación recae sobre este servicio: el origen MAY almacenar estado, y la
  traducción de estado a historial MUST ocurrir en la ingesta local.
- **FR-029e1**: Cada **emisión** recibida MUST portar un identificador propio, distinto del de
  emisiones anteriores sobre el mismo par usuario-ítem. Un identificador que identifique al *vínculo*
  en lugar de al *hecho* MUST rechazarse como incumplimiento de contrato, no absorberse: bajo la
  deduplicación de FR-011a, una transición reemitida con el identificador anterior se descartaría
  como duplicado y la transición se perdería en silencio.
- **FR-021a**: Cada ítem MUST tener asociado un conjunto **no vacío** de tags temáticos. La
  pertenencia MUST ser binaria: no MUST exigirse al origen un peso de relevancia por asignación. La
  ponderación relativa de cada tag MUST calcularse localmente al vectorizar.
- **FR-021b**: Un ítem que llegue sin tags MUST **rechazarse en la ingesta** y registrarse como
  **anomalía de contrato**. Un ítem sin tags no es recomendable por el término de contenido, que
  aporta la mayor parte del puntaje; admitirlo produciría un candidato estructuralmente incapaz de
  competir. El rechazo MUST NOT bloquear la ingesta del resto del catálogo ni ser silencioso: MUST
  quedar constancia del ítem rechazado y del motivo.
- **FR-030a**: La escala de clasificación etaria MUST ser **propia del sistema RecoMe**, definida
  en una única fuente versionada, y MUST NOT derivarse en tiempo de ejecución de ningún otro
  vocabulario. Las etiquetas que viajan por el contrato MUST coincidir **exactamente** con las
  de esa fuente; una etiqueta ausente del catálogo MUST tratarse como no apta (FR-030).
- **FR-030b**: La escala MUST ser única para todos los módulos. MUST NOT existir un vocabulario
  etario por módulo, porque el permiso etario del usuario es un valor único e independiente del
  módulo consultado.
- **FR-030**: Un ítem cuyo `age_rating` sea desconocido o ausente MUST tratarse como no apto.
- **FR-031**: La diversificación MMR MUST NOT reintroducir ningún ítem previamente filtrado.
- **FR-032**: La diversificación MUST reducir la dominancia de un único cluster de tags en el top-N,
  según un criterio de diversidad medible y documentado.
- **FR-033**: Si tras los filtros no quedan candidatos válidos, el resultado MUST ser un top-N vacío
  explícito y distinguible del vacío por recálculo pendiente, nunca un relleno con ítems no aptos.
- **FR-033a**: MUST existir un top-N de respaldo por módulo, basado en la popularidad global de los
  ítems, destinado a usuarios sin actividad suficiente para generar un perfil de tags. La
  popularidad MUST derivarse de **señales registradas en el propio sistema**, y MUST NOT
  depender de ningún campo de valoración externo provisto por `api-general`.
- **FR-033a1**: La popularidad MUST computarse sobre una **ventana temporal acotada** definida en
  configuración versionada, no sobre el histórico completo, para que el respaldo refleje interés
  actual y no quede fijado por ítems antiguos acumulados.
- **FR-033a3**: La popularidad de un ítem MUST definirse como el **límite inferior del intervalo de
  confianza de Wilson** sobre la **tasa de conversión a like entre quienes interactuaron** con el
  ítem dentro de la ventana. El nivel de confianza MUST ser un parámetro de la configuración
  versionada (`popularity_confidence_z`), MUST validarse como estrictamente positivo al cargar, y
  una configuración que no lo satisfaga MUST impedir el arranque (FR-027).
- **FR-033a3a**: El denominador de esa tasa MUST ser el número de **usuarios distintos** con alguna
  señal sobre el ítem en la ventana —like, dislike o consumo—, y MUST NOT ser la suma de los
  recuentos por tipo de señal: un mismo usuario puede haber registrado varias y contaría más de una
  vez. El numerador MUST ser el número de usuarios distintos cuya señal vigente sobre el ítem es un
  like. El numerador MUST NOT exceder al denominador.
- **FR-033a3b**: Las señales de consumo MUST participar del denominador y MUST NOT participar del
  numerador. Esto no contradice FR-022b: el consumo sigue sin expresar preferencia —por eso no suma
  como señal positiva—, pero constituye la oportunidad de expresarla.
- **FR-033a4**: El puntaje de popularidad MUST estar **materializado** antes de servirse: MUST NOT
  calcularse durante la atención de una solicitud ni durante el ordenamiento del respaldo (FR-003).
  Un ítem sin señales en la ventana MUST tener puntaje cero y MUST seguir siendo representable.
- **FR-033a6**: El respaldo global MUST reservar una **proporción del resultado**, declarada en
  configuración versionada (`fallback_new_item_quota_ratio` = 0,20), a ítems cuya evidencia acumulada no alcance un umbral mínimo,
  ordenados entre sí por **afinidad con el perfil del usuario** (FR-033a6f1). La cuota MUST ser un
  **máximo, no un mínimo**: si no hay suficientes ítems poco evidenciados, las posiciones sobrantes MUST
  ocuparse por puntaje ordinario y MUST NOT quedar vacías.
  > Dos correcciones respecto de la redacción anterior: la cuota era un conteo fijo de 3 posiciones
  > (RD-66, revertido por RD-77) y el orden interno era «por antigüedad de incorporación», criterio que
  > **RD-70 había eliminado por no ser computable** —`items` no tiene ese atributo y RD-10 prohíbe
  > agregarlo— sin que este enunciado se actualizara.
- **FR-033a6a**: La cuota efectiva MUST calcularse sobre el `top_n` **de la solicitud atendida**
  (FR-006, FR-006a), mediante `cuota = floor( top_n × fallback_new_item_quota_ratio )`, sin piso ni
  clamp. El redondeo MUST ser hacia abajo, con el efecto conocido de que la porción real oscila por
  debajo del 20 % dentro de cada tramo —en `top_n` = 14 la cuota es 2, el 14 %—: es inherente a una cuota
  entera sobre un resultado entero. Con `top_n_min` = 10 la cuota **nunca baja de 2**, de modo que el
  apagado por redondeo a cero que motivaba un piso es **irrepresentable** y el piso se elimina (RD-80).
- **FR-033a6b**: La cuota efectiva MUST ser estrictamente menor que el `top_n` atendido. Una cuota que
  iguale al tamaño del resultado convertiría al respaldo en una lista de novedades, que es un
  comportamiento distinto del especificado y no un caso extremo del mismo. La garantía MUST sostenerse en
  la **validación de arranque** —`0 < fallback_new_item_quota_ratio < 1` junto con
  `10 ≤ top_n_min ≤ top_n_default ≤ top_n_max`— y MUST NOT depender de un clamp en la fórmula: con
  `ratio < 1`, `floor(top_n × ratio) < top_n` para todo `top_n` admisible. El caso degenerado `top_n = 1`
  que RD-77 resolvió con clamp **deja de ser representable** (RD-80).
- **FR-033a6c**: El catálogo de respaldo MUST particionarse en **dos conjuntos disjuntos y
  exhaustivos**: el **conjunto emergente**, con los ítems cuya evidencia acumulada no alcanza el
  umbral, y el **conjunto general**, con el resto. Todo ítem incorporado MUST entrar al conjunto
  emergente. La pertenencia MUST derivarse del mismo par numerador/denominador que sostiene el puntaje
  (FR-033a5) y MUST NOT almacenarse como estado independiente, para que no pueda divergir del dato que
  la determina.
- **FR-033a6d**: El conjunto emergente MUST ordenarse por un criterio **propio**, y ese criterio MUST
  NOT ser el puntaje de FR-033a3. Ordenar por Wilson dentro del conjunto emergente reproduciría el
  sesgo que la partición existe para neutralizar, porque todos sus miembros tienen poca evidencia por
  definición y el estimador los ordenaría por la anchura de su intervalo antes que por su mérito.
- **FR-033a6e**: Un ítem que alcance el umbral de evidencia MUST promoverse al conjunto general, y esa
  promoción MUST ser **definitiva**. Un ítem promovido MUST NOT volver al conjunto emergente aunque su
  evidencia caiga por debajo del umbral. La evidencia se mide sobre una ventana móvil (FR-033a1) y por
  lo tanto puede decrecer; sin esta regla, un ítem antiguo que pierde tracción competiría por las
  posiciones reservadas a novedades, que es lo contrario del propósito de la cuota.
- ~~**FR-033a6f**~~ · ~~**FR-033a6g**~~: **eliminados por RD-70**. Declaraban un régimen de arranque
  en el que el respaldo se servía íntegramente desde el conjunto emergente, con transición monótona.
  Existían porque el usuario sin señales no tenía con qué personalizar y caía al respaldo. Con la
  declaración de gustos (FR-082) ese usuario se atiende por contenido desde su primera solicitud, el
  respaldo vuelve a ser lo que su nombre dice, y el régimen **pierde su razón de ser junto con su
  trinquete irreversible**. Los identificadores quedan retirados y **no se reutilizan**.
- **FR-033a6f1**: El conjunto emergente MUST ordenarse por **afinidad con el perfil del usuario**
  (FR-087), con el mismo criterio de contenido que ordena el resto del resultado y **sin usar el
  puntaje de popularidad**, que FR-033a6d prohíbe. La cuota de FR-033a6 deja de ser un orden global y
  pasa a resolverse por usuario.
- **FR-033a6f2**: La exposición de los ítems emergentes MUST repartirse como **consecuencia de la
  diversidad de perfiles**, y el sistema MUST NOT introducir aleatoriedad para lograrla. Usuarios con
  gustos distintos ven emergentes distintos; un criterio de orden único y global es lo que produciría
  el bucle en que unos pocos ítems acaparan la exposición y el resto nunca acumula evidencia.
- **FR-033a7**: Los ítems admitidos por la cuota MUST NOT recibir un puntaje alterado. Su puntaje de
  popularidad sigue siendo el de FR-033a3; lo que cambia es el **lugar donde se los ordena**, no el
  valor que los mide. Un puntaje artificialmente elevado contaminaría toda comparación posterior y
  dejaría de ser reconstruible a partir del numerador y el denominador (FR-033a5).
- **FR-033a8**: El sistema MUST exponer qué proporción del respaldo servido provino de la cuota
  (`fallback_new_item_share`, métrica observada — no confundir con el parámetro, que es un conteo de
  posiciones). MUST distinguirse la cuota **disponible** de la **efectivamente ocupada**: si las
  posiciones se llenan sistemáticamente por puntaje ordinario, el problema no es el tamaño de la cuota
  sino el umbral de evidencia que define quién puede entrar en ella, y sin esa distinción ambos casos
  se ven iguales.
- **FR-033a5**: El numerador y el denominador MUST persistirse junto al puntaje, de modo que un
  cambio del nivel de confianza pueda recalcularse **sin recorrer el historial de señales**.
- **FR-033a2**: Mientras no exista volumen de likes suficiente para poblar el respaldo, la respuesta
  MUST reportarse como *sin candidatos* según la precedencia de FR-056. MUST NOT sustituirse por
  ningún otro criterio de ordenamiento no declarado en configuración.
- **FR-033b**: El top-N de respaldo MUST diversificarse por MMR sobre el espacio de tags, de modo
  que exponga distintos clusters en lugar de concentrarse en el género globalmente dominante.
- **FR-033c**: El top-N de respaldo MUST precomputarse de forma global por módulo mediante un
  proceso asíncrono, con su propia periodicidad de actualización, y MUST NOT calcularse por usuario
  ni durante un request.
- **FR-033d**: Al servirse a un usuario concreto, el top-N de respaldo MUST someterse a los filtros
  obligatorios de ese usuario (edad y exclusión). Este filtrado está acotado a **operaciones de
  pertenencia y comparación sobre una lista ya ordenada y de tamaño acotado**: MUST NOT implicar
  cálculo de similitud, recomputación de scores, reordenamiento por relevancia ni diversificación.
  Cualquier operación fuera de ese conjunto MUST considerarse violación de FR-003, sin excepción por
  rendimiento o simplicidad.
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

**Fail-safe y seguridad (resueltos en revisión 2026-09-08)**

- **FR-049**: Todo filtro obligatorio MUST operar en modo **fail-closed**: ante cualquier
  incertidumbre —dato ausente, desconocido, ilegible o no disponible— MUST excluirse el ítem, nunca
  incluirlo. Esta regla prevalece sobre cualquier consideración de disponibilidad o rendimiento.
- **FR-050**: Si el conjunto de exclusión o los datos de edad del usuario **no están disponibles**
  al momento de servir, el servicio MUST rechazar la solicitud con un error explícito y reintentable;
  MUST NOT servir un resultado sin filtrar ni asumir un conjunto de exclusión vacío.
- **FR-051**: Un `age_rating` ausente, nulo, vacío o **no perteneciente al catálogo de valores
  válidos** MUST tratarse como no apto para todo público. La implementación MUST NOT usar un valor
  por defecto permisivo ante un rating desconocido.
- **FR-053**: El catálogo de valores válidos de `age_rating` y su equivalencia a edad mínima MUST
  estar definido explícitamente en la configuración versionada; incorporar un valor nuevo MUST
  requerir un cambio revisable.
- **FR-054**: Una configuración que intente desactivar, omitir o relajar los filtros obligatorios
  MUST provocar un fallo de arranque del componente, además de ser rechazada al cargarse.
- **FR-055**: La batería de verificación de los invariantes MUST cubrir, como mínimo: cada valor de
  `age_rating` válido cruzado con cada franja etaria relevante, cada origen de exclusión, cada uno
  de los estados de respuesta posibles, y los valores límite de edad. Un caso no cubierto MUST
  tratarse como cobertura incompleta.

**Contrato de lectura y estados de respuesta (resueltos en revisión 2026-09-08)**

- **FR-056**: Los estados de respuesta MUST ser mutuamente excluyentes y exhaustivos, resueltos por
  esta precedencia estricta: (1) recálculo pendiente si no hay resultado alguno servible;
  (2) sin candidatos si el resultado personalizado quedó vacío tras filtrar; (3) respaldo si se
  sirve el precomputado global; (4) obsoleto si el personalizado excedió su vigencia; (5) vigente.
  Un respaldo que queda vacío tras aplicar los filtros del usuario MUST reportarse como **sin
  candidatos**, no como respaldo.
- **FR-056a**: Cuando se sirva respaldo existiendo además un resultado personalizado vencido, la
  respuesta MUST señalar que ese personalizado obsoleto está **disponible y consultable**. El estado
  sigue siendo *respaldo* —la precedencia de FR-056 no cambia—, pero la existencia del personalizado
  vencido MUST NOT quedar oculta: el usuario MUST poder optar por verlo. Esa señal MUST distinguirse
  del estado, para que un cliente que la ignore siga comportándose correctamente.
- **FR-057**: El conjunto de estados de respuesta MUST tratarse como parte del contrato compartido:
  agregar, quitar o resignificar un estado MUST requerir coordinación y aprobación de `api-general`
  antes de mergear.
- **FR-058**: El endpoint de lectura MUST estar versionado explícitamente. MUST considerarse cambio
  incompatible: eliminar o renombrar un campo, volver obligatorio uno opcional, cambiar su tipo o
  semántica, agregar un estado de respuesta, o endurecer validaciones. Un cambio incompatible MUST
  publicarse como versión nueva conservando la anterior durante un período de coexistencia acordado.
- **FR-059**: La credencial de servicio MUST estar acotada a un único entorno. Una credencial
  válida en otro entorno MUST rechazarse igual que una credencial ausente, sin revelar el motivo
  del rechazo.
- **FR-060**: La inalcanzabilidad desde los frontends MUST ser verificable de forma automatizada:
  el servicio MUST NOT declarar ninguna ruta de exposición pública y su alcanzabilidad MUST
  restringirse por configuración de red auditable.

**Contrato de datos requerido a `api-general` (resuelto en revisión 2026-09-08)**

- **FR-061**: El evento `recomendacion.actualizar` MUST incluir, como mínimo: un **identificador
  único de evento** estable ante reentregas, el identificador del usuario, el módulo afectado, el
  ítem involucrado, el **tipo de señal** y su **marca temporal**. La ausencia de cualquiera de estos
  campos MUST considerarse un contrato insuficiente que impide implementar la feature.
- **FR-062**: El endpoint de actividad MUST permitir distinguir el tipo de señal (like, dislike,
  consumo) y su marca temporal por registro.
- **FR-063**: MUST mantenerse en este repo un documento único que enumere todos los campos
  requeridos de `api-general`, como insumo de la coordinación de contratos; ese documento MUST NOT
  sustituir a la documentación oficial alojada en `api-general`.
- **FR-064**: Si el contrato de actividad no expone el tipo de señal, la feature MUST considerarse
  bloqueada. MUST NOT implementarse un modo degradado que infiera preferencia a partir del consumo,
  salvo decisión explícita y documentada fuera de este repo.

**Resiliencia ante indisponibilidad (resueltos en revisión 2026-09-08)**

- **FR-065**: Ante indisponibilidad total de la caché —distinta de un miss— el servicio MUST
  responder con un error de servicio no disponible e indicación de reintento. MUST NOT recurrir a la
  base de datos para calcular en línea ni servir resultados sin filtrar.
- **FR-066**: La reconstrucción masiva de la caché MUST realizarse mediante un proceso asíncrono
  dedicado, con límite de tasa configurable y priorización, y MUST NOT dispararse como efecto
  colateral del tráfico de lectura.
- **FR-067**: El recálculo de cada módulo MUST ser una unidad independiente: MUST NOT exigirse
  atomicidad entre el módulo de la actividad y el módulo opuesto. El fallo de uno MUST NOT revertir
  ni invalidar el resultado ya persistido del otro, y MUST reintentarse por separado.
- **FR-068**: MUST declararse como parámetros de configuración obligatorios, con valor explícito por
  entorno: ventana de supresión de señales, número máximo de reintentos y política de backoff,
  período de retención de la marca de idempotencia, límite de antigüedad para servir resultados
  obsoletos, y vigencia de cada tipo de entrada en caché. Ninguno MUST quedar como valor implícito
  en el código.
- **FR-068a**: La retención de señales de actividad MUST ser finita y declarada como parámetro de
  configuración obligatorio por entorno. Las señales cuya antigüedad supere ese horizonte MUST
  purgarse. No MUST existir un modo de operación sin política de supresión.
- **FR-068b**: El horizonte de retención MUST ser estrictamente mayor que toda ventana operativa
  que dependa de las señales —en particular la ventana de popularidad y el período de retención de
  la marca de idempotencia—. La validación MUST ocurrir al cargar la configuración y MUST impedir
  el arranque si no se cumple, en lugar de manifestarse como degradación silenciosa.
- **FR-068c**: Antes de purgar una señal de consumo, el procedimiento MUST verificar que la
  exclusión permanente correspondiente ya esté materializada. Una señal cuya exclusión no esté
  materializada MUST NOT purgarse.
- **FR-068d**: La exclusión permanente MUST persistir **aunque su señal de origen haya sido purgada**.
  `user_exclusions` es un derivado materializado de `user_signals` con vida propia: una vez escrita,
  su permanencia no depende del hecho que la originó. La reconstrucción del conjunto de exclusiones
  a partir del historial MUST NOT considerarse un requisito.
- **FR-068d1**: El sistema MUST exponer, como medida **informativa y sin umbral de alerta**, cuántas
  exclusiones han quedado huérfanas de señal. No sostiene ninguna decisión operativa —dado FR-068d,
  la orfandad es el régimen normal, no una anomalía—, y MUST NOT usarse para disparar acciones.
- **FR-082**: El usuario MUST declarar un conjunto de **tags de gusto por módulo**, y ese conjunto
  MUST persistirse. Es el **único insumo funcional del motor que no se deriva de señal alguna**: el
  usuario lo enuncia en lugar de revelarlo al usar el sistema. MUST NOT existir un módulo activo para
  un usuario sin declaración asociada.
- **FR-083**: La declaración MUST exigir un **mínimo de cinco tags** y MUST NOT imponer máximo. El
  mínimo MUST declararse en configuración versionada (`declared_tags_min`, valor inicial **5**) y MUST
  NOT quedar implícito en el código.
- **FR-084**: La declaración MUST ocurrir **al ingresar por primera vez al módulo**, no al crear la
  cuenta. Un usuario que solo use recomendaciones de juegos MUST NOT tener que declarar tags de
  películas. La declaración de un módulo MUST NOT ser condición para operar en el otro.
- **FR-085**: Al declarar en un módulo, los tags ya declarados por el usuario en el **otro** módulo que
  pertenezcan al vocabulario compartido (FR-010b, `tag_modules`) MUST incorporarse al insumo del módulo
  nuevo, sin volver a pedirse. MUST NOT contarse para el mínimo de FR-083: el mínimo mide **elección
  deliberada en ese módulo**, y satisfacerlo con herencia dejaría a un usuario con declaración nula
  propia.
- **FR-086**: Los tags declarados MUST NOT caducar ni eliminarse por efecto del feedback posterior. El
  feedback MUST modular el **peso** del tag en el perfil, no la pertenencia del tag a la declaración.
  Un dislike sobre un ítem MUST reducir la contribución de sus tags al perfil; MUST NOT borrar una
  declaración del usuario, que es un enunciado suyo y no una inferencia del sistema.
- **FR-087**: El perfil vectorial del usuario MUST ser **derivado y reconstruible** a partir de los
  tags declarados y de las señales vigentes. MUST NOT actualizarse de forma incremental sobre su valor
  anterior, ni MUST existir un estado del perfil que no pueda recomputarse desde sus insumos. Si las
  señales se purgan (FR-068a), el perfil MUST seguir siendo reconstruible desde la declaración, que no
  se purga.
- **FR-088**: Una solicitud de recomendaciones para un módulo sin declaración MUST rechazarse como
  **precondición incumplida**, y MUST NOT producir un estado de respuesta nuevo. Los estados de
  FR-056 describen el resultado de un cálculo posible; la ausencia de declaración lo vuelve imposible
  y pertenece al contrato de la solicitud, no a su resultado. Agregar un sexto estado obligaría a
  actualizar a los tres consumidores para un caso que el cliente debe impedir antes de preguntar.
- **FR-089**: Este servicio MUST exponer un **endpoint de escritura** para registrar la declaración de
  gustos. Es una **excepción declarada** a la regla de que la API solo lee: la declaración no proviene
  de ninguna fuente externa y su autoridad nace en este repositorio (FR-082), de modo que ningún otro
  componente puede escribirla.
- **FR-089a**: El endpoint de declaración MUST responder de forma **síncrona** confirmando la
  persistencia, y MUST NOT delegarla a un proceso asíncrono. El usuario que acaba de elegir sus tags
  espera recomendaciones a continuación; una confirmación que no garantice la escritura produciría un
  rechazo inmediato por FR-088 sobre un dato que el usuario ya proporcionó.
- **FR-089b**: El endpoint de declaración MUST NOT ejecutar el motor de recomendación ni cómputo
  proporcional al catálogo. MUST limitarse a validar el mínimo (FR-083), resolver la herencia
  compartida (FR-085) y persistir, delegando el cálculo del perfil al recálculo asíncrono. La
  excepción de FR-089 alcanza a la **escritura**, no al cómputo: la prohibición de FR-003 sigue
  rigiendo sobre este endpoint como sobre el de lectura.
- **FR-090**: La segmentación regional MUST poder desactivarse por configuración: con
  `region_weight_factor = 0` el término colaborativo MUST comportarse exactamente como si la región no
  existiera, y activarla o desactivarla MUST NOT requerir cambio de esquema.
- **FR-090a**: `v1` MUST arrancar con la segmentación **activa en su intensidad mínima**
  (`region_weight_factor = 0,1`; el aporte extrarregional pesa 0,9), y MUST NOT arrancar desactivada. El
  propósito es que el camino de segmentación se ejerza en producción desde el primer despliegue, en lugar
  de estrenarse el día que alguien cambie el valor sobre tráfico real. Costo aceptado: `v1` no observa la
  línea de base sin segmentación, de modo que la condición de revisión de FR-081 exige poner el factor en
  `0` deliberadamente para medir (RD-79).
  > Revierte la prescripción de RD-74 (`v1` desactivada). No revierte la **capacidad**: FR-090 sigue
  > exigiendo que `0` sea representable, que es lo que RD-76 corrigió.
- **FR-081**: La segmentación regional del término colaborativo MUST implementarse como **ponderación**,
  no como filtro: los usuarios de la misma región MUST pesar más, y los de otras regiones MUST seguir
  contribuyendo con peso reducido. El factor MUST declararse en configuración versionada y MUST NOT
  quedar implícito en el código.
- **FR-081a**: La ponderación regional MUST degradar de forma continua: en una región con pocos
  usuarios, el término colaborativo MUST seguir produciendo resultado a partir de las demás regiones,
  en lugar de quedar sin insumo. No MUST existir un valor del factor que anule por completo el aporte
  de las otras regiones; ese caso equivaldría al filtro duro que FR-081 descarta.
- **FR-081b**: El factor MUST definirse como la **intensidad de la segmentación**: una señal de la misma
  región del usuario pesa `1` y una de otra región pesa `1 − region_weight_factor`. El dominio admisible
  MUST ser `0 <= region_weight_factor < 1`, **inclusivo abajo** —`0` es el neutro de FR-090— y
  **estricto arriba** —`1` anula el aporte extrarregional y es el caso que FR-081a prohíbe—.
- **FR-080**: La caché de recomendaciones de un usuario MUST invalidarse en el mismo acto en que se
  actualiza su resultado precomputado. No MUST existir una vía por la que el resultado se actualice y
  la caché sobreviva.
- **FR-080a**: El recálculo del top-N de un usuario MUST dispararse al acumular un número de
  interacciones nuevas declarado en **configuración versionada**, y ese umbral MUST NOT quedar
  implícito en el código. El conteo MUST llevarse por usuario y MUST reiniciarse al recalcular. El
  valor inicial de ese umbral es **10 interacciones**.
- **FR-069**: Un evento duplicado que llegue **después** de expirar su marca de idempotencia MUST
  poder reprocesarse sin corromper el estado: el resultado MUST ser equivalente al ya existente.

**Determinismo y diversidad (resueltos en revisión 2026-09-08)**

- **FR-070**: El desempate entre ítems con idéntico score MUST resolverse por un criterio secundario
  estable e independiente del orden de llegada de los datos, definido en la configuración versionada.
  El orden de iteración de las estructuras de datos MUST NOT ser el criterio de desempate.
- **FR-071**: La diversidad MUST medirse como la **proporción máxima del top-N atribuible a un mismo
  cluster de tags**, con la definición de cluster y el umbral máximo declarados en la configuración
  versionada. Esta métrica MUST ser evaluable de forma automatizada sobre cualquier top-N producido.

### Key Entities

- **Perfil de tags de usuario**: representación ponderada de las preferencias de un usuario sobre el
  vocabulario de tags; distingue el perfil por módulo del perfil general usado para la señal
  cruzada. Derivado de la actividad sincronizada; no es fuente de verdad.
- **Vector de tags de ítem**: representación de una película o juego en el espacio de tags, junto
  con su `age_rating` y el módulo al que pertenece.
- **Vocabulario de tags compartido**: espacio vectorial **único** para ambos módulos, dentro del
  cual se representan tanto películas como juegos. Su subconjunto de tags presentes en ítems de los
  dos módulos (p. ej. terror, comedia, ciencia ficción) determina qué actividades propagan su efecto
  al módulo opuesto y sostiene el cross-module boost. Es un **artefacto versionado propiedad de este
  repositorio**, derivado del catálogo sincronizado; no es contrato compartido.
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
