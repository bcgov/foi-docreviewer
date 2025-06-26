from reviewer_api.models.FileConversionJob import FileConversionJob
from reviewer_api.models.DeduplicationJob import DeduplicationJob
from reviewer_api.models.PDFStitchJob import PDFStitchJob
from reviewer_api.models.PageCalculatorJob import PageCalculatorJob
from reviewer_api.models.DocumentMaster import DocumentMaster
from reviewer_api.models.DocumentAttributes import DocumentAttributes
from reviewer_api.services.annotationservice import annotationservice
from reviewer_api.services.documentpageflagservice import documentpageflagservice
from reviewer_api.models.PDFStitchJobAttributes import PDFStitchJobAttributes
from reviewer_api.auth import auth, AuthHelper
from datetime import datetime as datetime2
from reviewer_api.utils.constants import FILE_CONVERSION_FILE_TYPES, DEDUPE_FILE_TYPES
import json, os
import asyncio
from reviewer_api.utils.util import pstformat
from reviewer_api.models.CompressionJob import CompressionJob
from reviewer_api.models.OCRActiveMQJob import OCRActiveMQJob

class jobrecordservice:
    conversionstreamkey = os.getenv('FILE_CONVERSION_STREAM_KEY')
    dedupestreamkey = os.getenv('DEDUPE_STREAM_KEY')

    def insertpdfstitchjobstatus(self, message, userid):
        row = PDFStitchJob(
                    version=1,
                    ministryrequestid=message['ministryrequestid'],
                    inputfiles=message['inputfiles'],
                    status='pushedtostream',
                    category= self.__assigncategory(message['category']),
                    createdby=userid
                )
        job = PDFStitchJob.insert(row)
        return job
    
    def __assigncategory(self, category):
        if "phase" in category:
            if "redline" in category:
                return "redline"
            else:
                return "responsepackage"
        return category
    
    def getpdfstitchjobstatus(self, requestid, category):
        if category == "redlinephase" or category == "responsepackagephase":
            package = "redline" if category == 'redlinephase' else "responsepackage"
            job = PDFStitchJob.getpdfstitchjobphasestatuses(requestid, package)
            return job
        job = PDFStitchJob.getpdfstitchjobstatus(requestid, category)
        return job
    
    def recordjobstatus(self, batchinfo, userid):
        """ Insert entry into correct job record table.
        """
        jobids = {}
        for record in batchinfo['records']:
            _filename, extension = os.path.splitext(record['s3uripath'])
            extension = extension.lower()
            if 'service' in record and record['service'] == 'compression' and batchinfo['trigger'] == 'recordretry':
                masterid = record['documentmasterid']
                row = CompressionJob(
                    version=1,
                    batch=batchinfo['batch'],
                    ministryrequestid=batchinfo['ministryrequestid'],
                    trigger=batchinfo['trigger'],
                    documentmasterid=masterid,
                    filename=record['filename'],
                    status='pushedtostream'
                )
                job = CompressionJob.insert(row)
                jobids[record['s3uripath']] = {'masterid': masterid, 'jobid': job.identifier}
            elif 'service' in record and record['service'] == 'ocr' and batchinfo['trigger'] == 'recordretry':
                masterid = record['documentmasterid']
                print("masterid:",masterid)
                row = OCRActiveMQJob(
                    version=1,
                    batch=batchinfo['batch'],
                    ministryrequestid=batchinfo['ministryrequestid'],
                    trigger=batchinfo['trigger'],
                    documentmasterid=masterid,
                    filename=record['filename'],
                    status='pushedtostream'
                )
                job = OCRActiveMQJob.insert(row)
                jobids[record['s3uripath']] = {'masterid': masterid, 'jobid': job.identifier}
                print("jobids:",jobids)
            elif extension in FILE_CONVERSION_FILE_TYPES:
                if batchinfo['trigger'] == 'recordupload':
                    master = DocumentMaster.create(
                        DocumentMaster(
                            filepath=record['s3uripath'],
                            ministryrequestid=batchinfo['ministryrequestid'],
                            recordid=record['recordid'],
                            isredactionready=False,
                            createdby=userid
                        )
                    )
                    masterid = master.identifier
                    print("Conversion-Attributes-replace:",record['attributes'])
                    DocumentAttributes.create(
                        DocumentAttributes(
                            documentmasterid=masterid,
                            attributes=record['attributes'],
                            createdby=userid,
                            version=1
                        )
                    )
                else:
                    masterid = record['documentmasterid']
                row = FileConversionJob(
                    version=1,
                    batch=batchinfo['batch'],
                    ministryrequestid=batchinfo['ministryrequestid'],
                    trigger=batchinfo['trigger'],
                    inputdocumentmasterid=masterid,
                    filename=record['filename'],
                    status='pushedtostream'
                )
                job = FileConversionJob.insert(row)
                jobids[record['s3uripath']] = {'masterid': masterid, 'jobid': job.identifier}
            elif extension in DEDUPE_FILE_TYPES:
                if batchinfo['trigger'] in ['recordupload', 'recordreplace']:
                    if batchinfo['trigger'] == 'recordreplace':
                        userinfo = AuthHelper.getuserinfo()
                        userinfo['trigger'] = batchinfo['trigger']
                        documentids = DocumentMaster.getprocessingchilddocumentids(record.get('documentmasterid'))
                        asyncio.ensure_future(annotationservice().deactivatedocumentannotations(documentids, userinfo))
                        # asyncio.ensure_future(documentpageflagservice().bulkarchivedocumentpageflag(batchinfo['ministryrequestid'], documentids, userinfo))
                    master = DocumentMaster.create(
                        DocumentMaster(
                            filepath=record['s3uripath'],
                            ministryrequestid=batchinfo['ministryrequestid'],
                            recordid=record['recordid'] if batchinfo['trigger'] == 'recordupload' else None,
                            processingparentid=record.get('documentmasterid') if batchinfo['trigger'] == 'recordreplace' else None,
                            isredactionready=False,
                            createdby=userid
                        )
                    )
                    masterid = master.identifier
                    ## Since replace attachment uses the same s3 uri path
                    ## need to set redactionready-false as the new file need to go through all the process again
                    if batchinfo['trigger'] == 'recordreplace' and record['isattachment'] == True:
                        _documentmasterid = record.get('documentmasterid')
                        if _documentmasterid:
                            DocumentMaster.updateredactionstatus(_documentmasterid, userid)
                    print("Attributes-replace:",record['attributes'])
                    DocumentAttributes.create(
                        DocumentAttributes(
                            documentmasterid=masterid,
                            attributes=record['attributes'],
                            createdby=userid,
                            version=1
                        )
                    )
                else:
                    masterid = record['documentmasterid']
                row = DeduplicationJob(
                    version=1,
                    batch=batchinfo['batch'],
                    ministryrequestid=batchinfo['ministryrequestid'],
                    type='rank1',
                    trigger=batchinfo['trigger'],
                    documentmasterid=masterid,
                    filename=record['filename'],
                    status='pushedtostream'
                )
                job = DeduplicationJob.insert(row)
                jobids[record['s3uripath']] = {'masterid': masterid, 'jobid': job.identifier}
            else:
                jobids[record['s3uripath']] = {'error': 'Invalid file type'}
        return jobids
    

    def insertpagecalculatorjobstatus(self, message, userid):
        row = PageCalculatorJob(
                    version=1,
                    ministryrequestid=message['ministryrequestid'],
                    inputmessage=message,
                    status='pushedtostream',
                    createdby=userid
                )
        job = PageCalculatorJob.insert(row)
        return job
    
    def insertpdfstitchjobattributes(self, message, pdfstitchjobid, userid):
        row = PDFStitchJobAttributes(
                    pdfstitchjobid=pdfstitchjobid,
                    version=1,
                    ministryrequestid=message['ministryrequestid'],
                    attributes=message['pdfstitchjobattributes'],
                    createdby=userid
                )
        job = PDFStitchJobAttributes.insert(row)
        return job

    def isbalancefeeoverrodforrequest(self, requestid):
        pdfstitchjobattributes= PDFStitchJobAttributes().getpdfstitchjobattributesbyid(requestid)
        isbalancefeeoverrode= False if pdfstitchjobattributes is None or not pdfstitchjobattributes else True
        return isbalancefeeoverrode
