# FOIMOD-5199 Compression Producer Migration Addendum

This addendum records the Dedupe producer migration implemented by the
[implementation plan](superpowers/plans/2026-08-18-compression-producer-messaging.md).
Operators must follow the detailed
[rollout runbook](runbooks/compression-producer-messaging-rollout.md).

## Scope and topics

The producer supports one mode per process: `legacy` during the rollback
window, or `standard` after the staged cutover. It never dual-publishes.
Standard normal Dedupe traffic uses `foi:compression`; large-file Dedupe uses
`foi:compression-large`. The OpenShift templates default to `legacy` and
parameterize the mode, prefix, and topic so each deployment can be switched
independently.

## Verification and rollback

Release legacy mode everywhere first, deploy compatible consumers on empty
standard topics, then cut over normal Dedupe before large-file Dedupe. Verify
typed consumption, acknowledgements, pending state, DLQ counts, topic
isolation, and approved version-3 job outcomes. The Redis/Go contract test is
an additional compatibility check; it requires its explicit Redis environment
and is not asserted as passed by this addendum.

Before rollback, inspect standard stream/group/pending/DLQ state using the
runbook's payload-safe commands. Restart only the affected deployment in
`legacy` mode with its existing `COMPRESSION_STREAM_KEY`. Keep the standard
stream for forensic metadata inspection until the rollback window closes; do
not dual-publish.

## Deferred work

After the rollback window, drain legacy streams and remove the legacy Walrus
formatter/configuration in a separately reviewed change. Production Go
consumer work, a transactional outbox, application-level retries, and changes
to page-calculator or notification publishers remain out of scope.
