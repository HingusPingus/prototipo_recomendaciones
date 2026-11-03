# Pendientes y contexto para seguir

Recordatorio del estado al **2026-10-26** y de lo que sigue. El detalle de cada tema está en los documentos
enlazados.

## Dónde quedamos

El sistema completo corre en Dokploy como una **prueba** (no va a producción por ahora):

- **Frontend** (`recome-Frontend`): registro y login contra `api-general`. Su nginx publica la SPA y reenvía
  `/api/v1/*` a `api-general`, salvo `/api/v1/internal/**` y el actuator (solo pasa `health`).
- **`api-general`** (`recome-api-general`): emite y valida el JWT de usuario (`/auth/signup`, `/auth/login`),
  contraseñas con BCrypt y mínimo de 8 caracteres. El registro público crea `USUARIO_FINAL`.
- **recomendaciones** (este repo): `reco-api` y `reco-worker`, conectados al `api-general` **real** por la
  sincronización REST cada 15 minutos, y al RabbitMQ de `notificaciones`. Ya no hay `api-general` simulado (RD-124).

Todo son *Applications* de Dokploy con proveedor Docker que descargan imágenes privadas de `ghcr.io`, más servicios
*Database* para Postgres y Redis. Cada merge a `main` que pasa el CI publica la imagen y redespliega solo
(`POST /api/application.deploy`). Guías:

- recomendaciones: [`recomendaciones/docs/despliegue.md`](recomendaciones/docs/despliegue.md)
- `api-general`: `docs/operations/despliegue-dokploy.md` de su repo
- frontend: `dockerfile/despliegue-dokploy.md` de su repo

## Lo que sigue

### En Dokploy

- [ ] **`reco-api`: cambiar el Run Command a `reco-api-con-migraciones`** y quitar el comando con `${IFS}`. La imagen
      ya lo trae.
- [ ] **Confirmar que se borraron los servicios Compose viejos**, y que el paquete `recomendaciones` de `ghcr.io`
      quedó privado. Las Applications ya tienen credenciales de registry, así que pasarlo a privado no rompe nada.

### Decisiones pendientes

- [ ] **Alta pública de vendedores de Bolucompras.** `POST /auth/vendedores/signup` en `api-general` crea cuentas
      `ADMIN_BOLUCOMPRAS`, que pueden publicar y ver las analíticas de los anuncios, y se alcanza desde internet a
      través del front. Para esta prueba alcanza con cerrarlo en el nginx del front. La alternativa es exigir una
      clave o que un admin promueva al vendedor, y hay que definirlo con el equipo de Bolucompras.
- [ ] **Riesgos abiertos de RD-123** (registrados en RD-124): sin backup de `reco-postgres` y sin alertas evaluadas,
      ahora con usuarios reales. Resolverlo (lo mínimo: un backup diario a un destino externo y alguien que reciba
      las alertas críticas) o aceptarlo de nuevo con fecha y motivo en `data-model.md`.

### Para que las recomendaciones tengan contenido

- [ ] **Catálogo en `api-general`.** Arranca vacío: la sincronización corre bien, pero con 0 ítems, así que no hay
      nada que recomendar. Hay que cargarlo con sus importadores (TMDB y Steam) o por su API de operador, con al
      menos 5 tags elegibles por módulo para poder declarar gustos.
- [ ] **Eventos en tiempo real.** `api-general` tiene el outbox apagado: las interacciones llegan cada 15 minutos con
      la sincronización. Para encenderlo:
      1. que `api-general` se conecte al broker de `notificaciones` (`SPRING_RABBITMQ_*`, con su vhost);
      2. correr la prueba de humo de
         [`migracion-v3.md`](recomendaciones/docs/contracts/migracion-v3.md);
      3. activar el outbox v3 con el v2 apagado.

### Tareas de la spec 001

- [ ] **T048**, la validación final, la última tarea abierta. Estaba bloqueada porque `api-general` no publicaba
      `usuario.eliminado`. Su `main` ya trae un commit que lo publica («publicar baja»): revisar si alcanza para
      cerrar el ítem del DoD, el criterio de T048 y la fila 180 de la matriz de trazabilidad.

### Seguridad (aceptado mientras sea una prueba)

- Todo va por HTTP, sin TLS: contraseñas y tokens viajan sin cifrar. Antes de cualquier uso real, activar HTTPS en el
  dominio del front.
- No hay límite de intentos en `/auth/login` ni revocación de sesiones: un token sirve hasta que vence (120 minutos).

## Para trabajar desde otra máquina

- **Workflows por SSH.** Un token OAuth de `gh` sin el scope `workflow` no puede pushear cambios en
  `.github/workflows/`: GitHub rechaza el push. Hay que pushear por SSH, o hacer `gh auth refresh -s workflow`.
- **PRs.** En este repo van a `dev`, y `dev` pasa a `main` por PR. En `recome-api-general` y `recome-Frontend` van
  directo a `main`. Se mergea con «Create a merge commit». Cada merge a `main` es un deploy.
- **Los clones de los otros repos dentro de esta carpeta están ignorados** (`.gitignore`) y tienen su propio git. En
  la máquina anterior, el clon de `recome-Frontend` tiene cambios sin commitear de otra sesión, ya superados por lo
  que se mergeó, y el de `recome-api-general` tiene un `main` local divergente. Conviene clonar de nuevo en vez de
  copiarlos.
