"""Registro de métricas Prometheus (T039; lo emiten las tareas que producen cada hecho).

Declara nombre, tipo y etiquetas de todas las métricas de `data-model.md` §4.4, §7 y de las agregadas
por RD-100…RD-111. Ninguna etiqueta lleva `user_id` ni datos personales (cardinalidad y privacidad).
Cada proceso usa su propio registro; los tests crean uno por instancia.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


@dataclass(frozen=True, slots=True)
class MetricSpec:
    kind: str  # counter | gauge | histogram
    labels: tuple[str, ...]
    help: str
    buckets: tuple[float, ...] | None = None


# `histogram_quantile` no puede superar el mayor límite finito: un rezago de horas exige cubetas de horas.
LAG_BUCKETS = (1.0, 10.0, 60.0, 300.0, 900.0, 1800.0, 3600.0, 7200.0, 21600.0, 86400.0)


SPECS: dict[str, MetricSpec] = {
    # --- API (FR-042) -------------------------------------------------------------------------------
    "reco_cache_hits_total": MetricSpec("counter", ("result_type",), "Respuestas por estado de FR-056"),
    "reco_request_duration_seconds": MetricSpec("histogram", ("endpoint",), "Latencia por endpoint"),
    "reco_recompute_signal_failures_total": MetricSpec("counter", (), "Solicitudes de recálculo no escritas (la lectura no falla)"),
    "reco_unavailable_responses_total": MetricSpec("counter", ("error",), "Respuestas 503 (Redis caído o filtros no disponibles)"),
    "age_stale_config_users_total": MetricSpec("gauge", (), "Usuarios con ordinal bajo escala no compatible (§7.5.1)"),
    # --- Worker (FR-043) --------------------------------------------------------------------------
    "reco_recompute_total": MetricSpec("counter", ("status", "module"), "Recálculos exitosos y fallidos"),
    "reco_recompute_duration_seconds": MetricSpec("histogram", ("module",), "Latencia de recálculo"),
    "reco_dlq_messages_total": MetricSpec("counter", ("reason",), "Mensajes derivados a dead-letter"),
    "reco_queue_depth": MetricSpec("gauge", ("queue",), "Profundidad de cola"),
    "reco_dead_letter_depth": MetricSpec("gauge", ("queue",), "Mensajes en la DLQ, los mande el consumidor o el broker (TTL, delivery-limit)"),
    "reco_cross_module_propagation_total": MetricSpec("counter", ("propagated",), "Decisión de propagar al módulo opuesto (FR-010c)"),
    "recompute_requests_pending": MetricSpec("gauge", (), "Pendientes de recompute:requests (RD-111)"),
    "recompute_requests_dropped_total": MetricSpec("counter", (), "Solicitudes descartadas al agotar entregas (RD-111)"),
    "diversity_cap_relaxed_total": MetricSpec("counter", ("module",), "Relajaciones del tope de cluster (FR-071a)"),
    "collab_insufficient_neighbors_total": MetricSpec("counter", ("module",), "Recálculos con menos de collab_min_neighbors vecinos (SC-031)"),
    "fallback_new_item_share": MetricSpec("gauge", ("module", "kind"), "Cuota de novedades disponible/ocupada (FR-033a8)"),
    "signal_duplicate_rejections_total": MetricSpec("counter", ("source",), "Reentregas de una misma interacción (§7.10)"),
    "signal_ingest_lag_seconds": MetricSpec("histogram", ("source",), "received_at − occurred_at (§7.10)", LAG_BUCKETS),
    "contract_violations_total": MetricSpec("counter", ("field",), "Incumplimientos de contrato del origen; esperado 0"),
    "exclusion_resolve_lag_seconds": MetricSpec("gauge", (), "Rezago del resolutor de exclusiones (§7.12)"),
    "suppressions_unverified_total": MetricSpec("gauge", (), "Supresiones sin constancia; esperado 0 (FR-095a)"),
    "user_deletion_residual_keys_total": MetricSpec("counter", (), "Residuos hallados al verificar una supresión (§7.11)"),
    # --- Data Transformer (FR-044) ------------------------------------------------------------------
    "catalog_sync_last_success_timestamp": MetricSpec("gauge", (), "Última sincronización exitosa (§7.7)"),
    "reco_sync_duration_seconds": MetricSpec("histogram", (), "Duración de la sincronización"),
    "sync_volume_delta_ratio": MetricSpec("gauge", ("entity",), "Volumen vs. última corrida exitosa (§7.12)"),
    "catalog_unrated_ratio": MetricSpec("gauge", (), "Ítems vigentes sin clasificación declarada (§7.7)"),
    "catalog_retired_total": MetricSpec("gauge", (), "Ítems retirados (panel, sin umbral)"),
    "projection_field_anomalies_total": MetricSpec("counter", ("field", "reason"), "Anomalías de proyección (§7.8)"),
    "retired_set_size": MetricSpec("gauge", ("module",), "Tamaño del set retired: (§4.4)"),
    # --- Vocabulario y vectores (T030) ------------------------------------------------------------
    "vector_recompute_lag_seconds": MetricSpec("gauge", (), "now − min(computed_at) sobre la versión activa (§7.9)"),
    "vocab_transition_progress": MetricSpec("gauge", (), "Vectores de la versión entrante / esperados (§7.9)"),
    "catalog_unvectorized_ratio": MetricSpec("gauge", (), "Vigentes sin vector bajo la versión activa (§7.9)"),
    "declarable_tags_total": MetricSpec("gauge", ("module",), "Tags elegibles para declarar (DEP-10, RD-110)"),
    # --- Batch ---------------------------------------------------------------------------------------
    "catalog_popularity_last_success_timestamp": MetricSpec("gauge", (), "Último recálculo de popularidad (§7.7)"),
    "age_refresh_last_success_timestamp": MetricSpec("gauge", (), "Liveness del refresco etario (§7.5.1)"),
    "age_threshold_crossings_total": MetricSpec("counter", (), "Usuarios que cruzan un umbral (panel)"),
    "signals_purge_deferred_total": MetricSpec("counter", (), "Consumos no purgados por faltar su exclusión (§7.10)"),
    "exclusions_orphaned_permanent_total": MetricSpec("gauge", (), "Exclusiones permanentes sin señal viva (informativa, sin alerta)"),
    # --- Configuración (FR-025d) --------------------------------------------------------------------
    "reco_active_config_version": MetricSpec("gauge", ("config_version", "component"), "Versión activa (1 = activa)"),
}

_FORBIDDEN_LABELS = {"user_id", "item_id", "email", "birth_date", "region"}


class Metrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self._metrics: dict[str, Counter | Gauge | Histogram] = {}
        for name, spec in SPECS.items():
            assert not _FORBIDDEN_LABELS & set(spec.labels), name
            if spec.kind == "counter":
                self._metrics[name] = Counter(name, spec.help, spec.labels, registry=self.registry)
            elif spec.kind == "gauge":
                gauge = Gauge(name, spec.help, spec.labels, registry=self.registry)
                if not spec.labels:
                    # Un gauge sin etiquetas se exporta como 0 hasta que alguien lo fija: en un proceso que
                    # nunca lo emite, `time() - <timestamp> > umbral` dispararía en falso. NaN no dispara.
                    gauge.set(float("nan"))
                self._metrics[name] = gauge
            elif spec.buckets:
                self._metrics[name] = Histogram(name, spec.help, spec.labels, registry=self.registry, buckets=spec.buckets)
            else:
                self._metrics[name] = Histogram(name, spec.help, spec.labels, registry=self.registry)

    def _metric(self, name: str, labels: dict[str, str]):  # noqa: ANN202
        metric = self._metrics[name]
        return metric.labels(**labels) if labels else metric

    def inc(self, name: str, amount: float = 1.0, **labels: str) -> None:
        self._metric(name, labels).inc(amount)

    def set(self, name: str, value: float, **labels: str) -> None:
        self._metric(name, labels).set(value)

    def observe(self, name: str, value: float, **labels: str) -> None:
        self._metric(name, labels).observe(value)

    def value(self, name: str, **labels: str) -> float:
        sample = name if SPECS[name].kind != "histogram" else f"{name}_count"
        found = self.registry.get_sample_value(sample, labels or None)
        if found is None or math.isnan(found):  # ausente o NaN (gauge nunca fijado)
            return 0.0
        return float(found)


class RecordingMetrics(Metrics):
    """`Metrics` de un proceso de una corrida (transformer, batch): además de fijar, registra (T066).

    Esos procesos terminan y no exponen servidor: lo registrado se persiste en `process_runs` al cerrar la
    corrida y el worker lo re-expone. Gauges: último valor; contadores: suma de incrementos;
    histogramas: observaciones.
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        super().__init__(registry)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._observations: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = {}

    @staticmethod
    def _key(name: str, labels: dict[str, str]) -> tuple[str, tuple[tuple[str, str], ...]]:
        return name, tuple(sorted((k, str(v)) for k, v in labels.items()))

    def inc(self, name: str, amount: float = 1.0, **labels: str) -> None:
        super().inc(name, amount, **labels)
        key = self._key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + amount

    def set(self, name: str, value: float, **labels: str) -> None:
        super().set(name, value, **labels)
        if math.isfinite(value):  # jsonb no admite NaN ni infinito; un gauge sin valor útil no se persiste
            self._gauges[self._key(name, labels)] = float(value)

    def observe(self, name: str, value: float, **labels: str) -> None:
        super().observe(name, value, **labels)
        self._observations.setdefault(self._key(name, labels), []).append(float(value))

    def snapshot(self) -> dict[str, list]:
        """Forma JSON persistible: listas de [nombre, etiquetas, valor]."""

        def rows(store: dict) -> list:
            return [[name, dict(labels), value] for (name, labels), value in sorted(store.items())]

        return {"gauges": rows(self._gauges), "counters": rows(self._counters), "histograms": rows(self._observations)}
