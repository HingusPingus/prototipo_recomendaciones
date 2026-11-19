"""S14 del plan de pruebas: cada migración de Alembic, una por una, con datos.

`test_migrations.py` recorre el ciclo completo (`head` → `base` → `head`). Acá se sube de a una migración desde
`0001` con datos sembrados, y en cada paso se baja una y se vuelve a subir: bajar tiene que dejar exactamente el
esquema anterior sin perder filas ajenas al cambio, y volver a subir tiene que dar el mismo esquema.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory

from tests.conftest import alembic_config
from tests.integration.test_migrations import _seed_config, _seed_item, _seed_user

TABLAS_SEMBRADAS = ("engine_config_versions", "users", "items", "tags", "item_tags", "user_signals")

_ESQUEMA = """
SELECT 'columna ' || table_name || '.' || column_name || ' ' || data_type || ' ' || udt_name || ' '
       || is_nullable || ' ' || coalesce(column_default, '')
  FROM information_schema.columns WHERE table_schema = 'public' AND table_name <> 'alembic_version'
UNION ALL
SELECT 'restriccion ' || c.conrelid::regclass || ' ' || c.conname || ' ' || pg_get_constraintdef(c.oid)
  FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
 WHERE n.nspname = 'public' AND c.conrelid::regclass::text <> 'alembic_version'
UNION ALL
SELECT 'indice ' || indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename <> 'alembic_version'
UNION ALL
SELECT 'enum ' || t.typname || ' ' || string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder)
  FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid GROUP BY t.typname
UNION ALL
SELECT 'disparador ' || tgrelid::regclass || ' ' || tgname FROM pg_trigger WHERE NOT tgisinternal
UNION ALL
SELECT 'funcion ' || p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'public' AND p.prokind = 'f'
   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
"""


@pytest.fixture(scope="module")
def url_paso_a_paso(pg_url: str) -> str:
    """Base propia del módulo: no comparte estado con `test_migrations.py`."""
    admin = sa.create_engine(pg_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text("DROP DATABASE IF EXISTS migpasos"))
        conn.execute(sa.text("CREATE DATABASE migpasos"))
    admin.dispose()
    return pg_url.rsplit("/", 1)[0] + "/migpasos"


@pytest.fixture
def motor(url_paso_a_paso: str) -> Iterator[sa.Engine]:
    eng = sa.create_engine(url_paso_a_paso)
    yield eng
    command.downgrade(alembic_config(url_paso_a_paso), "base")
    eng.dispose()


def _esquema(eng: sa.Engine) -> set[str]:
    with eng.connect() as conn:
        return set(conn.execute(sa.text(_ESQUEMA)).scalars())


def _filas(eng: sa.Engine) -> dict[str, int]:
    with eng.connect() as conn:
        return {t: conn.execute(sa.text(f"SELECT count(*) FROM {t}")).scalar_one() for t in TABLAS_SEMBRADAS}


def _revisiones(url: str) -> list[str]:
    script = ScriptDirectory.from_config(alembic_config(url))
    return [r.revision for r in reversed(list(script.walk_revisions("base", "heads")))]


def test_cada_migracion_baja_y_vuelve_a_subir_sin_perder_datos(motor: sa.Engine, url_paso_a_paso: str) -> None:
    cfg = alembic_config(url_paso_a_paso)
    revisiones = _revisiones(url_paso_a_paso)
    assert revisiones[0] == "0001_initial"

    command.upgrade(cfg, revisiones[0])
    with motor.begin() as conn:
        version = _seed_config(conn)
        user = _seed_user(conn, version)
        item = _seed_item(conn, version)
        conn.execute(sa.text("INSERT INTO tags (name, synced_at) VALUES ('horror', now())"))
        conn.execute(sa.text("INSERT INTO item_tags VALUES (:i, 'horror')"), {"i": item})
        conn.execute(
            sa.text(
                "INSERT INTO user_signals (origin_interaction_id, user_id, item_id, signal_type, "
                "occurred_at, source) VALUES ('int-1', :u, :i, 'like', now(), 'sync')"
            ),
            {"u": user, "i": item},
        )
    filas = _filas(motor)
    anterior = _esquema(motor)

    for revision in revisiones[1:]:
        command.upgrade(cfg, revision)
        migrado = _esquema(motor)
        assert migrado != anterior, f"{revision} no cambia el esquema"

        command.downgrade(cfg, "-1")
        assert _esquema(motor) == anterior, f"bajar {revision} no deja el esquema anterior"
        assert _filas(motor) == filas, f"bajar {revision} pierde filas"

        command.upgrade(cfg, revision)
        assert _esquema(motor) == migrado, f"{revision} no da el mismo esquema al volver a subir"
        assert _filas(motor) == filas, f"{revision} pierde filas"
        anterior = migrado


def test_0005_rellena_first_synced_at_de_los_items_existentes(motor: sa.Engine, url_paso_a_paso: str) -> None:
    cfg = alembic_config(url_paso_a_paso)
    command.upgrade(cfg, "0004_process_runs")
    with motor.begin() as conn:
        _seed_item(conn, _seed_config(conn))

    command.upgrade(cfg, "0005_items_first_synced_at")

    with motor.connect() as conn:
        sin_relleno = conn.execute(sa.text("SELECT count(*) FROM items WHERE first_synced_at IS DISTINCT FROM synced_at")).scalar_one()
    assert sin_relleno == 0
