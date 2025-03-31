from services.dal.documentpageflag import documentpageflag
from rstreamio.message.schemas.redactionsummary import get_in_summary_object,get_in_summarypackage_object
import json
from collections import defaultdict
import traceback

class redactionsummary():

    def prepareredactionsummary(self, message, documentids, pageflags, programareas):
        _ismcfpersonalrequest = True if message.bcgovcode == 'mcf' and message.requesttype == 'personal' else False
        if _ismcfpersonalrequest and (message.category == "responsepackage" or  "responsepackage_phase" in message.category):
            redactionsummary = self.__packagesummaryforcfdrequests(message, documentids)
        else:
            redactionsummary = self.__packaggesummary(message, documentids, pageflags, programareas)
        if (message.category == "responsepackage" or "responsepackage_phase" in message.category) and _ismcfpersonalrequest == False:
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
            print("\nInside __packaggesummary")
            redactionlayerid = self.__getredactionlayerid(message)
            summarymsg = message.summarydocuments
            summaryobject = get_in_summary_object(summarymsg)
            ordereddocids = summaryobject.sorteddocuments
            stitchedpagedata = documentpageflag().getpagecount_by_documentid(message.ministryrequestid, ordereddocids)
            totalpagecount = self.__calculate_totalpages(stitchedpagedata)
            print("\n __packaggesummary stitchedpagedata",stitchedpagedata)
            print("\n __packaggesummary totalpagecount",totalpagecount)
            
            if totalpagecount <=0:
                return 
            _pageflags = self.__transformpageflags(pageflags)
            print("\n_pageflags",_pageflags)
            summarydata = []
            docpageflags = documentpageflag().get_documentpageflag(message.ministryrequestid, redactionlayerid, ordereddocids)
            # this will remove any pages from docpageflags[pageflags] that are not associated with the redline phase for each doc
            phase = message.phase
            if phase is not None and phase !="" and 'redline_phase' in message.category:
                print("\nInside PHASEREDLINE __packaggesummary")
                docpagephase_map = {}
                for docid in docpageflags:
                    for flagobj in docpageflags[docid]['pageflag']:
                        if flagobj['flagid'] == 9 and int(phase) in flagobj['phase']:
                            if docid not in docpagephase_map:
                                docpagephase_map[docid] = [flagobj['page']]
                            else:
                                docpagephase_map[docid].append(flagobj['page'])
                for docid in docpageflags:
                    pageflags = docpageflags[docid]['pageflag']
                    docpageflags[docid]['pageflag'] = [flagobj for flagobj in pageflags if docid in docpagephase_map and flagobj['page'] in docpagephase_map[docid]]
            print("\n docpageflags",docpageflags)
            deletedpages = self.__getdeletedpages(message.ministryrequestid, ordereddocids)
            skippages= []     
            pagecount = 0
            try:
                for docid in ordereddocids:
                    if docid in documentids:
                        docdeletedpages = deletedpages[docid] if docid in deletedpages else []
                        if docpageflags is not None and docid in docpageflags.keys():
                            docpageflag = docpageflags[docid]
                            #print("docpageflag-display:",docpageflag["pageflag"])
                            pageswithphases=[]
                            if phase is not None and phase !="" and 'responsepackage_phase' in message.category:
                                pageswithphases= sorted({entry["page"] for entry in docpageflag["pageflag"] if entry.get("flagid") == 9 and 
                                                    int(phase) in entry.get("phase", [])})
                            print("\npageswithphases:",pageswithphases)
                            for pageflag in _pageflags:
                                filteredpages = self.__get_pages_by_flagid(docpageflag["pageflag"], docdeletedpages, pagecount, 
                                                    pageflag["pageflagid"], message.category,pageswithphases)
                                print("\nfilteredpages:",filteredpages)
                                if len(filteredpages) > 0:
                                    originalpagenos = [pg['originalpageno'] for pg in filteredpages]
                                    docpagesections = documentpageflag().getsections_by_documentid_pageno(redactionlayerid, docid, originalpagenos)
                                    docpageconsults = self.__get_consults_by_pageno(programareas, docpageflag["pageflag"], filteredpages)
                                    pageflag['docpageflags'] = pageflag['docpageflags'] + self.__get_pagesection_mapping(filteredpages, docpagesections, docpageconsults)
                            skippages = self.__get_skippagenos(docpageflag['pageflag'], message.category,pageswithphases)
                    if stitchedpagedata is not None:        
                        pagecount = (pagecount+stitchedpagedata[docid]["pagecount"])-len(skippages)
                print("\n_pageflags1",_pageflags)
                for pageflag in _pageflags:
                    _data = {}
                    if len(pageflag['docpageflags']) > 0:
                        _data = {}
                        _data["flagname"] = pageflag["header"].upper()
                        _data["pagecount"] = len(pageflag['docpageflags'])  
                        _data["sections"] = self.__format_redaction_summary(pageflag["description"], pageflag['docpageflags'], message.category)
                        summarydata.append(_data)
                #remove duplicate and NR for oipc review redline
                def removeduplicateandnr(pageflag):
                    if pageflag['flagname'].lower() != 'duplicate' and pageflag['flagname'].lower() != 'not responsive':
                        return True
                    return False
                if message.category == "oipcreviewredline":
                    print("\n removing duplicate and not responsive pages from summary")
                    summarydata = list(filter(removeduplicateandnr, summarydata))
            except (Exception) as err:
                traceback.print_exc()
                print('error occured in __packaggesummary redaction dts service: ', err)
            return {"requestnumber": message.requestnumber, "data": summarydata}
        except (Exception) as error:
            traceback.print_exc()
            print('error occured in redaction dts service: ', error)



    def __packagesummaryforcfdrequests(self, message, documentids):
        try:
            redactionlayerid = self.__getredactionlayerid(message)
            summarymsg = message.summarydocuments
            summaryobject = get_in_summary_object(summarymsg)
            ordereddocids = summaryobject.sorteddocuments
            stitchedpagedata = documentpageflag().getpagecount_by_documentid(message.ministryrequestid, ordereddocids)
            totalpagecount = self.__calculate_totalpages(stitchedpagedata)

            if totalpagecount <= 0:
                return

            pkgdocuments = summaryobject.pkgdocuments
            records = pkgdocuments[0].get('records', [])
            summarydata = []

            docpageflags = documentpageflag().get_documentpageflag(message.ministryrequestid, redactionlayerid, ordereddocids)
            # this will remove any pages from docpageflags[pageflags] that are not associated with the redline phase for each doc
            phase = message.phase
            if phase is not None and phase !="":
                print("\nInside phase logic for __packagesummaryforcfdrequests")
                docpagephase_map = {}
                for docid in docpageflags:
                    for flagobj in docpageflags[docid]['pageflag']:
                        if flagobj['flagid'] == 9 and int(phase) in flagobj['phase']:
                            if docid not in docpagephase_map:
                                docpagephase_map[docid] = [flagobj['page']]
                            else:
                                docpagephase_map[docid].append(flagobj['page'])
                for docid in docpageflags:
                    pageflags = docpageflags[docid]['pageflag']
                    docpageflags[docid]['pageflag'] = [flagobj for flagobj in pageflags if docid in docpagephase_map and flagobj['page'] in docpagephase_map[docid]]
            
            sorted_docpageflags = {k: docpageflags[k] for k in ordereddocids}
            # print("============>sorted_docpageflags:", sorted_docpageflags)
            deletedpages = self.__getdeletedpages(message.ministryrequestid, ordereddocids)
            #print("============>deletedpages:", deletedpages)
            mapped_flags = self.process_page_flags(sorted_docpageflags,deletedpages)
            # print("###mapped_flags1:",mapped_flags)
            filteredpageswithphase= self.removeduplicatepageswithphase(mapped_flags)
            pagecounts= self.count_pages_per_doc(filteredpageswithphase)
            # print("pagecounts:",pagecounts)
            #document_pages = self.__get_document_pages(docpageflags)
            #original_pages = self.__adjust_original_pages(document_pages)
            end_page = 0
            for record in records:
                for document_id in record["documentids"]:
                    if document_id in (set(pagecounts.keys())):
                        # print("-----------------------Record : ---------------------------", record["documentids"])
                        record_range, total_page_count,end_page  = self.__createrecordpagerange(record, pagecounts, document_id, end_page)
                        # print(f"Range for each record- record_range:{record_range} &&& total_page_count:{total_page_count} \
                        #     &&& end_page-{end_page}")
                        self.assignfullpagesections(redactionlayerid, mapped_flags)
                        # print("\nfilteredpageswithphase::",filteredpageswithphase)
                        range_result = self.__calculate_range(filteredpageswithphase, document_id)
                        recordwise_pagecount = next((record["pagecount"] for record in record_range if record["recordname"] == record['recordname'].upper()), 0)
                        # print(f"{record['recordname']} :{recordwise_pagecount}")
                        summarydata.append(self.__create_summary_data(record, range_result, mapped_flags, recordwise_pagecount))

            # print("\n summarydata:",summarydata)
            sortedredactions = sorted(summarydata, key=lambda x: self.__getrangenumber(x["sections"][0]["range"]) if '-' in x["sections"][0]["range"] else int(x["sections"][0]["range"])) 
            return {"requestnumber": message.requestnumber, "data": sortedredactions}

        except Exception as error:
            print('CFD Error occurred in redaction dts service: ', error)
            traceback.print_exc()

    def removeduplicatepageswithphase(self, mapped_flags):
        # Identify pages where flagid=9 exists
        pages_with_flagid_9 = {(entry['docid'], entry['originalpageno']) for entry in mapped_flags if entry['flagid'] == 9}
        # Keep only entries where either flagid=9 or the page does not have flagid=9 at all
        return [entry for entry in mapped_flags if entry['flagid'] == 9 or (entry['docid'], entry['originalpageno']) not in pages_with_flagid_9]



    def __calculate_range(self, mapped_flags, document_id):
        if not mapped_flags:
            return {}
        #min_stitched_page = min(flag['stitchedpageno'] for flag in mapped_flags)
        min_stitched_page = min(flag['stitchedpageno'] for flag in mapped_flags if flag['docid'] == document_id)
        max_stitched_page = max(flag['stitchedpageno'] for flag in mapped_flags if flag['docid'] == document_id)
        filtered_mapper = [flag for flag in mapped_flags if flag['docid'] == document_id and flag.get('flagid') == 3]
        # Sort the filtered flags by stitchedpageno
        filtered_mapper.sort(key=lambda x: x['stitchedpageno'])

        grouped_flags= self.__groupbysections(filtered_mapper)
        ranges = self.__create_ranges(grouped_flags)
        # print("\n ranges:",ranges)
        return {"range": f"{min_stitched_page} - {max_stitched_page}" if min_stitched_page != max_stitched_page else f"{min_stitched_page}", "flagged_range":ranges}
    

    def assignfullpagesections(self, redactionlayerid, mapped_flags):
        document_pages= self.get_sorted_original_pages_by_docid(mapped_flags)
        # print("document_pages:",document_pages)
        for item in document_pages:
            for doc_id, pages in item.items():
                docpagesections = documentpageflag().getsections_by_documentid_pageno(redactionlayerid, doc_id, pages)
                # print(f"\n doc_id-{doc_id}, docpagesections-{docpagesections}")
                for flag in mapped_flags:
                        if flag['docid'] == doc_id and flag['flagid'] == 3:
                            flag['sections']= self.__get_sections_mcf1(docpagesections, flag['dbpageno'])
                            #self.__get_pagesection_mapping_cfd1(mapped_flags, docpagesections)

    def __get_sections_mcf1(self, docpagesections, pageno):
        sections = []
        filtered = [x for x in docpagesections if x['pageno'] == pageno]   
        # print(f"\n pageno-{pageno}, filtered-{filtered}")
        if filtered:
            for dta in filtered:
                sections += [x.strip() for x in dta['section'].split(",")] 
        #print("\nSections::",sections)
        return list(filter(None, sections))


    def get_sorted_original_pages_by_docid(self,mapped_flags):
        pages_by_docid = {}
        for entry in mapped_flags:
            docid = entry['docid']
            original_page = entry['dbpageno']

            if docid not in pages_by_docid:
                pages_by_docid[docid] = []

            pages_by_docid[docid].append(original_page)

        # Sort the original pages for each docid
        for docid in pages_by_docid:
            pages_by_docid[docid].sort()

        # Convert to the desired format
        result = [{docid: pages} for docid, pages in pages_by_docid.items()]
        return result

    def __createrecordpagerange(self, record, pagecounts, doc_id, previous_end_page=0):
        total_page_count = pagecounts[doc_id]

        if total_page_count == 0:
            return [], total_page_count, previous_end_page

        start_page = previous_end_page + 1
        end_page = previous_end_page + total_page_count

        range_string = f"{start_page} - {end_page}" if total_page_count > 1 else f"{start_page}"
        result = {
            "recordname": record['recordname'].upper(),
            "range": range_string,
            "pagecount": total_page_count
        }

        return [result], total_page_count, end_page
    
    def count_pages_per_doc(self, mapped_flags):
        page_counts = {}
        #track pages per document
        processed_pages = {}
        for entry in mapped_flags:
            doc_id = entry['docid']
            page = entry['originalpageno']
            if doc_id not in processed_pages:
                processed_pages[doc_id] = set()
            # If the page was already counted, skip it
            if page in processed_pages[doc_id]:
                continue
            # Mark page as processed
            processed_pages[doc_id].add(page)
            # Count the page for the document
            if doc_id in page_counts:
                page_counts[doc_id] += 1
            else:
                page_counts[doc_id] = 1

        return page_counts

    
    # def count_pages_per_doc(self, mapped_flags):
    #     page_counts = {}
    #     for entry in mapped_flags:
    #         doc_id = entry['docid']
    #         if doc_id in page_counts:
    #             page_counts[doc_id] += 1
    #         else:
    #             page_counts[doc_id] = 1
    #     return page_counts

    
    def check_docid_in_stitched_pages(self, stitched_pages, doc_id):
        for key in stitched_pages.keys():
            if key[0] == doc_id:
                return True
        return False
    
    def get_pagecount_for_doc(self,stitched_pages, doc_id):
        # Initialize page count for the specified doc_id
        pagecount = 0
        # Iterate over the keys in stitched_pages
        for d_id, page in stitched_pages.keys():
            if d_id == doc_id:
                pagecount += 1
        return pagecount
    
    def process_page_flags(self, docpageflags, deletedpages):
        result = []
        current_stitched_page = 1  
        for doc_id, details in docpageflags.items():
            docdeletedpages = set(deletedpages.get(doc_id, []))
            stitched_page_map = {}
            # Identify pages that should be skipped
            pages_to_skip = {flag['page'] for flag in details['pageflag'] if flag['flagid'] in (5, 6)}
            for flag in details['pageflag']:
                original_page = flag['page']
                if original_page in pages_to_skip or original_page in docdeletedpages:
                    continue  # Skip invalid pages
                dbpageno = original_page - 1
                # Assign a stitched page number only once per unique page
                stitchedpageno = stitched_page_map.setdefault(original_page, current_stitched_page)
                # If this is the first time assigning the page, increment the counter
                if stitchedpageno == current_stitched_page:
                    current_stitched_page += 1
                result.append({
                    'docid': doc_id,
                    'originalpageno': original_page,
                    'dbpageno': dbpageno,
                    'stitchedpageno': stitchedpageno,
                    'flagid': flag['flagid']
                })
        return result


    
    # def process_page_flags(self,docpageflags, deletedpages):
    #     result = []
    #     stitched_pages = {}
    #     current_stitched_page = 1
        
    #     for doc_id, details in docpageflags.items():
    #         docdeletedpages = deletedpages.get(doc_id, [])
    #         for flag in details['pageflag']:
    #             original_page = flag['page']
                
    #             # Skip pages with flagid 5 or 6
    #             if flag['flagid'] in (5, 6):
    #                 continue
    #             # Skip deleted pages
    #             if original_page in docdeletedpages:
    #                 continue
                
    #             dbpageno = original_page - 1
    #             stitchedpageno = current_stitched_page
    #             stitched_pages[(doc_id, original_page)] = stitchedpageno
    #             result.append({
    #                 'docid': doc_id,
    #                 'originalpageno': original_page,
    #                 'dbpageno': dbpageno,
    #                 'stitchedpageno': stitchedpageno,
    #                 'flagid': flag['flagid']
    #             })
    #             current_stitched_page += 1
    #     return result
    
       
    def __groupbysections(self, filtered_mapper):
        # print("\n __groupbysections: ", filtered_mapper)
        # Group by sections
        grouped_flags = defaultdict(list)
        for flag in filtered_mapper:
            # Convert the list of sections to a tuple, or use an empty tuple if sections is empty
            sections_key = tuple(flag['sections']) if 'sections' in flag and flag['sections'] else ('No Section',)
            grouped_flags[sections_key].append(flag)
        grouped_flags = dict(grouped_flags)
        # print("\n grouped_flags:", grouped_flags)
        return grouped_flags

    
    def __create_ranges(self, grouped_flags):
        ranges = {}
        for sections_key, flags in grouped_flags.items():
            # Extract and sort stitched page numbers
            stitched_pagenos = sorted(flag['stitchedpageno'] for flag in flags)
            range_list = []
            # Create ranges
            start = stitched_pagenos[0]
            prev = start
            for page in stitched_pagenos[1:]:
                if page == prev + 1:
                    prev = page
                else:
                    if start == prev:
                        range_list.append(f"{start}")
                    else:
                        range_list.append(f"{start} - {prev}")
                    start = page
                    prev = page
            # Add the last range
            if start == prev:
                range_list.append(f"{start}")
            else:
                range_list.append(f"{start} - {prev}")
            # Save the range list for the current sections_key
            ranges[sections_key] = range_list
        return ranges


    def __create_summary_data(self, record, range_result, mapped_flags, recordwise_pagecount):
        #print(f"record --> {record}, range_result --> {range_result}, mapped_flags --> {mapped_flags}, recordwise_pagecount --> {recordwise_pagecount}")
        return {
            "recordname": record['recordname'].upper(),
            "pagecount": recordwise_pagecount,
            "sections": [{
                "range": range_result.get("range", ""),
                "section": self.generate_text(range_result)
            }]
        }

    def generate_text(self, range_result):
        pageflag = "Withheld in Full"
        section_list = []
        # Iterate over the items in the flagged_range dictionary
        for sections_key, range_list in range_result.get("flagged_range", {}).items():
            # Convert the sections_key to a string for better readability
            sections_str = ", ".join(sections_key) if isinstance(sections_key, tuple) else sections_key

            # Iterate over each range in the range_list
            for range_item in range_list:
                # Format the section information
                formatted_sections = f"{pageflag} under {sections_str}" if sections_str else ""
                # Append the formatted text to the section list
                section_list.append({"formatted" :f"pg(s). {range_item} {formatted_sections}" if formatted_sections else range_item, 
                                     "page_no": self.__getrangenumber(range_item) if '-' in range_item else int(range_item)})
        
        section_list.sort(key=lambda x: x['page_no'])
        formatted_section_list = [{"formatted":item['formatted']} for item in section_list]
        return formatted_section_list

    
    def __getredactionlayerid(self, message):
        if message.category == "responsepackage" or "responsepackage_phase" in message.category:
            return documentpageflag().getrecentredactionlayerid(message.ministryrequestid)
        return message.redactionlayerid 

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
        print("\n_sorted_pageredactions:",_sorted_pageredactions)
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
            skipconsult  = True if (category in ('oipcreviewredline','responsepackage', 'CFD_responsepackage') or 'responsepackage_phase' in category) else False
            if (currentpg["stitchedpageno"]+1 == nextpg["stitchedpageno"] 
                and (skipconsult == True or (skipconsult == False and currentpg["consults"] == nextpg["consults"]))
                and currentpg["sections"] == nextpg["sections"]
            ):
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
        # print(f"\n pageno-{pageno}, docpagesections-{docpagesections}")
        sections = []
        filtered = [x for x in docpagesections if x['pageno'] == pageno]   
        # print("\n filtered:",filtered)
        for dta in filtered:
            sections += [x.strip() for x in dta['section'].split(",")] 
        return list(filter(None, sections))

    def __get_pages_by_flagid(self, _docpageflags, deletedpages, totalpages, flagid, category,pageswithphases):
        pagenos = []
        skippages = self.__get_skippagenos(_docpageflags,category,pageswithphases)
        print("\nskippages::",skippages)
        for x in _docpageflags:
            if x["flagid"] == flagid and x["page"] not in deletedpages and x['page'] not in skippages: 
                #print("\nInsideLoop",x)
                pagenos.append({'originalpageno':x["page"]-1, 'stitchedpageno':self.__calcstitchedpageno(x["page"], totalpages, category, skippages, deletedpages)})
        return pagenos
    

    def __get_skippagenos(self, _docpageflags, category, pageswithphases=[]):
        #skippages = []
        skippages = set()
        if category in ['responsepackage', 'CFD_responsepackage', 'oipcreviewredline'] or "responsepackage_phase" in category:
           for x in _docpageflags:
               if x['flagid'] in (5,6) and x['page'] not in skippages:
                   skippages.add(x['page'])
               if ("responsepackage_phase" in category and (len(pageswithphases) >0 and 
                x['page'] not in pageswithphases ) or (len(pageswithphases) ==0)):
                   skippages.add(x['page'])
        return list(skippages)
                    
    def __calcstitchedpageno(self, pageno, totalpages, category, skippages, deletedpages):
        skipcount = 0
        if category in ["responsepackage", 'CFD_responsepackage', 'oipcreviewredline'] or "responsepackage_phase" in category:
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

