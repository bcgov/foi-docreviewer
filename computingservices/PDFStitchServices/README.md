# PDFStitchServices

The active entrypoint runs `rstreamio/reader/linearharmspdfstitch.py`. It merges
PDFs and images by division, flattens form pages, uploads the output and emits
the existing zipper event. Zipper completes successful jobs; this worker leaves
their status at `started` until that happens.

## Runtime

Both Dockerfiles use full `python:3.13-bookworm`, with the same OS packages,
`app_user`, working directory, fonts and entrypoint. Requirements are UTF-8.
Build both after one base pull to use the same resolved digest. The image tag
floats for security patches; record the digest and Python patch for each release.

Dependency changes are limited to demonstrated compatibility problems:

| Dependency | Before | After | Evidence/reason |
| --- | --- | --- | --- |
| psycopg2 | unpinned preinstall, 2.9.5 and psycopg2-binary 2.8.6 | source-built 2.9.10 only | Old source driver imports fail on 3.13 with undefined `_PyInterpreterState_Get`; eliminate overlapping driver distributions. |
| PyMuPDF | 1.23.8 | 1.24.14 | Original pin fails its 3.13 source build. This release supports 3.13 and precedes the widget-copy behavior in 1.25.3+. Probed 1.25.5 and 1.26.0 failed mixed form/plain-page stitching. |
| redis | 4.0.2 | 5.2.1 | Old version imports removed `distutils`. |
| walrus | 0.9.2 | 0.9.4 | Old version imports removed Redis client helpers and falls back to `object`, breaking client construction. |
| marshmallow | 3.0.0rc7 | 3.26.2 | Old version imports removed `distutils`; retain schema major version and include the 3.26.2 fix. |
| Pillow | unpinned transitive dependency | 11.1.0 | Explicit 3.13 wheel, validated PNG/JPEG conversion and rendering. |

ReportLab 3.6.12 and wrapt 1.14.1 build/import successfully and remain pinned.
The boto3/botocore/s3transfer set is unchanged. This is a runtime compatibility
upgrade, not a complete dependency security refresh. Native and schema libraries
emit deprecation warnings; a future interpreter upgrade needs fresh validation.

Upstream references: [PyMuPDF changes](https://pymupdf.readthedocs.io/en/latest/changes.html),
[psycopg2 2.9.10](https://www.psycopg.org/docs/news.html#what-s-new-in-psycopg-2-9-10),
[Marshmallow 3 changes](https://marshmallow.readthedocs.io/en/3.x-line/changelog.html).

## Build and offline tests

From this directory:

```bash
docker pull python:3.13-bookworm
docker image inspect python:3.13-bookworm --format '{{json .RepoDigests}}'
docker build --no-cache -t reviewer-pdfstitch:py313 -f Dockerfile .
docker build --no-cache -t reviewer-pdfstitch:py313-local -f Dockerfile.local .
docker run --rm --entrypoint python reviewer-pdfstitch:py313 -m pip check
docker run --rm --entrypoint python reviewer-pdfstitch:py313 integrationtests/runtime_smoke.py
docker build -t reviewer-pdfstitch:py313-tests -f - . <<'DOCKERFILE'
FROM reviewer-pdfstitch:py313
USER root
RUN python -m pip install --no-cache-dir -r requirements-test.txt
USER app_user
DOCKERFILE
docker run --rm --entrypoint python reviewer-pdfstitch:py313-tests -m pytest --collect-only -q unittests
docker run --rm --entrypoint python reviewer-pdfstitch:py313-tests -m pytest -q -p no:cacheprovider unittests
```

Repeat smoke, dependency and suite checks for `py313-local`, deriving its own
test image. Test requirements are installed only in disposable derived images.
The dedicated [CI workflow](../../.github/workflows/pdfstitch-services-tests.yml)
builds both variants, runs fresh native imports as `app_user`, rejects zero tests
or skips, and runs the isolated pipeline. Require this check before merge and
promotion; the existing catalog/publishing workflows are unchanged.

`pytest.ini` collects only `test_*.py`. The legacy `testproducer.py` is a manually
invoked producer, and `testcontext.py` imports a nonexistent module. Neither is
automated assertion coverage. Offline fixtures force loopback port 1 before
importing clients, and replace only external I/O; no production documents or
endpoints are used.

Regression coverage includes ordering, requested rotation, image orientation,
visible flattened widgets with plain pages retained, invalid/protected inputs,
unsupported references, output names and misspelled wire keys, active numbering,
byte message decoding, and completed/in-progress job and notification decisions.
Application modules are unchanged: the final dependency set passes the form
regression with the original page-copy call.

For baseline comparison, use the original dependency set in a Python 3.10
Bookworm image. The historical `python:3.10.8` Dockerfile fails `apt-get update`
against archived Debian repositories, so it cannot be rebuilt unchanged.
The baseline had no automated tests before this work. Run these tests in both
images, setting `PDFSTITCH_ARTIFACT_DIR` to separate writable artifact mounts.
Then mount both folders into a single candidate test image and run:

```bash
python integrationtests/compare_renderings.py /baseline /candidate
```

This renders both versions with one PyMuPDF build at 100 DPI and requires equal
page counts/dimensions and a mean normalized pixel difference below 0.01. It
compares appearance, not PDF byte hashes. Form tests also assert visible ink
inside the populated field rectangle.

Existing behavior deliberately retained: numbering can land outside the crop
on a rotated portrait page; all-invalid divisions lose their skipped-file details
when no PDF is emitted; successful stitching does not itself complete the job or
notify the requester. These are baseline findings, not delivery guarantees.

## Isolated worker integration

Run the following for each derived test image:

```bash
bash integrationtests/run-isolated.sh reviewer-pdfstitch:py313-tests
# CI also guards against accidentally replacing the packaged worker:
bash integrationtests/verify-packaged-worker.sh reviewer-pdfstitch:py313-tests
```

The harness creates a private Docker network and disposable Redis 7,
PostgreSQL 16 database and TLS SeaweedFS. Credentials and documents are synthetic.
It starts the **actual shipped entrypoint**, waits until Redis reports a blocked
XREAD before publishing, and asserts storage output, zipper metadata, job status,
notification behavior, cursor advancement/deletion and restart behavior. It runs
multiple divisions, a bounded 100-page job and a missing-object case, followed
by completed/in-progress and fresh jobs across restarts. It cleans up only its
own containers, network, database fixtures and temporary certificates.
Only the test harness is mounted into `/tests`; the application and entrypoint
run from the built image. The packaging check supplies a deliberately unusable
checkout entrypoint to ensure it cannot override the packaged worker. Baseline
comparison likewise requires baking the original source into its test image.
Restart cases queue work while stopped, resume from the saved cursor, and
assert that an older retained entry remains untouched.

The test prints wall duration, sampled worker peak RSS (including the Python
child), processing duration and sampled peak temporary bytes. These are bounded local measurements,
not deployed normal/large resource-limit certification. Explicit invocation
without `RUN_PDFSTITCH_INTEGRATION=1` fails instead of silently skipping.

Redis must contain only the harness's matching ownership marker before a test
starts; otherwise the fixture refuses to run. The cursor key is literally
`$:lastid`: `entrypoint.sh` passes the literal `$`
as the positional **consumer identity**, not as a start-from option. The worker
updates that key then deletes input entries after `handlemessage` returns,
including handled failures. It uses no consumer-group acknowledgement. Never
run the fixture on shared Redis: the literal cursor cannot be UUID-namespaced
while testing the unchanged entrypoint.

## Local stack and rollout

The current sibling local stack has no PDFStitch service or generator entry.
Once support is added, use
`foi-dev-environment/scripts/env-for.sh reviewer-pdfstitch --docker` for
generated local settings. Source its shell assignments; do not hand-copy deployed
secrets or treat its output as a Docker env-file. Use the stack's restart command
when integrating the image. Required settings are in `config.py`: Redis input,
zipper and notification connections/streams, `PDFSTITCH_DB_*`, `PDFSTITCH_S3_*`,
`DIVISION_STITCH_FOLDER_PATH`, `NUMBERING_ENABLED` and `NOTIFICATION_ENABLED`.

Preserve the effective zipper contract: `config.py` reads port/password into
reversed names, and `zipperproducerservice.py` reverses them again when connecting.
The integration fixture verifies connectivity using the existing environment
names. Do not partially rename those variables.

Deployment validation remains a release gate. For **both normal and large-file
workloads**, record the previous immutable digest, OS/Python, input routing,
consumer identity/cursor, effective settings and resource limits without printing
secrets. Run synthetic PDF/image/rotation/widget/mixed-invalid jobs and compare
output, skips, numbering, filenames, zipper packages, notifications and statuses
with the baseline. Record duration, peak memory and temporary storage against
the actual limits. Restart without resetting checkpoints, verify fresh work and
absence of historical replay. Promote the same immutable digest to test through
approved GitOps and repeat. OpenShift access here is read-only.

Rollback restores the previous image digest through GitOps while preserving
job rows, streams and cursor keys, then verifies a fresh synthetic job. No schema
migration or production configuration change is planned. Local tests do not prove
dev/test deployment, actual zipper package generation, or production S3 behavior.

