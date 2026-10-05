# Demo local

Levanta el servicio de recomendaciones completo con un **`api-general` simulado**, mientras la integración con
el `api-general` real no está disponible.

| Qué | ¿Real o simulado? |
|---|---|
| API de recomendaciones, worker, Data Transformer, jobs batch | **Reales**: los procesos de siempre (`reco-api`, `reco-worker`, `reco-transformer`, `reco-batch`), sin cambios |
| Postgres + pgvector, Redis, RabbitMQ | **Reales**, en contenedores |
| `api-general` | **Simulado** (`reco-demo api-general`, en [`src/recomendaciones/demo/`](../src/recomendaciones/demo/)): sirve el contrato de sync y reenvía las llamadas a la API, como lo haría el real |
| Catálogo y usuarios | Datos de demo ([`demo/datos.py`](../src/recomendaciones/demo/datos.py)): 40 películas, 36 juegos, 2 personas y 24 usuarios de fondo con actividad |

Todo corre desde la misma imagen, el [`Dockerfile`](../Dockerfile) del servicio. El
[`docker-compose.yml`](../docker-compose.yml) elige qué proceso corre en cada contenedor.

## Requisitos

Solo **Docker Desktop**. No hace falta Python.

## Levantar

```powershell
cd recomendaciones
docker compose up --build -d
docker compose ps -a
```

La primera vez tarda unos minutos, porque construye la imagen. Está lista cuando `api` figura como `healthy` y
`semilla-declaraciones` terminó con `Exited (0)`. Para seguir el arranque: `docker compose logs -f`.

| URL | Qué es |
|---|---|
| http://localhost:8080/docs | **Swagger de la demo**: desde acá se hace todo el recorrido |
| http://localhost:8000 | API de recomendaciones real (pide `X-Internal-API-Key`; sin Swagger, por FR-060) |
| http://localhost:15672 | Consola de RabbitMQ (usuario `reco`, clave `reco`) |

Los tres puertos se publican solo en `127.0.0.1`: se llega desde esta máquina, no desde la red. Los endpoints
`/demo` no piden credenciales y reenvían a la API con la API key interna, así que no conviene exponerlos.

## Guion sugerido

Todo desde http://localhost:8080/docs, con **Try it out**. En `usuario` se puede poner el alias (`ana`, `tomas`).

1. **Sin gustos declarados no hay recomendaciones.**
   `GET /demo/usuarios/ana/recomendaciones`, con `module=peliculas` → **412**. La declaración es obligatoria (FR-088).

2. **Ana declara sus gustos.** `POST /demo/usuarios/ana/declaracion`:
   ```json
   {"module": "peliculas", "tags": ["terror", "sobrenatural", "suspenso", "misterio", "drama"]}
   ```
   → **201**. Hay que usar al menos 5 tags del vocabulario (`GET /demo/tags`).

3. **Primero el respaldo, enseguida lo personalizado.** Repetir el `GET` del paso 1:
   - Si responde `result_type: "fallback"`, está sirviendo los populares mientras el worker calcula.
   - Uno o dos segundos después, responde **`"personalized"`**, con predominio de terror y suspenso. La
     diversificación (MMR) evita que un solo género ocupe toda la lista.

   La lectura nunca calcula nada: solo lee el top-N ya precalculado en Redis.

4. **Herencia entre módulos.** Declarar juegos:
   ```json
   {"module": "juegos", "tags": ["terror", "supervivencia", "puzzle", "accion", "aventura"]}
   ```
   La respuesta trae `inherited_tags`: los tags declarados en películas que también existen en juegos (acá,
   `terror`).

5. **Una interacción cambia las recomendaciones en vivo.** `POST /demo/usuarios/ana/interacciones`, con el
   título del primer ítem recomendado:
   ```json
   {"item": "El conjuro", "signal_type": "dislike"}
   ```
   Esto publica `recomendacion.actualizar` en RabbitMQ. Al repetir el `GET`, el ítem ya no aparece. Un `like`
   también lo saca (ya interactuó con él), pero además refuerza sus tags y el recálculo trae ítems parecidos
   (en la demo, cada interacción recalcula). Cómo funciona por dentro:
   [`src/recomendaciones/demo/README.md`](../src/recomendaciones/demo/README.md).

6. **Filtro de edad sin excepciones.** Tomás tiene 15 años. Declarar para `tomas` los mismos tags de
   terror del paso 2 y pedir sus recomendaciones: no aparece **ningún** ítem `+18`, aunque sean los más
   afines a sus gustos. Comparar con la lista de Ana (columna `age_rating`).

7. **La API real, directo** (opcional, para mostrar que la simulada solo reenvía):
   ```powershell
   curl.exe -i "http://localhost:8000/internal/v1/recommendations/<user_id de ana>?module=peliculas" `
     -H "X-Internal-API-Key: demo.clave-local-solo-para-la-demo"
   ```
   El `user_id` sale de `GET /demo/usuarios`. Sin el header, responde **401**.

## Reiniciar y apagar

```powershell
docker compose down -v                 # borra todo: la próxima vez arranca de cero
docker compose up --build -d
```

Una declaración es definitiva (FR-086a): para repetir el guion con la misma persona hay que reiniciar.

## Si algo falla

- `docker compose logs preparacion`: la sincronización o los jobs de popularidad y respaldo.
- `docker compose logs worker`: el cálculo de recomendaciones y el consumo de eventos.
- `docker compose logs api-general-simulada`: los pedidos del Transformer y las llamadas de la demo.
- Si el puerto 8000, 8080 o 15672 está ocupado, cambiar el primero de los dos números en `ports:` de
  `docker-compose.yml` (por ejemplo, `"127.0.0.1:8081:8080"`).

## Cuando esté el `api-general` real

El simulado cumple los contratos publicados
([`api-general-sync.openapi.yaml`](../specs/001-recomendaciones-precomputadas/contracts/api-general-sync.openapi.yaml)
y los schemas de eventos). Desde el 2026-10-05 el runtime de `api-general` también los cumple: ruta de sync,
header, IDs UUID, `module` en la actividad y v3 en su propio exchange (`docs/contracts/alineacion-sync.md`,
`migracion-v3.md`). **Lo que todavía impide usarlo** es operativo: su catálogo no tiene tags cargados, y su
sync de catálogo responde 503 hasta que todo ítem incluido tenga tags elegibles
(`vocabulario-catalogo-actividad.md`).

Cuando el catálogo esté etiquetado:

1. Sacar del `docker-compose.yml` los servicios `api-general-simulada` y `semilla-declaraciones`.
2. Apuntar `RECO_API_GENERAL_BASE_URL` a su URL, con `/api/v1`.
3. Usar su API key del entorno, recibida por un canal seguro: nunca en el repo.
4. Confirmar con `notificaciones` los exchanges `recomendacion.actualizar.v3` y `usuario.eliminado`.
5. Verificar en staging como indica `alineacion-sync.md` («Cómo lo verificamos»).

Fuera de eso, los procesos del servicio no cambian: el paquete `recomendaciones.demo` solo lo usa `reco-demo`.

### Qué no simula

Una demo en verde prueba este servicio contra el contrato propuesto, no la compatibilidad con el
`api-general` de hoy. El simulado no cubre:

- la baja de cuenta: no publica `usuario.eliminado`, así que la supresión no se ve en la demo;
- ítems retirados: todo el catálogo va como `available`;
- el vencimiento del snapshot de catálogo (410) del runtime real;
- el 503 de la sync de catálogo cuando un ítem no tiene tags elegibles o tiene una clasificación inválida.

## Imagen sin compose

El `Dockerfile` sirve para cualquier proceso. Toda la configuración llega por variables `RECO_*` (ver
`.env.example`):

```powershell
docker build -t recomendaciones .
docker run --env-file .env -p 8000:8000 recomendaciones                  # API (comando por defecto)
docker run --env-file .env recomendaciones reco-worker
docker run --env-file .env recomendaciones alembic upgrade head
```
