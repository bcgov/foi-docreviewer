# PageCountCalculator

Redis worker that persists page-calculation job history in Document Reviewer
and updates active FOI ministry request counts in a separate PostgreSQL database.
Both Dockerfiles use full `python:3.13.17-trixie`, source-built `psycopg2==2.9.10`,
and the existing `app_user`, working directory, environment and entrypoint.

## Build and test

From the repository root:

```bash
service=computingservices/PageCountCalculator
docker pull python:3.13.17-trixie
for dockerfile in Dockerfile Dockerfile.local; do
  image="reviewer-pagecountcalculator:${dockerfile,,}"
  docker build --no-cache -t "$image" -f "$service/$dockerfile" "$service"
  docker run --rm --entrypoint python "$image" -m pip check
  docker run --rm --entrypoint python "$image" integrationtests/runtime_smoke.py
  docker build -t "$image-tests" --build-arg "CANDIDATE=$image" \
    -f "$service/integrationtests/build-test-image.Dockerfile" "$service"
  docker run --rm --entrypoint sh -e REDIS_PORT=6379 "$image-tests" -ec '
    python -m pytest --collect-only -q -p no:cacheprovider unittests
    python -m pytest -q -p no:cacheprovider --junitxml=/tmp/results.xml unittests
    python integrationtests/check-results.py /tmp/results.xml
  '
  bash "$service/integrationtests/run-isolated.sh" "$image-tests"
done
```

The integration runner creates a private Docker network, password-protected
Redis, and separate disposable Document Reviewer/FOI databases. Both Redis and
the databases require this run's ownership token before fixture writes. The
worker connects using distinct non-superuser roles. The schema fixtures are
explicit DAL projections of the canonical models/migration cited in their SQL
files; they do not certify the complete application schema or migrations.
Only test files are mounted; application code and entrypoint come from the
built image. No shared streams, cursor keys or application rows are modified.
Fixtures run the actual `python __main__.py $` entrypoint, poll with deadlines,
verify both databases, retain input entries, and restart with queued work and
an older unprocessed entry. Test-only pytest is installed in derived images.

The workflow `pagecountcalculator-tests.yml` runs unit/native checks on both
images and transfers those exact test images to a separate integration job.
Both jobs must pass before merge/promotion. Repository required-check settings
and GitHub-hosted results must be verified during release. Do not run the legacy
manual `unittests/producer.py`: it contains a hardcoded Redis endpoint.

## Runtime dependency changes

| Dependency | Previous | Candidate | Observed reason |
| --- | --- | --- | --- |
| psycopg2 | 2.9.5 plus binary 2.8.6 and unpinned pre-install | 2.9.10 only | Old extension imports fail on 3.13; eliminate overlapping distributions. |
| redis | 4.0.2 | 5.3.1 | Old import requires removed `distutils`. |
| walrus | 0.8.2 | 0.9.5 | Old adapter loses Redis inheritance with new Redis. |
| marshmallow | 3.0.0rc7 | 3.26.1 | Old import requires removed `distutils`; schema behavior tested on major 3. |

Requirements were converted from UTF-16 to UTF-8 in a separate commit.
`maya==0.6.1`, `pytz==2021.1`, wrapt, crypto, pypdf and coupled AWS pins are
retained after actual install/import/behavior checks. Maya's resolved date/time
packages are pinned explicitly in requirements, including Pendulum and tzdata.
Historical Vancouver conversions match the baseline. These pins preserve
runtime behavior; they do not implement a new timezone policy or complete
security/dependency lifecycle modernization.

## Calculation and existing limitations

For stored Python `None`/integer `0`, the presence of an incoming `pagecount`
attribute selects it, including an explicit null. Otherwise metadata is
recomputed. Count eligible parent pages and their nonduplicate recursive
attachments; exclude duplicate/portfolio/incompatible parents. Database queries
filter deleted and inactive attributes. Hashes select the lowest master ID;
`.msg` attachments also compare filename, size and modification time.

Canonical FOI `recordspagecount` is `varchar(20)`: psycopg2 returns non-null
counts as strings. Consequently stored `"0"` recomputes rather than taking the
integer-zero shortcut, and equal textual/integer totals still trigger updates.
Tests intentionally preserve this behavior. Inactive request versions remain
unchanged; the update affects all active versions, as before.

Job versions 2/3 record started/completed or error. Exceptions swallowed in
`calculatepagecount` can produce a completed job with JSON null while the
request remains unchanged. A request update can commit even if writing job
version 3 fails. Repeated events do not replace existing job versions but can
update the request again. These are existing reliability defects requiring
separate work. A completed job alone is insufficient validation evidence.

The reader keeps stream entries and advances `{consumer_id}:lastid` after
processing attempts, including malformed messages and database failures. The
shipped consumer ID is `$`, hence `$:lastid`; never clear a shared checkpoint
or infer consumer-group acknowledgment guarantees. Existing byte/string quote
conversion corrupts non-ASCII filenames and apostrophes; direct schema parsing
does not. No reader redesign is included.

## Configuration, release and rollback

Use `sample.env` or the established `foi-dev-environment/scripts/env-for.sh
reviewer-pagecountcalculator --docker` generator. Required settings are
`REDIS_HOST/PORT/PASSWORD`, `PAGECALCULATOR_STREAM_KEY`, and both
`DOCUMENTSERVICE_DB_*` / `FOI_DB_*` connection groups. No new production settings,
secrets, SQL migrations, or downstream message fields are required. The local
stack currently overrides the consumer to `pagecount-local`; its cursor identity
differs from the packaged `$` entrypoint and must be respected.

Before release, record previous immutable deployed digests and effective configuration. Run
synthetic uploads through Dedupe and the UI in dev, verify request totals and
both job versions, deletion/duplicates/nested attachments and subsequent uploads,
then restart without resetting cursor state. Compare resource usage against
actual deployment limits. Promote the same immutable digest through the approved
GitOps process to test and repeat. OpenShift access here is read-only.

Rollback restores the recorded previous image via GitOps, preserves both
application databases and all Redis state, and verifies a fresh synthetic job.
Local fixtures do not establish dev/test acceptance or a deployed rollback.
