# Reviewer API failing-test investigation

Investigated 2026-10-26 in `feat/reviewer-api-python313`; application code and the five legacy test files/cases were not changed during investigation.

## Confirmed reproduction

The same targeted selection was run against the captured Python 3.10.8 baseline and Python 3.13.17 candidate, with `--runxfail` to expose the expected failure. Each run reported **six failures and one pass**. The five ordinary failures and the query exception match across runtimes. These observations do not identify an upgrade-caused regression.

Evidence is separate from the prior full-suite results:

- `/tmp/reviewer-api-python-upgrade/investigation-baseline/{tests.xml,checks.log}`
- `/tmp/reviewer-api-python-upgrade/investigation-candidate/{tests.xml,checks.log}`
- `/tmp/reviewer-api-python-upgrade/investigation-confirmed-probes/{tests.xml,checks.log}`

Both temporary confirmation probes passed; their source is retained as `investigation-confirmed-probes/probe.py` beside the JUnit/log evidence. They were removed from the service checkout after investigation.

The reproduction command, with its phase-specific evidence directory, was:

```bash
UPGRADE_EVIDENCE_DIR=/tmp/reviewer-api-python-upgrade/investigation-candidate \
  bash api/scripts/verify-python-upgrade.sh candidate \
  tests/restapi/test_redaction_api.py \
  tests/services/test_redaction_services.py \
  tests/services/test_python_upgrade_annotations.py::test_document_list_does_not_swallow_baseline_boolean_error \
  --runxfail
```

Use `baseline` and its evidence directory for the corresponding old-runtime run. The harness uses disposable peers; no deployment endpoints or shared accounts were used.

## Root causes

| Case | Immediate cause | What needs to change |
| --- | --- | --- |
| REST `test_document_list` | Its authentication factory posts to an unregistered Keycloak token endpoint. The fake environment has no real username/password, and the harness rejects the HTTP call before the document handler runs. | Use the existing synthetic signed identity; seed documents and register exact synthetic Request Management API/division responses required by the active route. |
| REST `test_annotation_create` | Same token lookup blocker. After that blocker is removed, its `/api/annotation/1/1/1/test123` URL is absent from the current route map. | Exercise the current `POST /api/annotation` route with valid XML metadata, a redaction layer and seeded document records; assert the saved record as well as status 201. |
| Service `test_get_documents` | Calls `redactionservice().getdocuments`, which does not exist. | Exercise `documentservice().getdocuments(requestid, bcgovcode)`. It returns a division-list/document-list pair, so replacing the method name and retaining `len(result) > 0` would be a weak assertion on the tuple itself. Check expected document IDs/content. |
| Service `test_save_annotation` | Passes six positional arguments to a method now accepting `(annotationschema, userinfo)`; it also expects one result instead of `(pageflagresponse, result)`. | Supply the current schema, seed the document/layer, destructure the result and verify persisted annotation content/version/type. |
| Service `test_deactive_annotation` | Positional arguments bind to the wrong current parameters: a string becomes `annotationschema`, integers become `userinfo`/`requestid`, and userinfo becomes `redactionlayerid`. The method then indexes that string as a dictionary. | Supply `(annotationschema, userinfo, requestid, redactionlayerid)`, with annotation objects under `annotations`, and verify the targeted record is deactivated. |
| Expected failure: `test_document_list_does_not_swallow_baseline_boolean_error` | The older `Document.getdocuments` helper evaluates Python `and`/`or` on SQLAlchemy expressions while building its joins/filters. `.contains(...) and ...` raises `TypeError: Boolean value of this clause is not defined`, before SQL executes. | Establish whether this older helper must remain supported; repair its SQL boolean composition and test filtering semantics, or separately retire unused code/coverage after checking ownership. |

## Additional confirmed blockers

A temporary diagnostic used a valid synthetic signed token and confirmed that the old annotation URL returns **404**. The current creation route is `POST /api/annotation`; the two-segment annotation route is a deactivation operation, not the old document/version/page/name creation contract.

The legacy XFDF fixture contains only `trn-annot-preview` in its custom-data JSON. Direct parsing raises **`KeyError: originalPageNo`**. The current parser also accesses `docid` and accepts `docversion` (defaulting to 1). Merely correcting the method signature or URL will expose this fixture defect next. The underline annotation itself is accepted by the parser; missing metadata is the issue.

The legacy tests assume document/request IDs of 1 and prior annotation state without creating those records. Migrations establish lookup/schema data; they do not make those business-record assumptions reliable. Each rewritten test needs independent synthetic fixtures and persistence assertions.

## Query-bug reachability correction

The query error is a real defect in the older model helper, but **no current application caller of `Document.getdocuments` was found in this checkout**. The only direct caller found is the upgrade characterization test.

The active `GET /api/document/<requestid>` route calls `documentservice.getdocuments(requestid, bcgovcode)`. That service calls `getdedupestatus`, which reads `DocumentMaster.getdocumentmaster`; it does not call the failing older `Document.getdocuments` implementation. The related older `Document.getdocumentsdedupestatus` method likewise has no identified current caller.

Consequently, the expected failure does not establish that the current document-list endpoint is broken. Its previously documented description as a general document-list limitation was too broad. Actual environment validation of the active endpoint is still required.

## Recommended scope

Modernize the five stale tests using current public contracts, shared synthetic identity and independently seeded records. Keep endpoint isolation enabled and retain business assertions; do not restore obsolete service signatures or permit shared-account token calls just to get a green suite.

Treat the old query helper separately from these test repairs. It dates to the pre-upgrade source (the affected join/filter code is present in 2023 history). Before changing its SQL semantics, decide whether it is still a supported path. No application fix or test rewrite was made as part of this investigation.
