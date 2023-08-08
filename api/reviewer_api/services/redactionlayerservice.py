from reviewer_api.models.RedactionLayers import RedactionLayer

import json

class redactionlayerservice:

    def getredactionlayers(self):
        return RedactionLayer.getall()


    def getdefaultredactionlayerid(self):
        _redactionlayer =  RedactionLayer.getredlineredactionlayer()    
        return _redactionlayer["redactionlayerid"]
    