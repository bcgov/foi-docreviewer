from reviewer_api.models.RedactionLayers import RedactionLayer

import json

class redactionlayerservice:

    def getredactionlayers(self, ministryrequestid):
        return RedactionLayer.getall(ministryrequestid)


    def getdefaultredactionlayerid(self):
        _redactionlayer =  RedactionLayer.getredlineredactionlayer()  
        return _redactionlayer["redactionlayerid"]
    
    def getmappedredactionlayers(self, redactionlayer):     
        mpxlayers = []  
        mpxlayers.append(redactionlayer["redactionlayerid"])
        return mpxlayers

    def validateredactionlayer(self, name, ministryrequestid):
        _name = self.__normalise(name)
        layers = self.getredactionlayers(ministryrequestid)
        for layer in layers:
            if (self.__normalise(layer['name']) == _name):
                return True, layer
        return False, None
                
    def __normalise(self, name):
        _name = name.replace(' ', '')
        _name = _name.lower()
        return _name
    
    