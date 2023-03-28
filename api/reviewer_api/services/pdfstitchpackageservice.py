from reviewer_api.models.PDFStitchPackage import PDFStitchPackage


class pdfstitchpackageservice:

    def getpdfstitchpackage(self, requestid, category):
        """ Returns the active records
        """
        return PDFStitchPackage.getpdfstitchpackage(requestid, category)
