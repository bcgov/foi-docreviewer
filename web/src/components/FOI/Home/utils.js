export const getStitchedPageNoFromOriginal = (docid, page, pageMappedDocs) => {
  let stitchedPageNo = 0;
  if (docid && !Array.isArray(pageMappedDocs)) {
    let doc = pageMappedDocs?.docIdLookup[docid];
    stitchedPageNo = doc?.pageMappings?.[page - 1].stitchedPageNo;
  }
  return stitchedPageNo;
};

export const createPageFlagPayload = (
  selectedPages,
  currentLayerId,
  flagId = 0,
  data = {}
) => {
  let documentpageflags = {};
  for (let page of selectedPages) {
    if (!(page.docid in documentpageflags)) {
      documentpageflags[page.docid] = [];
    }
    documentpageflags[page.docid].push({
      flagid: page.flagid || flagId,
      page: page.page,
      ...data,
    });
  }
  let payload = { documentpageflags: [] };
  for (let docid in documentpageflags) {
    payload.documentpageflags.push({
      documentid: docid,
      version: 1,
      pageflags: documentpageflags[docid],
      redactionlayerid: currentLayerId,
    });
  }
  return payload;
};

export const docSorting = (a, b) => {
  if (a.file) {
    a = a.file;
  }
  if (b.file) {
    b = b.file;
  }
  let sort =
    Date.parse(a.attributes.lastmodified) -
    Date.parse(b.attributes.lastmodified);
  if (sort === 0) {
    sort =
      Date.parse(a.attributes.attachmentlastmodified || "0") -
      Date.parse(b.attributes.attachmentlastmodified || "0");
  }
  if (sort === 0) {
    if (a.filename < b.filename) {
      return -1;
    }
    if (a.filename > b.filename) {
      return 1;
    }
    return 0;
  }
  return sort;
};

export const getProgramAreas = (pageFlagList) => {
  let consult = pageFlagList.find((pageFlag) => pageFlag.name === "Consult");
  return (({ others, programareas }) =>
    others ? { others, programareas } : { others: [], programareas })(consult);
};

// Helper function to sort files by lastmodified date
export const sortByLastModified = (files) => files.sort(docSorting);

export const getValidSections = (sections, redactionSectionsIds) => {
  return sections.filter((s) => redactionSectionsIds.indexOf(s.id) > -1);
};

export const getSections = (sections, redactionSectionsIds) => {
  return getValidSections(sections, redactionSectionsIds).map((s) => ({
    id: s.id,
    section: s.section,
  }));
};

export const createRedactionSectionsString = (
  sections,
  redactionSectionsIds
) => {
  const compareFn = (a, b) => {
    let sectionA = parseFloat(a.section.split("s. ")[1]);
    let sectionB = parseFloat(b.section.split("s. ")[1]);
    if (sectionA == undefined) sectionA = 100;
    if (sectionB == undefined) sectionB = 100;
    return sectionA - sectionB;
  };
  let redactionSections = getValidSections(sections, redactionSectionsIds)
    .sort(compareFn)
    .map((s) => s.section)
    .join(", ");
  if (redactionSectionsIds?.length == 1 && redactionSectionsIds[0] === 25) {
    redactionSections = "  ";
  }
  return redactionSections;
};

export const updatePageFlags = (
  defaultSections,
  selectedSections,
  fullpageredaction,
  pageFlagTypes,
  displayedDoc,
  pageSelectionList
) => {
  //page flag updates
  if (
    (defaultSections.length > 0 && defaultSections[0] === 25) ||
    (selectedSections && selectedSections[0] === 25)
  ) {
    pageSelectionList.push({
      page: Number(displayedDoc?.page),
      flagid: pageFlagTypes["In Progress"],
      docid: displayedDoc?.docid,
    });
  } else if (fullpageredaction === "fullPage") {
    pageSelectionList.push({
      page: Number(displayedDoc?.page),
      flagid: pageFlagTypes["Withheld in Full"],
      docid: displayedDoc?.docid,
    });
  } else if (selectedSections && selectedSections[0] !== 25) {
    pageSelectionList.push({
      page: Number(displayedDoc?.page),
      flagid: pageFlagTypes["Partial Disclosure"],
      docid: displayedDoc?.docid,
    });
  }
};
