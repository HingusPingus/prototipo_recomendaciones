"""TTLs de caché desde la configuración por entorno (FR-068): ninguno es constante de código (T018)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class _TTLSettings(Protocol):
    ttl_fresh_seconds: int
    ttl_stale_seconds: int
    ttl_filters_seconds: int
    ttl_fallback_seconds: int
    ttl_suppress_seconds: int
    ttl_dedupe_seconds: int

    @property
    def retired_window_seconds(self) -> int: ...


@dataclass(frozen=True, slots=True)
class CacheTTLs:
    fresh: int
    stale: int
    filters: int
    fallback: int
    suppress: int
    dedupe: int
    retired_window: int  # TTL_STALE + 1 día: derivada, no independiente (RD-39, DI-25)

    @classmethod
    def from_settings(cls, settings: _TTLSettings) -> CacheTTLs:
        return cls(
            fresh=settings.ttl_fresh_seconds,
            stale=settings.ttl_stale_seconds,
            filters=settings.ttl_filters_seconds,
            fallback=settings.ttl_fallback_seconds,
            suppress=settings.ttl_suppress_seconds,
            dedupe=settings.ttl_dedupe_seconds,
            retired_window=settings.retired_window_seconds,
        )
