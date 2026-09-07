"""
tests_cache_redis.py — Suite de tests para cache_redis.py

Cubre casos normales, de borde y nichos usando exclusivamente fakeredis.

Ejecutar:
    python3 -m pytest tests_cache_redis.py -v
"""

from __future__ import annotations
import json
import time
import pytest
from uuid import UUID, uuid4
from datetime import date, datetime, timezone

from domain import Movie, Game, User, Feedback
from recommenders import ScoredItem
from cache_redis import (
    RedisCache, DEFAULT_TTL,
    _item_to_dict, _dict_to_item,
    _scored_item_to_dict, _dict_to_scored_item,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def cache():
    """RedisCache fresco con fakeredis para cada test."""
    c = RedisCache(use_fake=True)
    yield c
    c.flush()

@pytest.fixture
def uid():
    return UUID("aaaa0000-0000-0000-0000-000000000001")

@pytest.fixture
def uid2():
    return UUID("aaaa0000-0000-0000-0000-000000000002")

@pytest.fixture
def sample_movie():
    return Movie(
        id=UUID("b3f1c2b0-0001-4a5b-9abc-100000000001"),
        title="El Conjuro",
        age_rating="PG-13",
        external_score=7.8,
        tags=["horror", "sobrenatural"],
    )

@pytest.fixture
def sample_game():
    return Game(
        id=UUID("9a7e5d40-0002-4f21-8b3a-200000000001"),
        title="Elden Ring",
        age_rating="M",
        external_score=9.5,
        tags=["rpg", "accion", "mundo_abierto"],
    )

@pytest.fixture
def scored_movie(sample_movie):
    return ScoredItem(item=sample_movie, score=0.95)

@pytest.fixture
def scored_game(sample_game):
    return ScoredItem(item=sample_game, score=0.87)

def make_top_n(n: int, module: str = "movie") -> list[ScoredItem]:
    """Genera una lista de n ScoredItems ficticios."""
    cls = Movie if module == "movie" else Game
    return [
        ScoredItem(
            item=cls(
                id=uuid4(),
                title=f"Item {i}",
                age_rating="PG-13",
                external_score=float(i),
                tags=[f"tag_{i}"],
            ),
            score=float(n - i) / n,
        )
        for i in range(n)
    ]


# ============================================================
# Serialización / deserialización
# ============================================================

class TestSerialization:
    def test_movie_roundtrip(self, sample_movie):
        d = _item_to_dict(sample_movie)
        restored = _dict_to_item(d)
        assert isinstance(restored, Movie)
        assert restored.id    == sample_movie.id
        assert restored.title == sample_movie.title
        assert restored.tags  == sample_movie.tags

    def test_game_roundtrip(self, sample_game):
        d = _item_to_dict(sample_game)
        restored = _dict_to_item(d)
        assert isinstance(restored, Game)
        assert restored.id    == sample_game.id
        assert restored.title == sample_game.title

    def test_scored_item_roundtrip(self, scored_movie):
        d = _scored_item_to_dict(scored_movie)
        restored = _dict_to_scored_item(d)
        assert abs(restored.score - scored_movie.score) < 1e-9
        assert restored.item.title == scored_movie.item.title

    def test_type_field_movie(self, sample_movie):
        assert _item_to_dict(sample_movie)["type"] == "movie"

    def test_type_field_game(self, sample_game):
        assert _item_to_dict(sample_game)["type"] == "game"

    def test_uuid_serialized_as_string(self, sample_movie):
        d = _item_to_dict(sample_movie)
        assert isinstance(d["id"], str)

    def test_tags_list_preserved(self, sample_movie):
        d = _item_to_dict(sample_movie)
        assert d["tags"] == sample_movie.tags

    def test_empty_tags_list(self):
        m = Movie(uuid4(), "Sin tags", "G", 5.0, [])
        d = _item_to_dict(m)
        assert d["tags"] == []
        restored = _dict_to_item(d)
        assert restored.tags == []

    def test_score_precision(self, sample_movie):
        """Scores con muchos decimales no se deben truncar al serializar."""
        si = ScoredItem(item=sample_movie, score=0.123456789012345)
        restored = _dict_to_scored_item(_scored_item_to_dict(si))
        assert abs(restored.score - si.score) < 1e-10

    def test_score_zero(self, sample_movie):
        si = ScoredItem(item=sample_movie, score=0.0)
        restored = _dict_to_scored_item(_scored_item_to_dict(si))
        assert restored.score == 0.0

    def test_score_negative(self, sample_movie):
        """El score puede ser negativo si el colaborativo o cross-boost lo bajan."""
        si = ScoredItem(item=sample_movie, score=-0.5)
        restored = _dict_to_scored_item(_scored_item_to_dict(si))
        assert abs(restored.score - (-0.5)) < 1e-9

    def test_title_with_special_chars(self):
        """Títulos con caracteres especiales, dos puntos y comillas."""
        m = Movie(uuid4(), 'Knives Out: "Glass Onion"', "PG-13", 7.1, ["misterio"])
        d = _item_to_dict(m)
        restored = _dict_to_item(d)
        assert restored.title == m.title

    def test_title_with_unicode(self):
        m = Movie(uuid4(), "Amélie — L'histoire de 愛", "R", 8.3, ["romance"])
        d = _item_to_dict(m)
        restored = _dict_to_item(d)
        assert restored.title == m.title


# ============================================================
# RedisCache — Construcción
# ============================================================

class TestRedisCacheInit:
    def test_mode_fakeredis(self, cache):
        assert "fakeredis" in cache.mode

    def test_custom_ttl(self):
        c = RedisCache(use_fake=True, ttl=300)
        assert c.ttl == 300


# ============================================================
# RedisCache — Keys
# ============================================================

class TestKeys:
    def test_reco_key_format(self, uid):
        key = RedisCache.reco_key(uid, "movie")
        assert key == f"reco:{uid}:movie"

    def test_excl_key_format(self, uid):
        key = RedisCache.excl_key(uid, "game")
        assert key == f"excl:{uid}:game"

    def test_movie_and_game_keys_are_different(self, uid):
        assert RedisCache.reco_key(uid, "movie") != RedisCache.reco_key(uid, "game")

    def test_keys_different_users(self, uid, uid2):
        assert RedisCache.reco_key(uid, "movie") != RedisCache.reco_key(uid2, "movie")


# ============================================================
# RedisCache — save_top_n / get_top_n  (casos normales)
# ============================================================

class TestTopN:
    def test_save_and_get_movie(self, cache, uid, scored_movie):
        cache.save_top_n(uid, "movie", [scored_movie])
        result = cache.get_top_n(uid, "movie")
        assert len(result) == 1
        assert result[0].item.title == scored_movie.item.title
        assert abs(result[0].score - scored_movie.score) < 1e-9

    def test_save_and_get_game(self, cache, uid, scored_game):
        cache.save_top_n(uid, "game", [scored_game])
        result = cache.get_top_n(uid, "game")
        assert len(result) == 1
        assert isinstance(result[0].item, Game)

    def test_get_unknown_user_returns_empty(self, cache):
        result = cache.get_top_n(uuid4(), "movie")
        assert result == []

    def test_get_wrong_module_returns_empty(self, cache, uid, scored_movie):
        cache.save_top_n(uid, "movie", [scored_movie])
        assert cache.get_top_n(uid, "game") == []

    def test_order_is_preserved(self, cache, uid):
        items = make_top_n(5, "movie")
        cache.save_top_n(uid, "movie", items)
        result = cache.get_top_n(uid, "movie")
        for orig, restored in zip(items, result):
            assert orig.item.title == restored.item.title

    def test_overwrite_replaces_previous(self, cache, uid, scored_movie):
        cache.save_top_n(uid, "movie", [scored_movie])
        new_items = make_top_n(3, "movie")
        cache.save_top_n(uid, "movie", new_items)
        result = cache.get_top_n(uid, "movie")
        assert len(result) == 3
        assert result[0].item.title == new_items[0].item.title

    def test_save_empty_list(self, cache, uid):
        """Guardar lista vacía → get devuelve []."""
        cache.save_top_n(uid, "movie", [])
        result = cache.get_top_n(uid, "movie")
        assert result == []

    def test_large_top_n(self, cache, uid):
        items = make_top_n(100, "movie")
        cache.save_top_n(uid, "movie", items)
        result = cache.get_top_n(uid, "movie")
        assert len(result) == 100

    def test_movie_and_game_independent(self, cache, uid, scored_movie, scored_game):
        """Los módulos no se pisan entre sí para el mismo usuario."""
        cache.save_top_n(uid, "movie", [scored_movie])
        cache.save_top_n(uid, "game",  [scored_game])
        movies = cache.get_top_n(uid, "movie")
        games  = cache.get_top_n(uid, "game")
        assert isinstance(movies[0].item, Movie)
        assert isinstance(games[0].item, Game)

    def test_two_users_independent(self, cache, uid, uid2, scored_movie):
        """Dos usuarios con el mismo módulo no comparten datos."""
        item2 = ScoredItem(
            item=Movie(uuid4(), "Otra Peli", "G", 6.0, ["comedia"]),
            score=0.5,
        )
        cache.save_top_n(uid,  "movie", [scored_movie])
        cache.save_top_n(uid2, "movie", [item2])
        assert cache.get_top_n(uid,  "movie")[0].item.title == scored_movie.item.title
        assert cache.get_top_n(uid2, "movie")[0].item.title == "Otra Peli"

    def test_all_item_fields_preserved(self, cache, uid, scored_movie):
        """Ningún campo del ítem se pierde en el viaje JSON."""
        cache.save_top_n(uid, "movie", [scored_movie])
        restored = cache.get_top_n(uid, "movie")[0].item
        orig = scored_movie.item
        assert restored.id             == orig.id
        assert restored.title          == orig.title
        assert restored.age_rating     == orig.age_rating
        assert restored.external_score == orig.external_score
        assert restored.tags           == orig.tags


# ============================================================
# RedisCache — TTL
# ============================================================

class TestTTL:
    def test_default_ttl_applied(self, cache, uid, scored_movie):
        cache.save_top_n(uid, "movie", [scored_movie])
        ttl = cache.ttl_remaining(uid, "movie")
        # fakeredis reporta TTL exacto → debe estar cerca de DEFAULT_TTL
        assert 0 < ttl <= DEFAULT_TTL

    def test_custom_ttl_applied(self, uid, scored_movie):
        c = RedisCache(use_fake=True, ttl=120)
        c.save_top_n(uid, "movie", [scored_movie])
        ttl = c.ttl_remaining(uid, "movie")
        assert 0 < ttl <= 120

    def test_ttl_missing_key_returns_negative(self, cache, uid):
        """Redis devuelve -2 si la key no existe."""
        ttl = cache.ttl_remaining(uid, "movie")
        assert ttl < 0

    def test_overwrite_resets_ttl(self, uid, scored_movie):
        """Al sobrescribir con save_top_n el TTL se renueva."""
        c = RedisCache(use_fake=True, ttl=60)
        c.save_top_n(uid, "movie", [scored_movie])
        ttl_before = c.ttl_remaining(uid, "movie")
        # Sobrescribir con TTL más alto
        c2 = RedisCache(use_fake=True, ttl=3600)
        # Usamos el mismo cliente interno (no aplica TTL de c2 directamente,
        # pero sí si save_top_n usa self.ttl) — verificamos con c2 independiente
        c2._client = c._client   # mismo backend fake
        c2.save_top_n(uid, "movie", [scored_movie])
        ttl_after = c2.ttl_remaining(uid, "movie")
        assert ttl_after > ttl_before


# ============================================================
# RedisCache — ExclusionSet
# ============================================================

class TestExclusionSet:
    def test_add_and_is_excluded(self, cache, uid):
        item_id = uuid4()
        cache.add_exclusion(uid, "movie", item_id)
        assert cache.is_excluded(uid, "movie", item_id)

    def test_not_excluded_by_default(self, cache, uid):
        assert not cache.is_excluded(uid, "movie", uuid4())

    def test_exclusion_modules_independent(self, cache, uid):
        """Excluir en 'movie' no afecta a 'game'."""
        item_id = uuid4()
        cache.add_exclusion(uid, "movie", item_id)
        assert not cache.is_excluded(uid, "game", item_id)

    def test_exclusion_users_independent(self, cache, uid, uid2):
        item_id = uuid4()
        cache.add_exclusion(uid, "movie", item_id)
        assert not cache.is_excluded(uid2, "movie", item_id)

    def test_get_exclusions_returns_set(self, cache, uid):
        ids = [uuid4() for _ in range(5)]
        for iid in ids:
            cache.add_exclusion(uid, "game", iid)
        result = cache.get_exclusions(uid, "game")
        assert len(result) == 5
        for iid in ids:
            assert str(iid) in result

    def test_add_same_item_twice_no_duplicate(self, cache, uid):
        """Redis SET no admite duplicados."""
        item_id = uuid4()
        cache.add_exclusion(uid, "movie", item_id)
        cache.add_exclusion(uid, "movie", item_id)
        assert len(cache.get_exclusions(uid, "movie")) == 1

    def test_populate_from_feedbacks(self, cache, uid):
        movie_id = UUID("b3f1c2b0-0001-4a5b-9abc-100000000001")
        game_id  = UUID("9a7e5d40-0002-4f21-8b3a-200000000001")
        fbs = [
            Feedback(uid, movie_id, "movie", "like"),
            Feedback(uid, game_id,  "game",  "dislike"),
        ]
        cache.populate_exclusions_from_feedbacks(uid, fbs)
        assert cache.is_excluded(uid, "movie", movie_id)
        assert cache.is_excluded(uid, "game",  game_id)

    def test_populate_excludes_all_states(self, cache, uid):
        """Todos los estados (like, dislike, visto, jugado) deben excluir."""
        ids = {state: uuid4() for state in ["like", "dislike", "visto", "jugado"]}
        fbs = [
            Feedback(uid, item_id, "movie", state)
            for state, item_id in ids.items()
        ]
        cache.populate_exclusions_from_feedbacks(uid, fbs)
        for state, item_id in ids.items():
            assert cache.is_excluded(uid, "movie", item_id), f"Estado '{state}' no excluyó"

    def test_exclusion_ttl_is_set(self, cache, uid):
        item_id = uuid4()
        cache.add_exclusion(uid, "movie", item_id)
        key = RedisCache.excl_key(uid, "movie")
        ttl = cache._client.ttl(key)
        assert ttl > 0

    def test_large_exclusion_set(self, cache, uid):
        ids = [uuid4() for _ in range(500)]
        for iid in ids:
            cache.add_exclusion(uid, "movie", iid)
        result = cache.get_exclusions(uid, "movie")
        assert len(result) == 500


# ============================================================
# RedisCache — flush
# ============================================================

class TestFlush:
    def test_flush_removes_all_keys(self, cache, uid, uid2, scored_movie, scored_game):
        cache.save_top_n(uid,  "movie", [scored_movie])
        cache.save_top_n(uid2, "game",  [scored_game])
        cache.add_exclusion(uid, "movie", uuid4())
        cache.flush()
        assert cache.get_top_n(uid,  "movie") == []
        assert cache.get_top_n(uid2, "game")  == []
        assert len(cache.get_exclusions(uid, "movie")) == 0

    def test_flush_on_empty_cache_is_safe(self, cache):
        cache.flush()   # no debe lanzar excepciones


# ============================================================
# Casos nicho / borde
# ============================================================

class TestEdgeCases:
    def test_uuid_as_string_user_id(self, cache, scored_movie):
        """user_id puede pasarse como string UUID."""
        uid_str = "cccc0000-0000-0000-0000-000000000001"
        cache.save_top_n(uid_str, "movie", [scored_movie])
        result = cache.get_top_n(uid_str, "movie")
        assert len(result) == 1

    def test_item_with_many_tags(self, cache, uid):
        """Ítem con 50 tags no debe romperse en serialización."""
        tags = [f"tag_{i}" for i in range(50)]
        m = Movie(uuid4(), "Tag Heavy Movie", "G", 7.0, tags)
        si = ScoredItem(item=m, score=0.5)
        cache.save_top_n(uid, "movie", [si])
        result = cache.get_top_n(uid, "movie")
        assert result[0].item.tags == tags

    def test_item_with_no_tags(self, cache, uid):
        m = Movie(uuid4(), "Sin Tags", "G", 5.0, [])
        si = ScoredItem(item=m, score=0.1)
        cache.save_top_n(uid, "movie", [si])
        assert cache.get_top_n(uid, "movie")[0].item.tags == []

    def test_score_is_exactly_one(self, cache, uid):
        m = Movie(uuid4(), "Perfect Score", "G", 10.0, ["drama"])
        si = ScoredItem(item=m, score=1.0)
        cache.save_top_n(uid, "movie", [si])
        assert cache.get_top_n(uid, "movie")[0].score == 1.0

    def test_score_very_small_float(self, cache, uid):
        m = Movie(uuid4(), "Casi cero", "G", 5.0, ["drama"])
        si = ScoredItem(item=m, score=1e-15)
        cache.save_top_n(uid, "movie", [si])
        result = cache.get_top_n(uid, "movie")[0].score
        assert abs(result - 1e-15) < 1e-20

    def test_mixed_movie_game_in_top_n_list_unsupported(self, cache, uid, sample_movie, sample_game):
        """Mezclar Movie y Game en el mismo módulo es inusual pero la serialización
        debe preservar los tipos correctamente si ocurre."""
        si_m = ScoredItem(item=sample_movie, score=0.9)
        si_g = ScoredItem(item=sample_game,  score=0.5)
        cache.save_top_n(uid, "movie", [si_m, si_g])
        result = cache.get_top_n(uid, "movie")
        assert isinstance(result[0].item, Movie)
        assert isinstance(result[1].item, Game)

    def test_concurrent_writes_same_user_last_wins(self, cache, uid):
        """Simula dos escrituras seguidas al mismo key — la última gana."""
        items_a = make_top_n(3, "movie")
        items_b = make_top_n(5, "movie")
        cache.save_top_n(uid, "movie", items_a)
        cache.save_top_n(uid, "movie", items_b)
        result = cache.get_top_n(uid, "movie")
        assert len(result) == 5

    def test_key_does_not_bleed_across_modules_after_flush(self, cache, uid, scored_movie, scored_game):
        cache.save_top_n(uid, "movie", [scored_movie])
        cache.save_top_n(uid, "game",  [scored_game])
        cache.flush()
        cache.save_top_n(uid, "game", [scored_game])
        # Movie debe seguir vacío
        assert cache.get_top_n(uid, "movie") == []
        assert len(cache.get_top_n(uid, "game")) == 1

    def test_exclusion_item_id_as_uuid_object(self, cache, uid):
        """item_id puede ser UUID o string — Redis lo guarda como string."""
        iid = uuid4()
        cache.add_exclusion(uid, "movie", iid)
        assert cache.is_excluded(uid, "movie", iid)
        # También debe encontrarlo como string
        assert cache.is_excluded(uid, "movie", str(iid))

    def test_top_n_json_is_valid_and_list(self, cache, uid, scored_movie):
        """El valor almacenado en Redis es JSON válido y es una lista."""
        cache.save_top_n(uid, "movie", [scored_movie])
        raw = cache._client.get(RedisCache.reco_key(uid, "movie"))
        parsed = json.loads(raw)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert "item" in parsed[0]
        assert "score" in parsed[0]

    def test_get_top_n_after_ttl_expiry(self):
        """Con TTL=1s, después de 1.1s la key no existe y devuelve []."""
        c = RedisCache(use_fake=True, ttl=1)
        uid = uuid4()
        m = Movie(uuid4(), "Efímera", "G", 5.0, ["drama"])
        c.save_top_n(uid, "movie", [ScoredItem(item=m, score=0.5)])
        assert len(c.get_top_n(uid, "movie")) == 1
        # fakeredis respeta TTL en tiempo real
        time.sleep(1.1)
        assert c.get_top_n(uid, "movie") == []

    def test_populate_feedbacks_game_module(self, cache):
        """populate_exclusions_from_feedbacks detecta 'game' correctamente."""
        uid = uuid4()
        game_id = uuid4()
        fb = Feedback(uid, game_id, "game", "jugado")
        cache.populate_exclusions_from_feedbacks(uid, [fb])
        assert cache.is_excluded(uid, "game",  game_id)
        assert not cache.is_excluded(uid, "movie", game_id)

    def test_many_users_no_cross_contamination(self, cache):
        """50 usuarios con distintos top-N no se mezclan."""
        users_items = {uuid4(): make_top_n(5, "movie") for _ in range(50)}
        for uid, items in users_items.items():
            cache.save_top_n(uid, "movie", items)
        for uid, items in users_items.items():
            result = cache.get_top_n(uid, "movie")
            assert len(result) == 5
            assert result[0].item.title == items[0].item.title

    def test_save_single_item_list_then_get(self, cache, uid, scored_game):
        cache.save_top_n(uid, "game", [scored_game])
        result = cache.get_top_n(uid, "game")
        assert len(result) == 1
        assert result[0].item.id == scored_game.item.id

    def test_external_score_float_precision(self, cache, uid):
        """external_score con decimales exactos se preserva."""
        m = Movie(uuid4(), "Float Test", "G", 7.777, ["drama"])
        si = ScoredItem(item=m, score=0.333)
        cache.save_top_n(uid, "movie", [si])
        restored = cache.get_top_n(uid, "movie")[0].item
        assert abs(restored.external_score - 7.777) < 1e-9
