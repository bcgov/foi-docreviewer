export const getStitchedPageNoFromOriginal = (docid, page, pageMappedDocs) => {
  let stitchedPageNo = 0;
  if (docid && !Array.isArray(pageMappedDocs)) {
    let doc = pageMappedDocs?.docIdLookup[docid];
    // stitchedPageNo = doc?.pageMappings?.[page - 1].stitchedPageNo;
    let stitchedPage = doc?.pageMappings?.filter(_page => _page.pageNo === page);
    if (stitchedPage && stitchedPage.length > 0) {
      stitchedPageNo = stitchedPage[0].stitchedPageNo;
    }
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
    let deleted = page?.deleted || false;
    if (data && data?.programareaid?.length === 0 && data?.other?.length === 0) {
      deleted = true;
    }
    documentpageflags[page.docid].push({
      flagid: page.flagid || flagId,
      page: page.page,
      deleted: deleted,
      ...data,
    });
  }
  let payload = { documentpageflags: [] };
  for (let docid in documentpageflags) {
      payload.documentpageflags.push({
        documentid: docid,
        version: 1,
        pageflags: documentpageflags[docid],
        redactionlayerid: currentLayerId 
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
    return a.filename.toLowerCase().localeCompare(b.filename.toLowerCase());
  }
  return sort;
};

// sort by parent-attachment, then last modified date
export const sortDocList = (fullDocList, currentDoc, sortedDocList) => {
  let parentid = null;
  if(currentDoc) {
    sortedDocList.push(currentDoc);
    if(currentDoc.file)
      parentid = currentDoc.file.documentmasterid;
    else
      parentid = currentDoc.documentmasterid;
  }

  //get all children of currentDoc
  let childDocList = fullDocList.filter((_doc) => {
    if(_doc.file)
      return _doc.file.parentid === parentid;
    else
      return _doc.parentid === parentid;
  });

  if(childDocList.length === 0) {
    return;
  } else {
    let sortedChildDocList = [];
    if(childDocList.length == 1) {
      sortedChildDocList = childDocList;
    } else {
      sortedChildDocList = childDocList.sort(docSorting);
    }

    sortedChildDocList.forEach((_doc, _index) => {
      sortDocList(fullDocList, _doc, sortedDocList);
    });
  }
};

export const getProgramAreas = (pageFlagList) => {
  let consult = pageFlagList.find((pageFlag) => pageFlag.name === "Consult");
  return (({ others, programareas }) =>
    others ? { others, programareas } : { others: [], programareas })(consult);
};

// Helper function to sort files by lastmodified date
export const sortByLastModified = (files) => {
  let sortedList = [];
  sortDocList(files, null, sortedList);
  return sortedList
};

export const sortBySortOrder = (doclist) => {
  doclist?.sort((a, b) => a?.sortorder - b?.sortorder);
  return doclist;
}

// pages array by removing deleted pages
export const getDocumentPages = (documentid, deletedDocPages, originalPagecount) => {
  const pages = [];
  let deletedPages = [];
  if (deletedDocPages) {
    deletedPages = deletedDocPages[documentid] || [];
  }
  for (let i = 0; i < originalPagecount; i++) {
    const pageNumber = i + 1;
    if (!deletedPages.includes(pageNumber)) {
      pages.push(pageNumber);
    }
  }
  return pages;
}

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
    //(defaultSections.length > 0 && defaultSections[0] === 25) ||
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

export const getSliceSetDetails = async (
  totaldocCount,
  autoselectslicer = false
) => {
  let slicersetdetail = new Object();
  slicersetdetail.slicer = 100; //default

  if (totaldocCount > slicersetdetail.slicer) {
    if (autoselectslicer) {
      switch (true) {
        case totaldocCount > 200 && totaldocCount <= 400:
          slicersetdetail.slicer = 200;
          break;
        case totaldocCount > 400 && totaldocCount <= 600:
          slicersetdetail.slicer = 200;
          break;
        case totaldocCount > 600 && totaldocCount <= 1000:
          slicersetdetail.slicer = 200;
          break;
        case totaldocCount > 1000 && totaldocCount <= 3000:
          slicersetdetail.slicer = 500;
          break;
        case totaldocCount > 3000:
          slicersetdetail.slicer = 600;
          break;
        default:
          slicersetdetail.slicer = 100;
          break;
      }
    }
  } else {
    slicersetdetail.slicer = totaldocCount;
  }

  slicersetdetail.setcount = Math.ceil(totaldocCount / slicersetdetail.slicer);
  return slicersetdetail;
};

export const sortDocObjects = (_pdftronDocObjs, doclist) => {
  let __refinedpdftronDocObjs = _pdftronDocObjs.sort(
    (a, b) => a.sortorder - b.sortorder
  );
  let returnObjs = [];
  for (
    let _soCtr = 0, _dlCtr = 0;
    _soCtr < __refinedpdftronDocObjs?.length, _dlCtr < doclist?.length;
    _dlCtr++, _soCtr++
  ) {
    //console.log("I LOGGED"); #IMPORTANT --  TOTAL TIMES THIS CONSOLE MESSAGE LOGGED SHOUDL BE EQUAL TO TOTAL DOCLIST LENTH !IMportant, else slow!!!
    if (
      __refinedpdftronDocObjs[_soCtr] != null &&
      __refinedpdftronDocObjs[_soCtr] != undefined
    ) {
      if (
        __refinedpdftronDocObjs[_soCtr].file.file.documentid ===
        doclist[_dlCtr].file.documentid
      ) {
        returnObjs.push(__refinedpdftronDocObjs[_soCtr]);
      } else {
        break;
      }
    }
  }

  return returnObjs;
};

export const sortDocObjectsForRedline = (_pdftronDocObjs, doclist) => {
  let __refinedpdftronDocObjs = _pdftronDocObjs.sort(
    (a, b) => a.sortorder - b.sortorder
  );
  let returnObjs = [];
  for (
    let _soCtr = 0, _dlCtr = 0;
    _soCtr < __refinedpdftronDocObjs?.length, _dlCtr < doclist?.length;
    _dlCtr++, _soCtr++
  ) {
    //console.log("REDLINE I LOGGED"); #IMPORTANT --  TOTAL TIMES THIS CONSOLE MESSAGE LOGGED SHOUDL BE EQUAL TO TOTAL DOCLIST LENTH !IMportant, else slow!!!
    if (
      __refinedpdftronDocObjs[_soCtr] != null &&
      __refinedpdftronDocObjs[_soCtr] != undefined
    ) {
      if (
        __refinedpdftronDocObjs[_soCtr].file.documentid ===
        doclist[_dlCtr].documentid
      ) {
        returnObjs.push(__refinedpdftronDocObjs[_soCtr]);
      } else {
        break;
      }
    }
  }

  return returnObjs;
};

export const addWatermarkToRedline = async (stitchedDocObj, redlineWatermarkPageMapping, division) => {
  // duplicate & NR watermark
  if (
    (redlineWatermarkPageMapping["duplicatewatermark"] && redlineWatermarkPageMapping["duplicatewatermark"][division]) ||
    (redlineWatermarkPageMapping["NRwatermark"] && redlineWatermarkPageMapping["NRwatermark"][division])
  ) {
    await stitchedDocObj.setWatermark({
      // Draw custom watermark in middle of the document
      custom: (ctx, pageNumber, pageWidth, pageHeight) => {
        // ctx is an instance of CanvasRenderingContext2D
        // https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D
        // Hence being able to leverage those properties
        if(redlineWatermarkPageMapping["duplicatewatermark"][division].includes(pageNumber)) {
          ctx.fillStyle = '#ff0000';
          ctx.font = '20pt Arial';
          ctx.globalAlpha = 0.4;
      
          ctx.save();
          ctx.translate(pageWidth / 2, pageHeight / 2);
          ctx.rotate(-Math.PI / 4);
          ctx.fillText('DUPLICATE', 0, 0);
          ctx.restore();
      
          // ctx.save();
          // ctx.translate(pageWidth, pageHeight / 2);
          // ctx.rotate(Math.PI / 2);
          // ctx.fillText('DUPLICATE', 0, 0);
          // ctx.restore();
        }

        if(redlineWatermarkPageMapping["NRwatermark"][division].includes(pageNumber)) {
          ctx.fillStyle = '#ff0000';
          ctx.font = '20pt Arial';
          ctx.globalAlpha = 0.4;
      
          ctx.save();
          ctx.translate(pageWidth / 2, pageHeight / 2);
          ctx.rotate(-Math.PI / 4);
          ctx.fillText('NOT RESPONSIVE', 0, 0);
          ctx.restore();
      
          // ctx.save();
          // ctx.translate(pageWidth, pageHeight / 2);
          // ctx.rotate(Math.PI / 2);
          // ctx.fillText('NOT RESPONSIVE', 0, 0);
          // ctx.restore();
        }
      },
    });
  }
};

// Get only document with Pages in it
export const getDocumentsForStitching = (doclist) => {
  return doclist.filter(_doc => _doc.file.pagecount > 0);
}

const getSectionArray = (sectionsStr) => {
  if (sectionsStr) {
    const sectionsArray = JSON.parse(sectionsStr);
    return sectionsArray;
  }
}
const getSectionValue = (sectionsStr) => {
  const sectionArray = getSectionArray(sectionsStr);
  return sectionArray[0].section;
}
export const getJoinedSections = (sectionsStr) => {
  const sectionArray = getSectionArray(sectionsStr);
  const sectionValues = sectionArray?.map(item => item.section);
  return sectionValues?.join(', ');
}


export const isObjectNotEmpty = (obj) => {
  return Object.keys(obj).length > 0;
}

export const getValidObject = (obj) => {
  if (isObjectNotEmpty(obj)) {
    return obj;
  }
}

const constructPageFlagsForDelete = (exisitngAnnotations, displayedDoc, pageFlagTypes) => {
  let pagesToUpdate = {};        
  let found = false;
  let foundNRAnnot = false;
  let foundBlankAnnot = false;
  let foundPartialAnnot = false;
  const fullPageRedaction = exisitngAnnotations?.filter(_annotation => _annotation.getCustomData("trn-redaction-type") == 'fullPage');
  // full page redaction is always have first priority
  if (fullPageRedaction.length > 0) {
    const fullPageSectionsStr = fullPageRedaction[0].getCustomData("sections");
    const fullPageSectionValue = getSectionValue(fullPageSectionsStr);    
    if (["", " "].includes(fullPageSectionValue)) {
      return { docid: displayedDoc?.docid, page: displayedDoc?.page, flagid: pageFlagTypes["In Progress"]};
    }
     return { docid: displayedDoc?.docid, page: displayedDoc?.page, flagid: pageFlagTypes["Withheld in Full"]};
  }
  else {
    // check other redactions
    for (let _annot of exisitngAnnotations) {
        found = true;
        const sectionsStr = _annot.getCustomData("sections");
        const sectionValue = getSectionValue(sectionsStr)             
          if (!["", "  ", "NR"].includes(sectionValue)) {
            // if a valid section found
            foundPartialAnnot = true;
          }             
          if ( sectionValue == "") {
            foundBlankAnnot = true;
          }
          else if (sectionValue == 'NR') {
            foundNRAnnot = true;
          }
    }
  }
  // precedence wise the conditions are added below.
  if (foundPartialAnnot) {
    return { docid: displayedDoc.docid, page: displayedDoc.page, flagid: pageFlagTypes["Partial Disclosure"]};
  }
  else if (foundNRAnnot) {
    return { docid: displayedDoc.docid, page: displayedDoc.page, flagid: pageFlagTypes["Full Disclosure"]};
  }
  else if (foundBlankAnnot) {
    return { docid: displayedDoc.docid, page: displayedDoc.page, flagid: pageFlagTypes["In Progress"]};
  }      
  else if (!found) {
    return { docid: displayedDoc.docid, page: displayedDoc.page, flagid: pageFlagTypes["No Flag"], deleted: true};
  }
  return getValidObject(pagesToUpdate);
}

const constructPageFlagsForAddOrEdit = (annotationsInfo, exisitngAnnotations, displayedDoc, pageFlagTypes) => {
  let pagesToUpdate = {};
  const foundBlank = ["", "  "].includes(annotationsInfo.section);
  const foundNR = annotationsInfo.section == "NR";
  // section with a valid number found
  const foundValidSection = !["", "  ", "NR"].includes(annotationsInfo.section);
  // add/edit - fullPage takes the precedence
  if (annotationsInfo?.redactiontype === "fullPage") {
    // addition of full page redaction with blank code return "In Progress" page flag.
    if (foundBlank) {
      return { docid: displayedDoc?.docid, page: displayedDoc?.page, flagid: pageFlagTypes["In Progress"]};
    }
    // adding a separate condition so that the control won't go to else if this condition is not matching
    else if (foundValidSection) { 
      return { docid: displayedDoc?.docid, page: displayedDoc?.page, flagid: pageFlagTypes["Withheld in Full"]};
    }
  }
  else {
    // loop through existing annotations to find any other redaction on the same page
    // based on the precedence, it will prepare the pageflag object

    // get exisitng FreeText annotations on the page
    const _exisitngAnnotations = exisitngAnnotations?.filter(_annotation => (_annotation.Subject === "Free Text" && _annotation.getPageNumber() === Number(annotationsInfo.stitchpage) + 1));
    // get fullpage redaction on the page
    const fullPageRedaction = _exisitngAnnotations?.filter(_annotation => _annotation.getCustomData("trn-redaction-type") == 'fullPage');
    // full page redaction is always have first priority
    if (fullPageRedaction.length > 0) {
      const fullPageSectionsStr = fullPageRedaction[0].getCustomData("sections");
      const fullPageSectionValue = getSectionValue(fullPageSectionsStr);    
      if (["", " "].includes(fullPageSectionValue)) {
        return { docid: displayedDoc?.docid, page: displayedDoc?.page, flagid: pageFlagTypes["In Progress"]};
      }
      return { docid: displayedDoc?.docid, page: displayedDoc?.page, flagid: pageFlagTypes["Withheld in Full"]};
    }
    else {
      // loop through the annotations(other than full page redaction) on the current page
      for (let _annot of _exisitngAnnotations) {
        const sectionsStr = _annot.getCustomData("sections");
        const sectionValue = getSectionValue(sectionsStr);
        if (foundBlank) {
          // partial disclosure - always takes priority over NR/BLANK
          if (!["", "  ", "NR"].includes(sectionValue)) {
            return { docid: displayedDoc.docid, page: displayedDoc.page, flagid: pageFlagTypes["Partial Disclosure"]};
          }
          else if (!["", "  "].includes(sectionValue)) {
            // NR take precedence over BLANK
            if (sectionValue === "NR") {
              return { docid: displayedDoc.docid, page: displayedDoc.page, flagid: pageFlagTypes["Full Disclosure"]};
            }
            else {
              return;
            }
          }
          else {
            // don't retrun, let the loop run and find if any redaction with valid section in it
            pagesToUpdate = { docid: displayedDoc.docid, page: displayedDoc.page, flagid: pageFlagTypes["In Progress"]};
          }
        }
        else if (foundNR) {
          // // partial disclosure - always takes priority over NR/BLANK
          if (!["", "  ", "NR"].includes(sectionValue)) {
            return { docid: displayedDoc.docid, page: displayedDoc.page, flagid: pageFlagTypes["Partial Disclosure"]};
          }
          else {
            // don't retrun, let the loop run and find if any redaction with valid section in it
            pagesToUpdate = { docid: displayedDoc.docid, page: displayedDoc.page, flagid: pageFlagTypes["Full Disclosure"]};
          }
        }
        else {
          pagesToUpdate = { docid: displayedDoc.docid, page: displayedDoc.page, flagid: pageFlagTypes["Partial Disclosure"]};
        }
      }
    }    
    return getValidObject(pagesToUpdate);
  }
}

export const constructPageFlags = (annotationsInfo, exisitngAnnotations, pageMappedDocs, pageFlagTypes, action="") => {
  // 1. always withheld in full takes precedence
  // 2. then, partial disclosure
  // 3. then, NR (full disclosure)
  // 4. lastly, BLANK (in progress)
  const displayedDoc = pageMappedDocs.stitchedPageLookup[Number(annotationsInfo.stitchpage) + 1];
  // get exisitng FreeText annotations on the page
  const _exisitngAnnotations = exisitngAnnotations?.filter(_annotation => (_annotation.Subject === "Free Text" && _annotation.getPageNumber() === Number(annotationsInfo.stitchpage) + 1));
  if (action === "add") {
    return constructPageFlagsForAddOrEdit(annotationsInfo, _exisitngAnnotations, displayedDoc, pageFlagTypes);
  }
  else if (action === "delete") {
    return constructPageFlagsForDelete(_exisitngAnnotations, displayedDoc, pageFlagTypes);
  }
  else {
    return constructPageFlagsForAddOrEdit(annotationsInfo, _exisitngAnnotations, displayedDoc, pageFlagTypes);
  }
}