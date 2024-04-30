from services.dal.documentpageflag import documentpageflag
from rstreamio.message.schemas.redactionsummary import get_in_summary_object,get_in_summarypackage_object

class redactionsummary():

    def prepareredactionsummary(self, message, documentids, pageflags, programareas):
        redactionsummary = self.__packaggesummary(message, documentids, pageflags, programareas)
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

    def __packaggesummary(self, message, documentids, pageflags, programareas):
        try:
            redactionlayerid = message.redactionlayerid
            summarymsg = message.summarydocuments
            summaryobject = get_in_summary_object(summarymsg)
            ordereddocids = summaryobject.sorteddocuments
            stitchedpagedata = documentpageflag().getpagecount_by_documentid(message.ministryrequestid, ordereddocids)
            totalpagecount = self.__calculate_totalpages(stitchedpagedata)
            if totalpagecount <=0:
                return 
            _pageflags = self.__transformpageflags(pageflags)
            
            summarydata = []
            docpageflags = documentpageflag().get_documentpageflag(message.ministryrequestid, redactionlayerid, ordereddocids)
            deletedpages = self.__getdeletedpages(message.ministryrequestid, ordereddocids)
            skippages= []     
            pagecount = 0
            for docid in ordereddocids:
                if docid in documentids:
                    docdeletedpages = deletedpages[docid] if docid in deletedpages else []
                    docpageflag = docpageflags[docid]
                    for pageflag in _pageflags:
                        filteredpages = self.__get_pages_by_flagid(docpageflag["pageflag"], docdeletedpages, pagecount, pageflag["pageflagid"], message.category)
                        if len(filteredpages) > 0:
                            originalpagenos = [pg['originalpageno'] for pg in filteredpages]
                            docpagesections = documentpageflag().getsections_by_documentid_pageno(redactionlayerid, docid, originalpagenos)
                            docpageconsults = self.__get_consults_by_pageno(programareas, docpageflag["pageflag"], filteredpages)
                            pageflag['docpageflags'] = pageflag['docpageflags'] + self.__get_pagesection_mapping(filteredpages, docpagesections, docpageconsults)
                    skippages = self.__get_skippagenos(docpageflag['pageflag'], message.category)
                pagecount = (pagecount+stitchedpagedata[docid]["pagecount"])-len(skippages)
                
            for pageflag in _pageflags:
                _data = {}
                if len(pageflag['docpageflags']) > 0:
                    _data = {}
                    _data["flagname"] = pageflag["header"].upper()
                    _data["pagecount"] = len(pageflag['docpageflags'])  
                    _data["sections"] = self.__format_redaction_summary(pageflag["description"], pageflag['docpageflags'], message.category)
                    summarydata.append(_data)
            return {"requestnumber": message.requestnumber, "data": summarydata}
        except (Exception) as error:
            print('error occured in redaction dts service: ', error)

    def __getdeletedpages(self, ministryid, ordereddocids):
        deletedpages = documentpageflag().getdeletedpages(ministryid, ordereddocids)
        documentpages = {}
        if deletedpages: 
            for entry in deletedpages:
                if entry["documentid"] not in documentpages:
                    documentpages[entry["documentid"]] = entry["pagemetadata"]
                else:
                    pages = documentpages[entry["documentid"]]+entry["pagemetadata"]                
                    documentpages[entry["documentid"]] = list(set(pages))
        return documentpages

    def __transformpageflags(self, pageflags):
        for entry in pageflags:
            entry['docpageflags']= []
            entry['header'] = entry['description']
            if entry['name'] == 'Full Disclosure':                
                entry['header'] = 'DISCLOSED IN FULL'
                entry['description'] = 'Disclosed in full'
            elif entry['name'] == 'Partial Disclosure':
                entry['header'] = 'DISCLOSED IN PART'  
            elif entry['name'] == 'Not Responsive':
                entry['description'] = 'Not Responsive to request'            
                
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

    def __format_redaction_summary(self, pageflag, pageredactions, category):
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
            skipconsult  = True if category in ('oipcreviewredline','responsepackage') else False
            if currentpg["stitchedpageno"]+1 == nextpg["stitchedpageno"] and (skipconsult == True or (skipconsult == False and currentpg["consults"] == nextpg["consults"])):
                range_sections.extend(nextpg["sections"])
                range_end = nextpg["stitchedpageno"]
            else:
                rangepg = str(range_start) if range_end == 0 else str(range_start)+" - "+str(range_end)
                rangepg = rangepg if (skipconsult or range_consults is None) else rangepg+" ("+range_consults+")"
                formatted.append({"range": rangepg, "section": self.__formatsections(pageflag, range_sections)}) 
                range_start, range_end = 0, 0,
                range_consults = None
                range_sections = []   
        #prepare ranges: End
        return formatted
    

    def __formatsections(self, pageflag, sections):
        if pageflag in ("Duplicate", "Not Responsive to request"):
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

    def __get_pages_by_flagid(self, _docpageflags, deletedpages, totalpages, flagid, category):
        pagenos = []
        skippages = self.__get_skippagenos(_docpageflags,category)
        for x in _docpageflags:
            if x["flagid"] == flagid and x["page"] not in deletedpages:   
                pagenos.append({'originalpageno':x["page"]-1, 'stitchedpageno':self.__calcstitchedpageno(x["page"], totalpages, category, skippages, deletedpages)})
        return pagenos
    
    def __get_skippagenos(self, _docpageflags, category):
        skippages = []
        if category == 'responsepackage':
           for x in _docpageflags:
               if x['flagid'] in (5,6) and x['page'] not in skippages:
                   skippages.append(x['page'])
        return skippages
                    
    def __calcstitchedpageno(self, pageno, totalpages, category, skippages, deletedpages):
        skipcount = 0
        if category == "responsepackage":  
            skipcount =  self.__calculateskipcount(pageno, skippages)     
        skipcount =  self.__calculateskipcount(pageno, deletedpages, skipcount)         
        return (pageno+totalpages)-skipcount
    
    def __calculateskipcount(self, pageno, ignorepages, skipcount=0):
        for dno in ignorepages:
            if dno < pageno:
                skipcount=skipcount+1
        return skipcount


    def __calculate_totalpages(self, data):
        totalpages = 0
        for entry in data:
            totalpages=totalpages+data[entry]['pagecount']
        return totalpages

