from reviewer_api.models.PDFStitchPackage import PDFStitchPackage
from reviewer_api.models.PDFStitchJob import PDFStitchJob
from reviewer_api.services.jobrecordservice import jobrecordservice


class pdfstitchpackageservice:

    def getpdfstitchpackage(self, requestid, category):
        """ Returns the active records
        """
        return PDFStitchPackage.getpdfstitchpackage(requestid, category)

    def getrecordschanged(self, requestid, category):
        job = jobrecordservice().getpdfstitchjobstatus(requestid, category)
        if job is not None and len(job) > 0:
            jobid = job.get("pdfstitchjobid")
            print("jobid = ", jobid)
            return PDFStitchJob.getrecordschanged(requestid, category, jobid)
        return {"recordchanged": False}

