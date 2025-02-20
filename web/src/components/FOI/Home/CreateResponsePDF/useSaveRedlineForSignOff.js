import React, { useState, useEffect } from "react";
import { useAppSelector } from "../../../../hooks/hook";
import { toast } from "react-toastify";
import {
  getStitchedPageNoFromOriginal,
  getSliceSetDetails,
  sortBySortOrder,
  addWatermarkToRedline,
  sortDocObjectsForRedline,
  skipDocument,
  skipDuplicateDocument,
  skipNRDocument
} from "../utils";
import {
  getFOIS3DocumentRedlinePreSignedUrl,
  saveFilesinS3,
} from "../../../../apiManager/services/foiOSSService";
import {
  fetchDocumentAnnotations,
  triggerDownloadRedlines,
} from "../../../../apiManager/services/docReviewerService";
import { pageFlagTypes, RequestStates } from "../../../../constants/enum";
import { useParams } from "react-router-dom";
import XMLParser from "react-xml-parser";

const useSaveRedlineForSignoff = (initDocInstance, initDocViewer) => {
  const currentLayer = useAppSelector((state) => state.documents?.currentLayer);
  const deletedDocPages = useAppSelector(
    (state) => state.documents?.deletedDocPages
  );
  const requestStatus = useAppSelector(
    (state) => state.documents?.requeststatus
  );
  const requestnumber = useAppSelector(
    (state) => state.documents?.requestnumber
  );
  const allPublicBodies = useAppSelector((state) => state.documents?.allPublicBodies);
  const toastId = React.useRef(null);
  const { foiministryrequestid } = useParams();

  //xml parser
  const parser = new XMLParser();
  const [docInstance, setDocInstance] = useState(initDocInstance);
  const [docViewer, setDocViewer] = useState(initDocViewer);
  const [redlineStitchInfo, setRedlineStitchInfo] = useState(null);
  const [isSingleRedlinePackage, setIsSingleRedlinePackage] = useState(null);
  const [redlinepageMappings, setRedlinepageMappings] = useState(null);
  const [redlineWatermarkPageMapping, setRedlineWatermarkPageMapping] =
    useState({});
  const [redlineIncompatabileMappings, setRedlineIncompatabileMappings] =
    useState(null);
  const [redlineDocumentAnnotations, setRedlineDocumentAnnotations] =
    useState(null);
  const [requestStitchObject, setRequestStitchObject] = useState({});
  const [incompatableList, setIncompatableList] = useState({});
  const [totalStitchList, setTotalStitchList] = useState([]);
  const [redlineStitchDivisionDetails, setRedlineStitchDivisionDetails] =
    useState({});
  const [pdftronDocObjectsForRedline, setPdftronDocObjectsForRedline] =
    useState([]);
  const [redlineZipperMessage, setRedlineZipperMessage] = useState(null);
  const [includeComments, setIncludeComments] = useState(false);
  const [includeNRPages, setIncludeNRPages] = useState(false);
  const [includeDuplicatePages, setIncludeDuplicatePages] = useState(false);
  const [stichedfilesForRedline, setstichedfilesForRedline] = useState(null);
  const [redlineStitchObject, setRedlineStitchObject] = useState(null);
  const [enableSavingRedline, setEnableSavingRedline] = useState(false);
  const [enableSavingOipcRedline, setEnableSavingOipcRedline] = useState(false);
  const [redlineCategory, setRedlineCategory] = useState(false);
  const [filteredComments, setFilteredComments] = useState({});
  const [alreadyStitchedList, setAlreadyStitchedList] = useState([]);
  const [enableSavingConsults, setEnableSavingConsults] = useState(false);
  const [selectedPublicBodyIDs, setSelectedPublicBodyIDs] = useState([]);
  const [documentPublicBodies, setDocumentPublicBodies] = useState([]);
  const [consultApplyRedactions, setConsultApplyRedactions] = useState(false);
  const [consultApplyRedlines, setConsultApplyRedlines] = useState(false);

  const requestInfo = useAppSelector((state) => state.documents?.requestinfo);
  const requestType = requestInfo?.requesttype ? requestInfo.requesttype : "public";

  const isValidRedlineDivisionDownload = (divisionid, divisionDocuments) => {
    let isvalid = false;
    for (let divObj of divisionDocuments) {    
      if (divObj.divisionid === divisionid)  {
        // enable the Redline for Sign off if a division has only Incompatable files
        if (divObj?.incompatableList?.length > 0) {
          if(isvalid === false) {
            isvalid = true; 
          } 
        }
        else {
          for (let doc of divObj.documentlist) {
            //page to pageFlag mappings logic used for consults
            const pagePageFlagMappings = {};
            for (let pageFlag of doc.pageFlag) {
              if (pageFlag.page in pagePageFlagMappings) {
                pagePageFlagMappings[pageFlag.page].push(pageFlag.flagid);
              } else {
                pagePageFlagMappings[pageFlag.page] = [pageFlag.flagid];
              }
            }
            for (const flagInfo of doc.pageFlag) {
              if (redlineCategory === "consult") {
                const pageFlagsOnPage = pagePageFlagMappings[flagInfo.page];
                for (let consult of doc.consult) {
                  if ((consult.page === flagInfo.page && consult.programareaid.includes(divObj.divisionid)) || (consult.page === flagInfo.page && consult.other.includes(divObj.divisionname))) {
                    if (
                      (
                      flagInfo.flagid !== pageFlagTypes["Duplicate"] && flagInfo.flagid !== pageFlagTypes["Not Responsive"]) ||
                      (
                        (includeDuplicatePages && flagInfo.flagid === pageFlagTypes["Duplicate"]) ||
                        (includeNRPages && flagInfo.flagid === pageFlagTypes["Not Responsive"])
                      )
                    ) {
                      if(isvalid === false) {
                        if ((!includeDuplicatePages && pageFlagsOnPage.some((flagId) => flagId === pageFlagTypes["Duplicate"])) || (!includeNRPages && pageFlagsOnPage.some((flagId) => flagId === pageFlagTypes["Not Responsive"]))) {
                          isvalid = false;
                        } else {
                          isvalid = true; 
                        }
                      } 
                    }
                  }
                }
              }
              // Added condition to handle Duplicate/NR clicked for Redline for Sign off Modal
              else if (
                  (flagInfo.flagid !== pageFlagTypes["Duplicate"] && flagInfo.flagid != pageFlagTypes["Not Responsive"]) ||
                  (
                    (includeDuplicatePages && flagInfo.flagid === pageFlagTypes["Duplicate"]) ||
                    (includeNRPages && flagInfo.flagid === pageFlagTypes["Not Responsive"])
                  )
                ) {
                  if(isvalid == false) {
                    isvalid = true; 
                  } 
              }
            }
          }
        }
      }
    }
    return isvalid;
  };
  const getDeletedPagesBeforeStitching = (documentid) => {
    let deletedPages = [];
    if (deletedDocPages) {
      deletedPages = deletedDocPages[documentid] || [];
    }
    return deletedPages;
  };
  // isIgnoredDocument is no longer needed as new logic exists for NR and Duplicates. Left just in case needed in the future.
  const isIgnoredDocument = (doc, pagecount, divisionDocuments) => {
    const divdocumentlist = JSON.parse(JSON.stringify(divisionDocuments));
    let removepagesCount = 0;
    for (let divsionentry of divdocumentlist) {
      for (let docentry of divsionentry["documentlist"]) {
        if (doc.documentid === docentry.documentid) {
          for (const flagInfo of docentry.pageFlag) {
            if (
              flagInfo.flagid === pageFlagTypes["Duplicate"] ||
              flagInfo.flagid === pageFlagTypes["Not Responsive"]
            ) {
              removepagesCount++;
            }
          }
        }
      }
    }
    return pagecount === removepagesCount;
  };
  const getDivisionsForSaveRedline = (divisionFilesList) => {
    let arr = [];
    const divisions = [
      ...new Map(
        divisionFilesList.reduce(
          (acc, file) => [
            ...acc,
            ...new Map(
              file.divisions.map((division) => [division.divisionid, division])
            ),
          ],
          arr
        )
      ).values(),
    ];
    return divisions;
  };
  const getDivisionDocumentMappingForRedline = (
    divisions,
    documentList,
    incompatibleFiles
  ) => {
    let newDocList = [];
    if (redlineCategory === "redline" || redlineCategory === "oipcreview") {
      for (let div of divisions) {
        let divDocList = documentList?.filter((doc) =>
          doc.divisions.map((d) => d.divisionid).includes(div.divisionid)
        );

        // sort based on sortorder as the sortorder added based on the LastModified
        divDocList = sortBySortOrder(divDocList);

        let incompatableList = incompatibleFiles.filter((doc) =>
          doc.divisions.map((d) => d.divisionid).includes(div.divisionid)
        );
        newDocList.push({
          divisionid: div.divisionid,
          divisionname: div.name,
          documentlist: divDocList,
          incompatableList: incompatableList,
        });
      }
    } else if (redlineCategory === "consult") {
      // map documents to publicBodies and custom public bodies (treated as Divisions) for consults package.
      // Consult Package logic will treat publicbodies (program areas + custom consults) as DIVISIONS and will incorporate the existing division mapping  + redline logic to generate the consult package
      for (let publicBodyId of divisions) {
        let publicBodyDocList = [];
        documentList.forEach((doc) => {
          let programareaids = new Set();
          if (doc.consult && doc.consult.length) {
            doc.consult.forEach((consult) => {
              consult.programareaid.forEach((programareaid) => {
                if (programareaid === publicBodyId) {
                  programareaids.add(programareaid);
                }
              })
            });
            for (let consult of doc.consult) {
              for (let customPublicBody of consult.other) {
                if (customPublicBody === publicBodyId) {
                  programareaids.add(customPublicBody);
                }
              }
            }
          }
          for (let programareaid of programareaids) {
            if (programareaid === publicBodyId) {
              publicBodyDocList.push({...doc})
            }
          }
        })
        publicBodyDocList = sortBySortOrder(publicBodyDocList);

        let incompatableList = [];

        // Custom public bodies/consults do not exist in allPublicBodies data (BE program area data) and are stored as simple strings with pageflag data (in other array attribute).
        // Therefore, if publicBodyInfo cannot be found in allPublicBodies, the publicbody is a custom one and we will create its 'divison' data in the FE with a random unique id (Math.floor(Math.random() * 100000)), and its publicBodyID (which is its name as a string) for consult package creation purposes
        const publicBodyInfo = allPublicBodies.find((body) => body.programareaid === publicBodyId);
        newDocList.push({
          divisionid: publicBodyInfo ? publicBodyInfo.programareaid : Math.floor(Math.random() * 100000),
          divisionname: publicBodyInfo ? publicBodyInfo.name : publicBodyId,
          documentlist: publicBodyDocList,
          incompatableList: incompatableList,
        })
      }
    }
    return newDocList;
  };
  const prepareRedlinePageMapping = (
    divisionDocuments,
    redlineSinglePkg,
    pageMappedDocs
  ) => {
    if (redlineSinglePkg === "Y") {
      let reqdocuments = [];
      for (let divObj of divisionDocuments) {    
        for (let doc of divObj.documentlist) {
          reqdocuments.push(doc);
        }
      }
      // sort based on sortorder as the sortorder added based on the LastModified
      prepareRedlinePageMappingByRequest(sortBySortOrder(reqdocuments), pageMappedDocs);
    } else if (redlineCategory === "consult") {
      prepareRedlinePageMappingByConsult(divisionDocuments);
    } else {
      prepareRedlinePageMappingByDivision(divisionDocuments);
    }
  }

  const prepareRedlinePageMappingByRequest = (
    divisionDocuments,
    pageMappedDocs
  ) => {
    let removepages = {};
    let pageMappings = {};
    let pagesToRemove = []; 
    let totalPageCount = 0;
    let totalPageCountIncludeRemoved = 0;
    let divPageMappings = {};
    let duplicateWatermarkPages = {};
    let duplicateWatermarkPagesEachDiv = [];
    let NRWatermarksPages = {};
    let NRWatermarksPagesEachDiv = [];
    for (let doc of divisionDocuments) {
      if (doc.pagecount > 0) {
        let pagesToRemoveEachDoc = [];
        pageMappings[doc.documentid] = {};
        //gather pages that need to be removed
        doc.pageFlag.sort((a, b) => a.page - b.page); //sort pageflag by page #
        let pageIndex = 1;
        for (const flagInfo of doc.pageFlag) {
          if (flagInfo.flagid !== pageFlagTypes["Consult"]) { // ignore consult flag to fix bug FOIMOD-3062
            if (flagInfo.flagid == pageFlagTypes["Duplicate"]) {
              if(includeDuplicatePages) {
                duplicateWatermarkPagesEachDiv.push(
                  getStitchedPageNoFromOriginal(
                    doc.documentid,
                    flagInfo.page,
                    pageMappedDocs
                  ) - pagesToRemove.length
                );

                pageMappings[doc.documentid][flagInfo.page] =
                  pageIndex +
                  totalPageCount -
                  pagesToRemoveEachDoc.length;
              } else {
                pagesToRemoveEachDoc.push(flagInfo.page);
                pagesToRemove.push(
                  getStitchedPageNoFromOriginal(
                    doc.documentid,
                    flagInfo.page,
                    pageMappedDocs
                  )
                );
              }
            } else if (flagInfo.flagid == pageFlagTypes["Not Responsive"]) {
              if(includeNRPages) {
                NRWatermarksPagesEachDiv.push(
                  getStitchedPageNoFromOriginal(
                    doc.documentid,
                    flagInfo.page,
                    pageMappedDocs
                  ) - pagesToRemove.length
                );

                pageMappings[doc.documentid][flagInfo.page] =
                  pageIndex +
                  totalPageCount -
                  pagesToRemoveEachDoc.length;
              } else {
                pagesToRemoveEachDoc.push(flagInfo.page);
                pagesToRemove.push(
                  getStitchedPageNoFromOriginal(
                    doc.documentid,
                    flagInfo.page,
                    pageMappedDocs
                  )
                );
              }
            } else {
              if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
                pageMappings[doc.documentid][flagInfo.page] =
                  pageIndex +
                  totalPageCount -
                  pagesToRemoveEachDoc.length;
              }
            }
            if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
              pageIndex ++;
            }
          }
        }
        //End of pageMappingsByDivisions
        totalPageCount += Object.keys(
          pageMappings[doc.documentid]
        ).length;
        totalPageCountIncludeRemoved += doc.pagecount;
      }
    }
    divPageMappings['0'] = pageMappings;
    removepages['0'] = pagesToRemove; 
    duplicateWatermarkPages['0'] = duplicateWatermarkPagesEachDiv;
    NRWatermarksPages['0'] = NRWatermarksPagesEachDiv;
    setRedlinepageMappings({
      'divpagemappings': divPageMappings,
      'pagemapping': pageMappings,
      'pagestoremove': removepages
    });
    setRedlineWatermarkPageMapping({
      'duplicatewatermark': duplicateWatermarkPages,
      'NRwatermark': NRWatermarksPages
    });
  };

  const prepareRedlinePageMappingByDivision = (divisionDocuments) => {
    let removepages = {};
    let pageMappings = {};
    let divPageMappings = {};
    let pagesToRemove = []; 
    let totalPageCount = 0;
    let totalPageCountIncludeRemoved = 0;
    let divisionCount = 0; 
    let duplicateWatermarkPages = {};
    let duplicateWatermarkPagesEachDiv = [];
    let NRWatermarksPages = {};
    let NRWatermarksPagesEachDiv = [];
    for (let divObj of divisionDocuments) {    
      divisionCount++;  
      // sort based on sortorder as the sortorder added based on the LastModified
      for (let doc of sortBySortOrder(divObj.documentlist)) {
        if (doc.pagecount > 0) {
          let pagesToRemoveEachDoc = [];
          pageMappings[doc.documentid] = {};
          let pageIndex = 1;
          //gather pages that need to be removed
          doc.pageFlag.sort((a, b) => a.page - b.page); //sort pageflag by page #
          let skipDocumentPages = false;
          let skipOnlyDuplicateDocument = false;
          let skipOnlyNRDocument = false;
          if (!includeDuplicatePages && !includeNRPages) {
            skipDocumentPages = skipDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
          }
          else if (!includeDuplicatePages) {
            skipOnlyDuplicateDocument = skipDuplicateDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
          }
          else if (!includeNRPages) {
            skipOnlyNRDocument = skipNRDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
          }
          //if(isIgnoredDocument(doc, doc['pagecount'], divisionDocuments) == false) {
          for (const flagInfo of doc.pageFlag) {
            if (flagInfo.flagid !== pageFlagTypes["Consult"]) { // ignore consult flag to fix bug FOIMOD-3062
              if (flagInfo.flagid == pageFlagTypes["Duplicate"]) {
                if(includeDuplicatePages) {
                  duplicateWatermarkPagesEachDiv.push(pageIndex + totalPageCountIncludeRemoved - pagesToRemove.length);

                  pageMappings[doc.documentid][flagInfo.page] =
                    pageIndex +
                    totalPageCount -
                    pagesToRemoveEachDoc.length;
                } else {
                  pagesToRemoveEachDoc.push(flagInfo.page);
                  if (!skipDocumentPages && !skipOnlyDuplicateDocument) {
                    pagesToRemove.push(                  
                      pageIndex + totalPageCountIncludeRemoved
                    );
                  }
                }

              } else if (flagInfo.flagid == pageFlagTypes["Not Responsive"]) {
                if(includeNRPages) {
                  NRWatermarksPagesEachDiv.push(pageIndex + totalPageCountIncludeRemoved - pagesToRemove.length);

                  pageMappings[doc.documentid][flagInfo.page] =
                  pageIndex +
                    totalPageCount -
                    pagesToRemoveEachDoc.length;
                } else {
                  pagesToRemoveEachDoc.push(flagInfo.page);
                  if (!skipDocumentPages && !skipOnlyNRDocument) {
                    pagesToRemove.push(                  
                      pageIndex + totalPageCountIncludeRemoved
                    );
                  }
                }
              } else {
                if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
                  pageMappings[doc.documentid][flagInfo.page] =
                    pageIndex +
                    totalPageCount -
                    pagesToRemoveEachDoc.length;
                }
              }
              if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
                pageIndex ++;
              }
            }
          }
          //End of pageMappingsByDivisions
          totalPageCount += Object.keys(
            pageMappings[doc.documentid]
          ).length;
          if (!skipDocumentPages && !skipOnlyDuplicateDocument && !skipOnlyNRDocument) {
            totalPageCountIncludeRemoved += doc.pagecount;
          }
        //}
        }
        
      }
      divPageMappings[divObj.divisionid] = pageMappings;
      removepages[divObj.divisionid] = pagesToRemove;
      duplicateWatermarkPages[divObj.divisionid] = duplicateWatermarkPagesEachDiv;
      NRWatermarksPages[divObj.divisionid] = NRWatermarksPagesEachDiv;
      pagesToRemove = [];
      duplicateWatermarkPagesEachDiv = [];
      NRWatermarksPagesEachDiv = [];
      totalPageCount = 0;
      totalPageCountIncludeRemoved = 0;
      pageMappings = {}
    }

    setRedlinepageMappings({
      'divpagemappings': divPageMappings,
      'pagemapping': pageMappings,
      'pagestoremove': removepages
    });
    setRedlineWatermarkPageMapping({
      'duplicatewatermark': duplicateWatermarkPages,
      'NRwatermark': NRWatermarksPages
    });
  }

  const prepareRedlinePageMappingByConsult = (divisionDocuments) => {
    let removepages = {};
    let pageMappings = {};
    let divPageMappings = {};
    let pagesToRemove = [];
    let totalPageCount = 0;
    let totalPageCountIncludeRemoved = 0;
    for (let divObj of divisionDocuments) {
      // sort based on sortorder as the sortorder added based on the LastModified
      for (let doc of sortBySortOrder(divObj.documentlist)) {
        if (doc.pagecount > 0) {
          let pagesToRemoveEachDoc = [];
          pageMappings[doc.documentid] = {};
          let pageIndex = 1;
          //gather pages that need to be removed
          doc.pageFlag.sort((a, b) => a.page - b.page); //sort pageflag by page #
          let skipDocumentPages = false;
          let skipOnlyDuplicateDocument = false;
          let skipOnlyNRDocument = false;
          if (!includeDuplicatePages && !includeNRPages) {
            skipDocumentPages = skipDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
          }
          else if (!includeDuplicatePages) {
            skipOnlyDuplicateDocument = skipDuplicateDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
          }
          else if (!includeNRPages) {
            skipOnlyNRDocument = skipNRDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
          }

          // for consults, go through all pages
          for (const page of doc.pages) {
            //find pageflags for this page
            const pageFlagsOnPage = doc.pageFlag.filter((pageFlag) => {
              return pageFlag.page === page;
            })
            const notConsultPageFlagsOnPage = pageFlagsOnPage.filter((pageFlag) => {
              return pageFlag.flagid !== pageFlagTypes["Consult"];
            })

            // if the page has no pageflags, remove it
            if (pageFlagsOnPage.length == 0) {
              pagesToRemoveEachDoc.push(page);
              if (!skipDocumentPages) {
                pagesToRemove.push(
                  pageIndex + totalPageCountIncludeRemoved
                );
              }
              pageIndex ++;
            }

            //differences in pagemapping for consults begin here
            //for pages with only consult flags, remove if page doesn't belong to current consult body
            if (pageFlagsOnPage.length > 0 && notConsultPageFlagsOnPage.length == 0) {
              for (let flagInfo of pageFlagsOnPage) {
                let hasConsult = false;
                  for (let consult of doc.consult) {
                    if ((consult.page === flagInfo.page && consult.programareaid.includes(divObj.divisionid)) || (consult.page === flagInfo.page && consult.other.includes(divObj.divisionname))) {
                      hasConsult = true;
                      break;
                    }
                  }
                  if (!hasConsult) {
                    if (!pagesToRemoveEachDoc.includes(flagInfo.page)) {
                      pagesToRemoveEachDoc.push(flagInfo.page);
                      if(!skipDocumentPages) {
                        delete pageMappings[doc.documentid][flagInfo.page];
                        pagesToRemove.push(pageIndex + totalPageCountIncludeRemoved)
                      }
                    }
                  } else {
                    // add page as it will match the curent publicBody / division id
                    pageMappings[doc.documentid][flagInfo.page] =
                      pageIndex +
                      totalPageCount -
                      pagesToRemoveEachDoc.length;
                  }
                }
              pageIndex ++;
            }

            // if the page does have pageflags, process it
            for (let flagInfo of notConsultPageFlagsOnPage) {
              if (flagInfo.flagid == pageFlagTypes["Duplicate"]) {
                if(includeDuplicatePages) {
                  for (let consult of doc.consult) {
                    if ((consult.page === flagInfo.page && consult.programareaid.includes(divObj.divisionid)) || (consult.page === flagInfo.page && consult.other.includes(divObj.divisionname))) {
                      pageMappings[doc.documentid][flagInfo.page] =
                        pageIndex +
                        totalPageCount -
                        pagesToRemoveEachDoc.length;
                    }
                  }
                } else {
                  pagesToRemoveEachDoc.push(flagInfo.page);
                  if (!skipDocumentPages && !skipOnlyDuplicateDocument) {
                    pagesToRemove.push(
                      pageIndex + totalPageCountIncludeRemoved
                    );
                  }
                }

              } else if (flagInfo.flagid == pageFlagTypes["Not Responsive"]) {
                if(includeNRPages) {
                  for (let consult of doc.consult) {
                    if ((consult.page === flagInfo.page && consult.programareaid.includes(divObj.divisionid)) || (consult.page === flagInfo.page && consult.other.includes(divObj.divisionname))) {
                      pageMappings[doc.documentid][flagInfo.page] =
                      pageIndex +
                        totalPageCount -
                        pagesToRemoveEachDoc.length;
                    }
                  }
                } else {
                  pagesToRemoveEachDoc.push(flagInfo.page);
                  if (!skipDocumentPages && !skipOnlyNRDocument) {
                    pagesToRemove.push(
                      pageIndex + totalPageCountIncludeRemoved
                    );
                  }
                }
              } else if (flagInfo.flagid == pageFlagTypes["In Progress"]) {
                for (let consult of doc.consult) {
                  if ((consult.page === flagInfo.page && consult.programareaid.includes(divObj.divisionid)) || (consult.page === flagInfo.page && consult.other.includes(divObj.divisionname))) {
                    pageMappings[doc.documentid][flagInfo.page] =
                      pageIndex +
                      totalPageCount -
                      pagesToRemoveEachDoc.length;
                  }
                }
              } else {
                if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
                  pageMappings[doc.documentid][flagInfo.page] =
                    pageIndex +
                    totalPageCount -
                    pagesToRemoveEachDoc.length;
                }
              }

              // Check if the page has relevant consult flag, if not remove the page
              let hasConsult = false;
              for (let consult of doc.consult) {
                if ((consult.page === flagInfo.page && consult.programareaid.includes(divObj.divisionid)) || (consult.page === flagInfo.page && consult.other.includes(divObj.divisionname))) {
                  hasConsult = true;
                  break;
                }
              }
              if (!hasConsult) {
                if (!pagesToRemoveEachDoc.includes(flagInfo.page)) {
                  pagesToRemoveEachDoc.push(flagInfo.page);
                  if(!skipDocumentPages) {
                    delete pageMappings[doc.documentid][flagInfo.page];
                    pagesToRemove.push(pageIndex + totalPageCountIncludeRemoved)
                  }
                }
              }
              if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
                pageIndex ++;
              }
            }
          }
          //End of pageMappingsByConsults

          totalPageCount += Object.keys(
            pageMappings[doc.documentid]
          ).length;
          if (!skipDocumentPages && !skipOnlyDuplicateDocument && !skipOnlyNRDocument) {
            totalPageCountIncludeRemoved += doc.pagecount;
          }
        }
      }
      divPageMappings[divObj.divisionid] = pageMappings;
      removepages[divObj.divisionid] = pagesToRemove;
      pagesToRemove = [];
      totalPageCount = 0;
      totalPageCountIncludeRemoved = 0;
      pageMappings = {}
    }

    setRedlinepageMappings({
      'divpagemappings': divPageMappings,
      'pagemapping': pageMappings,
      'pagestoremove': removepages
    });
  }

  const prepareRedlineIncompatibleMapping = (redlineAPIResponse) => {
    let divIncompatableMapping = {};
    let incompatibleFiles = [];
    let divCounter = 0;
    if (redlineAPIResponse.consultdocumentlist) {
      redlineAPIResponse.divdocumentList = redlineAPIResponse.consultdocumentlist
    }

    for (let divObj of redlineAPIResponse.divdocumentList) {
      divCounter++;
      let incompatableObj = {};
      incompatableObj["incompatibleFiles"] = [];
      if (divObj.incompatableList.length > 0) {
        const divIncompatableFiles = divObj.incompatableList
          .filter((record) =>
            record.divisions.some(
              (division) => division.divisionid === divObj.divisionid
            )
          )
          .map((record) => {
            let fname =
              redlineAPIResponse.issingleredlinepackage === "N"
                ? divObj.divisionname + "/" + record.filename
                : record.filename;
          return {
            filename: fname,
            s3uripath: record.filepath,
          };
          });
          incompatibleFiles = incompatibleFiles.concat(divIncompatableFiles);
      }
      if (divObj.publicBody && !divObj.divisionid) divObj.divisionid = divObj.publicBody;
      if (redlineAPIResponse.issingleredlinepackage == "Y") {
        if (divCounter == redlineAPIResponse.divdocumentList.length) {
          incompatableObj["divisionid"] = "0";
          incompatableObj["divisionname"] = "0";
          incompatableObj["incompatibleFiles"] = incompatibleFiles;
          divIncompatableMapping["0"] = incompatableObj;
        }
      } else {
        incompatableObj["divisionid"] = divObj.divisionid;
        incompatableObj["divisionname"] = divObj.divisionname;
        incompatableObj["incompatibleFiles"] = incompatibleFiles;
        divIncompatableMapping[divObj.divisionid] = incompatableObj;
        incompatibleFiles = [];
      }
    }
    setRedlineIncompatabileMappings(divIncompatableMapping);
    return divIncompatableMapping
  };
  
  const fetchDocumentRedlineAnnotations = async (
    requestid,
    documentids,
    layer
  ) => {
    let documentRedlineAnnotations = {};
    let docCounter = 0;
    for (let documentid of documentids) {
      fetchDocumentAnnotations(requestid, layer, documentid, async (data) => {
        docCounter++;
        documentRedlineAnnotations[documentid] = data[documentid];
        if (docCounter === documentids.length) {
          setRedlineDocumentAnnotations(documentRedlineAnnotations);
        }
      });
    }
  };
  const getzipredlinecategory = (layertype) => {
    if (redlineCategory === "consult") {
      return "consultpackage";
    }
    if (currentLayer.name.toLowerCase() === "oipc") {
      return layertype === "oipcreview" ? "oipcreviewredline" : "oipcredline";
    }
    return "redline";
  };

  const prepareredlinesummarylist = (stitchDocuments) => {
    let summarylist = [];
    let alldocuments = [];
    for (const [key, value] of Object.entries(stitchDocuments)) {
      let summary_division = {};
      summary_division["divisionid"] = key
      let documentlist = stitchDocuments[key];
      if(documentlist.length > 0) {
        let summary_divdocuments = []
        for (let doc of documentlist) {
          summary_divdocuments.push(doc.documentid);
          alldocuments.push(doc);
        }
        summary_division["documentids"] = summary_divdocuments;
      }
      summarylist.push(summary_division);
    }
    let sorteddocids = [];
    // sort based on sortorder as the sortorder added based on the LastModified
    let sorteddocs = sortBySortOrder(alldocuments);
    for (const sorteddoc of sorteddocs) {
      if (!sorteddocids.includes(sorteddoc['documentid'])) {
        sorteddocids.push(sorteddoc['documentid']);
      }
    }
    return { "sorteddocuments": sorteddocids, "pkgdocuments": summarylist };
  };
  const stitchForRedlineExport = async (
    _instance,
    divisionDocuments,
    stitchlist,
    redlineSinglePkg,
    incompatableList,
    applyRotations
  ) => {
    let requestStitchObject = {};
      let divCount = 0;
      const noofdivision = Object.keys(stitchlist).length;
      let stitchedDocObj = null;
      for (const [key, value] of Object.entries(stitchlist)) {
        divCount++;
        let docCount = 0;
        // added this vopy variable for validating the first document of a division with NR/Duplicate
        let docCountCopy = 0;
        let division = key;
        let documentlist = stitchlist[key];
        if (redlineSinglePkg == "N") {
          toast.update(toastId.current, {
            render: `Generating redline PDF for ${noofdivision} divisions...`,
            isLoading: true,
          });
        } else {
          toast.update(toastId.current, {
            render: `Generating redline PDF...`,
            isLoading: true,
          });
        }
        if(documentlist.length > 0) {
        for (let doc of documentlist) {
            let skipDocumentPages = false;
            let skipOnlyDuplicateDocument = false;
            let skipOnlyNRDocument = false;
            if (!includeDuplicatePages && !includeNRPages) {
              skipDocumentPages = skipDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
            }
            else if (!includeDuplicatePages) {
              skipOnlyDuplicateDocument = skipDuplicateDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
            }
            else if (!includeNRPages) {
              skipOnlyNRDocument = skipNRDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
            }
            await _instance.Core.createDocument(doc.s3path_load, {
              loadAsPDF: true,
              useDownloader: false, // Added to fix BLANK page issue
            }).then(async (docObj) => {
              applyRotations(docObj, doc.attributes.rotatedpages);
              //if (isIgnoredDocument(doc, docObj.getPageCount(), divisionDocuments) == false) {
                docCountCopy++;
                docCount++;
                if (docCountCopy == 1) {
                  // Delete pages from the first document
                  const deletedPages = getDeletedPagesBeforeStitching(doc.documentid);
                  if (deletedPages.length > 0) {
                      docObj.removePages(deletedPages);
                  }
                  if (!skipDocumentPages && !skipOnlyDuplicateDocument && !skipOnlyNRDocument) {           
                    stitchedDocObj = docObj;
                  }
                  else {
                    docCountCopy--;
                  }

                } else {
                  if (stitchedDocObj && (!skipDocumentPages && !skipOnlyDuplicateDocument && !skipOnlyNRDocument)) {
                    let pageIndexToInsert = stitchedDocObj?.getPageCount() + 1;
                    await stitchedDocObj.insertPages(
                      docObj,
                      doc.pages,
                      pageIndexToInsert
                    );
                  }
                }
              //}
            });
            if (docCount == documentlist.length && redlineSinglePkg == "N" ) {
              requestStitchObject[division] = stitchedDocObj;
            }
        }
        } else {
          if (incompatableList[division]["incompatibleFiles"].length > 0) {
            requestStitchObject[division] = null
          } 
        }
        if (redlineSinglePkg == "Y" && stitchedDocObj != null) {
          requestStitchObject["0"] = stitchedDocObj;
        }
        if (divCount == noofdivision) {
          setRedlineStitchObject(requestStitchObject);
        }
        if (redlineSinglePkg == "N") {
          stitchedDocObj = null;
        }
      }
  };
  
  const stitchSingleDivisionRedlineExport = async (
    _instance,
    divisionDocuments,
    stitchlist,
    redlineSinglePkg
  ) => {
    setRequestStitchObject({});
    let divCount = 0;
    const noofdivision = Object.keys(stitchlist).length;
    let stitchedDocObj = null;
    setTotalStitchList(stitchlist);
    for (const [key, value] of Object.entries(stitchlist)) {
      divCount++;
      let docCount = 0;
      let division = key;
      let documentlist = stitchlist[key];
      if (redlineSinglePkg === "N") {
        toast.update(toastId.current, {
          render: `Generating redline PDF for ${noofdivision} divisions...`,
          isLoading: true,
        });
      } else {
        toast.update(toastId.current, {
          render: `Generating redline PDF...`,
          isLoading: true,
        });
      }
      let documentlistCopy = [...documentlist];

      let slicerdetails = await getSliceSetDetails(documentlist.length, true);
      let setCount = slicerdetails.setcount;
      let slicer = slicerdetails.slicer;
      let objpreptasks = new Array(setCount);
      let divisionDetails = {
        divCount: divCount,
        noofdivision: noofdivision,
        division: division,
      };
      setRedlineStitchDivisionDetails(divisionDetails);
      for (let slicecount = 1; slicecount <= setCount; slicecount++) {
        const sliceDoclist = documentlistCopy.splice(0, slicer);
        objpreptasks.push(
          mergeObjectsPreparationForRedline(
            _instance.Core.createDocument,
            sliceDoclist,
            slicecount,
            divisionDocuments,
            docCount,
            stitchedDocObj
          )
        );
      }
      await Promise.all(objpreptasks);
    }
  };
  const mergeObjectsPreparationForRedline = async (
    createDocument,
    sliceDoclist,
    slicecount,
    divisionDocuments,
    docCount,
    stitchedDocObj
  ) => {
    for (const filerow of sliceDoclist) {
      try {
        await createDocument(filerow.s3path_load, {
          useDownloader: false, // Added to fix BLANK page issue
          loadAsPDF: true, // Added to fix jpeg/pdf stitiching issue #2941
        }).then(async (newDoc) => {
          docCount++;
          // if (isIgnoredDocument(filerow, newDoc, divisionDocuments) === false) {
            if (filerow.stitchIndex === 1) {
              // Delete pages from the first document
              const deletedPages = getDeletedPagesBeforeStitching(
                filerow?.documentid
              );
              if (deletedPages.length > 0) {
                await newDoc.removePages(deletedPages);
              }
              stitchedDocObj = newDoc;
              setstichedfilesForRedline(stitchedDocObj);
            } else {
              setPdftronDocObjectsForRedline((_arr) => [
                ..._arr,
                {
                  file: filerow,
                  sortorder: filerow.sortorder,
                  pages: filerow.pages,
                  pdftronobject: newDoc,
                  stitchIndex: filerow.stitchIndex,
                  set: slicecount,
                  totalsetcount: sliceDoclist.length,
                },
              ]);
            }
          // }
        });
      } catch (error) {
        console.error("An error occurred during create document:", error);
        // Handle any errors that occurred during the asynchronous operations
      }
    }
  };
  const setStitchDetails = (sortedList) => {
    let index = 0;
    let stitchIndex = 1;
    sortedList.forEach((sortedItem, _index) => {
      index = index + sortedItem.pagecount;
      /**  DO NOT setup the sortorder to 1 for 1st divisional document 
       * as the sort order is used to sort the document irrespective of the division 
       * sortedItem.sortorder = _index + 1; 
       */
      sortedItem.stitchIndex = stitchIndex;
      /**  No need to update the pages again as the pages are already updated while 
       * preparing prepareMapperObj sortedItem.pages = pages;*/
      stitchIndex += sortedItem.pagecount;
    });
    return sortedList;
  };
  const getPublicBodyList = (documentList) => {
    let publicBodyIdList = [];
    if (documentList?.length > 0) {
      for (const doc of documentList) {
        if ('pageFlag' in doc) {
          for (let pageflag of doc['pageFlag']) {
            if ('programareaid' in pageflag) {
              for (let programareaid of pageflag['programareaid']) {
                publicBodyIdList.push(programareaid);
              }
            }
            // Logic to include custom consults/public bodies as they are stored in another array (other) and not with programareaids
            if ('other' in pageflag) {
              for (let customPublicBody of pageflag['other']) {
                publicBodyIdList.push(customPublicBody);
              }
            }
          }
        }
      }
      const filteredPublicBodyIdList = [...new Set(publicBodyIdList)];
      return getPublicBodyObjs(filteredPublicBodyIdList);
    }
  }
  const getPublicBodyObjs = (publicBodyIDList) => {
    const publicBodies = [];
    for (let publicBodyId of publicBodyIDList) {
      const publicBody = allPublicBodies.find(publicBody => publicBody.programareaid === publicBodyId);
      if (publicBody) {
        publicBodies.push(publicBody);
      } else {
        // Custom public bodies/consults will not exist in allPublicBodies data (BE data for program areas) as they are not stored in the BE as programe areas (but rather as basic pageflags)
        const customPublicBody = {
          name: publicBodyId,
          programareaid: null,
          iaocode: publicBodyId
        };
        publicBodies.push(customPublicBody);
      }
    }
    return publicBodies;
  }

  const saveRedlineDocument = async (
    _instance,
    layertype, 
    incompatibleFiles,
    documentList,
    pageMappedDocs,
    applyRotations
  ) => {
    toastId.current = toast(`Start saving redline...`, {
      autoClose: false,
      closeButton: false,
      isLoading: true,
    });

    const divisionFilesList = [...documentList, ...incompatibleFiles];
    let divisions;
    if (redlineCategory === "consult") {
      //Key consult logic, uses preexisting division reldine logic for consults
      divisions = selectedPublicBodyIDs;
    } else {
      divisions = getDivisionsForSaveRedline(divisionFilesList);
    }
    const divisionDocuments = getDivisionDocumentMappingForRedline(divisions, documentList, incompatibleFiles);
    const documentids = documentList.map((obj) => obj.documentid);
    getFOIS3DocumentRedlinePreSignedUrl(
      foiministryrequestid,
      //normalizeforPdfStitchingReq(divisionDocuments),
      requestType,
      divisionDocuments,
      async (res) => {
        toast.update(toastId.current, {
          render: `Start saving redline...`,
          isLoading: true,
        });
        setIsSingleRedlinePackage(res.issingleredlinepackage);
        let stitchDoc = {};

        prepareRedlinePageMapping(
          res['divdocumentList'],
          res.issingleredlinepackage,
          pageMappedDocs
        );
        let IncompatableList = prepareRedlineIncompatibleMapping(res);
        setIncompatableList(IncompatableList);
        fetchDocumentRedlineAnnotations(foiministryrequestid, documentids, currentLayer.name.toLowerCase());
        
        let stitchDocuments = {};
        let documentsObjArr = [];
        let divisionstitchpages = [];
        let divCount = 0;
        for (let div of res.divdocumentList) {
          divCount++;
          let docCount = 0;
          if(res.issingleredlinepackage == "Y" || (res.issingleredlinepackage == "N" && isValidRedlineDivisionDownload(div.divisionid, divisionDocuments))) {
            for (let doc of div.documentlist) {
              docCount++;
              documentsObjArr.push(doc);
              let skipDocumentPages = false;
              let skipOnlyDuplicateDocument = false;
              let skipOnlyNRDocument = false;
              if (!includeDuplicatePages && !includeNRPages) {
                skipDocumentPages = skipDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
              }
              else if (!includeDuplicatePages) {
                skipOnlyDuplicateDocument = skipDuplicateDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
              }
              else if (!includeNRPages) {
                skipOnlyNRDocument = skipNRDocument(doc.pageFlag, doc.pagecount, pageFlagTypes);
              } 
              if (pageMappedDocs != undefined) {
                let divisionsdocpages = [];
                // for consults, no need to filter by division/consult
                if (redlineCategory === "consult") {
                  Object.values(
                    pageMappedDocs.redlineDocIdLookup
                  )
                  .forEach((obj) => {
                    divisionsdocpages = Object.values(
                      pageMappedDocs.redlineDocIdLookup
                    )
                      .filter((obj) => {
                        return obj.docId == doc.documentid;
                      })
                      .map((obj) => {
                        if (res.issingleredlinepackage == "Y" || (!skipDocumentPages && !skipOnlyDuplicateDocument && !skipOnlyNRDocument)) {
                          return obj.pageMappings;
                        }
                      });
                  })
                } else {
                  divisionsdocpages = Object.values(
                    pageMappedDocs.redlineDocIdLookup
                  )
                  .filter((obj) => {
                    return obj.division.includes(div.divisionid) && obj.docId == doc.documentid;
                  })
                  .map((obj) => {
                    if (res.issingleredlinepackage == "Y" || (!skipDocumentPages && !skipOnlyDuplicateDocument && !skipOnlyNRDocument)) {
                      return obj.pageMappings;
                    }
                  });
                }
                if (divisionsdocpages[0]) {
                  divisionsdocpages.forEach(function (_arr) {
                    _arr.forEach(function (value) {
                      divisionstitchpages.push(value);
                    });
                  });
                  divisionstitchpages.sort((a, b) =>
                    a.stitchedPageNo > b.stitchedPageNo
                      ? 1
                      : b.stitchedPageNo > a.stitchedPageNo
                      ? -1
                      : 0
                  );
                }
              }
            }
          }
          if (
            res.issingleredlinepackage == "Y" &&
            divCount == res.divdocumentList.length
          ) {
            let sorteddocIds = [];

            // sort based on sortorder as the sortorder added based on the LastModified
            let sorteddocuments =  sortBySortOrder(documentsObjArr);
            stitchDocuments["0"] = setStitchDetails(sorteddocuments);

            for(const element of sorteddocuments) {
              sorteddocIds.push(element['documentid']);
            }
            stitchDoc["0"] = {
              documentids: sorteddocIds,
              s3path: res.s3path_save,
              stitchpages: divisionstitchpages,
              bcgovcode: res.bcgovcode,
            };
          }
          if (
            res.issingleredlinepackage != "Y" &&
            docCount == div.documentlist.length
          ) {
                          
            let divdocumentids = [];
            // sort based on sortorder as the sortorder added based on the LastModified
            let sorteddocuments =  sortBySortOrder(div.documentlist);
            stitchDocuments[div.divisionid] = setStitchDetails(sorteddocuments);

            for(const element of sorteddocuments) {
              divdocumentids.push(element['documentid']);
            }
            stitchDoc[div.divisionid] = {
              documentids: divdocumentids,
              s3path: div.s3path_save,
              stitchpages: divisionstitchpages,
              bcgovcode: res.bcgovcode,
            };
            divisionstitchpages = [];
            documentsObjArr = [];
          }
        }
        
        setRedlineStitchInfo(stitchDoc);
        setIsSingleRedlinePackage(res.issingleredlinepackage);
        setRedlineZipperMessage({
          ministryrequestid: foiministryrequestid,
          category: getzipredlinecategory(layertype),
          attributes: [],
          requestnumber: res.requestnumber,
          bcgovcode: res.bcgovcode,
          summarydocuments: prepareredlinesummarylist(stitchDocuments),
          redactionlayerid: currentLayer.redactionlayerid,
          requesttype: requestType
        });
        if (res.issingleredlinepackage === "Y") {
          stitchSingleDivisionRedlineExport(
            _instance,
            divisionDocuments,
            stitchDocuments,
            res.issingleredlinepackage
          );
        }
        else {
          stitchForRedlineExport(
            _instance,
            divisionDocuments,
            stitchDocuments,
            res.issingleredlinepackage,
            IncompatableList,
            applyRotations
          );
        }
      },
      (error) => {
        console.log("Error fetching document:", error);
      },
      layertype,
      currentLayer.name.toLowerCase()
    );
  };
  
  const checkSavingRedline = (redlineReadyAndValid, instance) => {
    const validRedlineStatus = [
      RequestStates["Records Review"],
      RequestStates["Ministry Sign Off"],
      RequestStates["Peer Review"],
    ].includes(requestStatus);
    setEnableSavingRedline(redlineReadyAndValid && validRedlineStatus);
    if (instance) {
      const document = instance.UI.iframeWindow.document;
      document.getElementById("redline_for_sign_off").disabled =
        !redlineReadyAndValid || !validRedlineStatus;
    }
  };
  const checkSavingOIPCRedline = (
    oipcRedlineReadyAndValid,
    instance,
    readyForSignOff
  ) => {
    const validOIPCRedlineStatus = [
      RequestStates["Records Review"],
      RequestStates["Ministry Sign Off"],
    ].includes(requestStatus);
    setEnableSavingOipcRedline(
      oipcRedlineReadyAndValid && validOIPCRedlineStatus
    );
    if (instance) {
      const document = instance.UI.iframeWindow.document;
      document.getElementById("redline_for_oipc").disabled =
        !oipcRedlineReadyAndValid ||
        !validOIPCRedlineStatus ||
        !readyForSignOff;
    }
  };
  const checkSavingConsults = (documentList, instance) => {
    const publicBodyList = getPublicBodyList(documentList);
    setDocumentPublicBodies(publicBodyList);
    setEnableSavingConsults(
      publicBodyList.length > 0
    );
    if (instance) {
      const document = instance.UI.iframeWindow.document;
      document.getElementById("consult_package").disabled = !(publicBodyList.length > 0);
    }
  }
  const triggerRedlineZipper = (
    divObj,
    stitchedDocPath,
    divisionCountForToast,
    isSingleRedlinePackage
  ) => {
    prepareMessageForRedlineZipping(
      divObj,
      divisionCountForToast,
      redlineZipperMessage,
      isSingleRedlinePackage,
      stitchedDocPath
    );
    setIncludeDuplicatePages(false);
    setIncludeNRPages(false);
    setIncludeComments(false);
  };
  const prepareMessageForRedlineZipping = (
    divObj,
    divisionCountForToast,
    zipServiceMessage,
    redlineSinglePkg,
    stitchedDocPath = ""
  ) => {
    const zipDocObj = {
      divisionid: null,
      divisionname: null,
      files: [],
      includeduplicatepages: includeDuplicatePages,
      includenrpages: includeNRPages,
      includecomments: includeComments,
    };
    if (stitchedDocPath) {
      const stitchedDocPathArray = stitchedDocPath?.split("/");
      let fileName =
        stitchedDocPathArray[stitchedDocPathArray.length - 1].split("?")[0];
      if (redlineSinglePkg !== "Y") {
        fileName = divObj.divisionname + "/" + decodeURIComponent(fileName);
      }
      const file = {
        filename: fileName,
        s3uripath: decodeURIComponent(stitchedDocPath?.split("?")[0]),
      };
      zipDocObj.files.push(file);
    }
    if (divObj["incompatibleFiles"].length > 0) {
      zipDocObj.files = [...zipDocObj.files, ...divObj["incompatibleFiles"]];
    }
    if (redlineSinglePkg === "N") {
      zipDocObj.divisionid = divObj["divisionid"];
      zipDocObj.divisionname = divObj["divisionname"];
    }
    zipServiceMessage.attributes.push(zipDocObj);
    if (divisionCountForToast === zipServiceMessage.attributes.length) {
      triggerDownloadRedlines(zipServiceMessage, (error) => {
        console.log(error);
        window.location.reload();
      });
    }
    return zipServiceMessage;
  };

const stampPageNumberRedline = async (
      _docViwer,
      PDFNet,
      divisionsdocpages,
      isSingleRedlinePackage
    ) => {
      try {
        for (
          let pagecount = 1;
          pagecount <= divisionsdocpages.length;
          pagecount++
        ) {
          
          const doc = await _docViwer.getPDFDoc();
          // Run PDFNet methods with memory management
          await PDFNet.runWithCleanup(async () => {
            // lock the document before a write operation
            // runWithCleanup will auto unlock when complete
            doc.lock();
            const s = await PDFNet.Stamper.create(
              PDFNet.Stamper.SizeType.e_relative_scale,
              0.3,
              0.3
            );
            await s.setAlignment(
              PDFNet.Stamper.HorizontalAlignment.e_horizontal_center,
              PDFNet.Stamper.VerticalAlignment.e_vertical_bottom
            );
            const font = await PDFNet.Font.create(
              doc,
              PDFNet.Font.StandardType1Font.e_courier
            );
            await s.setFont(font);
            const redColorPt = await PDFNet.ColorPt.init(0, 0, 128, 0.5);
            await s.setFontColor(redColorPt);
            await s.setTextAlignment(PDFNet.Stamper.TextAlignment.e_align_right);
            await s.setAsBackground(false);
            const pgSet = await PDFNet.PageSet.createRange(pagecount, pagecount);
            let pagenumber =
              isSingleRedlinePackage === "Y" || redlineCategory === "oipcreview"
                ? pagecount
                : divisionsdocpages[pagecount - 1]?.stitchedPageNo;
            let totalpagenumber =
              redlineCategory === "oipcreview"
                ? _docViwer.getPageCount()
                : docViewer.getPageCount();
            await s.stampText(
              doc,
              `${requestnumber} , Page ${pagenumber} of ${totalpagenumber}`,
              pgSet
            );
          });
        }
      } catch (err) {
        console.log(err);
        throw err;
      }
    };

  const formatAnnotationsForRedline = (
    redlineDocumentAnnotations,
    redlinepageMappings,
    documentids
  ) => {
    let domParser = new DOMParser();
    let stitchAnnotation = [];
    for (let docid of documentids) {
      stitchAnnotation.push(
        formatAnnotationsForDocument(
          domParser,
          redlineDocumentAnnotations[docid],
          redlinepageMappings,
          docid
        )
      );
    }
    return stitchAnnotation.join("");
  };

  const formatAnnotationsForDocument = (
    domParser,
    data,
    redlinepageMappings,
    documentid
  ) => {
    let updatedXML = [];
    const { _freeTextIds, _annoteIds } = constructFreeTextAndannoteIds(data);

    for (let annotxml of data) {
      let xmlObj = parser.parseFromString(annotxml);
      let customfield = xmlObj.children.find(
        (xmlfield) => xmlfield.name === "trn-custom-data"
      );    
      let flags = xmlObj.attributes.flags;
      let txt = domParser.parseFromString(
        customfield.attributes.bytes,
        "text/html"
      );
      let customData = JSON.parse(txt.documentElement.textContent);
      let originalPageNo = parseInt(customData.originalPageNo);
      if (redlinepageMappings[documentid][originalPageNo + 1]) {
        //skip pages that need to be removed
        // page num from annot xml
        let y = annotxml.split('page="');
        let z = y[1].split('"');
        let oldPageNum = 'page="' + z[0] + '"';
        let newPage =
          'page="' +
          (redlinepageMappings[documentid][originalPageNo + 1] - 1) +
          '"';
        let updatedFlags = xmlObj.attributes.flags + ",locked";

        annotxml = annotxml.replace(flags, updatedFlags);
        annotxml = annotxml.replace(oldPageNum, newPage);

        if (
          xmlObj.name === "redact" ||
          customData["parentRedaction"] ||
          (Object.entries(filteredComments).length > 0 &&
            checkFilter(xmlObj, _freeTextIds, _annoteIds))
        ) 
          updatedXML.push(annotxml);
      }
    }
    return updatedXML.join("");
  };

  const constructFreeTextAndannoteIds = (data) => {
    let _freeTextIds = [];
    let _annoteIds = [];
    for (let annotxml of data) {
      let xmlObj = parser.parseFromString(annotxml);
      if (xmlObj.name === "freetext") _freeTextIds.push(xmlObj.attributes.name);
      else if (xmlObj.name !== "redact" && xmlObj.name !== "freetext") {
        let xmlObjAnnotId = xmlObj.attributes.name;
        _annoteIds.push({ [xmlObjAnnotId]: xmlObj });
      }
    }
    return { _freeTextIds, _annoteIds };
  };
  const checkFilter = (xmlObj, _freeTextIds, _annoteIds) => {
    //This method handles filtering of annotations in redline
    let filtered = false;
    const isType =
      filteredComments.types.includes(xmlObj.name) &&
      !_freeTextIds.includes(xmlObj.attributes.inreplyto);
    const isColor = filteredComments.colors.includes(
      xmlObj.attributes.color?.toLowerCase() + "ff"
    );
    const isAuthor = filteredComments.authors.includes(xmlObj.attributes.title);

    const parentIsType =
      _annoteIds.find((obj) =>
        obj.hasOwnProperty(xmlObj.attributes.inreplyto)
      ) &&
      filteredComments.types?.includes(
        _annoteIds.find((obj) =>
          obj.hasOwnProperty(xmlObj.attributes.inreplyto)
        )?.[xmlObj.attributes.inreplyto].name
      ) &&
      !_freeTextIds.includes(
        _annoteIds.find((obj) =>
          obj.hasOwnProperty(xmlObj.attributes.inreplyto)
        )?.[xmlObj.attributes.inreplyto].attributes.inreplyto
      );

    const parentIsColor =
      _annoteIds.find((obj) =>
        obj.hasOwnProperty(xmlObj.attributes.inreplyto)
      ) &&
      filteredComments.colors?.includes(
        _annoteIds
          .find((obj) => obj.hasOwnProperty(xmlObj.attributes.inreplyto))
          ?.[xmlObj.attributes.inreplyto].attributes.color?.toLowerCase() + "ff"
      );

    const parentIsAuthor =
      _annoteIds.find((obj) =>
        obj.hasOwnProperty(xmlObj.attributes.inreplyto)
      ) &&
      filteredComments.authors?.includes(
        _annoteIds.find((obj) =>
          obj.hasOwnProperty(xmlObj.attributes.inreplyto)
        )?.[xmlObj.attributes.inreplyto].attributes.title
      );

    if (
      filteredComments.types.length > 0 &&
      filteredComments.colors.length > 0 &&
      filteredComments.authors.length > 0
    ) {
      if (
        _annoteIds.find((obj) =>
          obj.hasOwnProperty(xmlObj.attributes.inreplyto)
        ) &&
        parentIsType &&
        parentIsColor &&
        parentIsAuthor
      ) {
        return true;
      } else if (
        typeof parentIsType !== "undefined" &&
        typeof parentIsColor !== "undefined" &&
        typeof parentIsAuthor !== "undefined"
      ) {
        return parentIsType && parentIsColor && parentIsAuthor;
      }
      filtered = isType && (isColor || parentIsColor) && isAuthor;
    } else if (
      filteredComments.types.length > 0 &&
      filteredComments.colors.length > 0
    ) {
      if (
        _annoteIds.find((obj) =>
          obj.hasOwnProperty(xmlObj.attributes.inreplyto)
        ) &&
        parentIsType &&
        parentIsColor
      ) {
        return true;
      } else if (
        typeof parentIsType !== "undefined" &&
        typeof parentIsColor !== "undefined"
      ) {
        return parentIsType && parentIsColor;
      }
      filtered = isType && (isColor || parentIsColor);
    } else if (
      filteredComments.types.length > 0 &&
      filteredComments.authors.length > 0
    ) {
      if (
        _annoteIds.find((obj) =>
          obj.hasOwnProperty(xmlObj.attributes.inreplyto)
        ) &&
        parentIsType &&
        parentIsAuthor
      ) {
        return true;
      } else if (
        typeof parentIsType !== "undefined" &&
        typeof parentIsAuthor !== "undefined"
      ) {
        return parentIsType && parentIsAuthor;
      }
      filtered = isType && isAuthor;
    } else if (
      filteredComments.colors.length > 0 &&
      filteredComments.authors.length > 0
    ) {
      if (
        _annoteIds.find((obj) =>
          obj.hasOwnProperty(xmlObj.attributes.inreplyto)
        ) &&
        parentIsColor &&
        parentIsAuthor
      ) {
        return true;
      } else if (
        typeof parentIsColor !== "undefined" &&
        typeof parentIsAuthor !== "undefined"
      ) {
        return parentIsColor && parentIsAuthor;
      }
      filtered = (isColor || parentIsColor) && isAuthor;
    } else if (filteredComments.types.length > 0) {
      if (
        _annoteIds.find((obj) =>
          obj.hasOwnProperty(xmlObj.attributes.inreplyto)
        ) &&
        parentIsType
      ) {
        return true;
      } else if (typeof parentIsType !== "undefined") {
        return parentIsType;
      }
      return isType;
    } else if (filteredComments.colors.length > 0) {
      if (
        _annoteIds.find((obj) =>
          obj.hasOwnProperty(xmlObj.attributes.inreplyto)
        ) &&
        parentIsColor
      ) {
        return true;
      } else if (typeof parentIsColor !== "undefined") {
        return parentIsColor;
      }
      return isColor;
    } else if (filteredComments.authors.length > 0) {
      if (
        _annoteIds.find((obj) =>
          obj.hasOwnProperty(xmlObj.attributes.inreplyto)
        ) &&
        parentIsAuthor
      ) {
        return true;
      } else if (typeof parentIsAuthor !== "undefined") {
        return parentIsAuthor;
      }
      return isAuthor;
    }
    return filtered;
  };
  const annotationSectionsMapping = async (
    xfdfString,
    formattedAnnotationXML
  ) => {
    let annotationManager = docInstance?.Core.annotationManager;
    let annotList = await annotationManager.importAnnotations(xfdfString);
    let sectionStamps = {};
    let annotationpagenumbers = annotationpagemapping(formattedAnnotationXML);
    for (const annot of annotList) {
      let parentRedaction = annot.getCustomData("parentRedaction");
      if (parentRedaction) {
        if (annot.Subject === "Free Text") {
          let parentRedactionId = parentRedaction
            .replace(/&quot;/g, '"')
            .replace(/\\/g, "");
          let sections = getAnnotationSections(annot);
          if (redlineCategory === "oipcreview" && sections.some((item) => item.section === "s. 14")) {
            sectionStamps[parentRedactionId] =
              annotationpagenumbers[parentRedactionId];
          }
          if (redlineCategory === "consult" && sections.some(item => item.section === 'NR')) {
            sectionStamps[parentRedactionId] = annotationpagenumbers[parentRedactionId];
          }
        }
      }
    }
    return sectionStamps;
  };
  const annotationpagemapping = (formattedAnnotationXML) => {
    let xmlstring = "<annots>" + formattedAnnotationXML + "</annots>";
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlstring, "text/xml");
    let annotnodes = xmlDoc.documentElement.childNodes;
    let annotationpages = {};
    for (const element of annotnodes) {
      if (element.nodeName === "redact") {
        annotationpages[element.getAttribute("name")] =
          parseInt(element.getAttribute("page")) + 1;
      }
    }
    return annotationpages;
  };
  const getAnnotationSections = (annot) => {
    let customSectionsData = annot.getCustomData("sections");
    let stampJson = JSON.parse(
      customSectionsData
        .replace(/&quot;\[/g, "[")
        .replace(/\]&quot;/g, "]")
        .replace(/&quot;/g, '"')
        .replace(/\\/g, "")
    );
    return stampJson;
  };
  const stitchPagesForRedline = (pdftronDocObjs) => {
    for (let filerow of pdftronDocObjs) {
      let _exists = alreadyStitchedList.filter(
        (_file) => _file.file.documentid === filerow.file.documentid
      );
      if (_exists?.length === 0) {
        let index = filerow.stitchIndex;
        try {
          stichedfilesForRedline
            ?.insertPages(filerow.pdftronobject, filerow.pages, index)
            .then(() => {})
            .catch((error) => {
              console.error("An error occurred during page insertion:", error);
            });
          setAlreadyStitchedList((_arr) => [..._arr, filerow]);
          setstichedfilesForRedline(stichedfilesForRedline);
        } catch (error) {
          console.error("An error occurred during page insertion:", error);
        }
      }
    }
  };

  //useEffects to keep docInstance and docViewer state up to date with Redlining.js
  useEffect(() => {
    setDocInstance(initDocInstance);
  }, [initDocInstance]);
  useEffect(() => {
    setDocViewer(initDocViewer);
  }, [initDocViewer]);

  const StitchAndUploadDocument = async () => {
    const { PDFNet, annotationManager } = docInstance.Core;
    const downloadType = "pdf";
    let currentDivisionCount = 0;
    const divisionCountForToast = Object.keys(redlineStitchObject).length;

    //Consult Package page removal logic
    let pagesOfEachDivisions = {};
    //get page numbers of each division
    Object.keys(redlineStitchInfo).forEach((_div) => {
      pagesOfEachDivisions[_div] = [];
      redlineStitchInfo[_div]["stitchpages"].forEach((pageinfo) => {
        pagesOfEachDivisions[_div].push(pageinfo["stitchedPageNo"]); 
      });
    });

    for (const [key, value] of Object.entries(redlineStitchObject)) {
      currentDivisionCount++;
      toast.update(toastId.current, {
        render:
          isSingleRedlinePackage == "N"
            ? `Saving redline PDF for ${divisionCountForToast} ${redlineCategory === "consult" ? "consultees" : "divisions"} to Object Storage...`
            : `Saving redline PDF to Object Storage...`,
        isLoading: true,
        autoClose: 5000,
      });
        let divisionid = key;
        let stitchObject = redlineStitchObject[key];
        if (stitchObject == null) {
          triggerRedlineZipper(
            redlineIncompatabileMappings[divisionid],
            null, // stitchObject == null then no stichedDocPath available
            divisionCountForToast,
            isSingleRedlinePackage
          );
        } else {
          let formattedAnnotationXML = formatAnnotationsForRedline(
            redlineDocumentAnnotations,
            redlinepageMappings["divpagemappings"][divisionid],
            redlineStitchInfo[divisionid]["documentids"]
          );
          if (redlineCategory === "redline") {
            await stampPageNumberRedline(
              stitchObject,
              PDFNet,
              redlineStitchInfo[divisionid]["stitchpages"],
              isSingleRedlinePackage
            );
          if (
            redlinepageMappings["pagestoremove"][divisionid] &&
            redlinepageMappings["pagestoremove"][divisionid].length > 0 &&
              stitchObject?.getPageCount() > redlinepageMappings["pagestoremove"][divisionid].length
          ) {
            await stitchObject.removePages(
              redlinepageMappings["pagestoremove"][divisionid]
            );
          }
            await addWatermarkToRedline(
              stitchObject,
              redlineWatermarkPageMapping,
              key
            );
          }
          
          let string = await stitchObject.extractXFDF();

          // for redline - formatted annots
          let xmlObj = parser.parseFromString(string.xfdfString);
          let annots = parser.parseFromString('<annots>' + formattedAnnotationXML + '</annots>');
          let annotsObj = xmlObj.getElementsByTagName('annots');
          if (annotsObj.length > 0) {
            annotsObj[0].children = annotsObj[0].children.concat(annots.children);
          } else {
            xmlObj.children.push(annots);
          }       
          let xfdfString = parser.toString(xmlObj);

          // for oipc review - re-apply annots after redaction - annots only no widgets/form fields
          let xmlObj1 = parser.parseFromString(string.xfdfString);
          xmlObj1.children = [];
          xmlObj1.children.push(annots);
          let xfdfString1 = parser.toString(xmlObj1);
          
          //Apply Redactions (if any)
          //OIPC - Special Block (Redact S.14) : Begin
          if(redlineCategory === "oipcreview") {
            let annotationManager = docInstance?.Core.annotationManager;
            let s14_sectionStamps = await annotationSectionsMapping(xfdfString, formattedAnnotationXML);
            let s14annots = [];
            for (const [key, value] of Object.entries(s14_sectionStamps)) {
              let s14annoation = annotationManager.getAnnotationById(key);
                  if ( s14annoation.Subject === "Redact") { 
                    s14annots.push(s14annoation);
                  }
            }
            
            let doc = docViewer.getDocument();
            await annotationManager.applyRedactions(s14annots);
                        
            /** apply redaction and save to s3 - newXfdfString is needed to display
             * the freetext(section name) on downloaded file.*/
            doc
              .getFileData({
                // export the document to arraybuffer
                // xfdfString: xfdfString,
                downloadType: downloadType,
                flatten: true,
              })
              .then(async (_data) => {
                const _arr = new Uint8Array(_data);
                const _blob = new Blob([_arr], { type: "application/pdf" });
  
                await docInstance?.Core.createDocument(_data, {
                  loadAsPDF: true,
                  useDownloader: false, // Added to fix BLANK page issue
                }).then( async (docObj) => {
  
                  /**must apply redactions before removing pages*/
                  if (redlinepageMappings["pagestoremove"][divisionid].length > 0) {
                    await docObj.removePages(redlinepageMappings["pagestoremove"][divisionid]);
                  }
  
                  await stampPageNumberRedline(
                    docObj,
                    PDFNet,
                    redlineStitchInfo[divisionid]["stitchpages"],
                    isSingleRedlinePackage
                  );

                  docObj.getFileData({
                    // saves the document with annotations in it
                    xfdfString: xfdfString1,
                    downloadType: downloadType,
                    flatten: true,
                  })
                  .then(async (__data) => {
                    const __arr = new Uint8Array(__data);
                    const __blob = new Blob([__arr], { type: "application/pdf" });
  
                    saveFilesinS3(
                      { filepath: redlineStitchInfo[divisionid]["s3path"] },
                      __blob,
                      (_res) => {
                        // ######### call another process for zipping and generate download here ##########
                        toast.update(toastId.current, {
                          render: `Redline PDF saved to Object Storage`,
                          type: "success",
                          className: "file-upload-toast",
                          isLoading: false,
                          autoClose: 3000,
                          hideProgressBar: true,
                          closeOnClick: true,
                          pauseOnHover: true,
                          draggable: true,
                          closeButton: true,
                        });
                        triggerRedlineZipper(
                          redlineIncompatabileMappings[divisionid],
                          redlineStitchInfo[divisionid]["s3path"],
                          divisionCountForToast,
                          isSingleRedlinePackage
                        );
                      },
                      (_err) => {
                        console.log(_err);
                        toast.update(toastId.current, {
                          render: "Failed to save redline pdf to Object Storage",
                          type: "error",
                          className: "file-upload-toast",
                          isLoading: false,
                          autoClose: 3000,
                          hideProgressBar: true,
                          closeOnClick: true,
                          pauseOnHover: true,
                          draggable: true,
                          closeButton: true,
                        });
                      }
                    );
                  });
                });
              });
          }
          //OIPC - Special Block : End
          //Consults - Redlines + Redactions (Redact S.NR) Block : Start
          else if (redlineCategory === "consult") {
            let doc = docViewer.getDocument();
            if (!consultApplyRedlines) {
              const publicbodyAnnotList = xmlObj1.getElementsByTagName('annots')[0]['children'];
              const filteredPublicbodyAnnotList = publicbodyAnnotList.filter((annot) => {
                return annot.name !== "freetext" && annot.name !== 'redact'
              });
              xmlObj1.getElementsByTagName('annots')[0].children = filteredPublicbodyAnnotList;
              xfdfString1 = parser.toString(xmlObj1);
            }
            if (consultApplyRedactions) {
              let annotationManager = docInstance?.Core.annotationManager;
              let nr_sectionStamps = await annotationSectionsMapping(xfdfString, formattedAnnotationXML);
              let nrAnnots = [];
              for (const [key, value] of Object.entries(nr_sectionStamps)) {
                let nrAnnotation = annotationManager.getAnnotationById(key);
                    if (nrAnnotation.Subject === "Redact") { 
                      nrAnnots.push(nrAnnotation);
                    }
              }
              await annotationManager.applyRedactions(nrAnnots);
            }
            /** apply redaction and save to s3 - newXfdfString is needed to display
            * the freetext(section name) on downloaded file.*/
            doc
            .getFileData({
              // export the document to arraybuffer
              downloadType: downloadType,
              flatten: true,
            })
            .then(async (_data) => {
              const _arr = new Uint8Array(_data);
              const _blob = new Blob([_arr], { type: "application/pdf" });

              await docInstance?.Core.createDocument(_data, {
                loadAsPDF: true,
                useDownloader: false, // Added to fix BLANK page issue
              }).then( async (docObj) => {

                // Consult Pacakge page removal of pages that are not in this division (will leave consult/division specific pages in docObj to be removed by redlinepagemappings pagestoremove below)
                let pagesNotBelongsToThisDivision = [];
                for(let i=1; i <= docObj.getPageCount(); i++) {
                  if(!pagesOfEachDivisions[key].includes(i))
                    pagesNotBelongsToThisDivision.push(i);
                }

                if(pagesNotBelongsToThisDivision.length > 0) {
                  await docObj.removePages(pagesNotBelongsToThisDivision);
                }

                await stampPageNumberRedline(
                  docObj,
                  PDFNet,
                  redlineStitchInfo[divisionid]["stitchpages"],
                  isSingleRedlinePackage
                );

                //Consult Pacakge page removal of pages/documents associated with divison/consult
                /**must apply redactions before removing pages*/
                if (redlinepageMappings["pagestoremove"][divisionid].length > 0) {
                  await docObj.removePages(redlinepageMappings["pagestoremove"][divisionid]);
                }

                docObj.getFileData({
                  // saves the document with annotations in it
                  xfdfString: xfdfString1,
                  downloadType: downloadType,
                  // flatten: true,
                })
                .then(async (__data) => {
                  const __arr = new Uint8Array(__data);
                  const __blob = new Blob([__arr], { type: "application/pdf" });

                  saveFilesinS3(
                    { filepath: redlineStitchInfo[divisionid]["s3path"] },
                    __blob,
                    (_res) => {
                      // ######### call another process for zipping and generate download here ##########
                      toast.update(toastId.current, {
                        render: `Consult PDF saved to Object Storage`,
                        type: "success",
                        className: "file-upload-toast",
                        isLoading: false,
                        autoClose: 3000,
                        hideProgressBar: true,
                        closeOnClick: true,
                        pauseOnHover: true,
                        draggable: true,
                        closeButton: true,
                      });
                      triggerRedlineZipper(
                        redlineIncompatabileMappings[divisionid],
                        redlineStitchInfo[divisionid]["s3path"],
                        divisionCountForToast,
                        isSingleRedlinePackage
                      );
                    },
                    (_err) => {
                      console.log(_err);
                      toast.update(toastId.current, {
                        render: "Failed to save redline pdf to Object Storage",
                        type: "error",
                        className: "file-upload-toast",
                        isLoading: false,
                        autoClose: 3000,
                        hideProgressBar: true,
                        closeOnClick: true,
                        pauseOnHover: true,
                        draggable: true,
                        closeButton: true,
                      });
                    }
                  );
                });
              });
            });
          }
          //Consults - Redlines + Redactions (Redact S.NR) Block : End
        else {
          let filteredAnnotations = [];
          let domParser = new DOMParser();
          if(includeComments && Object.entries(filteredComments).length > 0) {
            const annotFiltered = Object.values(redlineDocumentAnnotations).flat();
            const { _freeTextIds, _annoteIds } = constructFreeTextAndannoteIds(annotFiltered);
            let xmlObjOne = parser.parseFromString(string.xfdfString);
            xmlObjOne.children = [];
            for (let annotxml of annotFiltered) {
              let xmlObjTemp = parser.parseFromString(annotxml);
              let customfield = xmlObjTemp.children.find(
                (xmlfield) => xmlfield.name === "trn-custom-data"
              );    
              let txt = domParser.parseFromString(
                customfield.attributes.bytes,
                "text/html"
              );
              let customData = JSON.parse(txt.documentElement.textContent);
              if (xmlObjTemp.name !== 'redact' && !customData["parentRedaction"] && checkFilter(xmlObjTemp, _freeTextIds, _annoteIds)) {
                if(xmlObjOne.children.length >0 ) {
                  xmlObjOne.children[0].children.push(parser.parseFromString(parser.toString(xmlObjTemp)))
                } else {
                  xmlObjOne.children.push(parser.parseFromString('<annots>' +parser.toString(xmlObjTemp)+ '</annots>'))
                }
              }
            }
            let xfdfStringFiltered = parser.toString(xmlObjOne);
            filteredAnnotations = await annotationManager.importAnnotations(xfdfStringFiltered);
          }
          
          let _data = await stitchObject
          .getFileData({
            // saves the document with annotations in it
            xfdfString: xfdfString,
            downloadType: downloadType,
            flatten: true,
          })
          .then(async (_data) => {
            return _data;
          })
          const _arr = new Uint8Array(_data);
          const _blob = new Blob([_arr], { type: "application/pdf" });
          let docObj = await docInstance?.Core.createDocument(_data, {
            loadAsPDF: true,
            useDownloader: false, // Added to fix BLANK page issue
          }).then( async (docObj) => {
            return docObj
          })
          const xfdfStringTwo = await annotationManager.exportAnnotations({annotationList:filteredAnnotations});
          docObj
            .getFileData({
            // saves the document with annotations in it
            xfdfString: xfdfStringTwo,
            downloadType: downloadType,
          })
          .then(async (_data) => {
            const _arr = new Uint8Array(_data);
            const _blob = new Blob([_arr], {
                type: "application/pdf",
              }); 
            saveFilesinS3(
              { filepath: redlineStitchInfo[divisionid]["s3path"] },
              _blob,
              (_res) => {
                // ######### call another process for zipping and generate download here ##########
                toast.update(toastId.current, {
                  render: `Redline PDF saved to Object Storage`,
                  type: "success",
                  className: "file-upload-toast",
                  isLoading: false,
                  autoClose: 3000,
                  hideProgressBar: true,
                  closeOnClick: true,
                  pauseOnHover: true,
                  draggable: true,
                  closeButton: true,
                });
                triggerRedlineZipper(
                  redlineIncompatabileMappings[divisionid],
                  redlineStitchInfo[divisionid]["s3path"],
                  divisionCountForToast,
                  isSingleRedlinePackage
                );
              },
              (_err) => {
                console.log(_err);
                toast.update(toastId.current, {
                  render: "Failed to save redline pdf to Object Storage",
                  type: "error",
                  className: "file-upload-toast",
                  isLoading: false,
                  autoClose: 3000,
                  hideProgressBar: true,
                  closeOnClick: true,
                  pauseOnHover: true,
                  draggable: true,
                  closeButton: true,
                });
              }
            );
          });
        }
      }
    }
  };

  const getAdjustedRedactionCoordinates = async(pageRotation, recto, PDFNet,pageWidth,pageHeight) => {
    let x1 = recto.x1;
    let y1 = recto.y1;
    let x2 = recto.x2;
    let y2 = recto.y2;
    // Adjust Y-coordinates to account for the flipped Y-axis in PDF
    y1 = pageHeight - y1;
    y2 = pageHeight - y2;  
    // Adjust for page rotation (90, 180, 270 degrees)
    switch (pageRotation) {
      case 90:
        [x1, y1] = [y1, x1];
        [x2, y2] = [y2, x2];
        break;
      case 180:
        x1 = pageWidth - x1;
        y1 = pageHeight - y1;
        x2 = pageWidth - x2;
        y2 = pageHeight - y2;
        break;
      case 270:
        [x1, y1] = [pageHeight - y1, x1];
        [x2, y2] = [pageHeight - y2, x2];
        break;
    }  
    return await PDFNet.Rect.init(x1, y1, x2, y2);
  }
  
  useEffect(() => {
    if (
      redlineStitchObject &&
      redlineDocumentAnnotations &&
      redlineStitchInfo &&
      redlinepageMappings
    ) {
      StitchAndUploadDocument();
    }
  }, [redlineDocumentAnnotations, redlineStitchObject, redlineStitchInfo]);
  
  useEffect(() => {
    if (
      pdftronDocObjectsForRedline?.length > 0 &&
      totalStitchList[redlineStitchDivisionDetails.division]?.length > 0 &&
      stichedfilesForRedline != null
    ) {
      let divisionDocListCopy = [
        ...totalStitchList[redlineStitchDivisionDetails.division],
      ];
      if (divisionDocListCopy.length > 1) {
        divisionDocListCopy?.shift();
        let _pdftronDocObjects = sortDocObjectsForRedline(
          pdftronDocObjectsForRedline,
          divisionDocListCopy
        );
        if (_pdftronDocObjects.length > 0) {
          stitchPagesForRedline(_pdftronDocObjects);
        }
      }
    }
    if (
      isSingleRedlinePackage === "N" &&
      stichedfilesForRedline != null &&
      alreadyStitchedList?.length + 1 ===
        totalStitchList[redlineStitchDivisionDetails.division]?.length
    ) {
      requestStitchObject[redlineStitchDivisionDetails.division] =
        stichedfilesForRedline;
    } else {
      if (
        stichedfilesForRedline === null &&
        Object.keys(incompatableList)?.length > 0 &&
        incompatableList[redlineStitchDivisionDetails.division][
          "incompatibleFiles"
        ].length > 0
      ) {
        requestStitchObject[redlineStitchDivisionDetails.division] = null;
      }
    }
    if (
      isSingleRedlinePackage === "Y" &&
      stichedfilesForRedline != null &&
      alreadyStitchedList?.length + 1 ===
        totalStitchList[redlineStitchDivisionDetails.division]?.length
    ) {
      requestStitchObject["0"] = stichedfilesForRedline;
    }
    if (
      redlineStitchDivisionDetails.divCount ===
        redlineStitchDivisionDetails.noofdivision &&
      requestStitchObject != null &&
      requestStitchObject[redlineStitchDivisionDetails.division] != null
    ) {
      setRedlineStitchObject(requestStitchObject);
    }
  }, [
    pdftronDocObjectsForRedline,
    stichedfilesForRedline,
    alreadyStitchedList,
  ]);

  return {
    includeNRPages,
    includeDuplicatePages,
    setIncludeDuplicatePages,
    setIncludeNRPages,
    setIncludeComments,
    saveRedlineDocument,
    enableSavingOipcRedline,
    enableSavingRedline,
    enableSavingConsults,
    checkSavingRedline,
    checkSavingOIPCRedline,
    checkSavingConsults,
    setRedlineCategory,
    setFilteredComments,
    setSelectedPublicBodyIDs,
    setConsultApplyRedactions,
    selectedPublicBodyIDs,
    documentPublicBodies,
    consultApplyRedactions,
    setConsultApplyRedlines,
    consultApplyRedlines,
  };
};

export default useSaveRedlineForSignoff;