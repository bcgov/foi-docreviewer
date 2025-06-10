from reviewer_api.models.Documents import Document
from reviewer_api.models.DocumentMaster import DocumentMaster
from reviewer_api.models.FileConversionJob import FileConversionJob
from reviewer_api.models.DeduplicationJob import DeduplicationJob
from reviewer_api.models.PageCalculatorJob import PageCalculatorJob
from reviewer_api.models.CompressionJob import CompressionJob
from reviewer_api.models.OCRActiveMQJob import OCRActiveMQJob
from reviewer_api.models.DocumentOCRJob import DocumentOCRJob
from reviewer_api.models.DocumentProcesses import DocumentProcesses
from datetime import datetime as datetime2, timezone
from os import path
from reviewer_api.models.DocumentDeleted import DocumentDeleted
import json
from reviewer_api.utils.util import pstformat
from reviewer_api.models.DocumentAttributes import DocumentAttributes
from reviewer_api.services.pdfstitchpackageservice import pdfstitchpackageservice
from reviewer_api.services.external.eventqueueproducerservice import eventqueueproducerservice
import requests
from reviewer_api.auth import auth, AuthHelper
from os import getenv
from reviewer_api.utils.enums import StateName

requestapiurl = getenv("FOI_REQ_MANAGEMENT_API_URL")
pagecalculatorstreamkey = getenv("PAGECALCULATOR_STREAM_KEY")

class documentservice:
    def getdedupestatus(self, requestid):
        deleted = DocumentMaster.getdeleted(requestid)
        records = DocumentMaster.getdocumentmaster(requestid)
        conversions = FileConversionJob.getconversionstatus(requestid)
        dedupes = DeduplicationJob.getdedupestatus(requestid)
        compressions = CompressionJob.getcompressionstatus(requestid)
        ocractivemqjobs = OCRActiveMQJob.getocractivemqstatus(requestid)
        azureocrjobs = DocumentOCRJob.getazureocrjobstatus(requestid)
        properties = DocumentMaster.getdocumentproperty(requestid, deleted)
        redactions = DocumentMaster.getredactionready(requestid)
        #print("\n\nrecords :",records)
        #print("\nCompressions :",compressions)

        for record in records:
            record["duplicatemasterid"] = record["documentmasterid"]
            record["ministryrequestid"] = requestid
            record["isattachment"] = True if record["parentid"] is not None else False
            record["created_at"] = pstformat(record["created_at"])
            record["conversionstatus"] = record["deduplicationstatus"] = record["compressionstatus"]= None
            record["isredactionready"] = False #For duplicate scenario its added- check that after commenting
            record = self.__updatecoversionstatus(conversions, record)
            record = self.__updatededupestatus(dedupes, record)
            record= self.__updatecompressionstatus(compressions, record)
            record= self.__updateocractivemqstatus(ocractivemqjobs, record)
            record= self.__updateazureocrstatus(azureocrjobs, record)
            record = self.__updateredactionstatus(redactions, record)
            if record["recordid"] is not None:
                record["attachments"] = self.__getattachments(
                    records, record["documentmasterid"], []
                )
            #print("\neach RECORD:",record)
            
        # Duplicate check
        finalresults = []
        (
            parentrecords,
            parentswithattachmentsrecords,
            attachmentsrecords,
        ) = self.__filterrecords(records)
        #print("\nparentrecords:",parentrecords)
        parentproperties = self.__getrecordsproperties(parentrecords, properties)
        #print("\nparentproperties:",parentproperties)

        for record in records:
            if record["recordid"] is not None:
                finalresult = self.__updateproperties(
                    records,
                    properties,
                    record,
                    parentproperties,
                    parentswithattachmentsrecords,
                    attachmentsrecords,
                )
                finalresults.append(finalresult)
                print("\nfinalresult :",finalresult)
        return finalresults

    def __updateproperties(
        self,
        records,
        properties,
        record,
        parentproperties,
        parentswithattachmentsrecords,
        attachmentsrecords,
    ):
        if record["recordid"] is not None:
            _att_in_properties = []
            (
                record["originalpagecount"],
                record["pagecount"],
                record["filename"],
                record["documentid"],
                record["version"],
                record["selectedfileprocessversion"]
            ) = self.__getpagecountandfilename(record, parentproperties)
            (
                record["isduplicate"],
                record["duplicatemasterid"],
                record["duplicateof"],
            ) = self.__isduplicate(parentproperties, record)
            #print("isduplicate in __updateproperties-documentservice",record["isduplicate"])
            if len(record["attachments"]) > 0:
                if record["isduplicate"] == True:
                    duplicatemaster_attachments = self.__getduplicatemasterattachments(
                        parentswithattachmentsrecords, record["duplicatemasterid"]
                    )
                    if duplicatemaster_attachments is None:
                        _att_in_properties = self.__getattachmentproperties(
                            record["attachments"], properties
                        )
                    else:
                        _att_in_properties = self.__getattachmentproperties(
                            duplicatemaster_attachments + record["attachments"],
                            properties,
                        )
                elif len(record["attachments"]) > 0:
                    _att_in_properties = self.__getattachmentproperties(
                        record["attachments"], properties
                    )
                for attachment in record["attachments"]:
                    if len(_att_in_properties) > 1:
                        if attachment["filepath"].endswith(".msg"):
                            (
                                attachment["isduplicate"],
                                attachment["duplicatemasterid"],
                                attachment["duplicateof"],
                            ) = self.__getduplicatemsgattachment(
                                attachmentsrecords, _att_in_properties, attachment
                            )
                        else:
                            (
                                attachment["isduplicate"],
                                attachment["duplicatemasterid"],
                                attachment["duplicateof"],
                            ) = self.__isduplicate(_att_in_properties, attachment)

                    (
                        attachment["originalpagecount"],
                        attachment["pagecount"],
                        attachment["filename"],
                        attachment["documentid"],
                        attachment["version"],
                        attachment["selectedfileprocessversion"]
                    ) = self.__getpagecountandfilename(attachment, _att_in_properties)
        return record

    def __filterrecords(self, records):
        parentrecords = []
        parentswithattachments = []
        attchments = []
        for record in records:
            #print("record---",record)
            if record["recordid"] is not None:
                parentrecords.append(record)
            if "attachments" in record and len(record["attachments"]) > 0:
                parentswithattachments.append(record)
            if record["recordid"] is None:
                attchments.append(record)
        return parentrecords, parentswithattachments, attchments
      
    def __getpagecountandfilename(self, record, properties):
        originalpagecount = 0
        pagecount = 0
        filename = record["filename"] if "filename" in record else None
        documentid = None
        version = 0
        selectedfileprocessversion=None
        for property in properties:
            if record["documentmasterid"] == property["processingparentid"] or (
                property["processingparentid"] is None
                and record["documentmasterid"] == property["documentmasterid"]
            ):
                originalpagecount = property["originalpagecount"]
                pagecount = property["pagecount"]
                filename = property["filename"]
                documentid = property["documentid"]
                version = property["version"]
                selectedfileprocessversion = property["selectedfileprocessversion"]

        return originalpagecount, pagecount, filename, documentid, version,selectedfileprocessversion

    def __getduplicatemsgattachment(self, records, attachmentproperties, attachment):
        _occurances = []
        for entry in attachmentproperties:
            if entry["filename"] == attachment["filename"]:
                _lhsattribute = self.__getrecordproperty(
                    records, entry["processingparentid"], "attributes"
                )
                _rhsattribute = self.__getrecordproperty(
                    records, attachment["documentmasterid"], "attributes"
                )
                if (
                    _lhsattribute["filesize"] == _rhsattribute["filesize"]
                    and _lhsattribute["lastmodified"] == _rhsattribute["lastmodified"]
                ):
                    _occurances.append(entry)
        if len(_occurances) > 1:
            filtered = [x["processingparentid"] for x in _occurances]
            _firstupload = min(filtered)
            if _firstupload != attachment["documentmasterid"]:
                attachment["isduplicate"] = True
                attachment["duplicatemasterid"] = _firstupload
                attachment["duplicateof"] = self.__getduplicateof(
                    attachmentproperties, attachment, attachment["duplicatemasterid"]
                )
                return (
                    attachment["isduplicate"],
                    attachment["duplicatemasterid"],
                    attachment["duplicateof"],
                )
        return False, attachment["documentmasterid"], attachment["filename"]

    def __getduplicatemasterattachments(self, records, duplicatemasterid):
        return self.__getrecordproperty(records, duplicatemasterid, "attachments")

    def __getrecordproperty(self, records, documentmasterid, property):
        for x in records:
            if x["documentmasterid"] == documentmasterid:
                return x[property]
        return None

    def __getrecordsproperties(self, records, properties):
        filtered = []
        for record in records:
            for property in properties:
                if (property["processingparentid"] == record["documentmasterid"] or (
                    property["processingparentid"] is None
                    and record["documentmasterid"] == property["documentmasterid"]
                )) or (property["createdby"]=="compressionservice" and record["documentmasterid"] == property["documentmasterid"]):
                    filtered.append(property)
        return filtered

    def __getattachmentproperties(self, attachments, properties):
        filtered = []
        for attachment in attachments:
            for property in properties:
                if property["processingparentid"] == attachment["documentmasterid"] or (
                    property["processingparentid"] is None
                    and attachment["documentmasterid"] == property["documentmasterid"]
                ):
                    filtered.append(property)
        return filtered

    def __getattachments(self, records, documentmasterid, result=[]):
        for entry in records:
            if entry["recordid"] is None:
                if entry["parentid"] not in [None, ""] and int(
                    entry["parentid"]
                ) == int(documentmasterid):
                    result.append(entry)
                    result = self.__getattachments(
                        records, entry["documentmasterid"], result
                    )
        return result

    def __updatecoversionstatus(self, conversions, record):
        for conversion in conversions:
            if record["documentmasterid"] == conversion["documentmasterid"]:
                record["conversionstatus"] = conversion["status"]
                record["outputdocumentmasterid"] = conversion["outputdocumentmasterid"]
                record["filename"] = conversion["filename"]
                record["trigger"] = conversion["trigger"]
        return record

    def __updatededupestatus(self, dedupes, record):
        for dedupe in dedupes:   
            if record["documentmasterid"] == dedupe["documentmasterid"]:
                record["deduplicationstatus"] = dedupe["status"]
                record["filename"] = dedupe["filename"]
                record["trigger"] = dedupe["trigger"]
                record["message"] = dedupe["message"]
        return record

    def __updatecompressionstatus(self, compressions, record):
        for compression in compressions:
            if record["documentmasterid"] == compression["documentmasterid"]:
                record["compressionstatus"] = compression["status"]
                record["filename"] = compression["filename"]
                record["trigger"] = compression["trigger"]
                if "message" not in record or record["message"] in (None, '') :
                    record["message"] = compression["message"]
        return record
    
    def __updateocractivemqstatus(self, ocractivemqjobs, record):
        for ocractivemqjob in ocractivemqjobs:
            if record["documentmasterid"] == ocractivemqjob["documentmasterid"]:
                record["ocractivemqstatus"] = ocractivemqjob["status"]
                record["filename"] = ocractivemqjob["filename"]
                record["trigger"] = ocractivemqjob["trigger"]
                if "message" not in record or record["message"] in (None, '') :
                    record["message"] = ocractivemqjob["message"]
        return record
    
    def __updateazureocrstatus(self, azureocrjobs, record):
        for azureocrjob in azureocrjobs:
            if record["documentmasterid"] == azureocrjob["documentmasterid"]:
                record["azureocrjobstatus"] = "error" if azureocrjob["status"]=="ocrjobfailed" else azureocrjob["status"]
                #record["filename"] = azureocrjob["filename"]
                #record["trigger"] = azureocrjob["trigger"]
                if "message" not in record or record["message"] in (None, '') :
                    record["message"] = azureocrjob["message"]
        return record

    # def __updateproperties_old(self, properties, records, record):
    #     for property in properties:
    #         if record["documentmasterid"] == property["processingparentid"] or (
    #             property["processingparentid"] is None
    #             and record["documentmasterid"] == property["documentmasterid"]
    #         ):
    #             record["pagecount"] = property["pagecount"]
    #             (
    #                 record["isduplicate"],
    #                 record["duplicatemasterid"],
    #                 record["duplicateof"],
    #             ) = self.__isduplicate(properties, record)
    #             record["filename"] = property["filename"]
    #     """Begin        
    #     Below block is a temporary workaround to verify duplicate in msg.
    #     This verifies the duplicate with the parent hashcode and filename
    #     """
    #     if (
    #         record["isduplicate"] == False
    #         and record["parentid"] is not None
    #         and record["filepath"].endswith(".msg")
    #     ):
    #         _uploaded = self.__getuploadedrecord(records, record["parentid"])
    #         _occurances = [d for d in properties if d["filename"] == record["filename"]]
    #         if len(_occurances) > 1:
    #             (
    #                 record["isduplicate"],
    #                 record["duplicatemasterid"],
    #                 record["duplicateof"],
    #             ) = self.__isduplicate(properties, _uploaded)
    #             if record["isduplicate"] == True:
    #                 filtered = [
    #                     x["processingparentid"]
    #                     for x in properties
    #                     if x["filename"] == record["filename"]
    #                 ]
    #                 record["duplicatemasterid"] = min(filtered)
    #                 record["duplicateof"] = self.__getduplicateof(
    #                     properties, record, record["duplicatemasterid"]
    #                 )
    #     """End

    #     Duplicate block check end
    #     """
    #     return record

    def __updateredactionstatus(self, redactions, record):
        for entry in redactions:
            if record["documentmasterid"] == entry["processingparentid"] or (
                entry["processingparentid"] is None
                and record["documentmasterid"] == entry["documentmasterid"]
            ):
                record["isredactionready"] = entry["isredactionready"]
        return record

    def __isduplicate(self, properties, record):
        matchedhash = None
        isduplicate = False
        duplicatemasterid = record["documentmasterid"]
        duplicateof = record["filename"] if "filename" in record else None
        for property in properties:
            if property["processingparentid"] == record["documentmasterid"] or (
                property["processingparentid"] is None
                and record["documentmasterid"] == property["documentmasterid"]
            ):
                matchedhash = property["rank1hash"]

        filtered = []
        for x in properties:
            if x["rank1hash"] == matchedhash:
                value = (
                    x["processingparentid"]
                    if x["processingparentid"] is not None
                    else x["documentmasterid"]
                )
                filtered.append(value)
        if len(filtered) > 1 and filtered not in (None, []):
            originalid = min(filtered)
            if originalid != record["documentmasterid"]:
                isduplicate = True
                duplicatemasterid = originalid
                duplicateof = self.__getduplicateof(properties, record, originalid)
        return isduplicate, duplicatemasterid, duplicateof

    def __getduplicateof(self, properties, record, duplicatemasterid):
        duplicateof = record["filename"] if "filename" in record else None
        if duplicateof is None:
            return None
        for z in properties:
            if (duplicatemasterid == z["processingparentid"]) or (
                z["processingparentid"] is None
                and duplicatemasterid == z["documentmasterid"]
            ):
                duplicateof = z["filename"]
        return duplicateof

    def __getuploadedrecord(self, records, masterid):
        for record in records:
            if record["documentmasterid"] == masterid:
                if record["parentid"] is None and record["recordid"] is not None:
                    return record
                else:
                    return self.__getuploadedrecord(records, record["parentid"])
        return None

    def deletedocument(self, payload, userid):
        """Inserts document into list of deleted documents"""
        result = DocumentDeleted.create(
            [
                DocumentDeleted(
                    filepath=path.splitext(filepath)[0],
                    ministryrequestid=payload["ministryrequestid"],
                    deleted=True,
                    createdby=userid,
                    created_at=datetime2.now(),
                )
                for filepath in payload["filepaths"]
            ]
        )
        if result.success:
                streamobject = {
                        'ministryrequestid': payload["ministryrequestid"]
                    }
                row = PageCalculatorJob(
                    version=1,
                    ministryrequestid=payload["ministryrequestid"],
                    inputmessage=streamobject,
                    status='pushedtostream',
                    createdby='delete'
                )
                job = PageCalculatorJob.insert(row)
                streamobject["jobid"] = job.identifier
                streamobject["createdby"] = 'delete'
                eventqueueproducerservice().add(pagecalculatorstreamkey, streamobject)
        return result

    def updatedocumentattributes(self, payload, userid):
        """update document attributes"""

        docattributeslist = DocumentAttributes.getdocumentattributesbyid(
            payload["documentmasterids"]
        )
        oldRows = []
        newRows = []
        for docattributes in docattributeslist:
            oldRows.append(
                {
                    "attributeid": docattributes["attributeid"],
                    "version": docattributes["version"],
                    "documentmasterid": docattributes["documentmasterid"],
                    "attributes": docattributes["attributes"],
                    "createdby": docattributes["createdby"],
                    "created_at": docattributes["created_at"],
                    "updatedby": userid,
                    "updated_at": datetime2.now(),
                    "isactive": False,
                }
            )
            newdocattributes = json.loads(json.dumps(docattributes["attributes"]))
            if 'divisions' in payload:
                newdocattributes["divisions"] = payload["divisions"]
            if 'rotatedpages' in payload:
                if 'rotatedpages' not in newdocattributes:
                    newdocattributes['rotatedpages'] = {}
                newdocattributes['rotatedpages'].update(payload["rotatedpages"])
            newRows.append(
                DocumentAttributes(
                    version=docattributes["version"] + 1,
                    documentmasterid=docattributes["documentmasterid"],
                    attributes=newdocattributes,
                    createdby=docattributes["createdby"],
                    created_at=docattributes["created_at"],
                    isactive=True,
                )
            )

        return DocumentAttributes.update(newRows, payload["documentmasterids"])

    def updatedocumentpersonalattributes(self, payload, userid):
        """update document attributes"""

        docattributeslist = DocumentAttributes.getdocumentattributesbyid(
            payload["documentmasterids"]
        )
        oldRows = []
        newRows = []
        for docattributes in docattributeslist:
            oldRows.append(
                {
                    "attributeid": docattributes["attributeid"],
                    "version": docattributes["version"],
                    "documentmasterid": docattributes["documentmasterid"],
                    "attributes": docattributes["attributes"],
                    "createdby": docattributes["createdby"],
                    "created_at": docattributes["created_at"],
                    "updatedby": userid,
                    "updated_at": datetime2.now(),
                    "isactive": False,
                }
            )
            newdocattributes = json.loads(json.dumps(docattributes["attributes"]))
            if payload["personalattributes"] is not None:
                #apply change to all
                if(len(payload["documentmasterids"]) > 1):
                    for attribute in payload["personalattributes"]:
                        if(payload["personalattributes"][attribute] is not None and len(payload["personalattributes"][attribute]) > 0):
                            if 'personalattributes' not in newdocattributes:
                                newdocattributes['personalattributes'] = {}
                            newdocattributes["personalattributes"][attribute]=payload["personalattributes"][attribute]
                #apply change to individual
                else:
                    newdocattributes["personalattributes"] = payload["personalattributes"]
            newRows.append(
                DocumentAttributes(
                    version=docattributes["version"] + 1,
                    documentmasterid=docattributes["documentmasterid"],
                    attributes=newdocattributes,
                    createdby=docattributes["createdby"],
                    created_at=docattributes["created_at"],
                    isactive=True,
                )
            )

        return DocumentAttributes.update(newRows, payload["documentmasterids"])
    
    
    def getdocuments(self, requestid,bcgovcode):
        divisions_data = requests.request(
                method='GET',
                url=requestapiurl + "/api/foiflow/divisions/{0}".format(bcgovcode) + "/all",
                headers={'Authorization': AuthHelper.getauthtoken(), 'Content-Type': 'application/json'}
            ).json()
        divisions = {div['divisionid']: div for div in divisions_data['divisions']}
        documentdivisionids=set()
        filtered_maps=[]
        documents = {
            document["documentmasterid"]: document
            for document in self.getdedupestatus(requestid)
        }
        attachments = []
        for documentid in documents:
            _attachments = documents[documentid].pop("attachments", [])
            for attachment in _attachments:
                attachments.append(attachment)

        for attachment in attachments:
            documents[attachment["documentmasterid"]] = attachment

        removeids = []
        for documentid in documents:
            document = documents[documentid]
            # removed "or document['attributes'].get('incompatible', False)" from below if condition
            # to include incompatible files as part of documents.
            # Related to redline download changes.
            # if document['attributes'].get('isportfolio', False) or document['attributes'].get('incompatible', False) or not document['isredactionready']:
            if (
                document["attributes"].get("isportfolio", False)
                or not document["isredactionready"]
            ):
                removeids.append(document["documentmasterid"])
            elif document.get("isduplicate", False):
                documents[document["duplicatemasterid"]]["attributes"][
                    "divisions"
                ].extend(document["attributes"]["divisions"])
                removeids.append(document["documentmasterid"])
        for id in removeids:
            documents.pop(id)

        for documentid in documents:
            document = documents[documentid]
            documentdivisions = set(
                map(lambda d: d["divisionid"], document["attributes"]["divisions"])
            )
            document["attributes"]["divisions"] = list(
                map(lambda d: {"divisionid": d}, documentdivisions)
            )
            document["divisions"] = list(map(lambda d: divisions[d], documentdivisions))
            documentdivisionids.update(documentdivisions)

            # For replaced attachments, change filepath to .pdf instead of original extension
            if "trigger" in document["attributes"] and document["attributes"]["trigger"] == "recordreplace":
                base_path, current_extension = path.splitext(document["filepath"])
                document["filepath"] = base_path + ".pdf"

        filtered_maps=([item for item in divisions_data['divisions'] if item["divisionid"] in documentdivisionids])
        return filtered_maps,[documents[documentid] for documentid in documents]

    def getdocument(self, documentid):
        return Document.getdocument(documentid)

    def getdocumentbyids(self, documentids):
        return Document.getdocumentsbyids(documentids)

    def savedocument(self, documentid, documentversion, newfilepath, userid):
        return

    def deleterequestdocument(self, documentid, documentversion):
        return
    
    def getfilepathbydocumentid(self, documentid):
        return DocumentMaster.getfilepathbydocumentid(documentid)
    
    
    def validate_oipcreviewlayer(self, request_json, requestid):
        #check for OIPC & Reason 
        if 'isoipcreview' in request_json and request_json['isoipcreview'] == True and any((oipc['reasonid'] == 2 and oipc['outcomeid'] is None)for oipc in request_json['oipcdetails']):
            #Check for Reopen
            if 'isreopened' in request_json and request_json['isreopened'] == True:
                #Check is Response Package generated before closure.
                generatedbefore = self.__get_close_datetime(request_json)
                if generatedbefore is not None:
                    is_responsepackage_generated = pdfstitchpackageservice().isresponsepackagecreated(requestid, generatedbefore)
                    return is_responsepackage_generated
        return False  
    
    def __get_close_datetime(self, request_json):
        generatedbefore = None
        isresponsephasecompleted = False
        for state in request_json['stateTransition']:
            if state['status'] == StateName.closed.value and generatedbefore is None:     
                generatedbefore =  state['created_at']
            if state['status'] == StateName.response.value and isresponsephasecompleted == False:    
                isresponsephasecompleted = True    
        return generatedbefore if isresponsephasecompleted == True else None
    
    def updateselectedfileprocessversion(self, request_json, userid):
        documentmasterids = request_json["documentmasterids"]
        ministryrequestid = request_json["ministryrequestid"]
        recordretrieveversion = request_json["recordretrieveversion"]
        selectedfileprocessversion = DocumentProcesses.getdocumentprocessidbyname("compression")
        if recordretrieveversion == 'retrive_uncompressed' or "uncompressed" in recordretrieveversion:
            selectedfileprocessversion= DocumentProcesses.getdocumentprocessidbyname("dedupe")
        print("selectedfileprocessversion:", selectedfileprocessversion)
        return Document.updateselectedfileprocessversion(ministryrequestid,documentmasterids,selectedfileprocessversion, userid)


    def getdocumentfilepath(self, documentid):
        return DocumentMaster.getfilepathbydocumentid(documentid)
        
