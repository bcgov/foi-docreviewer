import sys
import random
from walrus import Database


def main(stream_key):
    rdb = Database(host='192.168.4.26', port=7379)

    stream = rdb.Stream(stream_key)

    msg_id = stream.add(
       
        # {'s3filepath': 'https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2024-16010730/a4e28721-adcb-4119-839e-4149b4b3421f.pdf', 'filename': 'Policy Summary.pdf', 'ministryrequestid': '22', 'documentmasterid': '380', 'trigger': 'recordupload'}
        # {'s3filepath': 'https://citz-foi-prod.objectstore.gov.bc.ca/edu-dev-e/EDU-2024-16010636/ee909132-8a96-451d-a681-c230a4d5a278.pdf', 'filename': 'Policy Summary.pdf', 'hashcode': '2f472e8be54a4cbdcb2437a96e2fdbc64429708d', 'pagecount': '2', 'ministryrequestid': '21', 'documentmasterid': '387', 'trigger': 'recordupload'}
        {'filename': 'Policy Summary - Copy.pdf', 'pagecount': '2', 'ministryrequestid': '21', 'documentmasterid': '388', 'trigger': 'recordupload'}
        ,
        id="*"
    )
    print(f"message {msg_id} sent")


if __name__ == "__main__":
    stream_key = "CALCULATE-PAGE-COUNT"
    #sensor = sys.argv[1]
    main(stream_key)
