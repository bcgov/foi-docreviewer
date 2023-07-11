from reviewer_api.models.Keywords import Keyword

class keywordservice:

    
    def getallkeywords(self):
        keywords = Keyword.getall()
        print("keywords:",keywords)
        return keywords
  