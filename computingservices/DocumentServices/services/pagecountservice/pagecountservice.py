import traceback
import json
from services.dal.pagecount.documentservice import documentservice

class pagecountservice():

    def calculatepagecount(self, message):
        try:
            deleted = documentservice().getdeleteddocuments(message.ministryrequestid)
            records = documentservice().getdocumentmaster(message.ministryrequestid, deleted)
            print(f'records = {records}')
        except (Exception) as error:
            print('error occured in pagecount calculation service: ', error)