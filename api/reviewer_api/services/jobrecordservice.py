from reviewer_api.models.FileConversionJob import FileConversionJob
from reviewer_api.models.DeduplicationJob import DeduplicationJob
from datetime import datetime as datetime2
from reviewer_api.utils.constants import FILE_CONVERSION_FILE_TYPES, DEDUPE_FILE_TYPES
import json, os
from reviewer_api.utils.util import pstformat

class jobrecordservice:
    conversionstreamkey = os.getenv('FILE_CONVERSION_STREAM_KEY')
    dedupestreamkey = os.getenv('DEDUPE_STREAM_KEY')

    def recordjobstatus(self, batchinfo):
        """ Insert entry into correct job record table.
        """
        jobids = {}
        for record in batchinfo['records']:
            _filename, extension = os.path.splitext(record['s3uripath'])
            if extension in FILE_CONVERSION_FILE_TYPES:
                row = FileConversionJob(
                    version=1,
                    batch=batchinfo['batch'],
                    ministryrequestid=batchinfo['ministryrequestid'],
                    trigger=batchinfo['trigger'],
                    inputfilepath=record['s3uripath'],
                    filename=record['filename'],
                    status='pushedtostream'
                )
                response = FileConversionJob.insert(row)
                jobids[record['s3uripath']] = response.identifier
            elif extension in DEDUPE_FILE_TYPES:
                row = DeduplicationJob(
                    version=1,
                    batch=batchinfo['batch'],
                    ministryrequestid=batchinfo['ministryrequestid'],
                    type='rank1',
                    trigger=batchinfo['trigger'],
                    filepath=record['s3uripath'],
                    filename=record['filename'],
                    status='pushedtostream'
                )
                response = DeduplicationJob.insert(row)
                jobids[record['s3uripath']] = response.identifier
            else:
                jobids[record['s3uripath']] = 'Invalid file type'
        return jobids