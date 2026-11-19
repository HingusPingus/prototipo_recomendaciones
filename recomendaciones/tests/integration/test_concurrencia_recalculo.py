"""S13 del plan de pruebas: un recálculo pedido muchas veces a la vez para el mismo usuario se emite una sola vez.

`recompute:lock` (`SET NX`) tiene que suprimir los duplicados también cuando los pedidos llegan en paralelo desde
varios hilos (una ráfaga de misses del frontend, el warmup y una señal al mismo tiempo), no solo en secuencia.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient
from recomendaciones.storage.cache.recompute import RecomputeStream

PEDIDOS = 100


def test_cien_pedidos_simultaneos_del_mismo_usuario_emiten_un_solo_recalculo(redis_client) -> None:  # noqa: ANN001
    stream = RecomputeStream(CacheClient(redis_client), maxlen=10_000, ttl_suppress=300)
    usuario = uuid.uuid4()
    largada = threading.Barrier(PEDIDOS)
    motivos = ("miss", "warmup", "signal", "declaration")

    def pedir(i: int) -> bool:
        largada.wait()
        return stream.request(usuario, Module.JUEGOS, motivos[i % len(motivos)])

    with ThreadPoolExecutor(max_workers=PEDIDOS) as hilos:
        emitidos = list(hilos.map(pedir, range(PEDIDOS)))

    assert emitidos.count(True) == 1
    entradas = redis_client.xrange(keys.RECOMPUTE_STREAM)
    assert [(e[1]["user_id"], e[1]["module"]) for e in entradas] == [(str(usuario), "juegos")]


def test_pedidos_simultaneos_de_otros_modulos_y_usuarios_no_se_suprimen_entre_si(redis_client) -> None:  # noqa: ANN001
    stream = RecomputeStream(CacheClient(redis_client), maxlen=10_000, ttl_suppress=300)
    usuarios = [uuid.uuid4() for _ in range(10)]
    pares = [(u, m) for u in usuarios for m in (Module.JUEGOS, Module.PELICULAS)]
    largada = threading.Barrier(len(pares) * 5)

    def pedir(par: tuple[uuid.UUID, Module]) -> bool:
        largada.wait()
        return stream.request(par[0], par[1], "miss")

    with ThreadPoolExecutor(max_workers=len(pares) * 5) as hilos:
        emitidos = list(hilos.map(pedir, pares * 5))

    assert emitidos.count(True) == len(pares)
    assert redis_client.xlen(keys.RECOMPUTE_STREAM) == len(pares)
