from reviewer_api.models.DocumentDeletedPages import DocumentDeletedPage
from reviewer_api.services.redactionlayerservice import redactionlayerservice

class docdeletedpageservice:

    def deletepages(self, ministryid, redactionlayer, docdeletedpage, userinfo):
        layerid = self.__getredactionlayerid(redactionlayer)
        result = DocumentDeletedPage().create(ministryid, layerid, docdeletedpage, userinfo)
        return result

    def getdeletedpages(self, ministryid, redactionlayer):
        layerid = self.__getredactionlayerid(redactionlayer)
        deletedpages = DocumentDeletedPage().getdeletedpages(ministryid, layerid)
        documentpages = {}
        for entry in deletedpages:
            pagemetadata = entry["pagemetadata"]
            for dpage in pagemetadata["documentpages"]:
                if dpage["docid"] not in documentpages:
                    documentpages[dpage["docid"]] = dpage["pages"]
                else:
                    documentpages[dpage["docid"]] = documentpages[dpage["docid"]]+ dpage["pages"]
        return documentpages
                


    def __getredactionlayerid(self, layername):
        return redactionlayerservice().getredactionlayerid(layername)

