from reviewer_api.models.Sections import Section

class sectionservice:

    def getsections(self):
        """ Returns the active records
        """
        return Section.getall()

