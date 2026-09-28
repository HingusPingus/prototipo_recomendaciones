"""Cliente Redis con timeout explícito que distingue *miss* de *caída* (T018, T021, FR-065).

Un miss devuelve `None`; Redis inalcanzable o lento levanta `CacheUnavailable` (→ `503` con
`Retry-After`). Nunca hay ruta de fallback a Postgres para calcular (FR-065, INV-1).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from recomendaciones.shared.errors import CacheUnavailable

T = TypeVar("T")

# Redis no representa un set vacío: sin centinela, «no hay retirados» sería un miss permanente y el
# camino normal de lectura volvería a Postgres en cada solicitud.
EMPTY_SET_SENTINEL = "__vacio__"


class CacheClient:
    def __init__(self, raw: redis.Redis) -> None:
        self.raw = raw

    @classmethod
    def from_url(cls, url: str, timeout_seconds: float) -> CacheClient:
        return cls(
            redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_timeout=timeout_seconds,
                socket_connect_timeout=timeout_seconds,
                retry_on_timeout=False,
            )
        )

    def call(self, fn: Callable[[], T]) -> T:
        try:
            return fn()
        except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
            raise CacheUnavailable() from exc

    def ping(self) -> bool:
        return bool(self.call(self.raw.ping))

    def get_json(self, key: str) -> Any | None:
        value = self.call(lambda: self.raw.get(key))
        if value is None:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None  # valor ilegible ⟹ miss, nunca interpretación a medias

    def get_many_json(self, keys: Iterable[str]) -> list[Any | None]:
        keys = list(keys)
        if not keys:
            return []
        values = self.call(lambda: self.raw.mget(keys))
        out: list[Any | None] = []
        for value in values:
            try:
                out.append(None if value is None else json.loads(value))
            except (TypeError, ValueError):
                out.append(None)
        return out

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        payload = json.dumps(value, separators=(",", ":"))
        self.call(lambda: self.raw.set(key, payload, ex=ttl_seconds))

    def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        return int(self.call(lambda: self.raw.delete(*keys)))

    def exists(self, key: str) -> bool:
        return bool(self.call(lambda: self.raw.exists(key)))

    def set_members(self, key: str, members: Iterable[str], ttl_seconds: int) -> None:
        values = sorted(set(members)) or [EMPTY_SET_SENTINEL]

        def write() -> None:
            pipe = self.raw.pipeline(transaction=True)
            pipe.delete(key)
            pipe.sadd(key, *values)
            pipe.expire(key, ttl_seconds)
            pipe.execute()

        self.call(write)

    def get_members(self, key: str) -> frozenset[str] | None:
        """Miembros del set; `None` si la clave no existe (miss)."""

        def read() -> tuple[bool, set[str]]:
            pipe = self.raw.pipeline(transaction=False)
            pipe.exists(key)
            pipe.smembers(key)
            exists, members = pipe.execute()
            return bool(exists), set(members)

        exists, members = self.call(read)
        if not exists:
            return None
        return frozenset(members - {EMPTY_SET_SENTINEL})

    def set_nx(self, key: str, ttl_seconds: int) -> bool:
        return bool(self.call(lambda: self.raw.set(key, "1", nx=True, ex=ttl_seconds)))

    def xadd(self, stream: str, fields: dict[str, str], maxlen: int) -> str:
        return str(self.call(lambda: self.raw.xadd(stream, fields, maxlen=maxlen, approximate=True)))
