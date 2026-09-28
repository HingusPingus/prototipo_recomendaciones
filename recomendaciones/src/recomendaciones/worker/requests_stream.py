"""Consumo de `recompute:requests` con grupo de consumidores (T027, RD-100, RD-111).

Cada entrada `{user_id, module, reason}` recalcula ese módulo sin pasar por el conteo de FR-080a. Se
confirma (`XACK`) **después** de escribir el resultado: una caída a mitad deja la entrada pendiente y
otro consumidor la reclama. Una entrada entregada más de `recompute_requests_max_deliveries` veces se
confirma y se descarta (`recompute_requests_dropped_total`): es reconstruible, el siguiente miss la
vuelve a emitir. La solicitud de un usuario en supresión se descarta (FR-092a).
"""

from __future__ import annotations

import logging
import uuid

from redis.exceptions import ResponseError

from recomendaciones.observability.metrics import Metrics
from recomendaciones.shared.domain import Module
from recomendaciones.storage.cache import keys
from recomendaciones.storage.cache.client import CacheClient

log = logging.getLogger(__name__)


class RecomputeRequestConsumer:
    def __init__(
        self,
        cache: CacheClient,
        recomputer,  # noqa: ANN001 — Recomputer
        metrics: Metrics,
        *,
        consumer_name: str,
        max_deliveries: int,
        claim_idle_ms: int = 60_000,
        block_ms: int = 1_000,
        batch: int = 16,
    ) -> None:
        self._cache = cache
        self._recomputer = recomputer
        self._metrics = metrics
        self._consumer = consumer_name
        self._max = max_deliveries
        self._idle = claim_idle_ms
        self._block = block_ms
        self._batch = batch
        self._group_ready = False

    def _ensure_group(self) -> None:
        if self._group_ready:
            return
        try:
            self._cache.call(
                lambda: self._cache.raw.xgroup_create(keys.RECOMPUTE_STREAM, keys.RECOMPUTE_GROUP, id="0", mkstream=True)
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        self._group_ready = True

    def _ack(self, entry_id: str) -> None:
        self._cache.call(lambda: self._cache.raw.xack(keys.RECOMPUTE_STREAM, keys.RECOMPUTE_GROUP, entry_id))

    def _deliveries(self, entry_id: str) -> int:
        rows = self._cache.call(
            lambda: self._cache.raw.xpending_range(keys.RECOMPUTE_STREAM, keys.RECOMPUTE_GROUP, entry_id, entry_id, 1)
        )
        return int(rows[0]["times_delivered"]) if rows else 0

    def _handle(self, entry_id: str, fields: dict[str, str]) -> None:
        try:
            user_id = uuid.UUID(fields["user_id"])
            module = Module(fields["module"])
        except (KeyError, ValueError):
            log.warning("solicitud de recálculo malformada", extra={"entry_id": entry_id})
            self._ack(entry_id)
            return
        try:
            self._recomputer.recompute(user_id, module, fields.get("reason", "miss"))
        except Exception:  # noqa: BLE001 — queda pendiente y se reclamará
            log.exception("recálculo fallido; la solicitud queda pendiente", extra={"entry_id": entry_id})
            return
        self._ack(entry_id)

    def poll_once(self) -> int:
        """Reclama pendientes ociosas, lee nuevas y procesa. Devuelve cuántas entradas atendió."""
        self._ensure_group()
        handled = 0
        claimed = self._cache.call(
            lambda: self._cache.raw.xautoclaim(
                keys.RECOMPUTE_STREAM, keys.RECOMPUTE_GROUP, self._consumer, self._idle, start_id="0-0", count=self._batch
            )
        )
        for entry_id, fields in claimed[1]:
            if not fields:
                continue  # entrada recortada por MAXLEN
            handled += 1
            if self._deliveries(entry_id) > self._max:
                self._ack(entry_id)
                self._metrics.inc("recompute_requests_dropped_total")
                log.warning("solicitud descartada tras agotar las entregas", extra={"entry_id": entry_id})
                continue
            self._handle(entry_id, fields)
        fresh = self._cache.call(
            lambda: self._cache.raw.xreadgroup(
                keys.RECOMPUTE_GROUP, self._consumer, {keys.RECOMPUTE_STREAM: ">"}, count=self._batch, block=self._block
            )
        )
        for _stream, entries in fresh or []:
            for entry_id, fields in entries:
                handled += 1
                self._handle(entry_id, fields)
        pending = self._cache.call(lambda: self._cache.raw.xpending(keys.RECOMPUTE_STREAM, keys.RECOMPUTE_GROUP))
        self._metrics.set("recompute_requests_pending", float(pending["pending"]))
        return handled
