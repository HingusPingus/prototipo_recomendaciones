"""Señalización de recálculo por el Stream interno `recompute:requests` (T018, T020, RD-100).

`recompute:lock:{user}:{module}` (`SET NX`, `TTL_SUPPRESS`) suprime duplicados: una ráfaga de
misses del mismo par produce una sola solicitud (SC-015). El Stream se acota con `MAXLEN`
aproximado: una solicitud perdida por el recorte la vuelve a emitir el siguiente miss.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient

REASONS = ("miss", "declaration", "warmup", "age_threshold", "snapshot")


class RecomputeSignaler(Protocol):
    def request(self, user_id: uuid.UUID, module: Module, reason: str) -> bool: ...


class RecomputeStream:
    def __init__(self, cache: CacheClient, *, maxlen: int, ttl_suppress: int) -> None:
        self._cache, self._maxlen, self._ttl = cache, maxlen, ttl_suppress

    def request(self, user_id: uuid.UUID, module: Module, reason: str) -> bool:
        """Emite a lo sumo una solicitud por (usuario, módulo) y ventana de supresión."""
        if reason not in REASONS:
            raise ValueError(f"motivo de recálculo desconocido: {reason}")
        module = Module(module)
        if not self._cache.set_nx(keys.lock_key(user_id, module), self._ttl):
            return False
        self._cache.xadd(
            keys.RECOMPUTE_STREAM,
            {"user_id": str(user_id), "module": module.value, "reason": reason},
            self._maxlen,
        )
        return True
