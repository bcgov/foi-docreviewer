from services.dal.documentpageflag import documentpageflag
import json

class redactionsummary():

    def prepareredactionsummary(self, message):
        try:
            documentids = json.loads(message.summarydocuments)
            redactionlayerid = message.redactionlayerid
            docpagedata = documentpageflag().getpagecount_by_documentid(message.ministryrequestid, documentids)
            totalpagecount = self.__calculate_totalpages(docpagedata)
            #Get all page flags
            if totalpagecount <=0:
                return 
            pageflags = documentpageflag().get_all_pageflags()
            # Get document page flags
            
            docpageflags = documentpageflag().get_documentpageflag(message.ministryrequestid, redactionlayerid, documentids)
            summarydata = []
            for pageflag in pageflags:
                pagecount = 0
                pageredactions = []
                _data = {}
                _data["flagname"] = pageflag["description"].upper()
                for docid in documentids:
                    docpageflag = docpageflags[docid]
                    filteredpages = self.__get_pages_by_flagid(docpageflag["pageflag"], pagecount, pageflag["pageflagid"])
                    if len(filteredpages) > 0:
                        orginalpagenos = [pg['orginalpageno']for pg in filteredpages]
                        docpagesections = documentpageflag().getsections_by_documentid_pageno(message.ministryrequestid, redactionlayerid, docid, orginalpagenos)
                        pageredactions.extend(self.__get_pagesection_mapping(filteredpages, docpagesections))
                    pagecount = pagecount+docpagedata[docid]["pagecount"]
                if len(pageredactions) >0:
                    _data["pagecount"] = len(pageredactions)
                    _data["sections"] = self.__format_redaction_summary(pageflag["description"], pageredactions)
                    summarydata.append(_data)
            print(summarydata)
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)

    def __format_redaction_summary(self, pageflag, pageredactions):
        totalpages = len(pageredactions)                
        _sortedpageumbers = sorted(pageredactions, key=lambda x: x["stitchedpageno"])
        #prepare ranges: Begin
        formatted = []
        range_start = 0
        range_end = 0
        range_sections = []
        for pgindex, pgentry in enumerate(_sortedpageumbers):
            currentpg = _sortedpageumbers[pgindex]
            nextindex = pgindex+1 if pgindex < totalpages-1 else pgindex 
            nextpg = _sortedpageumbers[nextindex]
            range_sections = currentpg["sections"] if range_start == 0 else range_sections
            range_start = currentpg["stitchedpageno"] if range_start == 0 else range_start                        
            if currentpg["stitchedpageno"]+1 == nextpg["stitchedpageno"]:
                range_sections.extend(nextpg["sections"])
                range_end = nextpg["stitchedpageno"]
            else:
                rangepg = range_start if range_end == 0 else str(range_start)+"-"+str(range_end)
                formatted.append({"range": rangepg, "section": self.__formatsections(pageflag, range_sections)}) 
                range_start = 0
                range_end = 0
                range_sections = []   
        #prepare ranges: End
        return formatted

    def __formatsections(self, pageflag, sections):
        if pageflag in ("Duplicate", "Not Responsive"):
            return pageflag
        distinct_sections = list(set(sections))
        return pageflag+" under "+",".join(distinct_sections)



    def __get_pagesection_mapping(self, docpages, docpagesections):
        for entry in docpages:
            entry["sections"] = self.__get_sections(docpagesections, entry['orginalpageno'])
        return docpages

    def __get_sections(self, docpagesections, pageno):
        sections = []
        filtered = [x for x in docpagesections if x['pageno'] == pageno]   
        for dta in filtered:
            _section = json.loads(dta['section'])
            for sec in _section['ids']:
                sections.append(sec["section"])
        return sections

    def __get_pages_by_flagid(self, _docpageflags, totalpages, flagid):
        pagenos = []
        for x in _docpageflags:
            if x["flagid"] == flagid:
                pagenos.append({'orginalpageno':x["page"]-1, 'stitchedpageno':x["page"]+totalpages})
        return pagenos
    
    def __calculate_totalpages(self, data):
        totalpages = 0
        for entry in data:
            totalpages=totalpages+data[entry]['pagecount']
        return totalpages

