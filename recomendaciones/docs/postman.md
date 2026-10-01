# Probar la API con Postman

## 1. Levantar la API

La API necesita Postgres, Redis, RabbitMQ y el worker. Todo eso se levanta junto con el archivo
[`docker-compose.yml`](../docker-compose.yml). Con **Docker Desktop abierto**:

```powershell
cd C:\Users\Gabriel\Desktop\Work\prototipo_recomendaciones\recomendaciones
docker compose up --build -d     # la primera vez, o después de cambiar código
docker compose ps -a             # lista cuando `api` dice (healthy)
```

| Puerto | Qué es |
|---|---|
| `http://localhost:8000` | **API de recomendaciones** (la real). Exige el header `X-Internal-API-Key` |
| `http://localhost:8080` | `api-general` simulado. Swagger en http://localhost:8080/docs |
| `http://localhost:15672` | Consola de RabbitMQ (`reco` / `reco`) |

Para apagar: `docker compose down`. Para **volver a cero** (borra declaraciones e interacciones):
`docker compose down -v` y después `docker compose up -d`.

## 2. Qué herramienta usar

| Herramienta | Notas |
|---|---|
| **Postman (app de escritorio)** | Recomendada. Descarga: https://www.postman.com/downloads/ o `winget install -e --id Postman.Postman` |
| Postman web | Solo llega a `localhost` si se instala el *Postman Desktop Agent*; es más simple usar la app |
| Thunder Client o Postman para VS Code | Extensiones de VS Code; importan la misma colección |
| Bruno o Insomnia | Alternativas de escritorio; también importan colecciones de Postman |
| Swagger de la simulada | http://localhost:8080/docs, sin instalar nada. Cubre la carpeta 2; la API real no tiene Swagger (FR-060) |

## 3. Importar la colección

1. En Postman: **Import** → arrastrar
   [`docs/postman/recomendaciones-demo.postman_collection.json`](postman/recomendaciones-demo.postman_collection.json).
2. La colección trae sus variables, sin necesidad de un *environment*:

   | Variable | Valor |
   |---|---|
   | `api_url` | `http://localhost:8000` |
   | `demo_url` | `http://localhost:8080` |
   | `api_key` | `demo.clave-local-solo-para-la-demo` (la del `docker-compose.yml`) |
   | `ana_id` | `87d0e2b0-b3ba-5d0a-90af-33694fa70903` (adulta) |
   | `tomas_id` | `b215a316-0b3b-54c4-a7a7-6084b723ccc6` (15 años) |
   | `usuario_inexistente_id` | un UUID que no existe, para el 404 |

3. Cada pedido tiene tests que verifican el status esperado. Para correr todo de una vez: clic derecho en la
   colección → **Run collection**. Hay que correrla **sobre un stack recién levantado**, porque declarar gustos
   es definitivo: la segunda corrida da 409 donde la primera daba 201.

La colección completa se probó contra el stack: 34 de 34 pedidos con el status esperado.

## 4. Endpoints

### API de recomendaciones (puerto 8000)

| Método | Ruta | Auth | Respuestas |
|---|---|---|---|
| GET | `/health/live` | no | 200: el proceso vive |
| GET | `/health/ready` | no | 200 si Postgres y Redis responden; si no, 503 |
| GET | `/health` | no | 200 con el detalle por dependencia |
| GET | `/internal/v1/recommendations/{user_id}?module=peliculas\|juegos` | sí | 200, 401, 404, 412, 422, 503 |
| POST | `/internal/v1/declarations/{user_id}` | sí | 201, 401, 404, 409, 422, 503 |

**`GET /internal/v1/recommendations/{user_id}`**

| Parámetro | Obligatorio | Valores |
|---|---|---|
| `module` | sí | `peliculas` o `juegos` |
| `top_n` | no | 10 a 50 (por defecto 20) |
| `prefer` | no | `stale`: si no hay resultado vigente pero sí uno anterior, lo prefiere al respaldo |

`limit` o `cursor` → 422: el contrato no pagina.

```json
{
  "user_id": "87d0e2b0-…",
  "module": "peliculas",
  "result_type": "personalized",
  "computed_at": "2026-09-30T23:51:40Z",
  "config_version": "…",
  "stale_available": false,
  "items": [{"item_id": "…", "position": 1, "score": 0.83, "config_version": "…"}]
}
```

`result_type` puede ser:

| Valor | Qué significa |
|---|---|
| `personalized` | Calculado para el usuario |
| `personalized_stale` | Calculado para el usuario, pero anterior al último cambio |
| `fallback` | Los populares, mientras el worker calcula |
| `empty_pending` | Todavía no hay nada que servir |
| `empty_no_candidates` | No hay ítems aptos para el usuario |

**`POST /internal/v1/declarations/{user_id}`**

```json
{"module": "peliculas", "tags": ["terror", "sobrenatural", "suspenso", "misterio", "drama"]}
```

- Exige al menos 5 tags del vocabulario del módulo. Para verlos: `GET {{demo_url}}/demo/tags?module=peliculas`.
- Responde `declared_tags` e `inherited_tags`: los tags del otro módulo que también existen en este.
- Una segunda declaración en el mismo módulo responde 409.

**Errores.** El cuerpo es `{"error": "<código>", "message": "…"}`:

| Status | Código | Cuándo |
|---|---|---|
| 401 | `unauthorized` | Falta la key, es inválida o es de otro entorno |
| 404 | `unknown_user` | El usuario no existe en la proyección |
| 409 | `declaration_already_exists` | Segunda declaración en el mismo módulo |
| 412 | `declaration_required` | No declaró gustos en ese módulo |
| 422 | `invalid_request` | Parámetros inválidos |
| 503 | — | Redis no disponible |

### `api-general` simulado (puerto 8080, sin auth en `/demo`)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/demo/usuarios[?incluir_fondo=true]` | Personas de la demo con su `user_id` |
| GET | `/demo/catalogo?module=` | Ítems con `item_id`, título, tags y clasificación |
| GET | `/demo/tags?module=` | Vocabulario declarable |
| POST | `/demo/usuarios/{alias o id}/declaracion` | Reenvía a `POST /internal/v1/declarations` |
| GET | `/demo/usuarios/{alias o id}/recomendaciones?module=&top_n=` | Reenvía a la API y agrega título, tags y clasificación |
| POST | `/demo/usuarios/{alias o id}/interacciones` | `{"item": "<título o id>", "signal_type": "like\|dislike\|consumo"}`. Publica el evento en RabbitMQ |
| GET | `/internal/v1/sync/users` · `/catalog/items` · `/activity[?since=]` | Contrato de sync que lee el Data Transformer (con API key) |

## 5. Ejemplos sin Postman

`curl.exe` viene con Windows:

```powershell
curl.exe -i http://localhost:8000/health/ready
curl.exe -i "http://localhost:8000/internal/v1/recommendations/87d0e2b0-b3ba-5d0a-90af-33694fa70903?module=peliculas" `
  -H "X-Internal-API-Key: demo.clave-local-solo-para-la-demo"
```

Con `Invoke-RestMethod`:

```powershell
$h = @{ "X-Internal-API-Key" = "demo.clave-local-solo-para-la-demo" }
$body = '{"module":"peliculas","tags":["terror","sobrenatural","suspenso","misterio","drama"]}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/internal/v1/declarations/87d0e2b0-b3ba-5d0a-90af-33694fa70903 `
  -Headers $h -ContentType "application/json" -Body $body
```
