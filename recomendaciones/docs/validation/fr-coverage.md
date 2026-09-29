# Cobertura FR → tarea (T048, Definition of Done)

**Fecha**: 2026-09-29 · **Rama**: `001-recomendaciones-precomputadas`

Recorrido de los **167** requisitos funcionales de `spec.md` contra `tasks.md`, que cierra el ítem de la DoD
«Ningún FR carece de tarea, o su ausencia está declarada con motivo». Resultado: **167 de 167 con tarea**.
Ninguno queda sin tarea; FR-079a es una expectativa externa y su tarea en este repositorio es T047, que la
registra y verifica solo su efecto.

`tests/contract/test_fr_coverage.py` verifica la **integridad**: que figuren todos los FR de `spec.md`, que
cada tarea citada exista en `tasks.md` y que cada evidencia exista. Que una tarea cite un FR no prueba que lo
cumpla; eso lo sostienen los tests de la tarea y la matriz `docs/validation/traceability-matrix.md`.

## 1. Requisitos que alguna tarea cita por identificador (133)

Tareas cuya sección en `tasks.md` nombra el requisito. Generado por búsqueda literal del identificador.

| FR | Tareas |
|---|---|
| FR-001 | T033 |
| FR-003 | T006, T037, T053, T065 |
| FR-004 | T033 |
| FR-005 | T033 |
| FR-006a | T033 |
| FR-008 | T034 |
| FR-010 | T064 |
| FR-010a | T027, T060 |
| FR-010c | T027, T040 |
| FR-010d | T007 |
| FR-010e | T030 |
| FR-010f | T003, T007, T030 |
| FR-010g | T030 |
| FR-011 | T003, T064 |
| FR-011a | T064 |
| FR-012 | T064 |
| FR-015 | T028 |
| FR-017 | T028 |
| FR-019 | T032 |
| FR-021 | T009 |
| FR-021b | T029 |
| FR-022 | T007, T009 |
| FR-022a | T004 |
| FR-022b | T004, T008 |
| FR-022c | T008 |
| FR-023 | T010 |
| FR-025 | T010, T012 |
| FR-025b | T003 |
| FR-025c | T018 |
| FR-025d | T039 |
| FR-027 | T004 |
| FR-028 | T065 |
| FR-029a | T008 |
| FR-029b1 | T014 |
| FR-029d | T008 |
| FR-029e | T064 |
| FR-029e1 | T029, T064 |
| FR-031 | T015, T065 |
| FR-033 | T016 |
| FR-033a1 | T029, T038 |
| FR-033a2 | T038 |
| FR-033a3 | T004, T063 |
| FR-033a3a | T063 |
| FR-033a3b | T063 |
| FR-033a4 | T063 |
| FR-033a5 | T063 |
| FR-033a6 | T065 |
| FR-033a6a | T065 |
| FR-033a6d | T065 |
| FR-033a6e | T063 |
| FR-033a6f1 | T038, T065 |
| FR-033a6f2 | T065 |
| FR-033a7 | T065 |
| FR-033a8 | T039, T065 |
| FR-033b | T038 |
| FR-033c | T038 |
| FR-033d | T037, T038, T065 |
| FR-033f | T004, T038 |
| FR-034 | T020 |
| FR-036 | T037 |
| FR-038 | T020 |
| FR-040 | T028, T032 |
| FR-042 | T039 |
| FR-043 | T039 |
| FR-044 | T039 |
| FR-048 | T045 |
| FR-049 | T013, T037 |
| FR-050 | T014, T037 |
| FR-051 | T003, T013, T029 |
| FR-053 | T004, T013 |
| FR-054 | T002, T004, T013 |
| FR-055 | T013, T017, T045 |
| FR-056 | T005, T017, T020, T037, T038, T049, T052, T055, T062, T063 |
| FR-056a | T020, T033, T049, T062 |
| FR-057 | T005 |
| FR-058 | T035 |
| FR-059 | T002, T034 |
| FR-060 | T034 |
| FR-061 | T023, T047, T049 |
| FR-062 | T005, T029 |
| FR-063 | T047 |
| FR-064 | T023 |
| FR-065 | T021 |
| FR-066 | T022 |
| FR-067 | T025, T027 |
| FR-068 | T018, T024, T025, T057 |
| FR-068a | T057 |
| FR-068b | T004, T057, T063 |
| FR-068c | T057 |
| FR-068d | T057 |
| FR-068d1 | T042, T057 |
| FR-068e | T006 |
| FR-069 | T024 |
| FR-070 | T004, T010, T012, T015, T038, T065 |
| FR-071 | T004, T015 |
| FR-071a | T015, T038, T039, T065 |
| FR-072 | T012, T017, T037, T038, T052 |
| FR-073 | T008, T017, T029, T052 |
| FR-074 | T029, T052 |
| FR-075 | T037, T052 |
| FR-079 | T003 |
| FR-079a | T047 |
| FR-080 | T051, T060 |
| FR-080a | T003, T004, T027, T060, T064 |
| FR-080b | T003, T060 |
| FR-080c | T014, T018, T029, T051, T053, T058, T060, T064 |
| FR-081 | T061 |
| FR-081a | T004, T061 |
| FR-081b | T004, T061 |
| FR-082 | T053, T056 |
| FR-083 | T053, T054 |
| FR-084 | T053 |
| FR-085 | T008, T017, T054 |
| FR-086 | T054 |
| FR-086a | T053 |
| FR-086b | T008 |
| FR-087 | T008, T056 |
| FR-088 | T017, T044, T047, T049, T053, T054, T055 |
| FR-089 | T049, T053 |
| FR-089a | T053 |
| FR-089b | T053 |
| FR-090 | T061 |
| FR-090a | T061 |
| FR-091 | T058, T059 |
| FR-091a | T029, T058 |
| FR-091b | T029 |
| FR-092 | T058 |
| FR-092a | T027, T058 |
| FR-093 | T058 |
| FR-094 | T059 |
| FR-095 | T059 |
| FR-095a | T039, T042, T059 |
| FR-096 | T061 |

## 2. Requisitos cubiertos por contenido, sin cita por identificador (34)

Ninguna sección de `tasks.md` los nombra, pero una tarea los implementa: casi todos son requisitos de la
primera versión de `spec.md`, anteriores a la costumbre de citar el identificador en cada criterio. Cada uno
se asignó leyendo su texto y se respalda con el test que hoy lo sostiene.

| FR | Tareas | Evidencia | Nota |
|---|---|---|---|
| FR-002 | T020, T033 | `tests/integration/test_no_heavy_compute.py::test_normal_path_emits_zero_queries` | Lectura cache-first; cero consultas en el camino normal |
| FR-006 | T033, T035, T062 | `tests/contract/test_read_endpoint.py::test_response_validates_against_the_published_contract`<br>`tests/unit/test_domain.py::test_result_type_has_exactly_the_five_states_of_fr056` | `computed_at` y `result_type` son requeridos en el OpenAPI |
| FR-007 | T034 | `tests/contract/test_auth.py::test_key_matrix_gives_identical_401`<br>`tests/contract/test_auth.py::test_every_route_requires_the_key_except_health` |  |
| FR-009 | T023, T043 | `tests/integration/test_consumer.py::test_invalid_payloads_are_rejected_with_cause`<br>`tests/contract/test_contract_gate.py::test_every_field_the_worker_consumes_is_required_by_the_official_event_schema` |  |
| FR-010b | T030 | `tests/unit/test_vocabulary.py::test_single_space_shared_by_both_modules`<br>`tests/integration/test_vector_reconciliation.py::test_new_item_with_existing_tags_gets_a_vector` | El vocabulario sale de los ítems materializados |
| FR-011b | T003, T024, T064 | `tests/integration/test_event_signals.py::test_interaction_that_arrived_first_by_sync_is_not_duplicated`<br>`tests/integration/test_idempotency.py::test_same_event_ten_times_processes_once` | Precisado por RD-111: interacciones y eventos |
| FR-013 | T025 | `tests/integration/test_retry_dlq.py::test_transient_failure_is_retried_until_success`<br>`tests/integration/test_retry_dlq.py::test_permanent_failure_goes_to_dlq_after_five_attempts_with_intact_payload` |  |
| FR-014 | T019 | `tests/integration/test_cache_repository.py::test_round_trip_is_exact_and_carries_config_version` |  |
| FR-016 | T027, T029, T030 | `tests/invariants/test_data_invariants.py::test_di_13_single_writer_per_table`<br>`tests/integration/test_sync_idempotent.py::test_pipeline_never_writes_derived_tables` | Escritor único por tabla (DI-13) |
| FR-018 | T029 | `tests/integration/test_sync_idempotent.py::test_double_execution_leaves_identical_state`<br>`tests/integration/test_sync_idempotent.py::test_interruption_leaves_consistent_state` |  |
| FR-020 | T029 | `tests/integration/test_sync_idempotent.py::test_birth_date_correction_rederives_and_invalidates_in_the_same_act`<br>`tests/integration/test_sync_idempotent.py::test_absence_from_a_complete_listing_retires_logically_and_reappearance_restores` | La corrección del origen reemplaza a la proyección local |
| FR-021a | T007, T029 | `tests/integration/test_sync_idempotent.py::test_item_without_tags_is_rejected_without_aborting`<br>`tests/unit/test_vocabulary.py::test_idf_formula_and_tag_in_every_item_weighs_exactly_one` | Pertenencia binaria; el peso se calcula al vectorizar |
| FR-024 | T011 | `tests/unit/test_cross_module.py::test_horror_movies_boost_horror_games`<br>`tests/unit/test_cross_module.py::test_no_activity_in_opposite_module_gives_zero` |  |
| FR-025a | T004 | `tests/unit/test_config_loader.py::test_hash_is_reproducible_and_content_based`<br>`tests/integration/test_config_registration.py::test_rollback_to_deactivated_version_fails` | La configuración vive en `src/recomendaciones/config/engine_config/` |
| FR-026 | T012 | `tests/unit/test_scoring.py::test_reproducible_in_100_runs_with_shuffled_input` |  |
| FR-029 | T004, T013, T014 | `tests/invariants/test_age_filter.py::test_filter_has_no_parameter_to_disable_it`<br>`tests/unit/test_config_loader.py::test_invalid_configurations_fail_naming_the_field` |  |
| FR-029b | T014 | `tests/invariants/test_exclusion.py::test_every_signal_kind_excludes` |  |
| FR-029c | T014 | `tests/invariants/test_exclusion.py::test_origin_resolution` |  |
| FR-030 | T013 | `tests/invariants/test_age_filter.py::test_garbage_ratings_map_to_most_restrictive`<br>`tests/integration/test_sync_idempotent.py::test_item_without_rating_or_with_unknown_rating_gets_most_restrictive` |  |
| FR-030a | T004, T013 | `tests/unit/test_config_loader.py::test_rating_outside_catalog_is_not_a_valid_rating`<br>`tests/invariants/test_age_filter.py::test_no_hardcoded_rating_dict_in_engine` |  |
| FR-030b | T004, T013 | `tests/invariants/test_age_filter.py::test_cartesian_product_rating_by_age_band` | Un único `age_rating_catalog` para ambos módulos |
| FR-032 | T015 | `tests/unit/test_mmr.py::test_diversity_improves_over_undiversified_top_n`<br>`tests/unit/test_mmr.py::test_every_prefix_respects_cluster_cap_unless_relaxed` |  |
| FR-033a | T038, T063 | `tests/integration/test_fallback_batch.py::test_diversity_beats_the_undiversified_ranking`<br>`tests/integration/test_popularidad.py::test_only_signals_inside_the_window_count` |  |
| FR-033a6b | T004 | `tests/unit/test_config_loader.py::test_invalid_configurations_fail_naming_the_field` | Validación de arranque, no al servir |
| FR-033a6c | T063 | `tests/integration/test_popularidad.py::test_promotion_is_recorded_once_and_never_revoked` | `item_promotions` (RD-102) |
| FR-033e | T020, T037 | `tests/integration/test_cache_miss.py::test_state_table`<br>`tests/unit/test_domain.py::test_precedence_order_is_fr056` |  |
| FR-033g | T020, T027 | `tests/integration/test_critical_scenarios.py::test_newly_declared_user_gets_non_personalized_fallback_then_personalized_after_recompute` |  |
| FR-035 | T020 | `tests/integration/test_cache_miss.py::test_fifty_concurrent_misses_produce_one_request` |  |
| FR-037 | T018, T020 | `tests/integration/test_redis.py::test_effective_ttls_and_filters_expire_before_reco`<br>`tests/unit/test_settings.py::test_operational_parameters_have_no_default` | El límite es `TTL_STALE`, operativo y sin valor por defecto |
| FR-039 | T022 | `tests/integration/test_recompute_requests.py::test_warmup_plus_worker_rebuild_every_entry` |  |
| FR-041 | T002, T021, T032 | `tests/integration/test_redis_down.py::test_redis_down_raises_503_error_and_never_reaches_postgres`<br>`tests/unit/test_settings.py::test_only_one_database_connection_string`<br>`tests/contract/test_auth.py::test_openapi_and_docs_are_not_exposed` |  |
| FR-045 | T041 | `tests/integration/test_health.py::test_liveness_does_not_depend_on_redis_and_readiness_does`<br>`tests/integration/test_health.py::test_worker_and_transformer_have_their_own_health` |  |
| FR-046 | T040 | `tests/integration/test_correlation.py::test_json_lines_with_stable_fields_and_no_secrets`<br>`tests/integration/test_correlation.py::test_correlation_id_travels_api_to_stream_to_worker` |  |
| FR-047 | T043, T049 | `tests/contract/test_contract_gate.py::test_every_exposed_operation_is_exercised_by_this_gate`<br>`tests/contract/test_contract_gate.py::test_worker_copies_are_identical_to_the_contracts` |  |
