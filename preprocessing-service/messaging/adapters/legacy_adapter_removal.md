# Removing Legacy Redis Adapter Support

This document describes how to remove the temporary compatibility layer once
Dedupe publishes the standard preprocessing envelope and CompressionServices no
longer requires flat legacy Redis messages.

## Compatibility currently provided

The preprocessing worker supports two message paths on its configured input
stream:

```text
standard PdfPreprocessingRequested envelope
  -> preprocessing handler
  -> detectors
  -> PdfPreprocessingCompleted envelope
```

```text
legacy flat Redis fields
  -> LegacyRedisMessageAdapter
  -> preprocessing handler
  -> detectors
  -> flat legacy Redis fields for CompressionServices
```

The legacy path preserves the complete inbound payload. When preprocessing
writes a repaired PDF, only the downstream `s3filepath` is changed to the
repaired output URI. When the PDF is clean, the original `s3filepath` is kept.

## Removal prerequisites

Do not remove the adapter while legacy messages can still be produced or
consumed. Confirm all of the following first:

- Dedupe publishes the standard `PdfPreprocessingRequested` envelope to the
  preprocessing input stream.
- No legacy flat-field messages remain pending in the preprocessing consumer
  group.
- The preprocessing input stream has no unprocessed legacy messages waiting for
  retry or reclaim.
- CompressionServices consumes the standard preprocessing completion contract,
  or another approved standard contract, instead of the flat legacy fields.
- The repaired-PDF URI and all metadata required by CompressionServices are
  represented in the new contract.
- The rollback window for legacy Dedupe publishing has ended.
- The deployment order and stream names have been reviewed with the owners of
  Dedupe, preprocessing, and CompressionServices.

If legacy and standard messages share a stream, inspect the stream and pending
entries before deploying the removal. A legacy message left behind after the
new worker is deployed will be rejected and dead-lettered.

## Code removal

Remove these compatibility pieces (check the commit that introduced this file for reference):

1. Delete `messaging/adapters/legacy_redis_message_adapter.py` and the adapter
   package initializer if it contains no other adapters.
2. Remove the `LegacyRedisMessageAdapter` import and instance from
   `messaging/consumer/redis_consumer.py`.
3. Remove the branch that adapts messages without an `event` field. Restore the
   original behavior for a missing `event` field: dead-letter it with the
   `missing_field` reason.
4. Remove `legacy_payload` from
   `messaging/models/events/pdf_preprocessing_requested.py`.
5. Remove `publish_legacy()` from
   `messaging/producer/redis_producer.py`.
6. In
   `messaging/consumer/handlers/pdf_preprocessing_requested.py`, remove the
   `payload.legacy_payload` branch and always publish the standard
   `PdfPreprocessingCompleted` envelope.
7. Remove legacy adapter, legacy consumer, and legacy downstream-forwarding
   tests. Keep the standard preprocessing and detector tests.
8. Remove this document after the migration is complete, or replace it with a
   short record of the completed migration.

Do not remove the detector pipeline, `RestoreResult`, `PipelineResult`, or the
standard preprocessing event models. Those are part of the normal service
architecture and are unrelated to legacy compatibility.

## Deployment order

Use a staged rollout so the worker never receives a message shape it cannot
handle:

1. Stop or redirect Dedupe so new legacy messages are no longer written.
2. Allow the existing preprocessing deployment to drain pending legacy
   messages, or explicitly process them according to the approved migration
   procedure.
3. Verify the input consumer group and dead-letter stream contain no remaining
   legacy messages.
4. Deploy the standard Dedupe producer and verify it emits the standard
   `PdfPreprocessingRequested` envelope.
5. Update CompressionServices to consume the standard completion contract.
6. Deploy preprocessing with legacy support removed.
7. Publish a controlled job and verify the full path:

   ```text
   Dedupe -> preprocessing -> detectors -> CompressionServices
   ```

8. Monitor preprocessing and CompressionServices DLQs, pending counts, and
   completion outcomes through the normal observability process.

The exact order of steps 4 and 5 may vary if both consumers support a staged
contract migration, but the compatibility window must overlap. Do not deploy a
producer or consumer that removes a format while messages in that format can
still arrive.

## Validation after removal

Run the preprocessing tests from the service directory:

```bash
cd preprocessing-service
poetry run pytest -m "not integration"
poetry run pytest -m integration
poetry run ruff check .
```

At minimum, verify these behaviors:

- A standard `PdfPreprocessingRequested` envelope is accepted and processed.
- A restored PDF is uploaded once and the standard completion event contains
  the repaired output URI.
- A clean PDF produces no output upload and reports `clean`.
- Detector ordering and aggregation remain unchanged.
- A malformed message without an `event` field is dead-lettered as
  `missing_field`.
- No code imports `messaging.adapters.legacy_redis_message_adapter`.
- No code calls `publish_legacy()`.

Then run the relevant CompressionServices contract and integration tests to
confirm that its new standard input contract contains every field it still
needs from the former legacy message.

## Rollback note

If rollback is required after removal, restore the adapter and flat-output
publisher from version control before redirecting Dedupe back to legacy
publishing. Do not send legacy messages into a worker that has already removed
legacy support.
