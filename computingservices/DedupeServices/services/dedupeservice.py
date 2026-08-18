
from .s3documentservice import gets3documenthashcode
from .dedupedbservice import savedocumentdetails, recordjobstart, recordjobend, updateredactionstatus, pagecalculatorjobstart, compressionjobstart
from .documentspagecalculatorservice import documentspagecalculatorproducerservice
from models.pagecalculatorproducermessage import pagecalculatorproducermessage
from models.compressionproducermessage import compressionproducermessage
from .compressionproducerservice import compressionproducerservice
import logging
from utils.loggingutils import log_context, log_event


_compressionproducer = None
logger = logging.getLogger(__name__)


def _get_compressionproducer():
    global _compressionproducer
    if _compressionproducer is None:
        _compressionproducer = compressionproducerservice()
    return _compressionproducer


def initialize_compressionproducer():
    return _get_compressionproducer()


def processmessage(message, *, log_context_data=None) -> None:
    """Process one Dedupe message while preserving its correlation context."""

    compressionproducer = _get_compressionproducer()
    recordjobstart(message)
    context = log_context(message, **(log_context_data or {}))
    stage = "dedupe"
    log_event(logger, logging.INFO, "dedupe_started", context=context, stage=stage)
    try:
        stage = "hashing"
        hashcode, _pagecount = gets3documenthashcode(message)
        log_event(logger, logging.INFO, "hash_completed", context=context, stage=stage)

        stage = "document_save"
        newdocumentid, _= savedocumentdetails(message, hashcode, _pagecount)
        log_event(logger, logging.INFO, "document_saved", context=context, stage=stage)
        recordjobend(message, False)
        #updateredactionstatus(message)
        _incompatible = True if str(message.incompatible).lower() == 'true' else False
        if not _incompatible:
            message.documentid= newdocumentid
            #message.needsocr= needs_ocr
            #compressionmessage =  compressionproducerservice().createcompressionproducermessage(message, _pagecount)
            stage = "compression_publish"
            compressionjobid = compressionjobstart(message)
            compressionproducer.producecompressionevent(message, compressionjobid)
            log_event(logger, logging.INFO, "compression_published", context=context, stage=stage)

            stage = "page_calculator_publish"
            pagecalculatormessage = documentspagecalculatorproducerservice().createpagecalculatorproducermessage(message, _pagecount)
            pagecalculatorjobid = pagecalculatorjobstart(pagecalculatormessage)
            documentspagecalculatorproducerservice().producepagecalculatorevent(pagecalculatormessage, _pagecount, pagecalculatorjobid)
            log_event(logger, logging.INFO, "page_calculator_published", context=context, stage=stage)
        else:
            stage = "incompatible"
            updateredactionstatus(message)
            log_event(logger, logging.INFO, "incompatible_completed", context=context, stage=stage)
    except(Exception) as error:
        log_event(logger, logging.ERROR, "dedupe_failed", context=context, stage=stage, exc_info=True)
        recordjobend(message, True, error.args[0])
        raise
