from services.dal.documentpageflag import documentpageflag

class redactionsummary():

    def prepareredactionsummary(self, message, documentids, pageflags, programareas):
        redactionsummary = self.prepare_pkg_redactionsummary(message, documentids, pageflags, programareas)
        if message.category == "responsepackage":
            consolidated_redactions = []
            for entry in redactionsummary['data']:
                consolidated_redactions += entry['sections']
            sortedredactions = sorted(consolidated_redactions, key=lambda x: self.__getrangenumber(x["range"])) 
            return {"requestnumber": message.requestnumber, "data": sortedredactions}
        return redactionsummary

    def __getrangenumber(self, rangeval):
        rangestart = str(rangeval).split('-')[0]
        rangestart = str(rangestart).split('(')[0]
        return int(rangestart)

    def prepare_pkg_redactionsummary(self, message, documentids, pageflags, programareas):
        try:
            redactionlayerid = message.redactionlayerid
            summarymsg = message.summarydocuments
            ordereddocids = summarymsg.sorteddocuments
            stitchedpagedata = documentpageflag().getpagecount_by_documentid(message.ministryrequestid, ordereddocids)
            totalpagecount = self.__calculate_totalpages(stitchedpagedata)
            if totalpagecount <=0:
                return 
            _pageflags = self.__transformpageflags(pageflags)
            
            summarydata = []
            docpageflags = documentpageflag().get_documentpageflag(message.ministryrequestid, redactionlayerid, ordereddocids)
                        
            pagecount = 0
            for docid in ordereddocids:
                if docid in documentids:
                    docpageflag = docpageflags[docid]
                    for pageflag in _pageflags:
                        filteredpages = self.__get_pages_by_flagid(docpageflag["pageflag"], pagecount, pageflag["pageflagid"])
                        if len(filteredpages) > 0:
                            originalpagenos = [pg['originalpageno'] for pg in filteredpages]
                            docpagesections = documentpageflag().getsections_by_documentid_pageno(redactionlayerid, docid, originalpagenos)
                            docpageconsults = self.__get_consults_by_pageno(programareas, docpageflag["pageflag"], filteredpages)
                            pageflag['docpageflags'] = pageflag['docpageflags'] + self.__get_pagesection_mapping(filteredpages, docpagesections, docpageconsults)
                pagecount = pagecount+stitchedpagedata[docid]["pagecount"]
                
            for pageflag in _pageflags:
                _data = {}
                if len(pageflag['docpageflags']) > 0:
                    _data = {}
                    _data["flagname"] = pageflag["description"].upper()
                    _data["pagecount"] = len(pageflag['docpageflags'])   
                    _data["sections"] = self.__format_redaction_summary(pageflag["description"], pageflag['docpageflags'])
                    summarydata.append(_data)
            return {"requestnumber": message.requestnumber, "data": summarydata}
        except (Exception) as error:
            print('error occured in redaction summary service: ', error)

    def __transformpageflags(self, pageflags):
        for entry in pageflags:
            entry['docpageflags']= []
        return pageflags
    def __get_consults_by_pageno(self, programareas, docpageflag, pagenos):
        consults = {}
        for entry in docpageflag:
            for pg in pagenos:
                if entry['flagid'] == 4 and entry['page']-1 == pg['originalpageno']:
                    additional_consults = entry["other"] if "other" in entry else []
                    consults[pg['originalpageno']] = self.__format_consults(programareas,entry['programareaid'], additional_consults)
        return consults
    
    def __format_consults(self, programareas, consultids, others):
        formatted = []
        for cid in consultids:
            formatted.append(programareas[cid]['iaocode'])
        if len(others) > 0:
            formatted = formatted+others
        return ",".join(formatted)

    def __format_redaction_summary(self, pageflag, pageredactions):
        totalpages = len(pageredactions)                
        _sorted_pageredactions = sorted(pageredactions, key=lambda x: x["stitchedpageno"])
        #prepare ranges: Begin
        formatted = []
        range_start, range_end = 0, 0
        range_sections = []
        range_consults = None
        for pgindex, pgentry in enumerate(_sorted_pageredactions):
            currentpg = _sorted_pageredactions[pgindex]
            nextindex = pgindex+1 if pgindex < totalpages-1 else pgindex 
            nextpg = _sorted_pageredactions[nextindex]
            range_sections = currentpg["sections"] if range_start == 0 else range_sections
            range_start = currentpg["stitchedpageno"] if range_start == 0 else range_start   
            range_consults = currentpg["consults"]                      
            if currentpg["stitchedpageno"]+1 == nextpg["stitchedpageno"] and currentpg["consults"] == nextpg["consults"]:
                range_sections.extend(nextpg["sections"])
                range_end = nextpg["stitchedpageno"]
            else:
                rangepg = str(range_start) if range_end == 0 else str(range_start)+" - "+str(range_end)
                rangepg = rangepg if range_consults is None else rangepg+" ("+range_consults+")"
                formatted.append({"range": rangepg, "section": self.__formatsections(pageflag, range_sections)}) 
                range_start, range_end = 0, 0,
                range_consults = None
                range_sections = []   
        #prepare ranges: End
        return formatted
    

    def __formatsections(self, pageflag, sections):
        if pageflag in ("Duplicate", "Not Responsive"):
            return pageflag
        distinct_sections = list(set(sections))
        return pageflag+" under "+", ".join(distinct_sections) if len(distinct_sections) > 0 else pageflag

    def __get_pagesection_mapping(self, docpages, docpagesections, docpageconsults):
        for entry in docpages:
            entry["sections"] = self.__get_sections(docpagesections, entry['originalpageno'])
            entry["consults"] = docpageconsults[entry['originalpageno']] if entry['originalpageno'] in docpageconsults else None
        return docpages

    def __get_sections(self, docpagesections, pageno):
        sections = []
        filtered = [x for x in docpagesections if x['pageno'] == pageno]   
        for dta in filtered:
            sections += [x.strip() for x in dta['section'].split(",")] 
        return list(filter(None, sections))

    def __get_pages_by_flagid(self, _docpageflags, totalpages, flagid):
        pagenos = []
        for x in _docpageflags:
            if x["flagid"] == flagid:
                pagenos.append({'originalpageno':x["page"]-1, 'stitchedpageno':x["page"]+totalpages})
        return pagenos
    
    def __calculate_totalpages(self, data):
        totalpages = 0
        for entry in data:
            totalpages=totalpages+data[entry]['pagecount']
        return totalpages

