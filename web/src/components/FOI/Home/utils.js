export const getStitchedPageNoFromOriginal = (docid, page, pageMappedDocs) => {
    let stitchedPageNo = 0;
    if (docid && !Array.isArray(pageMappedDocs) ) {
        let doc = pageMappedDocs?.docIdLookup[docid];
        stitchedPageNo = doc?.pageMappings?.[page - 1].stitchedPageNo;
    }
    return stitchedPageNo;
}

export const createPageFlagPayload = (selectedPages, flagId = 0, data = {}) => {
    var documentpageflags = {};
    for (let page of selectedPages) {
        if (!(page.docid in documentpageflags)) {
            documentpageflags[page.docid] = [];
        }
        documentpageflags[page.docid].push({"flagid": page.flagid || flagId, "page": page.page, ...data});
    }
    var payload = {documentpageflags: []}
    for (let docid in documentpageflags) {
        payload.documentpageflags.push({
            "documentid": docid,
            "version": 1,
            "pageflags": documentpageflags[docid]
        })
    }
    return payload
}

export const getProgramAreas = (pageFlagList) => {
    let consult = pageFlagList.find((pageFlag) => pageFlag.name === 'Consult')
    return (({others , programareas }) => (others ? { others, programareas } : {others: [], programareas}))(consult);
}