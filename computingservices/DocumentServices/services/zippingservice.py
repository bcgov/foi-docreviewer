
import json
from rstreamio.writer.zipperstreamwriter import zipperstreamwriter

class zippingservice():

    def sendtozipper(self, summaryfiles, message):
        updatedmessage = zippingservice().preparemessageforzipperservice(summaryfiles, message)
        zipperstreamwriter().sendmessage(updatedmessage)

    def preparemessageforzipperservice(self,summaryfiles, message):
        try:
            msgjson= json.loads(message)
            if summaryfiles and len(summaryfiles) > 0:                
                filestozip_list = json.loads(msgjson['filestozip'])+summaryfiles
            else:
                filestozip_list = json.loads(msgjson['filestozip'])
            print('filestozip_list: ', filestozip_list)
            msgjson['filestozip'] = self.to_json(filestozip_list)   
            msgjson['attributes'] = self.to_json(msgjson['attributes'])
            msgjson['summarydocuments'] = self.to_json(msgjson['summarydocuments'])         
            return msgjson
        except (Exception) as error:
            print('error occured in zipping service: ', error)

    def to_json(self, obj):
        return json.dumps(obj, default=lambda obj: obj.__dict__)

