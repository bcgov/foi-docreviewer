# Reviewer API upgrade test comparison

The same isolated harness runs frozen pre-upgrade application source and the Python 3.13 candidate. Baseline source is `3974e1d8ff69076defb753da19279164646568f4`; dependency layers came from the existing local Python 3.10.8 image, not a verified deployed image.

| Run | Pass | Fail | Error | Expected failure |
| --- | ---: | ---: | ---: | ---: |
| baseline | 65 | 7 | 9 | 1 |
| candidate | 76 | 5 | 0 | 1 |

**No previously passing baseline test fails, skips or disappears in the candidate.** Both runs contain 82 cases. The focused gate separately passes 74 cases with one strict expected failure.

Five unchanged legacy cases still fail: two REST tests try to obtain shared-account tokens (the harness rejects those requests); three service tests call obsolete methods/signatures. They remain in the full run and are not asserted green.

The strict expected failure is `test_document_list_does_not_swallow_baseline_boolean_error`: existing `Documents.getdocuments` uses Python boolean operators on SQL expressions. It remains visible pending separate ownership/repair review. Investigation found no current application caller of this older helper; the active document-list route uses a different service path. See [the failure investigation](python-upgrade-failure-investigation.md). No business expectation was rewritten to bless the exception.

Upgrade-only tracing checks intentionally block SBC imports, so the old implementation fails those checks. Other baseline startup failures establish the old `list_routes` converter bug and the shell entrypoint leaving a server after SIGTERM. The UTC date checks pass against the baseline and candidate, including aware offsets and nulls.

Raw JUnit, runtime inventories and logs are under `/tmp/reviewer-api-python-upgrade/{baseline,full-candidate}`. CI uploads equivalent synthetic evidence. Reconstructed CI baseline dependency resolution is distinct from the captured local layers; its source/SBC revision and image identity are recorded.

| Test | Baseline | Candidate |
| --- | --- | --- |
| `tests.restapi.test_foimasterdata_api::test_ping` | pass | pass |
| `tests.restapi.test_python_upgrade_auth::test_expired_wrong_issuer_or_wrong_audience_is_rejected[claims0]` | pass | pass |
| `tests.restapi.test_python_upgrade_auth::test_expired_wrong_issuer_or_wrong_audience_is_rejected[claims1]` | pass | pass |
| `tests.restapi.test_python_upgrade_auth::test_expired_wrong_issuer_or_wrong_audience_is_rejected[claims2]` | pass | pass |
| `tests.restapi.test_python_upgrade_auth::test_hmac_token_signed_with_public_key_is_rejected` | pass | pass |
| `tests.restapi.test_python_upgrade_auth::test_malformed_token_is_rejected` | pass | pass |
| `tests.restapi.test_python_upgrade_auth::test_missing_token_is_rejected` | pass | pass |
| `tests.restapi.test_python_upgrade_auth::test_valid_signed_token_and_permitted_role` | pass | pass |
| `tests.restapi.test_python_upgrade_auth::test_valid_token_without_permitted_role_is_denied` | pass | pass |
| `tests.restapi.test_python_upgrade_auth::test_wrong_signature_is_rejected` | pass | pass |
| `tests.restapi.test_python_upgrade_contracts::test_annotation_empty_request_preserves_json_shape` | pass | pass |
| `tests.restapi.test_python_upgrade_contracts::test_layer_response_preserves_json_shape_and_counts` | pass | pass |
| `tests.restapi.test_python_upgrade_contracts::test_registered_routes_reject_denied_group` | pass | pass |
| `tests.restapi.test_python_upgrade_storage::test_generated_signed_url_downloads_exact_bytes` | pass | pass |
| `tests.restapi.test_python_upgrade_storage::test_missing_document_preserves_error_response` | pass | pass |
| `tests.restapi.test_redaction_api::test_annotation_create` | failure | failure |
| `tests.restapi.test_redaction_api::test_document_list` | failure | failure |
| `tests.restapi.test_redaction_api::test_ping` | pass | pass |
| `tests.services.test_python_upgrade_annotations::test_annotation_upsert_preserves_xml_and_type` | pass | pass |
| `tests.services.test_python_upgrade_annotations::test_document_case_query_preserves_selected_path` | pass | pass |
| `tests.services.test_python_upgrade_annotations::test_document_list_does_not_swallow_baseline_boolean_error` | skipped | skipped |
| `tests.services.test_python_upgrade_annotations::test_inferred_model_dates_preserve_baseline_utc_format[-8-2026-01-02T11:04:05+00:00]` | pass | pass |
| `tests.services.test_python_upgrade_annotations::test_inferred_model_dates_preserve_baseline_utc_format[None-2026-01-02T03:04:05+00:00]` | pass | pass |
| `tests.services.test_python_upgrade_annotations::test_layer_mapping_and_deleted_replacement_filters` | pass | pass |
| `tests.services.test_python_upgrade_annotations::test_nonempty_document_master_retains_mapping_fields` | pass | pass |
| `tests.services.test_python_upgrade_annotations::test_nonempty_pageflag_rest_and_date_null_serialization` | pass | pass |
| `tests.services.test_python_upgrade_annotations::test_pagination_preserves_requested_size_and_meta` | pass | pass |
| `tests.services.test_python_upgrade_annotations::test_raw_annotation_read_preserves_named_fields` | pass | pass |
| `tests.services.test_python_upgrade_peer_contracts::test_redline_handoff_keeps_payload_and_job_before_publish` | pass | pass |
| `tests.services.test_python_upgrade_redis::test_producers_preserve_payload_and_return_decoded_id[document]` | pass | pass |
| `tests.services.test_python_upgrade_redis::test_producers_preserve_payload_and_return_decoded_id[zipper]` | pass | pass |
| `tests.services.test_python_upgrade_redis::test_redis_failure_preserves_result[documentserviceproducerservice]` | pass | pass |
| `tests.services.test_python_upgrade_redis::test_redis_failure_preserves_result[eventqueueproducerservice]` | pass | pass |
| `tests.services.test_python_upgrade_transactions::test_commit_rollback_and_savepoint_isolation` | pass | pass |
| `tests.services.test_python_upgrade_transactions::test_session_cleanup_after_query_failure` | pass | pass |
| `tests.services.test_redaction_services::test_deactive_annotation` | failure | failure |
| `tests.services.test_redaction_services::test_get_documents` | failure | failure |
| `tests.services.test_redaction_services::test_save_annotation` | failure | failure |
| `tests.test_baseline_preparation::test_baseline_requirements_support_legacy_and_upgraded_encoding[utf-16]` | pass | pass |
| `tests.test_baseline_preparation::test_baseline_requirements_support_legacy_and_upgraded_encoding[utf-8]` | pass | pass |
| `tests.test_python_upgrade_startup::test_actual_entrypoint_serves_and_terminates_cleanly` | failure | pass |
| `tests.test_python_upgrade_startup::test_existing_probes_preserve_payloads` | pass | pass |
| `tests.test_python_upgrade_startup::test_list_routes_retains_probe_routes` | failure | pass |
| `tests.test_python_upgrade_startup::test_migration_cli_exposes_commands` | pass | pass |
| `tests.test_python_upgrade_startup::test_migration_failure_prevents_server` | pass | pass |
| `tests.test_python_upgrade_tracing::test_bad_parent_header_starts_a_new_span` | error | pass |
| `tests.test_python_upgrade_tracing::test_handler_exception_is_reraised_and_span_is_finished` | error | pass |
| `tests.test_python_upgrade_tracing::test_http_exception_preserves_status_and_closes_span` | error | pass |
| `tests.test_python_upgrade_tracing::test_traced_handler_preserves_return_value_and_records_http_status[result0-200]` | error | pass |
| `tests.test_python_upgrade_tracing::test_traced_handler_preserves_return_value_and_records_http_status[result1-201]` | error | pass |
| `tests.test_python_upgrade_tracing::test_traced_handler_preserves_return_value_and_records_http_status[result2-202]` | error | pass |
| `tests.test_python_upgrade_tracing::test_traced_handler_preserves_return_value_and_records_http_status[result3-403]` | error | pass |
| `tests.test_python_upgrade_tracing::test_traced_route_preserves_response_and_parent_context` | error | pass |
| `tests.test_python_upgrade_tracing::test_tracer_initializes_once_without_sbc_or_flask_opentracing` | error | pass |
| `tests.test_test_environment::test_complete_fake_configuration_is_accepted` | pass | pass |
| `tests.test_test_environment::test_endpoint_overrides_are_rejected[DATABASE_HOST-shared-db]` | pass | pass |
| `tests.test_test_environment::test_endpoint_overrides_are_rejected[DATABASE_NAME-production]` | pass | pass |
| `tests.test_test_environment::test_endpoint_overrides_are_rejected[DATABASE_TEST_HOST-shared-db]` | pass | pass |
| `tests.test_test_environment::test_endpoint_overrides_are_rejected[DATABASE_TEST_URL-postgresql://postgres:test@shared:5432/production]` | pass | pass |
| `tests.test_test_environment::test_endpoint_overrides_are_rejected[DOCUMENTSERVICE_REDIS_HOST-shared]` | pass | pass |
| `tests.test_test_environment::test_endpoint_overrides_are_rejected[FLASK_ENV-production]` | pass | pass |
| `tests.test_test_environment::test_endpoint_overrides_are_rejected[FOI_RECORD_FORMATS-https://shared/formats]` | pass | pass |
| `tests.test_test_environment::test_endpoint_overrides_are_rejected[OSS_S3_HOST-real-storage.example]` | pass | pass |
| `tests.test_test_environment::test_endpoint_overrides_are_rejected[PYTHON_DOTENV_DISABLED-0]` | pass | pass |
| `tests.test_test_environment::test_endpoint_overrides_are_rejected[ZIPPER_REDIS_HOST-shared]` | pass | pass |
| `tests.test_test_environment::test_missing_isolation_is_rejected` | pass | pass |
| `tests.test_upgrade_result_comparison::test_previously_passing_case_must_still_pass[-1]` | pass | pass |
| `tests.test_upgrade_result_comparison::test_previously_passing_case_must_still_pass[<testcase classname='suite' name='ok'/>-0]` | pass | pass |
| `tests.test_upgrade_result_comparison::test_previously_passing_case_must_still_pass[<testcase classname='suite' name='ok'><failure/></testcase>-1]` | pass | pass |
| `tests.test_upgrade_result_comparison::test_previously_passing_case_must_still_pass[<testcase classname='suite' name='ok'><skipped/></testcase>-1]` | pass | pass |
| `tests.unit.test_annotation_pagination_session::test_get_request_annotations_pagination_closes_session_after_paginating` | pass | pass |
| `tests.unit.test_annotation_pagination_session::test_get_request_annotations_pagination_closes_session_when_paginate_fails` | pass | pass |
| `tests.unit.test_annotation_pagination_session::test_getrequestannotationspagination_formats_model_result` | pass | pass |
| `tests.unit.test_annotation_type::test_bulk_annotation_values_include_annotation_type` | pass | pass |
| `tests.unit.test_annotation_type::test_get_annotation_type_returns_none_for_empty_or_invalid_xml` | pass | pass |
| `tests.unit.test_annotation_type::test_get_annotation_type_returns_root_tag_name` | pass | pass |
| `tests.unit.test_annotation_type::test_getredactedsectionsbyrequest_prefilters_by_annotation_type` | pass | pass |
| `tests.unit.test_annotation_type::test_getredactionsbydocumentpages_filters_by_annotation_type` | pass | pass |
| `tests.unit.test_annotation_type::test_getredactionsbypage_filters_by_annotation_type` | pass | pass |
| `tests.unit.test_annotation_type::test_new_annotation_values_include_annotation_type` | pass | pass |
| `tests.unit.test_annotation_type::test_update_annotation_values_include_annotation_type` | pass | pass |
| `tests.unit.test_compressionjob_workload_migration::test_compressionjob_workload_migration_orders_schema_changes` | pass | pass |
