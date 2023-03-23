from reviewer_api.models.FileConversionJob import FileConversionJob
from reviewer_api.models.DeduplicationJob import DeduplicationJob
from reviewer_api.models.PDFStitchJob import PDFStitchJob
from reviewer_api.models.DocumentMaster import DocumentMaster
from reviewer_api.models.DocumentAttributes import DocumentAttributes
from datetime import datetime as datetime2
from reviewer_api.utils.constants import FILE_CONVERSION_FILE_TYPES, DEDUPE_FILE_TYPES
import json, os
from reviewer_api.utils.util import pstformat

class jobrecordservice:
    conversionstreamkey = os.getenv('FILE_CONVERSION_STREAM_KEY')
    dedupestreamkey = os.getenv('DEDUPE_STREAM_KEY')

    def insertpdfstitchjobstatus(self, message, userid):
        row = PDFStitchJob(
                    version=1,
                    ministryrequestid=message['ministryrequestid'],
                    inputfiles=message['inputfiles'],
                    status='pushedtostream',
                    category= message['category'],
                    createdby=userid
                )
        job = PDFStitchJob.insert(row)
        return job
    
    def getpdfstitchjobstatus(self, requestid, category):
        job = PDFStitchJob.getpdfstitchpackage(requestid, category)
        return job
    
    def recordjobstatus(self, batchinfo, userid):
        """ Insert entry into correct job record table.
        """
        jobids = {}
        for record in batchinfo['records']:
            _filename, extension = os.path.splitext(record['s3uripath'])
            if extension in FILE_CONVERSION_FILE_TYPES:
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
                    DocumentAttributes.create(
                        DocumentAttributes(
                            documentmasterid=masterid,
                            attributes=record['attributes'],
                            createdby=userid
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
                    master = DocumentMaster.create(
                        DocumentMaster(
                            filepath=record['s3uripath'],
                            ministryrequestid=batchinfo['ministryrequestid'],
                            recordid=record['recordid'] if batchinfo['trigger'] == 'recordupload' else None,
                            processingparentid=record.get('documentmasterid') if batchinfo['trigger'] == 'recordreplace' else None,
                            isredactionready=True,
                            createdby=userid
                        )
                    )
                    masterid = master.identifier
                    DocumentAttributes.create(
                        DocumentAttributes(
                            documentmasterid=masterid,
                            attributes=record['attributes'],
                            createdby=userid
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
                jobids[record['s3uripath']] = 'Invalid file type'
        return jobids