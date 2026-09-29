"""Esquema inicial de DB Recomendaciones: 18 tablas de data-model.md §2 (T003).

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-28
"""

from __future__ import annotations

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

ENUMS = {
    "module_enum": ("peliculas", "juegos"),
    "item_status": ("available", "retired"),
    # Replica age_rating_catalog de v1 (data-model.md §4.1); agregar un nivel es una migración.
    "age_rating": ("ATP", "+13", "+18"),
    "age_rating_source": ("declared", "unknown_defaulted"),
    "profile_scope": ("peliculas", "juegos", "general"),
    "signal_type": ("like", "dislike", "consumo"),
    "signal_source": ("sync", "evento"),
    "exclusion_origin": ("like", "dislike", "consumo"),
    "sync_status": ("running", "success", "failed"),
    "processed_result": (
        "recomputed",
        "skipped_no_shared_tag",
        "signal_recorded",
        "skipped_not_materialized",
        "dlq",
    ),
    "suppression_state": ("in_progress", "completed", "failed"),
}

TABLES_DDL = [
    # §2.8 — configuración versionada; inmutabilidad por atributo (RD-37, DI-24)
    """
    CREATE TABLE engine_config_versions (
        config_version  text PRIMARY KEY,
        payload         jsonb NOT NULL,
        activated_at    timestamptz NOT NULL,
        deactivated_at  timestamptz
    )
    """,
    """
    CREATE UNIQUE INDEX uq_engine_config_single_active
        ON engine_config_versions ((deactivated_at IS NULL)) WHERE deactivated_at IS NULL
    """,
    """
    CREATE FUNCTION engine_config_versions_immutable() RETURNS trigger AS $$
    BEGIN
        IF NEW.config_version IS DISTINCT FROM OLD.config_version
           OR NEW.payload IS DISTINCT FROM OLD.payload
           OR NEW.activated_at IS DISTINCT FROM OLD.activated_at THEN
            RAISE EXCEPTION 'engine_config_versions: config_version, payload y activated_at son inmutables (DI-24)';
        END IF;
        IF OLD.deactivated_at IS NOT NULL AND NEW.deactivated_at IS DISTINCT FROM OLD.deactivated_at THEN
            RAISE EXCEPTION 'engine_config_versions: una versión desactivada no se reactiva; el rollback es hacia adelante (DI-24, RD-94)';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER trg_engine_config_versions_immutable
        BEFORE UPDATE ON engine_config_versions
        FOR EACH ROW EXECUTE FUNCTION engine_config_versions_immutable()
    """,
    # §2.1 — usuarios
    """
    CREATE TABLE users (
        id                  uuid PRIMARY KEY,
        birth_date          date NOT NULL,
        max_age_ordinal     smallint NOT NULL,
        age_config_version  text NOT NULL REFERENCES engine_config_versions (config_version) ON DELETE RESTRICT,
        age_derived_at      timestamptz NOT NULL,
        region              char(2) NOT NULL CONSTRAINT ck_users_region_iso CHECK (region ~ '^[A-Z]{2}$'),
        synced_at           timestamptz NOT NULL
    )
    """,
    "CREATE INDEX idx_users_birth_date ON users (birth_date)",
    "CREATE INDEX idx_users_age_config_version ON users (age_config_version)",
    "CREATE INDEX idx_users_synced_at ON users (synced_at)",
    # §2.2 — ítems
    """
    CREATE TABLE items (
        id                  uuid PRIMARY KEY,
        module              module_enum NOT NULL,
        status              item_status NOT NULL DEFAULT 'available',
        retired_at          timestamptz,
        min_age_ordinal     smallint NOT NULL DEFAULT 2,
        age_config_version  text NOT NULL REFERENCES engine_config_versions (config_version) ON DELETE RESTRICT,
        age_rating          age_rating NOT NULL DEFAULT '+18',
        age_rating_source   age_rating_source NOT NULL,
        synced_at           timestamptz NOT NULL,
        CONSTRAINT ck_items_retired_at CHECK ((retired_at IS NOT NULL) = (status = 'retired'))
    )
    """,
    "CREATE INDEX idx_items_candidates ON items (module, min_age_ordinal) WHERE status = 'available'",
    "CREATE INDEX idx_items_synced_at ON items (synced_at)",
    # §2.3 — vocabulario y asignación
    """
    CREATE TABLE tags (
        name       text PRIMARY KEY CONSTRAINT ck_tags_name CHECK (name = btrim(name) AND length(name) > 0),
        synced_at  timestamptz NOT NULL
    )
    """,
    """
    CREATE TABLE item_tags (
        item_id   uuid NOT NULL REFERENCES items (id) ON DELETE CASCADE,
        tag_name  text NOT NULL REFERENCES tags (name) ON DELETE RESTRICT,
        PRIMARY KEY (item_id, tag_name)
    )
    """,
    "CREATE INDEX idx_item_tags_tag ON item_tags (tag_name)",
    # §2.13 — composición del vocabulario
    """
    CREATE TABLE vocab_versions (
        version         text PRIMARY KEY,
        tag_count       integer NOT NULL,
        created_at      timestamptz NOT NULL,
        activated_at    timestamptz,
        deactivated_at  timestamptz
    )
    """,
    """
    CREATE UNIQUE INDEX uq_vocab_single_active
        ON vocab_versions ((activated_at IS NOT NULL AND deactivated_at IS NULL))
        WHERE activated_at IS NOT NULL AND deactivated_at IS NULL
    """,
    """
    CREATE TABLE vocab_version_tags (
        version    text NOT NULL REFERENCES vocab_versions (version) ON DELETE CASCADE,
        tag_name   text NOT NULL,
        dimension  integer NOT NULL,
        PRIMARY KEY (version, tag_name),
        CONSTRAINT uq_vocab_version_dimension UNIQUE (version, dimension)
    )
    """,
    # §2.4 — vectores de ítem (pgvector sin dimensionalidad declarada, RD-21)
    """
    CREATE TABLE item_vectors (
        item_id        uuid NOT NULL REFERENCES items (id) ON DELETE CASCADE,
        vocab_version  text NOT NULL REFERENCES vocab_versions (version) ON DELETE RESTRICT,
        vector         vector NOT NULL,
        computed_at    timestamptz NOT NULL,
        PRIMARY KEY (item_id, vocab_version)
    )
    """,
    "CREATE INDEX idx_item_vectors_vocab ON item_vectors (vocab_version)",
    # §2.5 — perfiles
    """
    CREATE TABLE user_profiles (
        user_id        uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        scope          profile_scope NOT NULL,
        vocab_version  text NOT NULL REFERENCES vocab_versions (version) ON DELETE RESTRICT,
        vector         vector NOT NULL,
        signal_count   integer NOT NULL,
        computed_at    timestamptz NOT NULL,
        PRIMARY KEY (user_id, scope, vocab_version)
    )
    """,
    "CREATE INDEX idx_user_profiles_vocab ON user_profiles (vocab_version)",
    # §2.6 — señales (registro de hechos)
    """
    CREATE TABLE user_signals (
        id                     bigserial PRIMARY KEY,
        origin_interaction_id  text NOT NULL,
        user_id                uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        item_id                uuid NOT NULL REFERENCES items (id) ON DELETE RESTRICT,
        signal_type            signal_type NOT NULL,
        occurred_at            timestamptz NOT NULL,
        received_at            timestamptz NOT NULL DEFAULT now(),
        source                 signal_source NOT NULL,
        CONSTRAINT uq_signals_origin_interaction UNIQUE (origin_interaction_id)
    )
    """,
    "CREATE INDEX idx_signals_vigente ON user_signals (user_id, item_id, occurred_at DESC, id DESC)",
    "CREATE INDEX idx_signals_user_received ON user_signals (user_id, received_at)",
    # §2.7 — exclusiones (zona mixta, RD-29)
    """
    CREATE TABLE user_exclusions (
        user_id      uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        item_id      uuid NOT NULL REFERENCES items (id) ON DELETE RESTRICT,
        origin       exclusion_origin NOT NULL,
        resolved_at  timestamptz NOT NULL,
        PRIMARY KEY (user_id, item_id)
    )
    """,
    # §2.9 — bitácora de sincronización (sin FK)
    """
    CREATE TABLE sync_runs (
        id              bigserial PRIMARY KEY,
        started_at      timestamptz NOT NULL,
        finished_at     timestamptz,
        status          sync_status NOT NULL,
        entity_counts   jsonb,
        failure_reason  text
    )
    """,
    "CREATE INDEX idx_sync_runs_success ON sync_runs (finished_at DESC) WHERE status = 'success'",
    # §2.10 — idempotencia de eventos (sin FK)
    """
    CREATE TABLE processed_events (
        event_id      uuid PRIMARY KEY,
        processed_at  timestamptz NOT NULL,
        result        processed_result NOT NULL,
        expires_at    timestamptz NOT NULL
    )
    """,
    "CREATE INDEX idx_processed_expires ON processed_events (expires_at)",
    # §2.11 — popularidad por ventana
    """
    CREATE TABLE item_popularity (
        item_id             uuid NOT NULL REFERENCES items (id) ON DELETE CASCADE,
        config_version      text NOT NULL REFERENCES engine_config_versions (config_version) ON DELETE RESTRICT,
        like_count          integer NOT NULL DEFAULT 0,
        engaged_user_count  integer NOT NULL DEFAULT 0,
        popularity_score    double precision NOT NULL,
        computed_at         timestamptz NOT NULL,
        PRIMARY KEY (item_id, config_version),
        CONSTRAINT ck_popularity_counts CHECK (like_count >= 0 AND like_count <= engaged_user_count),
        CONSTRAINT ck_popularity_score CHECK (popularity_score BETWEEN 0 AND 1)
    )
    """,
    "CREATE INDEX idx_popularity_ranking ON item_popularity (config_version, popularity_score DESC)",
    # §2.12 — pertenencia de tag a módulo
    """
    CREATE TABLE tag_modules (
        tag_name     text NOT NULL REFERENCES tags (name) ON DELETE CASCADE,
        module       module_enum NOT NULL,
        computed_at  timestamptz NOT NULL,
        PRIMARY KEY (tag_name, module)
    )
    """,
    "CREATE INDEX idx_tag_modules_module ON tag_modules (module, tag_name)",
    # §2.14 — gustos declarados (dato de origen local)
    """
    CREATE TABLE user_declared_tags (
        user_id      uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        module       module_enum NOT NULL,
        tag_name     text NOT NULL REFERENCES tags (name) ON DELETE RESTRICT,
        declared_at  timestamptz NOT NULL,
        PRIMARY KEY (user_id, module, tag_name)
    )
    """,
    "CREATE INDEX idx_declared_user_module ON user_declared_tags (user_id, module)",
    "CREATE INDEX idx_declared_tag ON user_declared_tags (tag_name)",
    # §2.15 — constancia y lápida de la supresión (sin FK a users, deliberado)
    """
    CREATE TABLE user_suppressions (
        user_id       uuid PRIMARY KEY,
        requested_at  timestamptz NOT NULL,
        state         suppression_state NOT NULL,
        attempts      smallint NOT NULL DEFAULT 0,
        verified_at   timestamptz,
        CONSTRAINT ck_suppressions_verified CHECK ((state = 'completed') = (verified_at IS NOT NULL))
    )
    """,
    "CREATE INDEX idx_suppressions_open ON user_suppressions (requested_at) WHERE state <> 'completed'",
    # §2.16 — promoción definitiva
    """
    CREATE TABLE item_promotions (
        item_id         uuid PRIMARY KEY REFERENCES items (id) ON DELETE RESTRICT,
        promoted_at     timestamptz NOT NULL,
        config_version  text NOT NULL REFERENCES engine_config_versions (config_version) ON DELETE RESTRICT
    )
    """,
]

DROP_ORDER = [
    "item_promotions",
    "user_suppressions",
    "user_declared_tags",
    "tag_modules",
    "item_popularity",
    "processed_events",
    "sync_runs",
    "user_exclusions",
    "user_signals",
    "user_profiles",
    "item_vectors",
    "vocab_version_tags",
    "vocab_versions",
    "item_tags",
    "tags",
    "items",
    "users",
    "engine_config_versions",
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for name, values in ENUMS.items():
        labels = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({labels})")
    for ddl in TABLES_DDL:
        op.execute(ddl)


def downgrade() -> None:
    for table in DROP_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("DROP FUNCTION IF EXISTS engine_config_versions_immutable()")
    for name in reversed(list(ENUMS)):
        op.execute(f"DROP TYPE IF EXISTS {name}")
