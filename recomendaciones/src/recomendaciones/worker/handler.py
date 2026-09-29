"""Manejador de `recomendacion.actualizar` (T024 + T064 + T027; umbral de FR-080a con T060).

1. Idempotencia de evento por `event_id` (T024): un evento vigente ya procesado se confirma sin recalcular.
2. Persistencia de la señal y su exclusión (T064).
3. Si corresponde recalcular —umbral de interacciones por (usuario, módulo), FR-080a—, recálculo del
   módulo de la actividad y, si algún tag del ítem es compartido, del opuesto (T027, FR-010a).
4. Registro del resultado en `processed_events` (auditoría accionable de FR-010c).

Un crash entre 2 y 4 hace que el evento se reentregue: la señal se deduplica y el recálculo converge.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import numpy as np
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from recomendaciones.config.loader import EngineConfig
from recomendaciones.engine.collaborative import regional_weights, score_from_neighbors, select_neighbors
from recomendaciones.engine.content import content_scores
from recomendaciones.engine.cross_module import cross_module_scores
from recomendaciones.engine.postprocess import PostprocessRequest, postprocess
from recomendaciones.engine.profile import Profile, SignalWeights, build_profile
from recomendaciones.engine.scoring import Candidate, combine
from recomendaciones.engine.vocabulary import TagVector
from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module, ProfileScope
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.repository import CachedItem, RecommendationEntry, RecommendationRepository
from recomendaciones.storage.db.exclusions import load_exclusion_set
from recomendaciones.storage.db.models import (
    EngineConfigVersion,
    Item,
    User,
    UserDeclaredTag,
    UserProfile,
    UserSignal,
    UserSuppression,
)
from recomendaciones.storage.db.session import SessionFactory
from recomendaciones.worker.catalog import CatalogCache, CatalogSnapshot
from recomendaciones.worker.idempotency import EventIdempotency
from recomendaciones.worker.inputs import load_profile_inputs
from recomendaciones.worker.schemas import ActualizarEvent
from recomendaciones.worker.signals import NOT_MATERIALIZED, SignalIngestor


class RecomputeOnSignal(Protocol):
    def on_signal(self, event: ActualizarEvent) -> str: ...


class ActualizarHandler:
    def __init__(
        self,
        *,
        idempotency: EventIdempotency,
        ingestor: SignalIngestor,
        should_recompute: Callable[[ActualizarEvent], bool],
        recompute: RecomputeOnSignal,
    ) -> None:
        self._idempotency = idempotency
        self._ingestor = ingestor
        self._should_recompute = should_recompute
        self._recompute = recompute

    def _work(self, event: ActualizarEvent) -> str:
        outcome = self._ingestor.persist(event)
        if outcome.status == NOT_MATERIALIZED:
            return "skipped_not_materialized"
        if not self._should_recompute(event):
            return "signal_recorded"  # umbral de FR-080a no alcanzado (RD-95)
        return self._recompute.on_signal(event)

    def __call__(self, event: ActualizarEvent) -> str:
        result = self._idempotency.process_once(event.event_id, lambda: self._work(event))
        return "duplicate" if result is None else result


# --- Recálculo de un par (usuario, módulo) y propagación (T027) -----------------------------------

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ModuleOutcome:
    status: str  # written | skipped_undeclared | aborted_suppressed | skipped_incompatible_age | no_vocabulary | user_not_found
    items: int = 0


def _vector_literal(vec: TagVector) -> list[float]:
    return [float(x) for x in vec.values]


class Recomputer:
    """Recalcula un par (usuario, módulo) con el motor y el post-proceso completos y escribe Redis.

    Reconstruye y persiste `user_profiles` —es su escritor único (§2.5)—, pero solo los alcances que
    recalcula: el del módulo y el `general`. El conteo de FR-080a toma como cota el `computed_at` del
    perfil **de cada módulo** (RD-104); reescribir el del módulo opuesto reiniciaría su contador sin
    haberlo recalculado. La marca de supresión se consulta inmediatamente antes de escribir (FR-092a).
    """

    def __init__(
        self,
        factory: SessionFactory,
        repository: RecommendationRepository,
        config: EngineConfig,
        metrics: Metrics,
        *,
        catalog: CatalogCache | None = None,
        signaler=None,  # noqa: ANN001 — RecomputeSignaler: reencola el módulo opuesto que falló (T025)
    ) -> None:
        self._signaler = signaler
        self._factory = factory
        self._repository = repository
        self._cfg = config
        self._metrics = metrics
        self._catalog = catalog or CatalogCache()
        self._weights = SignalWeights(config.peso_like, config.peso_dislike)
        self._age_fingerprints: dict[str, str | None] = {}

    # --- datos ---------------------------------------------------------------------------------
    def _age_compatible(self, s, version: str) -> bool:  # noqa: ANN001
        if version == self._cfg.config_version:
            return True
        if version not in self._age_fingerprints:
            payload = s.scalar(sa.select(EngineConfigVersion.payload).where(EngineConfigVersion.config_version == version))
            catalog = None if payload is None else payload.get("age_rating_catalog")
            self._age_fingerprints[version] = None if catalog is None else json.dumps(catalog, sort_keys=True)
        active = json.dumps([lvl.model_dump() for lvl in self._cfg.age_rating_catalog], sort_keys=True)
        return self._age_fingerprints[version] == active

    def _suppressed(self, s, user_id: uuid.UUID) -> bool:  # noqa: ANN001
        return s.get(UserSuppression, user_id) is not None

    def _has_preference_activity(self, s, user_id: uuid.UUID, module: Module) -> bool:  # noqa: ANN001
        declared = s.scalar(
            sa.select(sa.literal(True)).where(UserDeclaredTag.user_id == user_id, UserDeclaredTag.module == module.value).limit(1)
        )
        if declared:
            return True
        signal = s.scalar(
            sa.select(sa.literal(True))
            .select_from(UserSignal)
            .join(Item, Item.id == UserSignal.item_id)
            .where(UserSignal.user_id == user_id, Item.module == module.value, UserSignal.signal_type.in_(("like", "dislike")))
            .limit(1)
        )
        return bool(signal)

    def _neighbor_likes(self, s, neighbors: list[uuid.UUID]) -> dict[uuid.UUID, frozenset[uuid.UUID]]:  # noqa: ANN001
        if not neighbors:
            return {}
        rows = s.execute(
            sa.text(
                "SELECT user_id, item_id FROM ("
                "  SELECT DISTINCT ON (user_id, item_id) user_id, item_id, signal_type FROM user_signals"
                "  WHERE user_id = ANY(:u) AND signal_type IN ('like', 'dislike')"
                "  ORDER BY user_id, item_id, occurred_at DESC, id DESC"
                ") v WHERE signal_type = 'like'"
            ),
            {"u": neighbors},
        ).all()
        out: dict[uuid.UUID, set[uuid.UUID]] = {}
        for user_id, item_id in rows:
            out.setdefault(user_id, set()).add(item_id)
        return {u: frozenset(items) for u, items in out.items()}

    def _other_profiles(self, s, user_id: uuid.UUID, module: Module, vocab_version: str):  # noqa: ANN001, ANN202
        """Perfiles de los demás usuarios del módulo y su región (T061). La región viaja por la PK de `users`:
        no es predicado de filtro, de modo que el índice que §2.1 difería a esta tarea no se justifica."""
        rows = s.execute(
            sa.select(UserProfile.user_id, UserProfile.vector, User.region)
            .join(User, User.id == UserProfile.user_id)
            .where(
                UserProfile.scope == module.value,
                UserProfile.vocab_version == vocab_version,
                UserProfile.user_id != user_id,
            )
        ).all()
        vectors = {r.user_id: TagVector(np.asarray(r.vector, dtype=np.float64), vocab_version) for r in rows}
        return vectors, {r.user_id: r.region for r in rows}

    def _persist_profiles(self, user_id: uuid.UUID, profiles: dict[ProfileScope, Profile]) -> None:
        with self._factory.begin() as s:
            for scope, profile in profiles.items():
                stmt = insert(UserProfile).values(
                    user_id=user_id,
                    scope=scope.value,
                    vocab_version=profile.vector.vocab_version,
                    vector=_vector_literal(profile.vector),
                    signal_count=profile.signal_count,
                    computed_at=sa.func.now(),
                )
                s.execute(
                    stmt.on_conflict_do_update(
                        index_elements=[UserProfile.user_id, UserProfile.scope, UserProfile.vocab_version],
                        set_={"vector": stmt.excluded.vector, "signal_count": stmt.excluded.signal_count, "computed_at": sa.func.now()},
                    )
                )

    # --- recálculo -----------------------------------------------------------------------------------
    def recompute(self, user_id: uuid.UUID, module: Module, reason: str) -> ModuleOutcome:
        module = Module(module)
        started = time.monotonic()
        with self._factory() as s:
            user = s.execute(sa.select(User.max_age_ordinal, User.age_config_version, User.region).where(User.id == user_id)).one_or_none()
            if user is None:
                return self._done(module, ModuleOutcome("user_not_found"), started)
            if self._suppressed(s, user_id):
                return self._done(module, ModuleOutcome("aborted_suppressed"), started)
            declared = s.scalar(
                sa.select(sa.literal(True)).where(UserDeclaredTag.user_id == user_id, UserDeclaredTag.module == module.value).limit(1)
            )
            if not declared:
                return self._done(module, ModuleOutcome("skipped_undeclared"), started)
            if not self._age_compatible(s, user.age_config_version):
                return self._done(module, ModuleOutcome("skipped_incompatible_age"), started)  # DI-2e
            snapshot = self._catalog.get(s, self._cfg.config_version)
            if snapshot is None:
                return self._done(module, ModuleOutcome("no_vocabulary"), started)
            profiles, general = self._profiles(s, user_id, module, snapshot)
            opposite_activity = self._has_preference_activity(s, user_id, module.opposite)
            own = profiles.get(ProfileScope(module.value))
            others, regions = self._other_profiles(s, user_id, module, snapshot.vocab.version)
            neighbors = select_neighbors(
                own.vector if own else None,
                others,
                self._cfg.k,
                weights=regional_weights(user.region, regions, self._cfg.region_weight_factor),  # FR-081, FR-090a
                min_neighbors=self._cfg.collab_min_neighbors,  # FR-096
            )
            if own is not None and len(neighbors) < self._cfg.collab_min_neighbors:  # SC-031: se registra que no los hubo
                self._metrics.inc("collab_insufficient_neighbors_total", module=module.value)
                log.info(
                    "vecindario colaborativo por debajo del mínimo",
                    extra={"user_id": str(user_id), "reco_module": module.value, "neighbors": len(neighbors)},
                )
            likes = self._neighbor_likes(s, [n.user_id for n in neighbors])
            exclusions = load_exclusion_set(s, user_id)
        entry = self._rank(user_id, module, user.max_age_ordinal, snapshot, profiles, general, opposite_activity, neighbors, likes, exclusions)

        with self._factory() as s:  # FR-092a: inmediatamente antes de escribir
            if self._suppressed(s, user_id):
                return self._done(module, ModuleOutcome("aborted_suppressed"), started)
        self._repository.write_personalized(entry)  # Redis primero (FR-080c)
        with self._factory() as s:  # una supresión iniciada durante la escritura no debe dejar residuo
            if self._suppressed(s, user_id):
                self._repository._cache.delete(  # noqa: SLF001
                    keys.reco_key(entry.config_version, user_id, module), keys.stale_key(entry.config_version, user_id, module)
                )
                return self._done(module, ModuleOutcome("aborted_suppressed"), started)
        self._persist_profiles(user_id, profiles)
        return self._done(module, ModuleOutcome("written", len(entry.items)), started)

    def _profiles(self, s, user_id: uuid.UUID, module: Module, snapshot: CatalogSnapshot):  # noqa: ANN001, ANN202
        module_inputs = load_profile_inputs(s, user_id, ProfileScope(module.value))
        general_inputs = load_profile_inputs(s, user_id, ProfileScope.GENERAL)
        module_profile = build_profile(
            module_inputs, snapshot.vectors, snapshot.seed_items((module.value,)), snapshot.vocab, self._weights
        )
        general_profile = build_profile(
            general_inputs,
            snapshot.vectors,
            snapshot.seed_items((Module.PELICULAS.value, Module.JUEGOS.value)),
            snapshot.vocab,
            self._weights,
        )
        profiles: dict[ProfileScope, Profile] = {}
        if module_profile is not None:
            profiles[ProfileScope(module.value)] = module_profile
        if general_profile is not None:
            profiles[ProfileScope.GENERAL] = general_profile
        return profiles, general_profile

    def _rank(self, user_id, module, max_age_ordinal, snapshot, profiles, general, opposite_activity, neighbors, likes, exclusions):  # noqa: ANN001, ANN202, PLR0913
        candidates = [
            Candidate(
                item_id=row.item_id,
                module=row.module,
                available=row.available,
                min_age_ordinal=row.min_age_ordinal,
                vector=snapshot.vectors.get(row.item_id),
                popularity=snapshot.popularity.get(row.item_id, 0.0),
                tags=row.tags,
            )
            for row in snapshot.items.values()
            if row.module == module.value and row.available  # WHERE status = 'available' (FR-072)
        ]
        vectors = {c.item_id: c.vector for c in candidates}
        module_profile = profiles.get(ProfileScope(module.value))
        content = content_scores(module_profile.vector if module_profile else None, vectors)
        collab = score_from_neighbors(neighbors, likes, vectors.keys())
        cross = cross_module_scores(general.vector if general else None, vectors, has_opposite_activity=opposite_activity)
        scoring = combine(candidates, content, collab, cross, self._cfg)
        vocab = snapshot.vocab
        result = postprocess(
            scoring,
            PostprocessRequest(
                user_max_age_ordinal=max_age_ordinal,
                exclusions=exclusions,
                lambda_mmr=self._cfg.lambda_mmr,
                max_cluster_share=self._cfg.diversity_max_cluster_share,
                limit=self._cfg.top_n_max,
                cluster_of=lambda c: c.vector.principal_tag(vocab) if c.vector is not None else None,
                # Cuota de novedades (T065, RD-102): emergente = vigente sin promoción registrada (DI-27),
                # ordenado por afinidad de contenido con el perfil (FR-033a6f1).
                emergent_items=frozenset(c.item_id for c in candidates if c.item_id not in snapshot.promoted),
                affinity=content,
                novelty_quota_ratio=self._cfg.fallback_new_item_quota_ratio,
            ),
        )
        if result.quota_available:  # FR-033a8: disponible vs. ocupada
            self._metrics.set("fallback_new_item_share", result.quota_available / self._cfg.top_n_max, module=module.value, kind="available")
            self._metrics.set("fallback_new_item_share", result.quota_occupied / self._cfg.top_n_max, module=module.value, kind="occupied")
        if result.relaxations:
            self._metrics.inc("diversity_cap_relaxed_total", result.relaxations, module=module.value)
        return RecommendationEntry(
            user_id=user_id,
            module=module,
            config_version=result.config_version,
            vocab_version=vocab.version,
            max_age_ordinal=max_age_ordinal,
            computed_at=datetime.now(UTC),
            items=tuple(CachedItem(i.item_id, i.rank, i.score, i.min_age_ordinal) for i in result.items),
        )

    def _done(self, module: Module, outcome: ModuleOutcome, started: float) -> ModuleOutcome:
        self._metrics.inc("reco_recompute_total", status=outcome.status, module=module.value)
        self._metrics.observe("reco_recompute_duration_seconds", time.monotonic() - started, module=module.value)
        return outcome

    # --- evento de actividad: principal y opuesto condicional (FR-010a) ----------------------------
    def on_signal(self, event: ActualizarEvent) -> str:
        self.recompute(event.user_id, event.module, "signal")
        with self._factory() as s:
            snapshot = self._catalog.get(s, self._cfg.config_version)
        item = snapshot.items.get(event.item_id) if snapshot else None
        shared = bool(item and item.tags & snapshot.shared_tags) if snapshot else False
        reason = "shared_tag" if shared else "no_shared_tag"
        log.info(
            "decisión de propagación cross-module",
            extra={
                "event_id": str(event.event_id),
                "user_id": str(event.user_id),
                "reco_module": event.module.value,
                "propagated": shared,
                "propagation_reason": reason,
            },
        )
        self._metrics.inc("reco_cross_module_propagation_total", propagated="true" if shared else "false")
        if shared:
            try:
                self.recompute(event.user_id, event.module.opposite, "signal")  # unidad independiente (FR-067)
            except Exception:  # noqa: BLE001 — éxito parcial: el principal ya está persistido y no se revierte
                log.warning(
                    "recálculo del módulo opuesto fallido; se reencola solo el opuesto",
                    extra={"event_id": str(event.event_id), "user_id": str(event.user_id), "reco_module": event.module.opposite.value},
                )
                self._metrics.inc("reco_recompute_total", status="opposite_requeued", module=event.module.opposite.value)
                if self._signaler is None:
                    raise
                self._signaler.request(event.user_id, event.module.opposite, "opposite_retry")
            return "recomputed"
        return "skipped_no_shared_tag"
