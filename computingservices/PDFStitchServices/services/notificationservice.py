
from .pdfstichservice import pdfstitchservice
from rstreamio.writer.redisstreamwriter import redisstreamwriter
import logging

class notificationservice:

    def sendnotification(self, producermessage):
        # send message to notification stream once the zip file is ready to download
        started, complete, err, total_skippedfilecount, skippedfiles = pdfstitchservice().ispdfstitchjobcompleted(producermessage.jobid, producermessage.category.lower())
        # send notification for both success and error cases
        if complete or err:
            redisstreamwriter().sendnotification(producermessage, err, total_skippedfilecount, skippedfiles)
        else:
            logging.info("pdfstitch not yet complete, no message sent")