from .zipperdboperations import ispdfstichjobcompleted, isredlineresponsezipjobcompleted
from utils.foizipperconfig import notification_stream_key
from utils.foiredisstreamdb import notificationredisstreamdb
from models.harrmsnotificationmessage import harmsnotificationmessage
from models.redlineresponsenotificationmessage import redlineresponsenotificationmessage
import logging, json


class notificationservice:
    def sendharmsnotification(self, producermessage):
        (
            complete,
            err,
            total_skippedfilecount,
            skippedfiles,
        ) = self.__ispdfstitchjobcompleted(
            producermessage.jobid, producermessage.category.lower()
        )

        if complete or err:
            self.__publishtostream(
                producermessage, err, total_skippedfilecount, skippedfiles
            )
        else:
            logging.info("pdfstitch not yet complete, no message sent")

    def sendredlineresponsenotification(self, producermessage):
        complete, err = self.__isredlineresponsezipjobcompleted(
            producermessage.jobid, producermessage.category.lower()
        )

        if complete or err:
            if producermessage.category.lower() == "redline":
                self.__redlinepublishtostream(producermessage, err)
            elif producermessage.category.lower() == "responsepackage":
                self.__responsepackagepublishtostream(producermessage, err)
        else:
            logging.info("redline zipping is not yet completed, no message to sent")

    def __responsepackagepublishtostream(self, message, error=False):
        try:
            notification_msg = redlineresponsenotificationmessage(
                ministryrequestid=message.ministryrequestid,
                serviceid="pdfstitchforresponsepackage",
                createdby=message.createdby,
                errorflag=self.__booltostr(error),
                feeoverridereason= message.feeoverridereason
            )

            logging.info(
                "Response package Notification message = %s ", notification_msg.__dict__
            )
            notificationstream = notificationredisstreamdb.Stream(
                notification_stream_key
            )

            msgid = notificationstream.add(notification_msg.__dict__, id="*")
            logging.info("Response package Notification message for msgid = %s ", msgid)
        except Exception as error:
            logging.error(
                f"Unable to write to notification stream for response package pdfstitch | ministryrequestid= {message.ministryrequestid}"
            )
            logging.error(error)

    def __redlinepublishtostream(self, message, error=False):
        try:
            notification_msg = redlineresponsenotificationmessage(
                ministryrequestid=message.ministryrequestid,
                serviceid="pdfstitchforredline",
                createdby=message.createdby,
                errorflag=self.__booltostr(error),
            )

            logging.info(
                "Redline Notification message = %s ", notification_msg.__dict__
            )
            notificationstream = notificationredisstreamdb.Stream(
                notification_stream_key
            )

            msgid = notificationstream.add(notification_msg.__dict__, id="*")
            logging.info("Redline Notification message for msgid = %s ", msgid)
        except Exception as error:
            logging.error(
                f"Unable to write to notification stream for redline pdfstitch | ministryrequestid= {message.ministryrequestid}"
            )
            logging.error(error)

    def __publishtostream(
        self, message, error=False, totalskippedfilecount=0, totalskippedfiles=[]
    ):
        try:
            notification_msg = harmsnotificationmessage(
                ministryrequestid=message.ministryrequestid,
                serviceid="pdfstitchforharms",
                totalskippedfilecount=totalskippedfilecount,
                totalskippedfiles=json.JSONEncoder().encode(totalskippedfiles),
                createdby=message.createdby,
                errorflag=self.__booltostr(error),
            )

            logging.info("Harms Notification message = %s ", notification_msg.__dict__)
            notificationstream = notificationredisstreamdb.Stream(
                notification_stream_key
            )

            msgid = notificationstream.add(notification_msg.__dict__, id="*")
            logging.info("Harms Notification message for msgid = %s ", msgid)
        except Exception as error:
            logging.error(
                f"Unable to write to notification stream for pdfstitch | ministryrequestid= {message.ministryrequestid}"
            )
            logging.error(error)

    def __booltostr(self, value):
        return "YES" if value == True else "NO"

    def __getskippedfiledetails(self, data):
        total_skippedfilecount = 0
        total_skippedfiles = []       
        data = json.loads(data)
        for output in data["stitchedoutput"]:
            skippedfilecount = output["skippedfilecount"]
            skippedfiles = output["skippedfiles"]
            total_skippedfilecount += skippedfilecount
            total_skippedfiles.extend(skippedfiles)

        total_skippedfiles = list(set(total_skippedfiles))
        return total_skippedfilecount, total_skippedfiles

    def __ispdfstitchjobcompleted(self, jobid, category):
        total_skippedfilecount = 0
        skippedfiles = None
        complete, err, attributes = ispdfstichjobcompleted(jobid, category)
        if attributes:
            total_skippedfilecount, skippedfiles = self.__getskippedfiledetails(
                attributes
            )
        return complete, err, total_skippedfilecount, skippedfiles

    def __isredlineresponsezipjobcompleted(self, jobid, category):
        return isredlineresponsezipjobcompleted(jobid, category)
