export const getStitchedPageNoFromOriginal = (docid, page, pageMappedDocs) => {
  let stitchedPageNo = 0;
  if (docid && pageMappedDocs) {
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
    return a.filename.toLowerCase().localeCompare(b.filename.toLowerCase());
  }
  return sort;
};

export const CFDSorting = (a, b) => {
  if (a.file) {
    a = a.file;
  }
  if (b.file) {
    b = b.file;
  }
  if (a.attributes.personalattributes.person !== b.attributes.personalattributes.person) {
    return (a.attributes.personalattributes.person > b.attributes.personalattributes.person) ? 1 : -1 
  } else if (a.attributes.personalattributes.filetype !== b.attributes.personalattributes.filetype) {
    return (a.attributes.personalattributes.filetype > b.attributes.personalattributes.filetype) ? 1 : -1 
  } else if (a.attributes.personalattributes.trackingid !== b.attributes.personalattributes.trackingid) {
    return (a.attributes.personalattributes.trackingid > b.attributes.personalattributes.trackingid) ? 1 : -1 
  } else if (a.attributes.personalattributes.volume !== b.attributes.personalattributes.volume) {
    return (a.attributes.personalattributes.volume > b.attributes.personalattributes.volume) ? 1 : -1 
  }
  return Date.parse(a.created_at) - Date.parse(b.created_at);
};

// sort by parent-attachment, then last modified date
export const sortDocList = (fullDocList, currentDoc, sortedDocList, requestInfo) => {
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
      if (requestInfo.bcgovcode === "MCF") {
        sortedChildDocList = childDocList.sort(CFDSorting);
      } else {
        // sortedChildDocList = childDocList.sort(docSorting);
        sortedChildDocList = childDocList.sort(CFDSorting);
      }
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

export const updatePageFlagOnPage = (documentpageflags, pageFlags) => {
  const updatedPageFlags = [...pageFlags]; // Create a copy of the pageFlags array
  for (let documentpageflag of documentpageflags) {
      let toBeUpdated = updatedPageFlags.find((pageflag) => pageflag.documentid == documentpageflag.documentid);
      if (toBeUpdated) {
          for (let pageFlag of documentpageflag.pageflags) {
              let pageFoundIndex = toBeUpdated.pageflag.findIndex((pageflag) => pageflag.page === pageFlag.page);
              if (pageFoundIndex !== -1) {
                  toBeUpdated.pageflag[pageFoundIndex] = pageFlag;
              } else {
                  toBeUpdated.pageflag.push(pageFlag);
              }
          }
      }
  }
  return updatedPageFlags;
}