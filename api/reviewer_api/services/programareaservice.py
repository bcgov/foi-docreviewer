from reviewer_api.models.ProgramAreas import ProgramArea

class programareaservice:

    def getprogramareas(self):
        """ Returns the active records
        """
        return ProgramArea.getprogramareas()

    def getprogramareasforministryuser(self, groups = None):
        """ Returns the active records
        """
        return ProgramArea.getprogramareasforministryuser(groups)