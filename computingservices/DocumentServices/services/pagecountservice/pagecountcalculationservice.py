
import traceback
import json
from .pagecountservice import pagecountservice

class pagecountcalculationservice():

    def processmessage(self, message):
        try:
            records = pagecountservice().calculatepagecount(message)
            print(f"records == {records}")

        except (Exception) as error:
            print('error occured in pagecount calculation service: ', error)