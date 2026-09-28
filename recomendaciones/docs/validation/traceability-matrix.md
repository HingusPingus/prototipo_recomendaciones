# Matriz de trazabilidad ítem → evidencia (T048)

**Fecha**: 2026-09-28 · **Rama**: `001-recomendaciones-precomputadas`

Cada ítem de los dos checklists (30 de `requirements-contracts.md` y 46 de
`requirements-clarify-2026-09-14.md`), cada invariante transversal, cada Success Criterion y cada deuda del
prototipo, con el test o archivo que **hoy** lo sostiene. **Un ítem sin evidencia concreta no se marca**: se
deja `[ ]` con el motivo.

`tests/contract/test_traceability.py` verifica la **integridad**: que figuren todos los ítems, que cada
evidencia citada exista (archivo, y función de test si se nombra con `::`) y que ningún ítem marcado carezca
de evidencia. Que la evidencia esté **en verde** lo garantiza el pipeline de CI, que corre toda la suite en
el mismo PR. El juicio sobre si la evidencia es **suficiente** es revisión humana y queda declarado así en el
PR de cierre.

Rutas relativas a `recomendaciones/`; las que empiezan por `.github/` son relativas a la raíz del repositorio.

## Checklist de contratos (`requirements-contracts.md`)

| Ítem | Estado | Evidencia | Nota |
|---|---|---|---|
| CHK001 | [x] | `tests/contract/test_contract_gate.py::test_dependency_is_declared_in_the_contract`<br>`tests/unit/test_domain.py::test_signal_without_type_cannot_be_built` | DEP-1 |
| CHK002 | [x] | `tests/unit/test_profile.py::test_consumo_does_not_alter_the_profile`<br>`tests/integration/test_consumer.py::test_invalid_payloads_are_rejected_with_cause` | FR-064: sin `signal_type` el evento va a DLQ; nunca se infiere |
| CHK003 | [x] | `tests/contract/test_contract_artifacts.py::test_event_schema_requires_the_seven_fields_of_fr061`<br>`tests/integration/test_idempotency.py::test_same_event_ten_times_processes_once` | |
| CHK004 | [x] | `tests/contract/test_contract_gate.py::test_dependency_is_declared_in_the_contract`<br>`tests/integration/test_sync_idempotent.py::test_activity_keeps_signal_type_and_origin_timestamp` | DEP-2 |
| CHK005 | [x] | `docs/contracts/required-fields.md`<br>`tests/contract/test_required_fields_doc.py::test_every_field_the_contract_tests_validate_is_named_in_the_document` | FR-063 |
| CHK006 | [x] | `tests/integration/test_popularidad.py::test_only_signals_inside_the_window_count`<br>`tests/integration/test_popularidad.py::test_wilson_formula` | DEP-4 resuelta internamente |
| CHK007 | [x] | `tests/unit/test_domain.py::test_precedence_order_is_fr056`<br>`tests/integration/test_cache_miss.py::test_state_table`<br>`tests/integration/test_cache_miss.py::test_fallback_empty_after_filters_is_no_candidates` | |
| CHK008 | [x] | `tests/contract/test_contract_artifacts.py::test_read_endpoint_contract`<br>`tests/contract/test_rechazo_sin_declaracion.py::test_the_set_of_result_states_still_has_five_members` | DEP-6 |
| CHK009 | [x] | `tests/contract/test_contract_artifacts.py::test_event_schema_requires_the_seven_fields_of_fr061`<br>`tests/contract/test_contract_gate.py::test_every_field_the_worker_consumes_is_required_by_the_official_event_schema` | |
| CHK010 | [x] | `specs/001-recomendaciones-precomputadas/contracts/recomendaciones-api.openapi.yaml`<br>`tests/contract/test_openapi_conformance.py::test_operation_conforms` | La ruta está versionada (`/internal/v1`) y el gate detecta todo cambio de contrato. El período de coexistencia de FR-058 es política de despliegue: se ejerce recién con una `v2` |
| CHK011 | [x] | `tests/unit/test_settings.py::test_presented_key_of_other_environment_is_rejected`<br>`tests/contract/test_auth.py::test_key_matrix_gives_identical_401` | |
| CHK012 | [x] | `tests/contract/test_auth.py::test_network_restriction_is_declared_and_auditable`<br>`tests/contract/test_auth.py::test_openapi_and_docs_are_not_exposed`<br>`ops/network-policy.yaml` | |
| CHK013 | [x] | `tests/unit/test_fallback_bounded.py::test_guard_is_membership_and_comparison_only`<br>`tests/unit/test_architecture.py::test_repository_respects_architecture`<br>`tests/integration/test_no_heavy_compute.py::test_normal_path_emits_zero_queries` | |
| CHK014 | [x] | `tests/invariants/test_exclusion.py::test_unavailable_exclusion_set_rejects_instead_of_serving_unfiltered`<br>`tests/invariants/test_fallback_filtering.py::test_unavailable_exclusion_set_rejects_with_retryable_error` | |
| CHK015 | [x] | `tests/integration/test_critical_scenarios.py::test_minor_receives_zero_unsuitable_content_in_all_five_result_types`<br>`tests/invariants/test_data_invariants.py::test_every_result_type_respects_age_and_exclusion` | |
| CHK016 | [x] | `tests/invariants/test_age_filter.py::test_garbage_ratings_map_to_most_restrictive`<br>`tests/integration/test_sync_idempotent.py::test_item_without_rating_or_with_unknown_rating_gets_most_restrictive` | |
| CHK017 | [x] | `tests/integration/test_migrations.py::test_user_ingest_constraints`<br>`tests/invariants/test_age_filter.py::test_cartesian_product_rating_by_age_band` | FR-052 quedó retirado: un usuario sin `birth_date` ya no se atiende en modo restrictivo, se rechaza (RD-61, RD-85) |
| CHK018 | [x] | `tests/unit/test_config_loader.py::test_invalid_configurations_fail_naming_the_field`<br>`tests/invariants/test_age_filter.py::test_filter_has_no_parameter_to_disable_it` | |
| CHK019 | [x] | `tests/invariants/test_age_filter.py::test_cartesian_product_rating_by_age_band`<br>`tests/invariants/test_exclusion.py::test_every_signal_kind_excludes`<br>`tests/invariants/test_data_invariants.py::test_every_result_type_respects_age_and_exclusion`<br>`tools/mutation_postprocess.py` | |
| CHK020 | [x] | `tests/unit/test_config_loader.py::test_invalid_configurations_fail_naming_the_field`<br>`tests/unit/test_config_loader.py::test_v1_loads_with_decided_values` | |
| CHK021 | [x] | `tests/unit/test_scoring.py::test_ties_break_by_popularity_then_item_id`<br>`tests/unit/test_scoring.py::test_reproducible_in_100_runs_with_shuffled_input` | Desempate fijo (RD-10), no configurable |
| CHK022 | [x] | `tests/unit/test_mmr.py::test_every_prefix_respects_cluster_cap_unless_relaxed`<br>`tests/unit/test_mmr.py::test_cap_holds_exactly_when_other_clusters_are_available` | |
| CHK023 | [x] | `tests/unit/test_profile.py::test_profile_is_l2_normalized_for_any_signals`<br>`tests/unit/test_profile.py::test_null_vector_similarity_is_zero`<br>`tests/unit/test_profile.py::test_cosine_always_within_bounds` | |
| CHK024 | [x] | `tests/unit/test_vocabulary.py::test_single_space_shared_by_both_modules`<br>`tests/integration/test_vocab_transition.py::test_new_vocabulary_is_fully_vectorized_before_activation`<br>`tests/integration/test_vocab_transition.py::test_versions_are_identified_by_content` | |
| CHK025 | [x] | `tests/unit/test_profile.py::test_general_profile_aggregates_both_modules`<br>`tests/integration/test_herencia_tags_db.py::test_general_scope_aggregates_both_modules_declarations` | |
| CHK026 | [x] | `tests/integration/test_redis_down.py::test_redis_down_raises_503_error_and_never_reaches_postgres`<br>`tests/contract/test_errors.py::test_redis_down_is_503_with_retry_after_never_200` | |
| CHK027 | [x] | `tests/unit/test_fallback_bounded.py::test_guard_is_membership_and_comparison_only`<br>`tests/unit/test_fallback_bounded.py::test_read_service_imports_no_engine_nor_similarity` | |
| CHK028 | [x] | `tests/integration/test_warmup.py::test_is_not_triggered_by_reads`<br>`tests/integration/test_warmup.py::test_respects_rate_limit`<br>`tests/integration/test_requests_stream_recovery.py::test_consumer_recreates_its_group_after_redis_loses_everything` | |
| CHK029 | [x] | `tests/integration/test_propagation.py::test_modules_are_independent_units`<br>`tests/integration/test_retry_dlq.py::test_opposite_module_failure_keeps_primary_and_requeues_only_the_opposite` | |
| CHK030 | [x] | `tests/unit/test_settings.py::test_operational_parameters_have_no_default`<br>`tests/integration/test_idempotency.py::test_duplicate_after_mark_expiry_is_reprocessed_and_converges` | |

## Checklist de clarificación (`requirements-clarify-2026-09-14.md`)

| Ítem | Estado | Evidencia | Nota |
|---|---|---|---|
| CHK031 | [x] | `tests/integration/test_alerts.py::test_every_required_alert_exists`<br>`tests/integration/test_metrics.py::test_registry_declares_every_required_metric`<br>`docs/runbook.md` | `declarable_tags_total{module}` con alerta `DeclarableTagsBelowMinimum` |
| CHK032 | [x] | `tests/unit/test_config_loader.py::test_v1_loads_with_decided_values`<br>`tests/unit/test_declaracion_minimo.py::test_minimum_without_maximum` | |
| CHK033 | [x] | `tests/contract/test_declaracion_endpoint.py::test_declaring_one_module_does_not_require_the_other`<br>`tests/contract/test_rechazo_sin_declaracion.py::test_rejection_is_per_module` | |
| CHK034 | [x] | `tests/contract/test_rechazo_sin_declaracion.py::test_rejection_is_per_module`<br>`tests/integration/test_critical_scenarios.py::test_user_without_declaration_is_rejected_as_precondition_without_a_sixth_state` | |
| CHK035 | [x] | `tests/unit/test_herencia_tags.py::test_five_inherited_and_zero_own_is_rejected`<br>`tests/integration/test_herencia_tags_db.py::test_table_holds_only_own_and_profile_input_adds_inherited` | |
| CHK036 | [x] | `tests/unit/test_herencia_tags.py::test_inherited_are_other_module_declared_intersect_shared`<br>`tests/integration/test_tag_modules.py::test_retiring_the_last_item_of_a_module_removes_the_tag_from_it` | |
| CHK037 | [x] | `tests/integration/test_herencia_tags_db.py::test_feedback_never_alters_declaration_membership`<br>`tests/unit/test_profile.py::test_three_dislikes_can_cancel_a_declared_tag_and_a_like_raises_it_again`<br>`tests/unit/test_user_profile_derivado.py::test_the_only_public_operation_is_rebuild_from_inputs` | |
| CHK038 | [x] | `tests/contract/test_declaracion_endpoint.py::test_second_declaration_is_409_and_leaves_rows_intact` | Declaración definitiva por decisión (RD-109): la edición está fuera de alcance y declarada |
| CHK039 | [x] | `tests/contract/test_rechazo_sin_declaracion.py::test_the_set_of_result_states_still_has_five_members`<br>`tests/contract/test_rechazo_sin_declaracion.py::test_precondition_runs_before_result_resolution`<br>`tests/unit/test_domain.py::test_declaration_required_is_an_error_not_a_result_type` | |
| CHK040 | [x] | `tests/contract/test_declaracion_endpoint.py::test_the_engine_is_never_invoked`<br>`tests/unit/test_architecture.py::test_repository_respects_architecture` | |
| CHK041 | [x] | `tests/contract/test_declaracion_endpoint.py::test_the_engine_is_never_invoked` | Criterio observable: ausencia de llamada al motor, no una cota de tiempo |
| CHK042 | [x] | `tests/contract/test_declaracion_endpoint.py::test_valid_declaration_is_confirmed_synchronously`<br>`tests/contract/test_declaracion_endpoint.py::test_invalidates_filters_before_writing` | |
| CHK043 | [x] | `tests/integration/test_migrations.py::test_declared_tags_asymmetric_fks`<br>`tests/invariants/test_data_invariants.py::test_di_16_tag_with_assignments_cannot_be_deleted` | |
| CHK044 | [x] | `tests/invariants/test_data_invariants.py::test_di_28_declared_minimum_audit` | |
| CHK045 | [x] | `tests/integration/test_supresion_aborta_recalculo.py::test_redis_is_cleared_before_postgres`<br>`tests/integration/test_supresion_aborta_recalculo.py::test_recompute_in_flight_is_aborted_and_does_not_rewrite_the_suppressed_result` | |
| CHK046 | [x] | `tests/integration/test_supresion_verificada.py::test_persistent_residue_in_redis_ends_in_visible_failure_and_increments_the_alert_metric`<br>`tests/integration/test_supresion_verificada.py::test_unverified_gauge_counts_open_suppressions`<br>`tests/integration/test_alerts.py::test_every_required_alert_exists` | |
| CHK047 | [x] | `tests/integration/test_supresion_verificada.py::test_clean_suppression_is_verified_and_the_row_keeps_only_identifier_and_timestamps` | |
| CHK048 | [x] | `tests/integration/test_supresion_verificada.py::test_residue_detects_rows_in_every_table_and_pending_stream_entries`<br>`tests/integration/test_supresion_aborta_recalculo.py::test_suppression_reaches_the_five_tables_and_every_user_key_of_every_version_and_module` | |
| CHK049 | [x] | `tests/integration/test_supresion_aborta_recalculo.py::test_suppression_reaches_the_five_tables_and_every_user_key_of_every_version_and_module` | |
| CHK050 | [x] | `tests/unit/test_architecture.py::test_detection_power`<br>`tests/unit/test_architecture.py::test_repository_respects_architecture`<br>`docs/runbook.md` | FR-068e: solo purga y supresión borran lo no recuperable |
| CHK051 | [x] | `tests/unit/test_config_loader.py::test_retention_must_exceed_all_three_windows`<br>`tests/integration/test_purga_senales.py::test_retention_that_does_not_exceed_every_window_refuses_to_start` | |
| CHK052 | [x] | `tests/integration/test_purga_senales.py::test_orphaned_permanent_exclusions_are_measured_without_threshold`<br>`tests/integration/test_alerts.py::test_orphaned_exclusions_have_no_alert`<br>`tests/integration/test_purga_senales.py::test_exclusion_survives_the_purge_of_its_origin_signal` | |
| CHK053 | [x] | `tests/integration/test_sync_idempotent.py::test_user_without_region_is_rejected_and_counted_separately`<br>`docs/contracts/required-fields.md` | El comportamiento está especificado y probado (rechazo, DEP-11); el backfill mismo depende de `api-general` |
| CHK054 | [x] | `tests/integration/test_sync_idempotent.py::test_user_without_region_is_rejected_and_counted_separately`<br>`tests/integration/test_migrations.py::test_user_ingest_constraints` | |
| CHK055 | [x] | `tests/unit/test_ponderacion_regional.py::test_factor_sweep_has_no_discontinuities`<br>`tests/unit/test_ponderacion_regional.py::test_small_region_is_completed_with_extraregional_neighbors` | |
| CHK056 | [x] | `tests/unit/test_config_loader.py::test_region_weight_factor_zero_is_representable`<br>`tests/unit/test_config_loader.py::test_v1_loads_with_decided_values` | |
| CHK057 | [x] | `tests/unit/test_ponderacion_regional.py::test_factor_one_is_rejected_by_the_loader_not_by_the_engine`<br>`tests/unit/test_config_loader.py::test_invalid_configurations_fail_naming_the_field` | |
| CHK058 | [x] | `tests/unit/test_ponderacion_regional.py::test_factor_zero_is_identical_to_no_segmentation`<br>`tests/unit/test_config_loader.py::test_v1_loads_with_decided_values` | |
| CHK059 | [x] | `specs/001-recomendaciones-precomputadas/spec.md` | Ítem de redacción: la condición de revisión está en FR-090a |
| CHK060 | [x] | `src/recomendaciones/config/engine_config/v1.yaml` | El comentario junto a `region_weight_factor` declara que 0 es el neutro |
| CHK061 | [x] | `tests/integration/test_trigger_recalculo.py::test_no_read_between_cause_and_invalidation_returns_the_old_result`<br>`tests/integration/test_event_signals.py::test_next_read_excludes_the_disliked_item_even_with_populated_filters` | |
| CHK062 | [x] | `tests/integration/test_supresion_aborta_recalculo.py::test_redis_is_cleared_before_postgres`<br>`tests/integration/test_exclusion_resolver.py::test_invalidates_filters_before_writing` | Una sola regla: Redis primero (FR-080c) |
| CHK063 | [x] | `tests/unit/test_settings.py::test_operational_parameters_have_no_default`<br>`tests/integration/test_trigger_recalculo.py::test_n_minus_one_signals_do_not_trigger_and_n_do` | |
| CHK064 | [x] | `tests/integration/test_trigger_recalculo.py::test_count_is_per_user_and_module`<br>`tests/integration/test_trigger_recalculo.py::test_count_restarts_after_recomputing_that_module` | |
| CHK065 | [x] | `specs/001-recomendaciones-precomputadas/spec.md`<br>`tests/contract/test_contract_gate.py::test_every_active_external_dependency_is_covered_by_the_gate` | |
| CHK066 | [x] | `docs/contracts/required-fields.md`<br>`tests/contract/test_required_fields_doc.py::test_every_dependency_and_contract_requirement_is_indexed` | |
| CHK067 | [x] | `tests/contract/test_contract_gate.py::test_dependency_is_declared_in_the_contract`<br>`tests/unit/test_declaracion_minimo.py::test_only_current_vocabulary_is_acceptable` | |
| CHK068 | [x] | `tests/contract/test_required_fields_doc.py::test_document_names_the_most_severe_dependency_and_the_source_of_truth` | |
| CHK069 | [x] | `tests/integration/test_event_signals.py::test_reused_identifier_with_other_content_is_a_contract_violation`<br>`tests/integration/test_sync_idempotent.py::test_reused_interaction_with_other_type_is_a_contract_violation` | |
| CHK070 | [x] | `tests/contract/test_required_fields_doc.py::test_every_dependency_and_contract_requirement_is_indexed`<br>`specs/001-recomendaciones-precomputadas/spec.md` | |
| CHK071 | [x] | `specs/001-recomendaciones-precomputadas/spec.md` | FR-070 designa solo el desempate; la supresión es FR-091…FR-095 y `FR-070a`…`e` quedan retirados |
| CHK072 | [x] | `specs/001-recomendaciones-precomputadas/spec.md` | SC-028…SC-031 cubren declaración, supresión, región e ingesta |
| CHK073 | [x] | `tests/integration/test_models_match_migrations.py::test_models_match_migration`<br>`tests/integration/test_migrations.py::test_upgrade_downgrade_upgrade_on_empty_database` | 18 tablas en esquema, modelo y documento |
| CHK074 | [x] | `tests/unit/test_config_loader.py::test_v1_loads_with_decided_values`<br>`specs/001-recomendaciones-precomputadas/plan.md` | |
| CHK075 | [x] | `tests/integration/test_recompute_requests.py::test_warmup_plus_worker_rebuild_every_entry`<br>`specs/001-recomendaciones-precomputadas/tasks.md` | Matiz de INV-2 en T003: se persisten los insumos, no el top-N |
| CHK076 | [x] | `specs/001-recomendaciones-precomputadas/tasks.md`<br>`tests/contract/test_rechazo_sin_declaracion.py::test_rejection_is_per_module` | T053–T055 |

## Invariantes transversales

| Invariante | Estado | Evidencia |
|---|---|---|
| INV-1 | [x] | `tests/unit/test_architecture.py::test_repository_respects_architecture`<br>`tests/integration/test_no_heavy_compute.py::test_normal_path_emits_zero_queries`<br>`tests/performance/test_read_latency.py::test_read_latency_is_independent_of_catalog_size_and_meets_sc001` |
| INV-2 | [x] | `tests/integration/test_recompute_requests.py::test_warmup_plus_worker_rebuild_every_entry`<br>`tests/integration/test_idempotency.py::test_losing_redis_does_not_break_idempotency` |
| INV-3 | [x] | `tests/invariants/test_pipeline_order.py::test_output_satisfies_age_exclusion_and_subset_simultaneously`<br>`tests/invariants/test_data_invariants.py::test_every_result_type_respects_age_and_exclusion`<br>`tools/mutation_postprocess.py` |
| INV-4 | [x] | `tests/unit/test_settings.py::test_only_one_database_connection_string`<br>`tests/integration/test_no_external_writes.py::test_only_get_requests_are_ever_sent` |

## Success Criteria

| SC | Estado | Evidencia |
|---|---|---|
| SC-001 | [x] | `tests/performance/test_read_latency.py::test_read_latency_is_independent_of_catalog_size_and_meets_sc001`<br>`docs/validation/performance-report.md` |
| SC-002 | [x] | `tests/integration/test_critical_scenarios.py::test_minor_receives_zero_unsuitable_content_in_all_five_result_types`<br>`tests/invariants/test_age_filter.py::test_no_minor_ever_receives_adult_content` |
| SC-003 | [x] | `tests/invariants/test_exclusion.py::test_no_excluded_item_survives`<br>`tests/integration/test_critical_scenarios.py::test_strict_exclusion_zero_excluded_items_in_any_response` |
| SC-004 | [x] | `tests/integration/test_cache_repository.py::test_round_trip_is_exact_and_carries_config_version`<br>`tests/contract/test_read_endpoint.py::test_response_validates_against_the_published_contract` |
| SC-005 | [x] | `tests/integration/test_propagation.py::test_reprocessing_produces_identical_top_n` |
| SC-006 | [x] | `tests/integration/test_sync_idempotent.py::test_double_execution_leaves_identical_state` |
| SC-007 | [x] | `tests/integration/test_invalid_payload.py::test_interleaved_invalid_messages_never_block_valid_ones`<br>`tests/integration/test_consumer.py::test_invalid_payloads_are_rejected_with_cause` |
| SC-008 | [x] | `tests/integration/test_recompute_requests.py::test_warmup_plus_worker_rebuild_every_entry` |
| SC-009 | [x] | `tests/integration/test_no_heavy_compute.py::test_normal_path_emits_zero_queries`<br>`tests/unit/test_architecture.py::test_repository_respects_architecture` |
| SC-010 | [x] | `tests/integration/test_critical_scenarios.py::test_cross_cold_start_movie_activity_and_game_declaration_produce_non_trivial_games`<br>`tests/integration/test_propagation.py::test_cold_start_cross_module_gives_non_trivial_games` |
| SC-011 | [x] | `tests/unit/test_mmr.py::test_every_prefix_respects_cluster_cap_unless_relaxed` |
| SC-012 | [x] | `tests/unit/test_architecture.py::test_repository_respects_architecture`<br>`tests/contract/test_auth.py::test_network_restriction_is_declared_and_auditable` |
| SC-013 | [x] | `tests/contract/test_contract_gate.py::test_every_exposed_operation_is_exercised_by_this_gate`<br>`tests/contract/test_contract_gate.py::test_every_read_response_validates_against_the_published_openapi` |
| SC-014 | [x] | `tests/integration/test_freshness.py::test_freshness_is_queryable_without_entering_the_db_from_any_long_running_process` |
| SC-015 | [x] | `tests/integration/test_cache_miss.py::test_fifty_concurrent_misses_produce_one_request` |
| SC-016 | [x] | `tests/integration/test_propagation.py::test_shared_tag_recomputes_both_modules_and_logs_the_reason` |
| SC-017 | [x] | `tests/integration/test_propagation.py::test_shared_tag_recomputes_both_modules_and_logs_the_reason`<br>`tests/integration/test_propagation.py::test_no_shared_tag_recomputes_only_its_module` |
| SC-018 | [x] | `tests/invariants/test_exclusion.py::test_every_signal_kind_excludes` |
| SC-019 | [x] | `tests/integration/test_critical_scenarios.py::test_dislike_measurably_lowers_items_sharing_its_tags_and_a_later_like_reverts_it` |
| SC-020 | [x] | `tests/integration/test_critical_scenarios.py::test_dislike_measurably_lowers_items_sharing_its_tags_and_a_later_like_reverts_it`<br>`tests/unit/test_profile.py::test_later_like_reverts_earlier_dislike` |
| SC-021 | [x] | `tests/unit/test_scoring.py::test_reproducible_in_100_runs_with_shuffled_input` |
| SC-022 | [x] | `tests/unit/test_cache_keys.py::test_config_version_is_in_both_fresh_and_stale_keys`<br>`tests/integration/test_cache_miss.py::test_previous_version_with_same_age_catalog_is_served_with_its_label_without_signal` |
| SC-023 | [x] | `tests/integration/test_health.py::test_health_exposes_active_config_version_without_secrets` |
| SC-024 | [x] | `tests/integration/test_critical_scenarios.py::test_newly_declared_user_gets_non_personalized_fallback_then_personalized_after_recompute` |
| SC-025 | [x] | `tests/integration/test_fallback_batch.py::test_diversity_beats_the_undiversified_ranking` |
| SC-026 | [x] | `tests/invariants/test_fallback_filtering.py::test_minor_never_receives_adult_content_via_fallback` |
| SC-027 | [x] | `tests/integration/test_cache_miss.py::test_state_table`<br>`tests/contract/test_estado_obsoleto.py::test_fallback_with_stale_signals_it` |
| SC-028 | [x] | `tests/integration/test_sync_idempotent.py::test_user_without_region_is_rejected_and_counted_separately`<br>`tests/integration/test_migrations.py::test_user_ingest_constraints` |
| SC-029 | [x] | `tests/contract/test_declaracion_endpoint.py::test_valid_declaration_is_confirmed_synchronously`<br>`tests/contract/test_declaracion_endpoint.py::test_second_declaration_is_409_and_leaves_rows_intact`<br>`tests/contract/test_rechazo_sin_declaracion.py::test_rejection_is_per_module` |
| SC-030 | [x] | `tests/integration/test_supresion_aborta_recalculo.py::test_suppression_reaches_the_five_tables_and_every_user_key_of_every_version_and_module`<br>`tests/integration/test_supresion_verificada.py::test_persistent_residue_in_redis_ends_in_visible_failure_and_increments_the_alert_metric`<br>`tests/integration/test_sync_idempotent.py::test_suppressed_user_is_never_rematerialized` |
| SC-031 | [x] | `tests/unit/test_ponderacion_regional.py::test_factor_zero_is_identical_to_no_segmentation`<br>`tests/unit/test_ponderacion_regional.py::test_insufficient_neighbors_is_recorded` |

## Deuda del prototipo

| Deuda | Estado | Tarea | Evidencia |
|---|---|---|---|
| Caché en memoria → Redis persistente | [x] | T018, T022 | `tests/integration/test_redis.py::test_effective_ttls_and_filters_expire_before_reco`<br>`tests/integration/test_recompute_requests.py::test_warmup_plus_worker_rebuild_every_entry` |
| `ExclusionSet` con interfaz pública | [x] | T014 | `tests/unit/test_exclusion_api.py::test_no_caller_reaches_into_private_attributes`<br>`tests/unit/test_exclusion_api.py::test_public_query_interface` |
| Una reacción no deja el top-N desactualizado en silencio | [x] | T064, T027, T060 | `tests/integration/test_event_signals.py::test_next_read_excludes_the_disliked_item_even_with_populated_filters`<br>`tests/integration/test_trigger_recalculo.py::test_n_minus_one_signals_do_not_trigger_and_n_do` |
| Constantes del motor y mapeo de `age_rating` externalizados | [x] | T004, T013 | `tests/unit/test_scoring.py::test_module_has_no_numeric_constants`<br>`tests/invariants/test_age_filter.py::test_no_hardcoded_rating_dict_in_engine`<br>`tests/unit/test_config_loader.py::test_loader_module_has_no_engine_constants` |

## Estado de la Definition of Done

Lo que no depende de este repositorio queda `[ ]` con su motivo. No se marca por anticipado.

| Ítem de la DoD | Estado | Evidencia o motivo |
|---|---|---|
| Invariantes bloqueantes (edad, exclusión, MMR, arquitectura, cero queries, 503, recuperación, cero bases ajenas) | [x] | `tests/invariants/test_data_invariants.py::test_every_result_type_respects_age_and_exclusion`<br>`tests/unit/test_mmr.py::test_output_is_subset_of_input`<br>`tests/unit/test_architecture.py::test_repository_respects_architecture`<br>`tests/integration/test_no_heavy_compute.py::test_normal_path_emits_zero_queries`<br>`tests/integration/test_redis_down.py::test_redis_down_raises_503_error_and_never_reaches_postgres`<br>`tests/integration/test_recompute_requests.py::test_warmup_plus_worker_rebuild_every_entry`<br>`tests/unit/test_settings.py::test_only_one_database_connection_string` |
| US1…US7 y los cinco `result_type` alcanzables | [x] | `tests/integration/test_phase1_end_to_end.py::test_declared_user_gets_a_materialized_top_n_end_to_end`<br>`tests/contract/test_contract_gate.py::test_every_read_response_validates_against_the_published_openapi` |
| Toda tarea `[TDD]` test-first | [x] | Historial de la rama: cada tarea de producción tiene su commit `(rojo)` antes del `(verde)`. T056 es la excepción declarada (la implementación de T008 ya la satisfacía; poder de detección por mutación) |
| Test de mutación en verde | [x] | `tools/mutation_postprocess.py` |
| `contracts/` materializado | [x] | `specs/001-recomendaciones-precomputadas/contracts/README.md` |
| Contract tests como gate bloqueante | [ ] | El gate existe (`.github/workflows/ci.yml`); que bloquee el merge exige marcar `gates` como required check en la protección de rama (acción humana en GitHub) |
| Casos críticos en verde | [x] | `tests/integration/test_critical_scenarios.py` |
| Configuración trazable, `config_version` en ambas claves, `v1.yaml` valida | [x] | `tests/unit/test_cache_keys.py::test_config_version_is_in_both_fresh_and_stale_keys`<br>`tests/unit/test_config_loader.py::test_v1_loads_with_decided_values` |
| SC-001 verificado | [x] | `docs/validation/performance-report.md` |
| Métricas de observabilidad declaradas y emitidas | [x] | `tests/integration/test_metrics.py::test_registry_declares_every_required_metric`<br>`tests/integration/test_metrics.py::test_worker_emits_dlq_and_queue_depth` |
| Alertas probadas induciendo su condición, umbrales justificados por escrito | [x] | `tests/integration/test_alerts.py::test_promtool_every_alert_fires_on_its_condition_and_clears`<br>`tests/integration/test_alerts.py::test_every_alert_has_justified_threshold_owner_and_runbook_entry` — la **revisión humana** de las justificaciones (T042) sigue pendiente |
| Ejecución de prueba del runbook registrada | [ ] | `docs/validation/runbook-dry-run.md` es la plantilla: la ejecución la hace alguien ajeno a la feature (T046) |
| Documento de campos requeridos publicado | [ ] | Redactado (`docs/contracts/required-fields.md`); publicarlo en `api-general` es acción humana (T049) |
| Ningún FR carece de tarea | [ ] | No se recorrieron los 167 FR contra `tasks.md` en esta implementación; queda para la revisión de cierre |
| Constitución v1.1.1 aprobada por PR | [ ] | Pendiente de aprobación (gobernanza de la constitución, RD-98) |
| `event_redelivery_window_hours` copiado del broker real | [ ] | `.env.example` lleva un valor provisional; el real lo fija la configuración de `notificaciones` |
| Evento de baja publicado por `api-general` | [ ] | Schema propuesto en `specs/001-recomendaciones-precomputadas/contracts/usuario-eliminado.schema.json`; la publicación es de `api-general` (DEP-12) |
