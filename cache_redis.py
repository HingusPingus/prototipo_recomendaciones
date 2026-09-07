"""
cache_redis.py — Capa de caché Redis para RecoMe.

Esquema de keys (paso 3):
  reco:{user_id}:{module}   →  STRING  con JSON del top-N (lista de ScoredItem)
  excl:{user_id}:{module}   →  SET     con los item_ids excluidos

`module` es "movie" o "game".

Por defecto usa fakeredis (sin infraestructura externa).
Para apuntar a un Redis real, instanciá RedisCache(use_fake=False).
"""

from __future__ import annotations
import json
from typing import Literal
from uuid import UUID

try:
    import fakeredis
    _FAKEREDIS_AVAILABLE = True
except ImportError:
    _FAKEREDIS_AVAILABLE = False

import redis as redis_lib

from recommenders import ScoredItem
from domain import Movie, Game, Item

Module = Literal["movie", "game"]

# TTL por defecto: 7 días (vida útil del batch semanal)
DEFAULT_TTL = 60 * 60 * 24 * 7


# ── Serialización / deserialización ────────────────────────────────────────

def _item_to_dict(item: Item) -> dict:
    return {
        "id":             str(item.id),
        "type":           "movie" if isinstance(item, Movie) else "game",
        "title":          item.title,
        "age_rating":     item.age_rating,
        "external_score": item.external_score,
        "tags":           item.tags,
    }

def _scored_item_to_dict(si: ScoredItem) -> dict:
    return {"item": _item_to_dict(si.item), "score": si.score}

def _dict_to_item(d: dict) -> Item:
    cls = Movie if d["type"] == "movie" else Game
    return cls(
        id=UUID(d["id"]),
        title=d["title"],
        age_rating=d["age_rating"],
        external_score=d["external_score"],
        tags=d["tags"],
    )

def _dict_to_scored_item(d: dict) -> ScoredItem:
    return ScoredItem(item=_dict_to_item(d["item"]), score=d["score"])


# ── Cliente Redis ───────────────────────────────────────────────────────────

class RedisCache:
    """
    Wrapper sobre redis-py.  Un único cliente reusado (paso 2).
    use_fake=True  → fakeredis en memoria (demo sin infraestructura).
    use_fake=False → Redis real en localhost:6379 (o la URL que pases).
    """

    def __init__(
        self,
        use_fake: bool = True,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        ttl: int = DEFAULT_TTL,
    ):
        self.ttl = ttl

        if use_fake:
            if not _FAKEREDIS_AVAILABLE:
                raise RuntimeError("Instalá fakeredis: pip install fakeredis")
            self._client = fakeredis.FakeRedis(decode_responses=True)
            self._mode = "fakeredis (in-memory)"
        else:
            self._client = redis_lib.Redis(
                host=host, port=port, db=db, decode_responses=True
            )
            self._mode = f"redis://{host}:{port}/{db}"

    @property
    def mode(self) -> str:
        return self._mode

    # ── Keys ────────────────────────────────────────────────────────────────

    @staticmethod
    def reco_key(user_id, module: Module) -> str:
        return f"reco:{user_id}:{module}"

    @staticmethod
    def excl_key(user_id, module: Module) -> str:
        return f"excl:{user_id}:{module}"

    # ── Top-N ────────────────────────────────────────────────────────────────

    def save_top_n(
        self, user_id, module: Module, items: list[ScoredItem]
    ) -> None:
        """Serializa el top-N a JSON y lo guarda con TTL."""
        key  = self.reco_key(user_id, module)
        data = json.dumps([_scored_item_to_dict(si) for si in items])
        self._client.set(key, data, ex=self.ttl)

    def get_top_n(self, user_id, module: Module) -> list[ScoredItem]:
        """Lee y deserializa el top-N. Devuelve [] si no existe la key."""
        key = self.reco_key(user_id, module)
        raw = self._client.get(key)
        if not raw:
            return []
        return [_dict_to_scored_item(d) for d in json.loads(raw)]

    # ── ExclusionSet ─────────────────────────────────────────────────────────

    def add_exclusion(self, user_id, module: Module, item_id) -> None:
        key = self.excl_key(user_id, module)
        self._client.sadd(key, str(item_id))
        self._client.expire(key, self.ttl)

    def is_excluded(self, user_id, module: Module, item_id) -> bool:
        key = self.excl_key(user_id, module)
        return self._client.sismember(key, str(item_id))

    def get_exclusions(self, user_id, module: Module) -> set[str]:
        key = self.excl_key(user_id, module)
        return self._client.smembers(key)

    def populate_exclusions_from_feedbacks(self, user_id, feedbacks: list) -> None:
        """Carga los exclusion sets a partir de una lista de Feedback."""
        for fb in feedbacks:
            module: Module = "movie" if fb.item_type == "movie" else "game"
            self.add_exclusion(user_id, module, fb.item_id)

    # ── Utilidades ───────────────────────────────────────────────────────────

    def flush(self) -> None:
        """Borra todas las keys (útil en tests y demos)."""
        self._client.flushall()

    def ttl_remaining(self, user_id, module: Module) -> int:
        """Segundos restantes del TTL de la key de recomendaciones."""
        return self._client.ttl(self.reco_key(user_id, module))
