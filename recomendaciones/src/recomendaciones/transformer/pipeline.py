"""Data Transformer: materialización idempotente de usuarios, catálogo y actividad (T029).

Proyecta dato ajeno —solo lee de `api-general` (Principio IV)— y escribe únicamente la **proyección**:
`users`, `items`, `tags`, `item_tags` y `user_signals` (`source = 'sync'`), más la bitácora `sync_runs`.
Los derivados los escriben sus procesos propios (DI-13): este módulo no toca popularidad, vocabulario,
vectores ni perfiles. Las exclusiones las materializa el resolutor (T014), que invalida `filters:`.

Una corrida:
1. Registra `sync_runs` en curso (transacción propia: una interrupción queda distinguible).
2. Lee los tres listados. Si el catálogo no se confirma completo, o su volumen cae por debajo de
   `sync_volume_delta_ratio` respecto de la última corrida exitosa, **aborta sin marcar retiros** (CR-9,
   FR-074): un listado truncado que se procesa retira ítems vigentes en masa.
3. Escribe todo en **una** transacción: una interrupción no deja estado a medias.
   - Usuarios: sin `birth_date` o sin `region` ISO válida ⟹ rechazo, violación de contrato con contador
     propio por campo y corrida `failed` (§7.5, §7.6). Lápida: un `user_id` suprimido no se materializa
     (DI-29). La ausencia de un usuario **no** es una baja (FR-091a).
   - Ítems: sin tags válidos ⟹ rechazo sin bloquear al resto (FR-021b). Tags tal cual llegan (RD-16);
     vacío o mal formado ⟹ se descarta la asignación y se cuenta (§7.8). Rating fuera del catálogo ⟹ el
     más restrictivo (FR-051, CR-15). Retiro lógico por señal explícita (CR-7) o por ausencia de un
     listado completo (CR-8), por **una sola rama**; reaparecer lo repone (FR-074 es revocable).
   - Actividad: deduplicación por `origin_interaction_id` con la comparación de §7.10.
   - Una corrección de `birth_date` que cambia el ordinal invalida los resultados del usuario en el mismo
     acto, Redis primero (DI-2c, FR-080c).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from recomendaciones.config.loader import EngineConfig
from recomendaciones.engine.age import derive_max_age_ordinal, min_age_ordinal_for_rating
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.errors import UpstreamError
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient, delete_user_scope
from recomendaciones.storage.cache.filters import FiltersCache
from recomendaciones.storage.db.exclusions import ExclusionResolver, ResolveResult
from recomendaciones.storage.db.models import Item, ItemTag, SyncRun, Tag, User, UserSignal, UserSuppression
from recomendaciones.storage.db.session import SessionFactory
from recomendaciones.transformer.client import ApiGeneralClient, Listing
from recomendaciones.transformer.regions import is_valid_region

log = logging.getLogger(__name__)
MODULES = ("peliculas", "juegos")


@dataclass
class SyncReport:
    run_id: int
    status: str
    failure_reason: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    retired: int = 0
    rejected_users: int = 0


@dataclass
class _Plan:
    """Lo que la corrida escribirá: calculado antes de abrir la transacción de escritura."""

    users: pd.DataFrame
    items: list[dict[str, Any]]
    activity: list[dict[str, Any]]
    violations: list[str] = field(default_factory=list)


class SyncPipeline:
    def __init__(
        self,
        factory: SessionFactory,
        client: ApiGeneralClient,
        filters: FiltersCache,
        cache: CacheClient,
        config: EngineConfig,
        metrics: Metrics,
        *,
        volume_delta_ratio: float,
        redelivery_window_hours: int,
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self._factory = factory
        self._client = client
        self._filters = filters
        self._cache = cache
        self._cfg = config
        self._metrics = metrics
        self._ratio = volume_delta_ratio
        self._window = timedelta(hours=redelivery_window_hours)
        self._today = today
        self._resolver = ExclusionResolver(filters.invalidate)

    # --- bitácora ----------------------------------------------------------------------------
    def _start(self) -> int:
        with self._factory.begin() as s:
            run = SyncRun(started_at=datetime.now(UTC), status="running")
            s.add(run)
            s.flush()
            return run.id

    def _finish(self, run_id: int, status: str, reason: str | None, counts: dict[str, int] | None) -> None:
        with self._factory.begin() as s:
            self._finish_in(s, run_id, status, reason, counts)

    def _finish_in(self, s: Session, run_id: int, status: str, reason: str | None, counts: dict[str, int] | None) -> None:
        s.execute(
            sa.update(SyncRun)
            .where(SyncRun.id == run_id)
            .values(status=status, failure_reason=reason, entity_counts=counts, finished_at=sa.func.now())
        )

    def _last_success_counts(self) -> dict[str, int] | None:
        with self._factory() as s:
            return s.scalar(
                sa.select(SyncRun.entity_counts)
                .where(SyncRun.status == "success")
                .order_by(SyncRun.finished_at.desc())
                .limit(1)
            )

    def _high_watermark(self) -> datetime | None:
        with self._factory() as s:
            latest = s.scalar(sa.select(sa.func.max(UserSignal.occurred_at)).where(UserSignal.source == "sync"))
        return None if latest is None else latest - self._window

    # --- validación (pandas: transformación del Data Transformer, constitución) ---------------
    def _validate_users(self, rows: list[dict[str, Any]], run_id: int) -> tuple[pd.DataFrame, list[str]]:
        frame = pd.DataFrame(rows, columns=["id", "birth_date", "region"])
        frame["birth"] = pd.to_datetime(frame["birth_date"], errors="coerce", format="%Y-%m-%d").dt.date
        missing_birth = frame["birth"].isna()
        bad_region = ~frame["region"].map(is_valid_region).astype(bool)
        violations: list[str] = []
        for _, row in frame[missing_birth].iterrows():
            self._metrics.inc("contract_violations_total", field="birth_date")
            log.warning("violación de contrato: usuario sin birth_date (CR-1)", extra={"user_id": row["id"], "sync_run_id": run_id})
            violations.append(f"birth_date:{row['id']}")
        for _, row in frame[bad_region].iterrows():
            self._metrics.inc("contract_violations_total", field="region")
            log.warning("violación de contrato: usuario sin region ISO válida (CR-5)", extra={"user_id": row["id"], "sync_run_id": run_id})
            violations.append(f"region:{row['id']}")
        valid = frame[~missing_birth & ~bad_region].copy()
        valid["id"] = valid["id"].map(uuid.UUID)
        return valid, violations

    def _validate_items(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for row in rows:
            names: list[str] = []
            for raw in row.get("tags") or []:
                name = raw if isinstance(raw, str) else ""
                if not name.strip():
                    self._metrics.inc("projection_field_anomalies_total", field="tag_name", reason="empty")
                elif name != name.strip():
                    self._metrics.inc("projection_field_anomalies_total", field="tag_name", reason="malformed")
                elif name not in names:
                    names.append(name)  # mismo nombre dos veces: se unifica (RD-16)
            module = row.get("module")
            if module not in MODULES:
                self._metrics.inc("projection_field_anomalies_total", field="module", reason="invalid")
                continue
            if not names:
                self._metrics.inc("projection_field_anomalies_total", field="tags", reason="missing")
                log.warning("ítem sin tags rechazado en la ingesta (FR-021b)", extra={"item_id": row.get("id")})
                continue
            rating = row.get("age_rating")
            declared = self._cfg.ordinal_for_rating(rating) is not None
            out.append(
                {
                    "id": uuid.UUID(str(row["id"])),
                    "module": module,
                    "tags": sorted(names),
                    "age_rating": rating if declared else self._cfg.most_restrictive_rating,
                    "min_age_ordinal": min_age_ordinal_for_rating(rating, self._cfg),
                    "age_rating_source": "declared" if declared else "unknown_defaulted",
                    "retired": row.get("status") == "retired",
                }
            )
        return out

    # --- corrida ----------------------------------------------------------------------------
    def run(self) -> SyncReport:
        run_id = self._start()
        try:
            users, catalog, activity = self._client.list_users(), self._client.list_catalog(), None
            activity = self._client.list_activity(self._high_watermark())
        except UpstreamError as exc:
            self._finish(run_id, "failed", f"api-general no disponible: {exc.message}", None)
            return SyncReport(run_id, "failed", exc.message)
        abort = self._completeness_problem(catalog)
        if abort:
            self._finish(run_id, "failed", abort, {"items": len(catalog.rows)})
            log.warning("sincronización abortada sin marcar retiros", extra={"sync_run_id": run_id, "reason": abort})
            return SyncReport(run_id, "failed", abort)

        valid_users, violations = self._validate_users(users.rows, run_id)
        plan = _Plan(valid_users, self._validate_items(catalog.rows), activity.rows, violations)
        counts = {"users": len(users.rows), "items": len(catalog.rows), "activity": len(activity.rows)}
        status = "failed" if plan.violations else "success"
        reason = f"violaciones de contrato en usuarios: {len(plan.violations)}" if plan.violations else None
        with self._factory.begin() as s:
            changed_age = self._write_users(s, plan.users)
            retired = self._write_items(s, plan.items)
            affected = self._write_activity(s, plan.activity)
            resolved = self._resolver.resolve(s, affected)
            for user_id in sorted(changed_age, key=str):  # Redis primero (FR-080c)
                delete_user_scope(self._cache, keys.user_scoped_patterns(user_id))
            self._finish_in(s, run_id, status, reason, counts)
        self._after_commit(resolved, changed_age)
        return SyncReport(run_id, status, reason, counts, retired, len(plan.violations))

    def _completeness_problem(self, catalog: Listing) -> str | None:
        if not catalog.complete:
            return f"listado de catálogo no confirmado completo: {len(catalog.rows)} de {catalog.total} (CR-9)"
        last = self._last_success_counts()
        if last and last.get("items"):
            ratio = len(catalog.rows) / last["items"]
            self._metrics.set("sync_volume_delta_ratio", ratio, entity="items")
            if ratio < self._ratio:
                return f"volumen anómalo del catálogo: ratio {ratio:.2f} < {self._ratio} (FR-074)"
        return None

    def _after_commit(self, resolved: ResolveResult, changed_age: set[uuid.UUID]) -> None:
        self._resolver.after_commit(resolved)
        for user_id in changed_age:
            self._filters.invalidate(user_id)

    def _write_users(self, s: Session, frame: pd.DataFrame) -> set[uuid.UUID]:
        suppressed = set(s.scalars(sa.select(UserSuppression.user_id)))
        existing = {r.id: r for r in s.execute(sa.select(User.id, User.birth_date, User.max_age_ordinal, User.region))}
        changed_age: set[uuid.UUID] = set()
        today = self._today()
        for row in frame.itertuples(index=False):
            if row.id in suppressed:
                continue  # lápida (FR-091b)
            ordinal = derive_max_age_ordinal(row.birth, today, self._cfg)
            current = existing.get(row.id)
            if current is None:
                s.execute(
                    insert(User).values(
                        id=row.id,
                        birth_date=row.birth,
                        max_age_ordinal=ordinal,
                        age_config_version=self._cfg.config_version,
                        age_derived_at=sa.func.now(),
                        region=row.region,
                        synced_at=sa.func.now(),
                    )
                )
                continue
            values: dict[str, Any] = {"synced_at": sa.func.now(), "region": row.region}
            if current.birth_date != row.birth or current.max_age_ordinal != ordinal:
                values.update(birth_date=row.birth, max_age_ordinal=ordinal, age_config_version=self._cfg.config_version, age_derived_at=sa.func.now())
                if current.max_age_ordinal != ordinal:
                    changed_age.add(row.id)
            s.execute(sa.update(User).where(User.id == row.id).values(**values))
        return changed_age

    def _write_items(self, s: Session, items: list[dict[str, Any]]) -> int:
        listed = {item["id"] for item in items}
        for name in sorted({t for item in items for t in item["tags"]}):
            s.execute(insert(Tag).values(name=name, synced_at=sa.func.now()).on_conflict_do_update(index_elements=[Tag.name], set_={"synced_at": sa.func.now()}))
        current_status = dict(s.execute(sa.select(Item.id, Item.status)).all())
        retired = 0
        for item in items:
            status = "retired" if item["retired"] else "available"
            stmt = insert(Item).values(
                id=item["id"],
                module=item["module"],
                status=status,
                retired_at=sa.func.now() if status == "retired" else None,
                min_age_ordinal=item["min_age_ordinal"],
                age_config_version=self._cfg.config_version,
                age_rating=item["age_rating"],
                age_rating_source=item["age_rating_source"],
                synced_at=sa.func.now(),
            )
            keep_retired_at = sa.case((Item.status == "retired", Item.retired_at), else_=sa.func.now())
            s.execute(
                stmt.on_conflict_do_update(
                    index_elements=[Item.id],
                    set_={
                        "module": stmt.excluded.module,
                        "status": stmt.excluded.status,
                        "retired_at": keep_retired_at if status == "retired" else None,
                        "min_age_ordinal": stmt.excluded.min_age_ordinal,
                        "age_config_version": stmt.excluded.age_config_version,
                        "age_rating": stmt.excluded.age_rating,
                        "age_rating_source": stmt.excluded.age_rating_source,
                        "synced_at": sa.func.now(),
                    },
                )
            )
            if status == "retired" and current_status.get(item["id"]) != "retired":
                retired += 1
            wanted = set(item["tags"])
            have = set(s.scalars(sa.select(ItemTag.tag_name).where(ItemTag.item_id == item["id"])))
            if have - wanted:
                s.execute(sa.delete(ItemTag).where(ItemTag.item_id == item["id"], ItemTag.tag_name.in_(sorted(have - wanted))))
            for tag in sorted(wanted - have):
                s.execute(insert(ItemTag).values(item_id=item["id"], tag_name=tag))
        # Retiro por ausencia de un listado completo (CR-8): misma rama que el retiro explícito.
        absent = [item_id for item_id, st in current_status.items() if st == "available" and item_id not in listed]
        if absent:
            s.execute(sa.update(Item).where(Item.id.in_(absent)).values(status="retired", retired_at=sa.func.now()))
            retired += len(absent)
        return retired

    def _write_activity(self, s: Session, rows: list[dict[str, Any]]) -> set[uuid.UUID]:
        users = set(s.scalars(sa.select(User.id)))
        items = set(s.scalars(sa.select(Item.id)))
        affected: set[uuid.UUID] = set()
        now = datetime.now(UTC)
        for row in rows:
            try:
                user_id, item_id = uuid.UUID(row["user_id"]), uuid.UUID(row["item_id"])
                occurred = datetime.fromisoformat(str(row["occurred_at"]).replace("Z", "+00:00"))
                kind = row["signal_type"]
                oid = row["origin_interaction_id"]
            except (KeyError, ValueError, TypeError):
                self._metrics.inc("projection_field_anomalies_total", field="activity", reason="invalid")
                continue
            if kind not in ("like", "dislike", "consumo") or not oid:
                self._metrics.inc("projection_field_anomalies_total", field="activity", reason="invalid")
                continue
            if user_id not in users or item_id not in items:
                continue  # usuario rechazado o suprimido, o ítem aún no materializado
            inserted = s.execute(
                insert(UserSignal)
                .values(origin_interaction_id=oid, user_id=user_id, item_id=item_id, signal_type=kind, occurred_at=occurred, source="sync")
                .on_conflict_do_nothing(index_elements=[UserSignal.origin_interaction_id])
                .returning(UserSignal.id)
            ).scalar_one_or_none()
            if inserted is None:
                existing = s.execute(
                    sa.select(UserSignal.user_id, UserSignal.item_id, UserSignal.signal_type, UserSignal.occurred_at).where(
                        UserSignal.origin_interaction_id == oid
                    )
                ).one()
                if tuple(existing) == (user_id, item_id, kind, occurred):
                    self._metrics.inc("signal_duplicate_rejections_total", source="sync")
                else:
                    self._metrics.inc("contract_violations_total", field="origin_interaction_id")
                    log.warning("origin_interaction_id reutilizado para otro hecho (FR-029e1)", extra={"origin_interaction_id": oid})
                continue
            self._metrics.observe("signal_ingest_lag_seconds", max((now - occurred).total_seconds(), 0.0), source="sync")
            affected.add(user_id)
        return affected
