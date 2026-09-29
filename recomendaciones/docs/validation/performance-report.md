# Reporte de rendimiento — SC-001 (T050)

**Fecha**: 2026-09-28 · **Commit medido**: el de la migración `0003_idx_items_retired` · **Prueba**:
`pytest -m performance tests/performance -s` (bajo demanda, no es gate de CI).

## Resultado

**SC-001 se cumple**: la latencia de lectura con el catálogo a 10× es **p95 = 2,61 ms** con caché poblada,
frente al umbral de 50 ms (RD-105). Y **no depende del tamaño del catálogo**: a 1× el p95 es 4,08 ms. La
diferencia está dentro del ruido de medición; no hay tendencia creciente.

| Escala | Ítems por módulo | Usuarios | Retirados en ventana | Poblada p50 / p95 / p99 (ms) | Fría p50 / p95 / p99 (ms) |
|---|---|---|---|---|---|
| 1× | 10 000 | 2 000 | 96 + 102 | 2,30 / **4,08** / 4,45 | 5,21 / **6,21** / 7,32 |
| 10× | 100 000 | 20 000 | 984 + 1 009 | 2,27 / **2,61** / 2,84 | 8,32 / **9,31** / 10,07 |

1 500 solicitudes por escenario sobre 300 usuarios medidos, `top_n = 20`, entradas de 50 ítems.

- **Caché poblada**: `reco:`, `filters:` y `retired:` presentes. Es el camino normal.
- **Caché fría**: `filters:{user}` y `retired:{module}` se borran antes de cada solicitud, así que cada una
  repuebla desde Postgres, el único acceso a la base que INV-1 admite en la lectura. Es el peor caso.
  El top-N sigue presente, porque sin él solo se mediría `empty_pending`.

Los máximos aislados de ~40–50 ms en 1× son las primeras solicitudes tras generar los datos (caché del
planificador y del pool de conexiones). No se repiten en 10×.

## Hallazgo corregido durante la medición

La primera corrida mostró que el **camino frío crecía con el catálogo**: p95 7,97 ms (1×) → 18,55 ms (10×).
El repoblado de `retired:{module}` (§3.1) recorría `items` entero, porque ningún índice cubría
`status = 'retired'`: `idx_items_candidates` es parcial sobre `available`. La migración
`0003_idx_items_retired` agrega `items (module, retired_at) WHERE status = 'retired'`. Con ella el camino frío
queda en 6,21 → 9,31 ms. El crecimiento que resta es el tamaño del propio set de retirados (≈10× más
miembros a transferir), que §4.4 declara proporcional a la **tasa de retiro**, no al histórico. La prueba
fija ambas independencias como aserción.

## Hardware y entorno

| | |
|---|---|
| CPU | Intel Core i5-10400 @ 2,90 GHz, 6 núcleos / 12 hilos |
| Memoria | 31 GiB |
| SO | Linux 7.0.0-31 (x86_64, glibc 2.39) |
| Python | 3.12.3 |
| Infraestructura | Docker 28.4.0 local: `pgvector/pgvector:pg16`, `redis:7-alpine` (testcontainers, sin tuning) |

## Método y límites

- La latencia se mide alrededor de la llamada HTTP del `TestClient`, **en el mismo proceso** que la
  aplicación. Incluye enrutamiento, autenticación, guardas y serialización; no incluye red ni el servidor
  ASGI. Es la medida «en el servicio» que fija RD-105.
- Una sola instancia, solicitudes secuenciales: mide latencia, no capacidad. La capacidad bajo concurrencia
  depende del despliegue (réplicas, workers de uvicorn, pool de Redis) y no es parte de SC-001.
- El generador (`tests/performance/fixtures/catalog_10x.py`) es determinista por semilla. Solo los usuarios
  medidos tienen declaración, exclusiones (50 por usuario) y entradas en Redis. El resto de la población existe
  en `users`, lo que dimensiona la base sin inflar Redis: un `GET` de Redis es O(1) en el número de claves.
