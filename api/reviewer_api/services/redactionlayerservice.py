from reviewer_api.models.RedactionLayers import RedactionLayer

import json

class redactionlayerservice:

    def getredactionlayers(self, ministryrequestid):
        return RedactionLayer.getall(ministryrequestid)
    
    def getall(self):
        return RedactionLayer.getlayers()


    def getdefaultredactionlayerid(self):
        _redactionlayer =  RedactionLayer.getredlineredactionlayer()  
        return _redactionlayer["redactionlayerid"]
    
    def getredactionlayerid(self, name):
        _name = self.__normalise(name)
        layers = RedactionLayer.getlayers()
        for layer in layers:
            if (self.__normalise(layer['name']) == _name):
                return layer["redactionlayerid"]
        return 0
    

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
    
    