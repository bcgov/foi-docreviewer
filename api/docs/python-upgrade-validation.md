# Reviewer API Python 3.13 upgrade validation

Status: development candidate verified; DEV smoke test and normal security/release review pending. No commit, PR publication, image publication or deployment has been performed.

## Candidate and provenance

- Branch/worktree: `feat/reviewer-api-python313`, `.worktrees/reviewer-api-python313`.
- Starting source SHA: `3974e1d8ff69076defb753da19279164646568f4`; changes remain uncommitted.
- Runtime-source/dependency diff SHA-256: `ced369cc35e9913bedaf077c9cbc285a019bff5bf8b36e463383889f0562c120`.
- Tested image: `sha256:4fa00ce0e34ba5d6477e6b8bcfd23570a155410d4923671d3c69920b79cb01e0`.
- Python 3.13.17 Trixie base is pinned by index digest `sha256:d5a186865324088bd10d1671801b42297a8fe3f8059143fb22b2e2b776ffa6dd`.
- Baseline: frozen current API source over the existing local `docreviewerapiimage` dependency layers (Python 3.10.8). Captured SBC commit: `67bb5e775370970aa7b674b1185d195a51fd7eeb`. This is not deployed runtime/image provenance.
- CI reconstructs its PR-base source with the captured SBC commit when the legacy editable dependency exists. Both UTF-16 legacy requirements and UTF-8 upgraded locks are supported. This reconstruction builds successfully locally; it is recorded separately from the captured image.

## Changes

Reviewer has its own direct inputs and full Linux/Python 3.13 hash-locked dependency graph. Only actively imported packages and required transitive packages remain; one psycopg2 distribution retains the existing driver API. Flask/ORM/auth/serialization dependencies were resolved together. Production and local Dockerfiles use the same runtime and lock.

SQLAlchemy compatibility changes preserve selected fields and queries through positional `case` arguments, named result mappings and explicit uncapped annotation pagination. Model serialization preserves the former Marshmallow rc7 UTC timestamp format, including naive `+00:00`, aware offset normalization and nulls. No migration revision or schema change was added.

Flask-Script is replaced by a supported Flask CLI retaining `python manage.py db upgrade|current|heads` and `list_routes`. Migration-before-server behavior remains, and `exec` forwards termination to the server. The unused removed `distutils` import is removed. Local tracing preserves the existing Jaeger/OpenTracing decorator, service name, propagation, responses and error behavior without SBC/Flask-OpenTracing.

## Verification results

- Focused gate: **74 passed, one strict expected failure**.
- Full candidate: **76 passed, five legacy failures, one strict expected failure**.
- Full baseline: **65 passed, seven failures, nine errors, one strict expected failure**.
- **Zero previously passing baseline tests regressed.** The [complete comparison](python-upgrade-test-comparison.md) names every case and retained failure.
- Production/local image builds and dependency consistency checks passed; candidate reports Python 3.13.17.
- Real disposable PostgreSQL tests cover annotation insert/update/type/XML, mapping fields, replacement/deletion/layers, pagination above 100 records, commit/rollback/savepoints and cleanup. A nonempty page-flag REST read checks exact flags and date/null representation.
- Real signed identity checks cover valid/denied groups, expired/wrong-signature/issuer/audience, malformed/missing tokens and forged HS256 using a DER public key. Normal JWT initialization is exercised by the real entrypoint in production mode against a synthetic JWKS peer.
- Both real Redis producers preserve stream keys, payload bytes, decoded IDs and failure results. Redline handoff verifies job-before-publish ordering and decoded message fields with a synthetic job-write boundary.
- The registered authenticated S3 URL route downloads exact uploaded bytes/content type over TLS. Synthetic credentials are enforced by the disposable storage peer; SigV4 fields and rejection of a tampered signature are checked. Account/mapper lookups use synthetic boundary fixtures, not deployed storage configuration.
- Baseline-to-candidate migration startup leaves canonical schemas and Alembic heads identical. Candidate-created annotations and Redis events remain readable by the old image in the disposable rollback rehearsal.
- Actual migration-failure/startup/probes/SIGTERM, tracing return/error/parent cleanup, shell syntax, actionlint and diff whitespace checks passed.

Use only the isolated runner; bare pytest is intentionally rejected without its endpoint configuration. The guard runs before API imports/migrations, validates both DB/Redis configurations and import-time format/JWKS/storage hosts, and blocks unregistered HTTP requests. Peers use an internal network, fake credentials, temporary data and no shared volumes/ports. Each run owns its Compose project and TLS directory.

```bash
# From repository/worktree root; preserve a captured baseline image/source first.
bash api/scripts/prepare-upgrade-baseline.sh <pre-upgrade-source-sha>
bash api/scripts/verify-python-upgrade.sh baseline
bash api/scripts/verify-python-upgrade.sh candidate @tests/python-upgrade-focused.txt
UPGRADE_EVIDENCE_DIR=/tmp/reviewer-api-python-upgrade/full-candidate bash api/scripts/verify-python-upgrade.sh candidate
python3 api/scripts/compare-upgrade-results.py /tmp/reviewer-api-python-upgrade/baseline/tests.xml /tmp/reviewer-api-python-upgrade/full-candidate/tests.xml
```

`prepare-upgrade-baseline.sh` refuses to overwrite an existing snapshot. Supply `UPGRADE_BASELINE_IMAGE` and `UPGRADE_BASELINE_SOURCE` to reuse a captured alternative; do not rebuild the baseline from candidate source. The migration gate fails if baseline evidence is missing. `.github/workflows/reviewer-api-python-upgrade.yml` uses these checks without deployment credentials and rejects regressions even though known full-suite failures remain visible.

## Security findings and limits

Grype scanned image `sha256:1bf10eb0283580ffe9800054143c2b6f3a145c6ed2b46b5f2fb4f797152bdb8c`. Its first 11 of 12 layers match the tested image; all OS, native and installed-dependency layers are identical. The final application/test-source layer differs following compatibility/test edits. Evidence: `/tmp/reviewer-api-python-upgrade/grype-reviewed.json` and `scan-layer-proof.json`.

The available High/Critical fix for `libunbound8` is installed as `1.26.2-0+deb13u1` in both Dockerfiles. The subsequent scan reports **zero High/Critical matches with published fixes**, while retaining 116 unique High/Critical advisory IDs, including inherited OS/native findings and the Python advisories below. This is not vulnerability clearance; normal applicability/acceptance review remains required.

- [python-jose DER/HMAC confusion advisory](https://github.com/advisories/GHSA-3qf3-8w2g-rqmx) has no patched release. Reviewer uses jose for unverified claim parsing, with cryptographic REST verification through flask-jwt-oidc/PyJWT. The tested RS256 configuration rejects the forged HMAC token. Confirm the deployed algorithm configuration and active call paths in release review.
- [ECDSA timing advisory](https://github.com/advisories/GHSA-wj6h-64fc-37mp) has no patched release. No application ECDSA signing/key generation was found; this is a source applicability assessment, not blanket clearance of the installed library.

Some invalid-token responses retain the baseline framework's 500/error behavior instead of introducing a new 401 contract. They do not reach protected handlers in the signed-token checks. The older `Document.getdocuments` helper has a boolean-query defect and the five stale legacy tests remain explicitly visible. Investigation found no current API caller of that older helper; the active document-list route uses the DocumentMaster-based service path. See [the failure investigation](python-upgrade-failure-investigation.md) for root causes and reachability.

## DEV handoff and release boundary

Before promotion record the actual deployed image/configuration reference, previous immutable rollback image, tester and candidate source/image. A local reconstructed image cannot establish those production facts.

- Confirm successful migration startup, runtime and `/api/healthz`/`/api/readyz`.
- Check login, permitted/denied groups and actual identity-provider settings.
- Open representative document lists/state through the active document service; the older model-helper expected failure does not establish failure of this endpoint.
- Save/reload annotation XML/type, layers and page flags; inspect pagination and timestamp/null payloads.
- Exercise redline/final-package handoff with unchanged downstream services.
- Upload/download synthetic records through actual signed storage URLs; compare bytes and content type.
- Check Redis handoff, application/DB/storage/auth logs and resource/probe behavior against the deployed baseline.
- Record results and affected synthetic IDs against the tested image. TEST/PROD promotion, security acceptance, operational rollback rehearsal and owner acceptance remain under Task 2 and the existing release process.

Image reversion cannot undo completed DB, storage or Redis effects. Do not downgrade schemas, reset streams or replay whole queues. Keep effects traceable and use existing recovery procedures.

## Review decisions

A fresh independent review found and the implementation fixed document mapping and future UTF-8 baseline CI defects, added the missing page-flag/date check, and strengthened signature verification. Baseline comparison additionally caught and fixed datetime serialization drift. Regression cases were observed failing before their fixes; final suites retain the five known legacy failures.

The preserved decisions are: keep worktree/ledger until changes are committed; distinguish captured local, reconstructed CI and deployed baselines; reuse Task 1 code without asserting stale local dev refs prove its merge; adapt fixture paths/session classes without changing business expectations; preserve the baseline document-list/token-error behavior; validate the actual environment-owned storage host and synthetic account data; keep repeated production app initialization outside scope; and require environment/security acceptance before release. The cost of these limits is that local checks cannot establish deployed/load compatibility or repair unrelated baseline defects. No deferred review polish findings remain.
