from reviewer_api.models.RedactionLayers import RedactionLayer

import json

class redactionlayerservice:

    def getredactionlayers(self):
        return RedactionLayer.getall()


    def getdefaultredactionlayerid(self):
        _redactionlayer =  RedactionLayer.getredlineredactionlayer()  
        return _redactionlayer["redactionlayerid"]
    
    def getmappedredactionlayers(self, redactionlayer):     
        mpxlayers = []  
        defaultlayerid = self.getdefaultredactionlayerid()
        if redactionlayer["redactionlayerid"] != defaultlayerid:
            mpxlayers.append(defaultlayerid)      
        mpxlayers.append(redactionlayer["redactionlayerid"])
        return mpxlayers

    def validateredactionlayer(self, name):
        _name = self.__normalise(name)
        layers = self.getredactionlayers()
        for layer in layers:
            if (self.__normalise(layer['name']) == _name):
                return True, layer
        return False, None
                
    def __normalise(self, name):
        _name = name.replace(' ', '')
        _name = _name.lower()
        return _name
    
    