from reviewer_api.models.BCGovIDIRs import BCGovIDIR

class bcgovidirservice:



    def get_idirs_by_samaccountnames(self, samaccountnames):
        """
        Accepts an array of sAMAccountName strings and returns matching BCGovIDIR records.
        """
        if not samaccountnames or not isinstance(samaccountnames, list):
            return []
        return BCGovIDIR.fetch_by_samaccountnames(samaccountnames)