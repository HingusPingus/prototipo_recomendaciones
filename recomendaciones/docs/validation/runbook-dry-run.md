# Ejecución de prueba del runbook — Reconstrucción tras pérdida total de Redis (T046)

> **Estado: PENDIENTE de ejecución humana.** T046 exige que el procedimiento lo ejecute **alguien ajeno a la
> feature**, que registre cada punto donde se trabó o tuvo que preguntar, y que esos puntos se corrijan en
> el runbook antes de cerrar la tarea. Este archivo es el registro; no se completa por inspección.

## Datos de la ejecución

| Campo | Valor |
|---|---|
| Fecha | _(AAAA-MM-DD)_ |
| Ejecutor (ajeno a la feature) | _(nombre)_ |
| Acompañante (solo observa, no ayuda) | _(nombre)_ |
| Entorno | _(staging / local con docker compose)_ |
| Commit del runbook usado | _(hash)_ |
| Hora de inicio / fin | _( / )_ |

## Preparación (la hace el acompañante, no el ejecutor)

1. Entorno con datos: al menos un usuario declarado en cada módulo y respaldo calculado.
2. Provocar la pérdida: `redis-cli FLUSHALL` (con la API y los workers corriendo).
3. Entregar al ejecutor solo: el enlace a `docs/runbook.md`, acceso a las herramientas del entorno y el
   aviso «Redis perdió su contenido».

## Registro de bloqueos

Una fila por cada punto donde el ejecutor se trabó, dudó, o tuvo que preguntar.

| # | Paso del runbook | Qué pasó | Corrección aplicada (commit o enlace) |
|---|---|---|---|
| 1 | | | |

## Hallazgos previos a la ejecución (del autor, al redactar)

| # | Hallazgo | Corrección |
|---|---|---|
| P1 | El consumidor de `recompute:requests` recordaba haber creado su grupo: tras un `FLUSHALL`, cada lectura fallaba con `NOGROUP` hasta reiniciar el worker, y el warm-up encolaba solicitudes que nadie atendía | El consumidor recrea el grupo ante `NOGROUP` (`worker/requests_stream.py`, test `tests/integration/test_requests_stream_recovery.py`); el paso 2 del runbook lo verifica |

## Cierre

- [ ] Ejecución realizada por alguien ajeno a la feature
- [ ] Cada bloqueo registrado tiene su corrección enlazada
- [ ] El runbook corregido quedó en el mismo PR que este registro
