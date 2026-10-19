# Ejecución de prueba del runbook — Reconstrucción tras pérdida total de Redis (T046)

> **Estado: EJECUTADA el 2026-10-19, sin bloqueos informados.** T046 exige que el procedimiento lo ejecute
> **alguien ajeno a la feature**, que registre cada punto donde se trabó o tuvo que preguntar, y que esos
> puntos se corrijan en el runbook antes de cerrar la tarea. Este archivo es el registro; no se completa por
> inspección.
>
> **Dos apartamientos del procedimiento, aceptados por el equipo** (opción elegida el 2026-10-19):
> 1. **Ejecutor no del todo ajeno**: Albano Fazzito no es autor de la feature, pero revisó y aprobó los PR
>    #95, #96 y #97, así que conoce el servicio más que alguien externo.
> 2. **Sin acompañante**: nadie observó la ejecución. «Sin bloqueos» es lo que informó el ejecutor al
>    terminar, no un registro tomado en el momento.

## Datos de la ejecución

| Campo | Valor |
|---|---|
| Fecha | 2026-10-19 |
| Ejecutor (ajeno a la feature) | Albano Fazzito — revisor de los PR #95, #96 y #97, no autor (ver arriba) |
| Acompañante (solo observa, no ayuda) | Ninguno |
| Entorno | Local con `docker compose` |
| Commit del runbook usado | `34b113f`. La sección «Reconstrucción tras pérdida total de Redis» es idéntica en `ac858f1`, el `dev` al cerrar este registro: el PR #97 solo cambió `SyncVolumeDrop` |
| Hora de inicio / fin | 07:45 / 08:15 (UTC−3), 30 minutos |

## Preparación (la hace el acompañante, no el ejecutor)

1. Entorno con datos: al menos un usuario declarado en cada módulo y respaldo calculado.
2. Provocar la pérdida: `redis-cli FLUSHALL` (con la API y los workers corriendo).
3. Entregar al ejecutor solo: el enlace a `docs/runbook.md`, acceso a las herramientas del entorno y el
   aviso «Redis perdió su contenido».

## Registro de bloqueos

Una fila por cada punto donde el ejecutor se trabó, dudó, o tuvo que preguntar.

| # | Paso del runbook | Qué pasó | Corrección aplicada (commit o enlace) |
|---|---|---|---|
| — | — | Ninguno informado por el ejecutor | No hizo falta |

## Hallazgos previos a la ejecución (del autor, al redactar)

| # | Hallazgo | Corrección |
|---|---|---|
| P1 | El consumidor de `recompute:requests` recordaba haber creado su grupo: tras un `FLUSHALL`, cada lectura fallaba con `NOGROUP` hasta reiniciar el worker, y el warm-up encolaba solicitudes que nadie atendía | El consumidor recrea el grupo ante `NOGROUP` (`worker/requests_stream.py`, test `tests/integration/test_requests_stream_recovery.py`); el paso 2 del runbook lo verifica |

## Cierre

- [x] Ejecución realizada por alguien ajeno a la feature — con el apartamiento 1 de arriba
- [x] Cada bloqueo registrado tiene su corrección enlazada — no se informaron bloqueos
- [x] El runbook corregido quedó en el mismo PR que este registro — no hubo correcciones que hacer
