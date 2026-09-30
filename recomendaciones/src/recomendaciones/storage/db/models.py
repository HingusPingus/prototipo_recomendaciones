"""Esquema de DB Recomendaciones — las 18 tablas de `data-model.md` §2 (T003).

`data-model.md` es autoritativo: cada tabla cita su subsección. Toda FK declara su política
`ON DELETE` (criterio explícito de T003, cuatro omisiones históricas: RD-19, RD-31, RD-35, RD-43).
La migración inicial (`migrations/versions/0001_initial.py`) es la fuente del DDL; este módulo es
su espejo ORM y `tests/integration/test_models_match_migrations.py` verifica que no diverjan.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --- Enumerados (nombres de tipo en Postgres) ----------------------------------------------------
# `age_rating` replica el `age_rating_catalog` de v1 (§4.1). Agregar un nivel es migración del enum
# en ambos repos más versión nueva de config (§4.1): la migración es una instantánea versionada.
Module = ENUM("peliculas", "juegos", name="module_enum", create_type=False)
ItemStatus = ENUM("available", "retired", name="item_status", create_type=False)
AgeRating = ENUM("ATP", "+13", "+18", name="age_rating", create_type=False)
AgeRatingSource = ENUM("declared", "unknown_defaulted", name="age_rating_source", create_type=False)
ProfileScope = ENUM("peliculas", "juegos", "general", name="profile_scope", create_type=False)
SignalType = ENUM("like", "dislike", "consumo", name="signal_type", create_type=False)
SignalSource = ENUM("sync", "evento", name="signal_source", create_type=False)
ExclusionOrigin = ENUM("like", "dislike", "consumo", name="exclusion_origin", create_type=False)
SyncStatus = ENUM("running", "success", "failed", name="sync_status", create_type=False)
ProcessedResult = ENUM(
    "recomputed",
    "skipped_no_shared_tag",
    "signal_recorded",
    "skipped_not_materialized",
    "dlq",
    "suppressed",  # 0002: baja de cuenta procesada (T058)
    name="processed_result",
    create_type=False,
)
SuppressionState = ENUM("in_progress", "completed", "failed", name="suppression_state", create_type=False)

TSTZ = DateTime(timezone=True)


# §2.8 --------------------------------------------------------------------------------------------
class EngineConfigVersion(Base):
    __tablename__ = "engine_config_versions"

    config_version: Mapped[str] = mapped_column(Text, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(TSTZ)

    __table_args__ = (
        Index(
            "uq_engine_config_single_active",
            text("(deactivated_at IS NULL)"),
            unique=True,
            postgresql_where=text("deactivated_at IS NULL"),
        ),
    )


# §2.1 --------------------------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    max_age_ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    age_config_version: Mapped[str] = mapped_column(
        Text, ForeignKey("engine_config_versions.config_version", ondelete="RESTRICT"), nullable=False
    )
    age_derived_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)  # forense (RD-6)
    region: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)

    __table_args__ = (
        CheckConstraint("region ~ '^[A-Z]{2}$'", name="ck_users_region_iso"),
        Index("idx_users_birth_date", "birth_date"),
        # §2.1 declara un índice parcial `WHERE age_config_version <> :activa`: un predicado con
        # parámetro no es expresable en DDL. La causa B se consulta por igualdad sobre las versiones
        # inactivas (`IN (...)`), que este índice sí sirve.
        Index("idx_users_age_config_version", "age_config_version"),
        Index("idx_users_synced_at", "synced_at"),
    )


# §2.2 --------------------------------------------------------------------------------------------
class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    module: Mapped[str] = mapped_column(Module, nullable=False)
    status: Mapped[str] = mapped_column(ItemStatus, nullable=False, server_default="available")
    retired_at: Mapped[datetime | None] = mapped_column(TSTZ)
    min_age_ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="2")
    age_config_version: Mapped[str] = mapped_column(
        Text, ForeignKey("engine_config_versions.config_version", ondelete="RESTRICT"), nullable=False
    )
    age_rating: Mapped[str] = mapped_column(AgeRating, nullable=False, server_default="+18")
    age_rating_source: Mapped[str] = mapped_column(AgeRatingSource, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)

    __table_args__ = (
        CheckConstraint("(retired_at IS NOT NULL) = (status = 'retired')", name="ck_items_retired_at"),
        Index(
            "idx_items_candidates",
            "module",
            "min_age_ordinal",
            postgresql_where=text("status = 'available'"),
        ),
        # 0003: repoblado de `retired:{module}` acotado por la ventana, no por el catálogo (T050).
        Index("idx_items_retired", "module", "retired_at", postgresql_where=text("status = 'retired'")),
        Index("idx_items_synced_at", "synced_at"),
    )


# §2.3 --------------------------------------------------------------------------------------------
class Tag(Base):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    synced_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)

    __table_args__ = (CheckConstraint("name = btrim(name) AND length(name) > 0", name="ck_tags_name"),)


class ItemTag(Base):
    __tablename__ = "item_tags"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    tag_name: Mapped[str] = mapped_column(Text, ForeignKey("tags.name", ondelete="RESTRICT"), primary_key=True)

    __table_args__ = (Index("idx_item_tags_tag", "tag_name"),)


# §2.13 -------------------------------------------------------------------------------------------
class VocabVersion(Base):
    __tablename__ = "vocab_versions"

    version: Mapped[str] = mapped_column(Text, primary_key=True)
    tag_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(TSTZ)
    deactivated_at: Mapped[datetime | None] = mapped_column(TSTZ)

    __table_args__ = (
        Index(
            "uq_vocab_single_active",
            text("(activated_at IS NOT NULL AND deactivated_at IS NULL)"),
            unique=True,
            postgresql_where=text("activated_at IS NOT NULL AND deactivated_at IS NULL"),
        ),
    )


class VocabVersionTag(Base):
    __tablename__ = "vocab_version_tags"

    # §2.13 no declara política para esta FK: la composición es parte de la versión, y una versión
    # purgada (sin vectores) se lleva su composición. CASCADE.
    version: Mapped[str] = mapped_column(
        Text, ForeignKey("vocab_versions.version", ondelete="CASCADE"), primary_key=True
    )
    tag_name: Mapped[str] = mapped_column(Text, primary_key=True)  # sin FK a tags (RD-18)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint("version", "dimension", name="uq_vocab_version_dimension"),)


# §2.4 --------------------------------------------------------------------------------------------
class ItemVector(Base):
    __tablename__ = "item_vectors"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    vocab_version: Mapped[str] = mapped_column(
        Text, ForeignKey("vocab_versions.version", ondelete="RESTRICT"), primary_key=True
    )
    vector: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)

    __table_args__ = (Index("idx_item_vectors_vocab", "vocab_version"),)


# §2.5 --------------------------------------------------------------------------------------------
class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(ProfileScope, primary_key=True)
    vocab_version: Mapped[str] = mapped_column(
        Text, ForeignKey("vocab_versions.version", ondelete="RESTRICT"), primary_key=True
    )
    vector: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)

    __table_args__ = (Index("idx_user_profiles_vocab", "vocab_version"),)


# §2.6 --------------------------------------------------------------------------------------------
class UserSignal(Base):
    __tablename__ = "user_signals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    origin_interaction_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), nullable=False
    )
    signal_type: Mapped[str] = mapped_column(SignalType, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)
    received_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False, server_default=func.now())
    source: Mapped[str] = mapped_column(SignalSource, nullable=False)

    __table_args__ = (
        UniqueConstraint("origin_interaction_id", name="uq_signals_origin_interaction"),
        Index(
            "idx_signals_vigente",
            "user_id",
            "item_id",
            text("occurred_at DESC"),
            text("id DESC"),
        ),
        Index("idx_signals_user_received", "user_id", "received_at"),
    )


# §2.7 --------------------------------------------------------------------------------------------
class UserExclusion(Base):
    __tablename__ = "user_exclusions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), primary_key=True
    )
    origin: Mapped[str] = mapped_column(ExclusionOrigin, nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)


# §2.9 --------------------------------------------------------------------------------------------
class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TSTZ)
    status: Mapped[str] = mapped_column(SyncStatus, nullable=False)
    entity_counts: Mapped[dict | None] = mapped_column(JSONB)
    failure_reason: Mapped[str | None] = mapped_column(Text)  # forense

    __table_args__ = (
        Index(
            "idx_sync_runs_success",
            text("finished_at DESC"),
            postgresql_where=text("status = 'success'"),
        ),
    )


# §2.17 -------------------------------------------------------------------------------------------
class ProcessRun(Base):
    """Resultado de cada corrida de un proceso de una corrida —transformer y jobs batch— (T066).

    Esos procesos no exponen servidor de métricas: lo que fijan queda acá y el worker lo re-expone.
    """

    __tablename__ = "process_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    component: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)  # forense
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB)  # hechos propios del job (p. ej. retención vigente, RD-54)

    __table_args__ = (
        CheckConstraint("status IN ('success', 'failed')", name="ck_process_runs_status"),
        Index("idx_process_runs_component", "component", text("finished_at DESC")),
    )


# §2.10 -------------------------------------------------------------------------------------------
class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)  # forense
    result: Mapped[str] = mapped_column(ProcessedResult, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)

    __table_args__ = (Index("idx_processed_expires", "expires_at"),)


# §2.11 -------------------------------------------------------------------------------------------
class ItemPopularity(Base):
    __tablename__ = "item_popularity"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    config_version: Mapped[str] = mapped_column(
        Text, ForeignKey("engine_config_versions.config_version", ondelete="RESTRICT"), primary_key=True
    )
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    engaged_user_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    popularity_score: Mapped[float] = mapped_column(Double, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "like_count >= 0 AND like_count <= engaged_user_count", name="ck_popularity_counts"
        ),
        CheckConstraint("popularity_score BETWEEN 0 AND 1", name="ck_popularity_score"),
        Index("idx_popularity_ranking", "config_version", text("popularity_score DESC")),
    )


# §2.12 -------------------------------------------------------------------------------------------
class TagModule(Base):
    __tablename__ = "tag_modules"

    tag_name: Mapped[str] = mapped_column(Text, ForeignKey("tags.name", ondelete="CASCADE"), primary_key=True)
    module: Mapped[str] = mapped_column(Module, primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)

    __table_args__ = (Index("idx_tag_modules_module", "module", "tag_name"),)


# §2.14 -------------------------------------------------------------------------------------------
class UserDeclaredTag(Base):
    __tablename__ = "user_declared_tags"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    module: Mapped[str] = mapped_column(Module, primary_key=True)
    tag_name: Mapped[str] = mapped_column(Text, ForeignKey("tags.name", ondelete="RESTRICT"), primary_key=True)
    declared_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)  # forense

    __table_args__ = (
        Index("idx_declared_user_module", "user_id", "module"),
        Index("idx_declared_tag", "tag_name"),
    )


# §2.15 -------------------------------------------------------------------------------------------
class UserSuppression(Base):
    __tablename__ = "user_suppressions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)  # sin FK: lápida
    requested_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)
    state: Mapped[str] = mapped_column(SuppressionState, nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    verified_at: Mapped[datetime | None] = mapped_column(TSTZ)

    __table_args__ = (
        CheckConstraint("(state = 'completed') = (verified_at IS NOT NULL)", name="ck_suppressions_verified"),
        Index("idx_suppressions_open", "requested_at", postgresql_where=text("state <> 'completed'")),
    )


# §2.16 -------------------------------------------------------------------------------------------
class ItemPromotion(Base):
    __tablename__ = "item_promotions"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), primary_key=True
    )
    promoted_at: Mapped[datetime] = mapped_column(TSTZ, nullable=False)  # forense
    config_version: Mapped[str] = mapped_column(
        Text, ForeignKey("engine_config_versions.config_version", ondelete="RESTRICT"), nullable=False
    )


ALL_TABLES = tuple(sorted(Base.metadata.tables))
