# ZippingServices

Build both Dockerfiles on standard CPython 3.13 / Debian 13 Trixie. The shipped
entrypoint runs as `app_user`: `python __main__.py $`. No production Python source,
message keys, schema, stream settings or credentials changed for FOIMOD-5495.

## Dependencies

Requirements are now UTF-8, with one source-built PostgreSQL distribution.
Both images install `gcc`/`libpq-dev`; neither pre-installs an unpinned driver.

| Pin | Demonstrated reason |
| --- | --- |
| psycopg2 2.9.5 → 2.9.10 | Original 3.13 extension imports with undefined `_PyInterpreterState_Get` |
| Remove psycopg2-binary 2.8.6 | Overlapping distribution; use the tested source driver |
| redis 4.0.2 → 5.2.1 | Original imports removed `distutils` on 3.13 |
| walrus 0.9.2 → 0.9.4 | Original `Database()` raises missing `register_script`, including with corrected Redis |
| marshmallow rc7 → 3.26.2 | Original imports removed `distutils` |

reportlab moves from 3.6.12 to 4.5.1: 3.6.12 has no Python 3.13 wheel and its C
accelerator fails to compile with GCC 14 on Trixie (on Bookworm it built but failed
to import, so ReportLab already ran in pure Python). PyPDF2 3.0.1, pypdf 3.5.1 and
wrapt 1.14.1 are retained after
successful real imports and archive/PDF tests. Requests, certifi, charset-normalizer,
idna and Pillow are explicitly pinned to the successful probe resolutions;
these were previously unconstrained transitives. boto3 1.26.16, botocore 1.29.16,
s3transfer 0.6.0 and their urllib3 constraint remain consistent (`pip check`).
This is runtime compatibility validation, not a full dependency security audit.

## Reproduce local checks

From the repository root:

```bash
service=computingservices/ZippingServices
docker pull python:3.13.17-trixie
# Keep this resolved base unchanged for the paired builds.
for variant in Dockerfile Dockerfile.local; do
  image="reviewer-zippingservice:${variant,,}"
  docker build --no-cache -t "$image" -f "$service/$variant" "$service"
  docker run --rm --entrypoint python "$image" -m pip check
  docker run --rm --entrypoint python "$image" integrationtests/runtime_smoke.py
  docker build --build-arg "CANDIDATE=$image" -t "$image-tests" \
    -f "$service/integrationtests/build-test-image.Dockerfile" "$service"
  docker run --rm --entrypoint sh "$image-tests" -ec '
    python -m pip check
    python -m pytest --collect-only -q -p no:cacheprovider unittests
    python -m pytest -q -p no:cacheprovider --junitxml=/tmp/unit.xml unittests
    python integrationtests/check-results.py /tmp/unit.xml
  '
  bash "$service/integrationtests/run-isolated.sh" "$image-tests"
done
```

The assertion suite never imports the infinite manual `unittests/testproducer.py`.
`pytest.ini` discovers only `test_*.py` under `unittests`; integration is an
explicit separate invocation, fails without opt-in, and never silently skips.
Tests run as `app_user`; only derived test images install pytest. The workflow
builds both images, checks fresh imports first, and transfers those same tested
images to the pipeline job. JUnit gates reject empty suites and any skips.

The runner owns a unique private network, Redis, PostgreSQL database and TLS
SeaweedFS 4.46 store, with no host ports or live application connections.
Ownership markers are checked before fixture SQL/state changes. The worker
uses its baked application and literal entrypoint, not mounted application
modules or stubs. Fixtures match PDFStitch/DocumentServices wire shapes;
they do not run those upstream services or the UI. SQL projects the canonical
DAL with JSON and required constraints; it is not a migration test.

Coverage: ZIP entry order/CRC/byte fidelity, empty/repeated/nested/Unicode names,
folder capitalization and phase mapping, multipage PDF text/rotation/metadata,
link/form annotations, malformed/password-protected fallback, versions 3/4/5,
package paths, harms/redline/response/phase notifications, incomplete jobs,
fee overrides, saved cursor restart, failure deletion and 8 MiB compressible
and incompressible fixtures. The runner bounds tests at 512 MiB/2 CPUs and
records processing duration and sampled worker RSS high-water values. This
synthetic limit is not a discovered deployment limit or production capacity proof.
ZIP64 stays enabled; no multi-gigabyte fixture is allocated.

## Existing behavior and release blockers

The PDF rewrite copies pages into a new PyPDF2 writer. Document author/title
are removed, but links and form annotations/values survive. Malformed/protected
PDFs fall back to original bytes. This is not comprehensive sanitization.

**A completed job does not prove a valid uploaded archive.** Baseline and candidate
both archive a missing GET's HTTP error body, and can persist a final path and
send `NO` error notifications after a rejected PUT with no object stored.
These reproduced storage-status defects remain release blockers for fault
acceptance and require separate reliability fixes. Upload retry cleanup also
deletes `filebytes` between retries. No storage/retry redesign is included.

The consumer uses plain XREAD, saves `$:lastid`, and deletes input entries in
`finally`, including failures. Restart tests preserve this behavior; they do not
establish exactly-once processing. A false upload result records version 5 on
the `-zipper` category; a thrown download/upload error uses the base category.
Notifications for unsupported categories (including openinfo) remain absent.

## Configuration, release and rollback

Generate local settings with `foi-dev-environment/scripts/env-for.sh reviewer-zipper
--docker`. Required groups are `REDIS_*`, `ZIPPER_STREAM_KEY`, `DB_*`, `S3_HOST`,
`S3_REGION`, `S3_SERVICE`, `S3_ENV`, `NOTIFICATION_REDIS_*` and
`NOTIFICATION_STREAM_KEY`; `FAILUREATTEMPT` defaults to 3. Storage still uses
HTTPS. The local Compose consumer is `zipper-local`, distinct from the packaged
`$`; preserve the effective cursor for the chosen mode.

Before release, require the dedicated ZippingServices checks and ETL dependency
checks in branch protection through the repository administration process.
Run real synthetic upstream harms/response/redline/phased/other supported
packages in dev, independently download each archive, inspect summaries,
attachments and rewritten PDFs, verify jobs/notifications and restart without
resetting cursors. Resolve the storage fault blockers and verify representative
production-sized packages under actual deployment limits. Promote the same
immutable digest to test through approved GitOps and repeat. OpenShift access
from this workspace is read-only.

Record the previous deployed immutable digest before promotion. Rollback
restores it through GitOps while preserving PostgreSQL jobs and Redis cursors,
then verifies a fresh synthetic package. No schema migration is planned.
See [execution evidence](foimod-5495-runtime-validation.md) for local results
and the remaining deployed/hosted-CI acceptance gates.
