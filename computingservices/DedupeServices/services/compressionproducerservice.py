import logging

import redis
from walrus import Database

from models.compressionproducermessage import compressionproducermessage
from rstreamio.compressionevents import CompressionEventDefinition, StandardCompressionPublisher
from rstreamio.legacycompressionpublisher import LegacyCompressionPublisher
from utils.loggingutils import log_event
from utils.foidedupeconfig import (
    compression_messaging_mode,
    compression_topic,
    compressionredishost,
    compressionredispassword,
    compressionredisport,
    compressionstreamkey,
    health_check_interval,
    messaging_stream_prefix,
)


logger = logging.getLogger(__name__)

COMPRESSION_EVENT_TYPE = "document.compression.requested"
COMPRESSION_SCHEMA_VERSION = "1.0.0"
COMPRESSION_EVENT_SOURCE = "foi-docreviewer.dedupe"

class compressionproducerservice:
    compressionredisdb = None
    compressionredisstream = None

    def __init__(self) -> None:
        self.mode = self._validate_configuration()
        self.compressionredisdb = None
        self.compressionredisstream = None

        if self.mode == "legacy":
            self.compressionredisdb = Database(
                host=str(compressionredishost),
                port=str(compressionredisport),
                db=0,
                password=str(compressionredispassword),
                retry_on_timeout=True,
                health_check_interval=int(health_check_interval),
                socket_keepalive=True,
            )
            self.compressionredisstream = self.compressionredisdb.Stream(compressionstreamkey)
            self.stream = compressionstreamkey
            self.publisher = LegacyCompressionPublisher(self.compressionredisstream)
        else:
            self.compressionredisdb = redis.Redis(
                host=str(compressionredishost),
                port=int(compressionredisport),
                db=0,
                password=str(compressionredispassword),
                retry_on_timeout=True,
                health_check_interval=int(health_check_interval),
                socket_keepalive=True,
            )
            event_definition = CompressionEventDefinition(
                topic=compression_topic,
                event_type=COMPRESSION_EVENT_TYPE,
                schema_version=COMPRESSION_SCHEMA_VERSION,
                source=COMPRESSION_EVENT_SOURCE,
            )
            self.stream = f"{messaging_stream_prefix}:{compression_topic}"
            self.publisher = StandardCompressionPublisher(
                self.compressionredisdb,
                messaging_stream_prefix,
                event_definition,
            )

        log_event(logger, logging.INFO, "compression_producer_initialized", stage=self.stream)

    def producecompressionevent(self, finalmessage, jobid, correlation_id=None):
        compression_request = self.createcompressionproducermessage(finalmessage, jobid=jobid)
        payload = compression_request.to_dict()

        if self.mode == "standard":
            result = self.publisher.publish(payload, correlation_id=correlation_id)
            log_event(
                logger,
                logging.INFO,
                "compression_published",
                context=compression_request,
                stage=self.stream,
                stream_id=result.stream_id,
                event_id=result.event_id,
                correlation_id=result.correlation_id,
            )
            return result

        result = self.publisher.publish(payload)
        log_event(
            logger,
            logging.INFO,
            "compression_published",
            context=compression_request,
            stage=self.stream,
            stream_id=result,
        )
        return result

    def createcompressionproducermessage(self,message,  jobid = 0):
        return compressionproducermessage(jobid=jobid, message=message)

    @staticmethod
    def _validate_configuration():
        if compression_messaging_mode not in ("legacy", "standard"):
            raise ValueError("compression_messaging_mode must be 'legacy' or 'standard'")

        compressionproducerservice._require_value("compressionredishost", compressionredishost)
        compressionproducerservice._require_value("compressionredisport", compressionredisport)
        try:
            if not 1 <= int(compressionredisport) <= 65535:
                raise ValueError
        except (TypeError, ValueError) as error:
            raise ValueError("compressionredisport must be an integer between 1 and 65535") from error

        if compression_messaging_mode == "legacy":
            compressionproducerservice._require_value("compressionstreamkey", compressionstreamkey)
        else:
            compressionproducerservice._require_value("messaging_stream_prefix", messaging_stream_prefix)
            compressionproducerservice._require_value("compression_topic", compression_topic)
            compressionproducerservice._require_value("COMPRESSION_EVENT_TYPE", COMPRESSION_EVENT_TYPE)
            compressionproducerservice._require_value("COMPRESSION_SCHEMA_VERSION", COMPRESSION_SCHEMA_VERSION)
            compressionproducerservice._require_value("COMPRESSION_EVENT_SOURCE", COMPRESSION_EVENT_SOURCE)

        return compression_messaging_mode

    @staticmethod
    def _require_value(name, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
