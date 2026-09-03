# cli.py
"""
The producer side of the sample, as a one-shot command.

Publishing lives in a CLI rather than an HTTP endpoint because this template
has no HTTP surface: a worker consumes events, and something else produces
them. Run it twice with the same --job-id to watch the consumer's idempotency
guard turn the second delivery into a logged no-op.

    python -m cli publish --source-uri s3://my-bucket/incoming/doc.pdf --count 2
"""

import argparse
import asyncio
import sys
from uuid import uuid4

from opentelemetry import trace

from config.logging import configure_logging
from config.tracing import init_tracing
from messaging.models import EventEnvelope, PdfPreprocessingRequestedEvent
from messaging.producer.redis_producer import RedisProducer

configure_logging()
init_tracing()

tracer = trace.get_tracer(__name__)


def positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be one or greater")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    publish_parser = sub.add_parser(
        "publish", help="Publish a PdfPreprocessingRequested event"
    )
    publish_parser.add_argument(
        "--source-uri",
        required=True,
        help="s3://bucket/key of the PDF to preprocess",
    )
    publish_parser.add_argument(
        "--job-id",
        default=None,
        help="Idempotency key; a random hex id is generated if omitted",
    )
    publish_parser.add_argument(
        "--count",
        type=positive_int,
        default=1,
        help="Publish the same event N times, to demonstrate idempotency",
    )
    return parser


async def publish(args: argparse.Namespace) -> tuple[str, list[str]]:
    """Publish `count` copies of one request event; return (job_id, message ids)."""
    job_id = args.job_id or uuid4().hex
    producer = RedisProducer()
    message_ids: list[str] = []
    try:
        for _ in range(args.count):
            # The CLI process is the root of the distributed trace. Without this
            # span the worker's spans start a trace that begins mid-pipeline.
            with tracer.start_as_current_span("cli.publish"):
                message_ids.append(
                    await producer.publish(
                        EventEnvelope.create(
                            event_type="PdfPreprocessingRequested",
                            payload=PdfPreprocessingRequestedEvent(
                                job_id=job_id, source_uri=args.source_uri
                            ),
                            correlation_id=job_id,
                            source="cli",
                        )
                    )
                )
    finally:
        await producer.close()
    return job_id, message_ids


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    job_id, message_ids = asyncio.run(publish(args))

    print(
        f"published {len(message_ids)} x PdfPreprocessingRequested "
        f"job_id={job_id} source_uri={args.source_uri}"
    )
    for message_id in message_ids:
        print(f"  {message_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
