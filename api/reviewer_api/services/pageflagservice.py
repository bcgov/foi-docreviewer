from reviewer_api.models.Pageflags import Pageflag
from reviewer_api.models.ProgramAreas import ProgramArea

import json

class pageflagservice:

    
    def getpageflags(self):
        pageflags = Pageflag.getall()
        programareas = ProgramArea.getprogramareas()
        for entry in pageflags:
            if entry["name"] == "Consult":
                entry["programareas"] = programareas
        return pageflags

    
    