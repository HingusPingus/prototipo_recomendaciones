"""S10 del plan de pruebas: eventos del mismo usuario y título que llegan al revés de como ocurrieron.

El broker no garantiza orden entre reintentos ni entre réplicas del publicador. El estado final tiene que reflejar el
evento que OCURRIÓ último (`occurred_at`), no el que llegó último.
"""

from __future__ import annotations

import sqlalchemy as sa

from tests.integration.test_event_signals import Stack, _event, _signals, world  # noqa: F401 — fixture compartida


def _exclusiones(db_factory, user) -> list[tuple]:  # noqa: ANN001
    with db_factory() as s:
        return s.execute(
            sa.text("SELECT item_id, origin::text FROM user_exclusions WHERE user_id = :u"), {"u": user}
        ).all()


def test_un_dislike_nuevo_que_llega_antes_que_un_like_viejo_sigue_excluyendo(db_factory, redis_client, world) -> None:  # noqa: ANN001, F811
    user, item = world
    stack = Stack(db_factory, redis_client)
    viejo = _event(user, item, "like", minutes=0)
    nuevo = _event(user, item, "dislike", minutes=5)

    stack.handler(nuevo)
    stack.handler(viejo)

    assert len(_signals(db_factory, user)) == 2
    assert _exclusiones(db_factory, user) == [(item, "dislike")]


def test_un_like_nuevo_que_llega_antes_que_un_dislike_viejo_deja_la_exclusion_del_like(db_factory, redis_client, world) -> None:  # noqa: ANN001, F811
    user, item = world
    stack = Stack(db_factory, redis_client)
    viejo = _event(user, item, "dislike", minutes=0)
    nuevo = _event(user, item, "like", minutes=5)

    stack.handler(nuevo)
    stack.handler(viejo)

    assert len(_signals(db_factory, user)) == 2
    # Un like también excluye (el título ya se vio); lo que importa es que el origen sea el del evento más nuevo.
    assert _exclusiones(db_factory, user) == [(item, "like")]


def test_el_orden_de_llegada_no_cambia_el_resultado(db_factory, redis_client) -> None:  # noqa: ANN001
    """Las mismas cinco señales, en orden y al revés, dejan las mismas exclusiones."""
    from tests.integration import seed

    resultados = []
    for invertir in (False, True):
        with db_factory.begin() as s:
            user = seed.user(s)
            item = seed.item(s, "peliculas", ["horror"])
        stack = Stack(db_factory, redis_client)
        eventos = [_event(user, item, kind, minutes=i) for i, kind in enumerate(["like", "dislike", "like", "dislike", "like"])]
        for evento in reversed(eventos) if invertir else eventos:
            stack.handler(evento)
        resultados.append([origen for _, origen in _exclusiones(db_factory, user)])
    assert resultados[0] == resultados[1] == ["like"]
