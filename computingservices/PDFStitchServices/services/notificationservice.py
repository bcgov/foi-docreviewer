
from config import error_flag
from .pdfstichservice import pdfstitchservice
from rstreamio.writer.redisstreamwriter import redisstreamwriter

class notificationservice:

    def sendnotification(self, producermessage):
        # send message to notification stream once the zip file is ready to download
        complete, err, total_skippedfilecount, skippedfiles = pdfstitchservice().ispdfstitchjobcompleted(producermessage.jobid, producermessage.category.lower())
        print("complete == ", complete)
        print("err == ", err)

        # send notification for both success and error cases
        if complete or err:
            err = True if error_flag else err
            redisstreamwriter().sendnotification(producermessage, err, total_skippedfilecount, skippedfiles)
        else:
            print("pdfstitch not yet complete, no message sent")