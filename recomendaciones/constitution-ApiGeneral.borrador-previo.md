<!-- Borrador previo a la constitution ratificada de api-general, separado el 2026-09-27 del archivo
     entrelazado. Superado por constitution-ApiGeneral.md (v1.0.0). Se conserva solo como registro. -->

# Constitution — `recome-api-general`

**Sistema:** RecoMe — hub de recomendaciones de películas y videojuegos
**Repo:** `recome-api-general` (API General + DB General + DB Logs)
**Versión:** 1.0
**Estado:** Vigente — cualquier propuesta de excepción a este documento requiere revisión explícita, no una decisión unilateral de este equipo.

> Este documento es la ley interna de este repositorio. Ninguna decisión de diseño, por más
> simple o urgente que parezca, puede contradecir lo establecido acá. Si una solución "más
> fácil" implica romper uno de estos principios, la solución está mal — no el principio.

---

## 0. Este repo no es un sistema aislado

`api-general` es **una de cuatro partes** de RecoMe. Los otros tres repos —
`recomendaciones`, `notificaciones` y `frontend` — son mantenidos por otros equipos, con sus
propias bases de datos, sus propios ciclos de deploy y sus propias decisiones internas. Este
repo no tiene visibilidad ni control sobre lo que pasa *dentro* de esos repos, y ellos no
tienen visibilidad ni control sobre lo que pasa dentro de este.

Todo lo que este repo necesita de otro repo se pide por un canal explícito y contractual
(REST u evento de RabbitMQ). Nunca por atajo.

---

## 1. Rol de este repo dentro de RecoMe

`api-general` cumple tres roles no negociables en el sistema:

1. **Punto de entrada único del sistema.** Frontend Usuario y Frontend Vendedor/Admin (repo
   `frontend`) **solo** hablan con `api-general`. Ningún otro repo interno (`recomendaciones`,
   `notificaciones`) es alcanzable directamente desde un frontend. Si un frontend necesita datos
   de recomendaciones o necesita disparar una notificación o un reporte, la petición pasa por
   `api-general`, que orquesta hacia el repo correspondiente.
2. **Autenticación y autorización centralizada.** Este repo es el dueño de la identidad de
   usuario y de las reglas de autorización del sistema. Ningún otro repo reimplementa o
   duplica esta lógica.
3. **Fuente única de verdad de los contratos compartidos.** Este repo aloja y versiona:
   - Las specs **OpenAPI** de todos los endpoints internos consumidos entre repos.
   - Los **JSON Schema** de todos los eventos de RabbitMQ del sistema.

   Esto aplica incluso para contratos cuya implementación *runtime* no vive acá (por ejemplo,
   el broker de RabbitMQ lo hostea `notificaciones`, pero el schema del evento se documenta
   acá). Si un contrato no está documentado en este repo, no es un contrato válido del sistema.

### Lo que este repo NO es

- No es el dueño de los datos de perfiles de tags, vectores de similitud ni del cálculo de
  recomendaciones — eso vive y se calcula en `recomendaciones`.
- No es el dueño de la infraestructura de mensajería (broker, definición base de
  exchanges/colas) — eso lo hostea `notificaciones`, aunque los *contratos* de los eventos que
  viajan por ahí se documenten acá.
- No renderiza ni sirve UI — eso es responsabilidad de `frontend`.
- No genera ni almacena archivos exportables (reportes, adjuntos) — eso vive en `notificaciones`
  (DB Archivos en MinIO + webserver Nginx).

---

## 2. Principios no negociables (heredados del sistema, no reabribles acá)

Estos principios gobiernan a los cuatro repos por igual. Este repo los implementa; no los
reinterpreta ni los relaja bajo ninguna circunstancia, incluyendo presión de deadline,
"total, es solo para una feature interna", o cualquier argumento de simplicidad.

1. **Cero acceso directo a base de datos ajena.** `api-general` nunca se conecta directamente
   a la DB de `recomendaciones` (PostgreSQL+pgvector) ni a la DB Archivos de `notificaciones`
   (MinIO), ni ningún otro repo se conecta directo a DB General o DB Logs. Toda esa
   comunicación es HTTP REST o evento de RabbitMQ.
2. **`api-general` es la única puerta de entrada para los frontends.** No se expone ningún
   endpoint de `recomendaciones` o `notificaciones` directamente a `frontend`, ni siquiera
   "temporalmente" o "solo para un dashboard interno".
3. **Los contratos de eventos son compartidos, no propiedad de quien los publica o consume.**
   `api-general` puede publicar (`recomendacion.actualizar`, `reporte.generar`,
   `notificacion.enviar`) y consumir (`reporte.listo`) eventos, pero ningún cambio a un schema
   de evento es una decisión unilateral de este equipo, aunque este repo sea quien lo publica.
4. **Todo contrato REST expuesto a otro repo se documenta con OpenAPI en este repo**, y se
   versiona explícitamente si el cambio rompe compatibilidad. No se modifica de forma breaking
   un endpoint consumido por otro repo sin coordinación previa.
5. **Autenticación servicio-a-servicio separada de la autenticación de usuario final.** Las
   llamadas internas que otros repos hacen contra `api-general` (p. ej. Data Transformer o
   Analytics) usan API key interna por entorno. Ningún endpoint interno queda expuesto sin
   este control, incluso si "no tiene datos sensibles".
6. **Cada repo es dueño exclusivo de su propio esquema de datos.** Ningún otro repo puede
   asumir la estructura interna de DB General o DB Logs más allá de lo que expone el contrato
   REST. Simétricamente, este repo no asume estructura interna de las bases de los otros repos.
7. **Nombres de eventos y convenciones de API se definen una sola vez, acá, antes de
   implementarse en cualquier lado.** Si este equipo necesita un evento o endpoint nuevo que
   afecta a otro repo, primero se define en la documentación de contratos de este repo y se
   coordina con los equipos afectados — no se implementa primero "para probar" y se documenta
   después.

Cualquier decisión de diseño interna a este repo que entre en conflicto con estos siete puntos
**no es una decisión válida**, sin importar cuánto simplifique el desarrollo a corto plazo.

---

## 3. Stack tecnológico de este repo

Decidido a nivel de sistema; no se reabre salvo justificación técnica fuerte y coordinación
explícita con los otros tres equipos (un cambio acá puede tener impacto en cómo los demás
repos consumen este servicio).

| Componente | Tecnología |
|---|---|
| API General | Java / Spring Boot |
| DB General | PostgreSQL (usuarios, catálogo, actividad) |
| DB Logs | Cassandra (eventos y trazas de alto volumen) |
| Mensajería (cliente) | Cliente RabbitMQ compatible (broker hosteado por `notificaciones`) |
| Documentación de contratos | OpenAPI (REST) + JSON Schema (eventos) |

**Por qué DB General es PostgreSQL y DB Logs es Cassandra**, y por qué son bases separadas:
usuarios/catálogo/actividad son datos transaccionales y relacionales; eventos y trazas son de
alto volumen, append-heavy y no requieren las garantías transaccionales de Postgres. No se
migra una a la otra, ni se fusionan, sin discusión explícita de arquitectura.

---

## 4. Comunicación saliente y entrante de este repo

### 4.1 REST — expuesto por este repo

- Todo endpoint que otro repo (`recomendaciones`, `notificaciones`, `frontend`/Analytics)
  consuma de acá debe tener spec OpenAPI versionada en este repo.
- Cambios breaking requieren nueva versión de endpoint (no se pisa la anterior sin período de
  coexistencia coordinado con los consumidores conocidos).
- Todo acceso interno (no de usuario final) requiere la API key interna del entorno
  correspondiente.

### 4.2 REST — consumido por este repo

- Si `api-general` necesita datos o funcionalidad de `recomendaciones` o `notificaciones`,
  lo hace exclusivamente contra los endpoints REST que esos repos expongan y documenten
  (documentación linkeada o replicada en este repo), nunca contra su base de datos.
- Cualquier suposición sobre la estructura interna de esos servicios más allá de lo que su
  contrato expone es una violación de este documento.

### 4.3 RabbitMQ — eventos publicados por este repo

| Evento | Consumidor | Notas |
|---|---|---|
| `recomendacion.actualizar` | Worker de `recomendaciones` | Dispara recálculo asíncrono; el cálculo pesado nunca ocurre en este repo ni en tiempo de request. |
| `reporte.generar` | Módulo de Reportes Exportables (`notificaciones`) | |
| `notificacion.enviar` | Módulo de Notificaciones Push/Mail (`notificaciones`) | También puede ser publicado por otros módulos, no solo por este repo. |

### 4.4 RabbitMQ — eventos consumidos por este repo

| Evento | Publicador | Notas |
|---|---|---|
| `reporte.listo` | Módulo de Reportes Exportables (`notificaciones`) | Este repo reacciona (p. ej. actualiza estado, notifica al usuario final vía sus propios canales) sin asumir estructura interna del módulo de reportes. |

### 4.5 Reglas de contrato de eventos

- El **schema** (JSON Schema) de cada evento de la tabla anterior vive documentado en este
  repo, sin importar quién lo publica o consume.
- Este repo puede publicar/consumir estos eventos, pero **no puede cambiar su schema
  unilateralmente**. Todo cambio de contrato de evento requiere:
  1. Actualizar la documentación del contrato en este repo.
  2. Avisar explícitamente a todos los repos publicadores/consumidores del evento afectado.
  3. Obtener conformidad de esos equipos antes de mergear el cambio — no después.
- El broker en sí (deploy, exchanges/colas base) es infraestructura de `notificaciones`. Este
  repo no administra esa infraestructura, solo publica/consume contra ella como cliente.

---

## 5. Qué se considera "cambio interno" y qué no

Un cambio es **interno** (no requiere coordinación externa) si:
- Solo afecta lógica, código o esquema de datos que ningún otro repo consume directa o
  indirectamente vía contrato.
- No modifica ningún endpoint documentado en OpenAPI ni ningún schema de evento.
- No cambia el comportamiento observable de un contrato ya publicado (aunque la
  implementación interna cambie).

Un cambio **no es interno**, y requiere coordinación explícita fuera de este repo, si:
- Modifica el request/response de un endpoint consumido por `recomendaciones`,
  `notificaciones`, `frontend` o Analytics.
- Modifica el schema, el nombre, o la semántica de cualquiera de los eventos listados en la
  sección 4.
- Introduce un endpoint o evento nuevo que otro repo va a necesitar consumir.
- Cambia las reglas de autenticación servicio-a-servicio (API key interna).

Ante la duda, se trata como cambio no-interno. Es más barato coordinar de más que romper un
contrato en producción.

---

## 6. Testing mínimo requerido

Este repo no puede validar su corrección solo con tests unitarios internos, porque su
superficie de riesgo principal es romper contratos que otros tres equipos dependen de leer.

**Obligatorio antes de cualquier release:**

1. **Tests unitarios** de la lógica de negocio propia (auth, orquestación, reglas de
   catálogo/actividad).
2. **Tests de integración contra DB General y DB Logs** reales (o equivalentes de test:
   Postgres/Cassandra efímeros), no mockeadas, para validar migraciones y queries.
3. **Contract testing de todo endpoint expuesto** contra su spec OpenAPI documentada en este
   repo — cualquier divergencia entre la implementación y la spec publicada es un bug de
   release, no un detalle menor.
4. **Contract testing / validación de schema de cada evento publicado** (`recomendacion.actualizar`,
   `reporte.generar`, `notificacion.enviar`) contra el JSON Schema documentado, antes de
   publicarlo a RabbitMQ.
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
