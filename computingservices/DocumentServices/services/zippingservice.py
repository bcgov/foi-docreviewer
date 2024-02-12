
import json
from rstreamio.writer.zipperstreamwriter import zipperstreamwriter

class zippingservice():

    def sendtozipper(self, summaryfiles, message):
        updatedmessage = zippingservice().preparemessageforzipperservice(summaryfiles, message)
        print('updatedmessage',updatedmessage)
        zipperstreamwriter().sendmessage(updatedmessage)

    def preparemessageforzipperservice(self,updatedfilestozip, message):
        try:
            msgjson= json.loads(message)
            filestozip_list = msgjson['filestozip']+updatedfilestozip
            msgjson['filestozip'] = self.to_json(filestozip_list)
            msgjson['attributes'] = self.to_json(msgjson['attributes'])
            msgjson['summarydocuments'] = self.to_json(msgjson['summarydocuments'])
            return msgjson
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)

    def to_json(self, obj):
        return json.dumps(obj, default=lambda obj: obj.__dict__)

