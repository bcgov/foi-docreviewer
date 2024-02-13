from services.dal.pagecount.documentservice import documentservice
from services.dal.pagecount.ministryservice import ministryervice
from utils.basicutils import pstformat

class pagecountservice():

    def calculatepagecount(self, message):
        try:
            requestpagecount = ministryervice().getlatestrecordspagecount(message.ministryrequestid)
            print(f'requestpagecount == {requestpagecount}')
            if requestpagecount in (None, 0) and hasattr(message, "pagecount"):
                calculatedpagecount = message.pagecount
            else:
                calculatedpagecount = self.__calculatepagecount(message)
            print(f'calculatedpagecount == {calculatedpagecount}')
            if requestpagecount != calculatedpagecount:
                ministryervice().updaterecordspagecount(message.ministryrequestid, calculatedpagecount, message.createdby)
            return {'prevpagecount': requestpagecount, 'calculatedpagecount': calculatedpagecount}
        except (Exception) as error:
            print('error occured in pagecount calculation service: ', error)
    
    def __calculatepagecount(self, message):
        records = self.__getdocumentdetails(message)
        print(f'records == {records}')
        page_count = 0
        for record in records:
            if self.__pagecountcalculationneeded(record):
                page_count += record.get("pagecount", 0)
                attachments = record.get("attachments", [])
                for attachment in attachments:
                    if not attachment.get("isduplicate", False):
                        page_count += attachment.get("pagecount", 0)
        return page_count

    def __pagecountcalculationneeded(self, record):
        if not record.get("isduplicate", False) and not record["attributes"].get("isportfolio", False) and not record['attributes'].get('incompatible', False):
            return True
        return False

    def __getdocumentdetails(self, message):
        deleted = documentservice().getdeleteddocuments(message.ministryrequestid)
        dedupes = documentservice().getdedupestatus(message.ministryrequestid)
        records = documentservice().getdocumentmaster(message.ministryrequestid, deleted)        
        properties = documentservice().getdocumentproperties(message.ministryrequestid, deleted)
        for record in records:
            record["duplicatemasterid"] = record["documentmasterid"]
            record["ministryrequestid"] = message.ministryrequestid
            record["isattachment"] = True if record["parentid"] is not None else False
            record["created_at"] = pstformat(record["created_at"])
            record = self.__updatededupestatus(dedupes, record)
            if record["recordid"] is not None:
                record["attachments"] = self.__getattachments(records, record["documentmasterid"], [])

        # Duplicate check
        finalresults = []
        (
            parentrecords,
            parentswithattachmentsrecords,
            attachmentsrecords,
        ) = self.__filterrecords(records)
        parentproperties = self.__getrecordsproperties(parentrecords, properties)

        for record in records:
            if record["recordid"] is not None:
                finalresult = self.__updateproperties(
                    properties,
                    record,
                    parentproperties,
                    parentswithattachmentsrecords,
                    attachmentsrecords,
                )
                finalresults.append(finalresult)

        return finalresults
    
    def __updatededupestatus(self, dedupes, record):
        for dedupe in dedupes:
            if record["documentmasterid"] == dedupe["documentmasterid"]:
                record["filename"] = dedupe["filename"]
        return record

    def __getattachments(self, records, documentmasterid, result=None):
        if not result:
            result = []
        for entry in records:
            if entry["recordid"] is None:
                if entry["parentid"] not in [None, ""] and int(entry["parentid"]) == int(documentmasterid):
                    result.append(entry)
                    result = self.__getattachments(
                        records, entry["documentmasterid"], result
                    )
        return result

    def __filterrecords(self, records):
        parentrecords = []
        parentswithattachments = []
        attchments = []
        for record in records:
            if record["recordid"] is not None:
                parentrecords.append(record)
            if "attachments" in record and len(record["attachments"]) > 0:
                parentswithattachments.append(record)
            if record["recordid"] is None:
                attchments.append(record)
        return parentrecords, parentswithattachments, attchments
    
    def __getrecordsproperties(self, records, properties):
        filtered = []
        for record in records:
            for property in properties:
                if property["processingparentid"] == record["documentmasterid"] or (
                    property["processingparentid"] is None
                    and record["documentmasterid"] == property["documentmasterid"]
                ):
                    filtered.append(property)
        return filtered
    
    def __updateproperties(
        self,
        properties,
        record,
        parentproperties,
        parentswithattachmentsrecords,
        attachmentsrecords,
    ):
        if record["recordid"] is not None:
            _att_in_properties = []
            (record["pagecount"], record["filename"]) = self.__getpagecountandfilename(record, parentproperties)
            record["isduplicate"], record["duplicatemasterid"] = self.__isduplicate(parentproperties, record)
            if "attachments" in record and len(record["attachments"]) > 0:
                if record["isduplicate"] == True:
                    duplicatemaster_attachments = self.__getduplicatemasterattachments(parentswithattachmentsrecords, record["duplicatemasterid"])
                    if duplicatemaster_attachments is None:
                        _att_in_properties = self.__getattachmentproperties(record["attachments"], properties)
                    else:
                        _att_in_properties = self.__getattachmentproperties(duplicatemaster_attachments + record["attachments"],properties)
                elif len(record["attachments"]) > 0:
                    _att_in_properties = self.__getattachmentproperties(record["attachments"], properties)
                for attachment in record["attachments"]:
                    if len(_att_in_properties) > 1:
                        if attachment["filepath"].endswith(".msg"):                          
                            attachment["isduplicate"], attachment["duplicatemasterid"] = self.__getduplicatemsgattachment(attachmentsrecords, _att_in_properties, attachment)
                        else:
                            attachment["isduplicate"], attachment["duplicatemasterid"] = self.__isduplicate(_att_in_properties, attachment)
                    else:
                        attachment["isduplicate"] = False
                        attachment["duplicatemasterid"] = attachment["documentmasterid"]
                    (attachment["pagecount"], attachment["filename"]) = self.__getpagecountandfilename(attachment, _att_in_properties)
        return record

    def __getpagecountandfilename(self, record, properties):
        pagecount = 0
        filename = record["filename"] if "filename" in record else None
        for property in properties:
            if record["documentmasterid"] == property["processingparentid"] or (
                property["processingparentid"] is None
                and record["documentmasterid"] == property["documentmasterid"]
            ):
                pagecount = property["pagecount"]
                filename = property["filename"]
        return pagecount, filename

    def __getduplicatemasterattachments(self, records, duplicatemasterid):
        return self.__getrecordproperty(records, duplicatemasterid, "attachments")

    def __getrecordproperty(self, records, documentmasterid, property):
        for x in records:
            if x["documentmasterid"] == documentmasterid:
                return x[property]
        return None
    
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
                return attachment["isduplicate"], attachment["duplicatemasterid"]
        return False, attachment["documentmasterid"]

    def __isduplicate(self, properties, record):
        matchedhash = None
        isduplicate = False
        duplicatemasterid = record["documentmasterid"]
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
        return isduplicate, duplicatemasterid