import React, { useState, useEffect } from "react";
import { useAppSelector } from "../../../../hooks/hook";
import { toast } from "react-toastify";
import {
  getStitchedPageNoFromOriginal,
  getSliceSetDetails,
  sortBySortOrder,
  addWatermarkToRedline,
  sortDocObjectsForRedline,
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
  const [includeNRPages, setIncludeNRPages] = useState(false);
  const [includeDuplicatePages, setIncludeDuplicatePages] = useState(false);
  const [stichedfilesForRedline, setstichedfilesForRedline] = useState(null);
  const [redlineStitchObject, setRedlineStitchObject] = useState(null);
  const [enableSavingRedline, setEnableSavingRedline] = useState(false);
  const [enableSavingOipcRedline, setEnableSavingOipcRedline] = useState(false);
  const [redlineCategory, setRedlineCategory] = useState(false);
  const [filteredComments, setFilteredComments] = useState({});
  const [alreadyStitchedList, setAlreadyStitchedList] = useState([]);

  const isValidRedlineDivisionDownload = (divisionid, divisionDocuments) => {
    console.log("isValidRedlineDivisionDownload");
    let isvalid = false;
    for (let divObj of divisionDocuments) {
      if (divObj.divisionid === divisionid) {
        // enable the Redline for Sign off if a division has only Incompatable files
        if (divObj?.incompatableList?.length > 0) {
          if (isvalid === false) {
            isvalid = true;
          }
        } else {
          for (let doc of divObj.documentlist) {
            for (const flagInfo of doc.pageFlag) {
              // Added condition to handle Duplicate/NR clicked for Redline for Sign off Modal
              if (
                (flagInfo.flagid !== pageFlagTypes["Duplicate"] &&
                  flagInfo.flagid !== pageFlagTypes["Not Responsive"]) ||
                (includeDuplicatePages &&
                  flagInfo.flagid === pageFlagTypes["Duplicate"]) ||
                (includeNRPages &&
                  flagInfo.flagid === pageFlagTypes["Not Responsive"])
              ) {
                if (isvalid === false) {
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
  const isIgnoredDocument = (doc, pagecount, divisionDocuments) => {
    const divdocumentlist = JSON.parse(JSON.stringify(divisionDocuments));
    let removepagesCount = 0;
    console.log("IGNORED");
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
    console.log("divdocmapping");
    let newDocList = [];
    for (let div of divisions) {
      let divDocList = documentList.filter((doc) =>
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
    return newDocList;
  };
  const prepareRedlinePageMapping = (
    divisionDocuments,
    redlineSinglePkg,
    pageMappedDocs
  ) => {
    console.log("prep redline page mapping");
    if (redlineSinglePkg === "Y") {
      let reqdocuments = [];
      for (let divObj of divisionDocuments) {
        for (let doc of divObj.documentlist) {
          reqdocuments.push(doc);
        }
      }
      // sort based on sortorder as the sortorder added based on the LastModified
      prepareRedlinePageMappingByRequest(
        sortBySortOrder(reqdocuments),
        pageMappedDocs
      );
    } else {
      prepareRedlinePageMappingByDivision(divisionDocuments);
    }
  };
  const prepareRedlinePageMappingByRequest = (
    divisionDocuments,
    pageMappedDocs
  ) => {
    let removepages = {};
    let pageMappings = {};
    let pagesToRemove = [];
    let totalPageCount = 0;
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
          if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
            // ignore consult flag to fix bug FOIMOD-3062
            if (flagInfo.flagid === pageFlagTypes["Duplicate"]) {
              if (includeDuplicatePages) {
                duplicateWatermarkPagesEachDiv.push(
                  getStitchedPageNoFromOriginal(
                    doc.documentid,
                    flagInfo.page,
                    pageMappedDocs
                  ) - pagesToRemove.length
                );

                pageMappings[doc.documentid][flagInfo.page] =
                  pageIndex + totalPageCount - pagesToRemoveEachDoc.length;
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
            } else if (flagInfo.flagid === pageFlagTypes["Not Responsive"]) {
              if (includeNRPages) {
                NRWatermarksPagesEachDiv.push(
                  getStitchedPageNoFromOriginal(
                    doc.documentid,
                    flagInfo.page,
                    pageMappedDocs
                  ) - pagesToRemove.length
                );

                pageMappings[doc.documentid][flagInfo.page] =
                  pageIndex + totalPageCount - pagesToRemoveEachDoc.length;
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
                  pageIndex + totalPageCount - pagesToRemoveEachDoc.length;
              }
            }
            if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
              pageIndex++;
            }
          }
        }
        //End of pageMappingsByDivisions
        totalPageCount += Object.keys(pageMappings[doc.documentid]).length;
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
    let duplicateWatermarkPages = {};
    let duplicateWatermarkPagesEachDiv = [];
    let NRWatermarksPages = {};
    let NRWatermarksPagesEachDiv = [];
    for (let divObj of divisionDocuments) {
      // sort based on sortorder as the sortorder added based on the LastModified
      for (let doc of sortBySortOrder(divObj.documentlist)) {
        if (doc.pagecount > 0) {
          let pagesToRemoveEachDoc = [];
          pageMappings[doc.documentid] = {};
          let pageIndex = 1;
          //gather pages that need to be removed
          doc.pageFlag.sort((a, b) => a.page - b.page); //sort pageflag by page #
          //if(isIgnoredDocument(doc, doc['pagecount'], divisionDocuments) == false) {
          for (const flagInfo of doc.pageFlag) {
            if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
              // ignore consult flag to fix bug FOIMOD-3062
              if (flagInfo.flagid === pageFlagTypes["Duplicate"]) {
                if (includeDuplicatePages) {
                  duplicateWatermarkPagesEachDiv.push(
                    pageIndex +
                      totalPageCountIncludeRemoved -
                      pagesToRemove.length
                  );

                  pageMappings[doc.documentid][flagInfo.page] =
                    pageIndex + totalPageCount - pagesToRemoveEachDoc.length;
                } else {
                  pagesToRemoveEachDoc.push(flagInfo.page);

                  pagesToRemove.push(pageIndex + totalPageCountIncludeRemoved);
                }
              } else if (flagInfo.flagid === pageFlagTypes["Not Responsive"]) {
                if (includeNRPages) {
                  NRWatermarksPagesEachDiv.push(
                    pageIndex +
                      totalPageCountIncludeRemoved -
                      pagesToRemove.length
                  );

                  pageMappings[doc.documentid][flagInfo.page] =
                    pageIndex + totalPageCount - pagesToRemoveEachDoc.length;
                } else {
                  pagesToRemoveEachDoc.push(flagInfo.page);

                  pagesToRemove.push(pageIndex + totalPageCountIncludeRemoved);
                }
              } else {
                if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
                  pageMappings[doc.documentid][flagInfo.page] =
                    pageIndex + totalPageCount - pagesToRemoveEachDoc.length;
                }
              }
              if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
                pageIndex++;
              }
            }
          }
          //End of pageMappingsByDivisions
          totalPageCount += Object.keys(pageMappings[doc.documentid]).length;
          totalPageCountIncludeRemoved += doc.pagecount;
        }
      }
      divPageMappings[divObj.divisionid] = pageMappings;
      removepages[divObj.divisionid] = pagesToRemove;
      duplicateWatermarkPages[divObj.divisionid] =
        duplicateWatermarkPagesEachDiv;
      NRWatermarksPages[divObj.divisionid] = NRWatermarksPagesEachDiv;
      pagesToRemove = [];
      duplicateWatermarkPagesEachDiv = [];
      NRWatermarksPagesEachDiv = [];
      totalPageCount = 0;
      totalPageCountIncludeRemoved = 0;
      pageMappings = {};
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
  };

  const prepareRedlineIncompatibleMapping = (redlineAPIResponse) => {
    let divIncompatableMapping = {};
    let incompatibleFiles = [];
    let divCounter = 0;

    console.log("prep redline incomp mapping");
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
      if (redlineAPIResponse.issingleredlinepackage === "Y") {
        if (divCounter === redlineAPIResponse.divdocumentList.length) {
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
    return divIncompatableMapping;
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
    if (currentLayer.name.toLowerCase() === "oipc") {
      return layertype === "oipcreview" ? "oipcreviewredline" : "oipcredline";
    }
    return "redline";
  };
  const prepareredlinesummarylist = (stitchDocuments) => {
    console.log("PREP SUMM");
    let summarylist = [];
    let alldocuments = [];
    for (const [key, value] of Object.entries(stitchDocuments)) {
      let summary_division = {};
      summary_division["divisionid"] = key;
      let documentlist = stitchDocuments[key];
      if (documentlist.length > 0) {
        let summary_divdocuments = [];
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
      sorteddocids.push(sorteddoc["documentid"]);
    }
    return { sorteddocuments: sorteddocids, pkgdocuments: summarylist };
  };
  const stitchForRedlineExport = async (
    _instance,
    divisionDocuments,
    stitchlist,
    redlineSinglePkg,
    incompatableList
  ) => {
    console.log("STITHC MULTI DIV FOR REDLINE");
    let requestStitchObject = {};
    let divCount = 0;
    const noofdivision = Object.keys(stitchlist).length;
    let stitchedDocObj = null;
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
      if (documentlist.length > 0) {
        for (let doc of documentlist) {
          await _instance.Core.createDocument(doc.s3path_load, {
            loadAsPDF: true,
            useDownloader: false, // Added to fix BLANK page issue
          }).then(async (docObj) => {
            //if (isIgnoredDocument(doc, docObj.getPageCount(), divisionDocuments) == false) {
            docCount++;
            if (docCount === 1) {
              // Delete pages from the first document
              const deletedPages = getDeletedPagesBeforeStitching(
                doc.documentid
              );
              if (deletedPages.length > 0) {
                docObj.removePages(deletedPages);
              }
              stitchedDocObj = docObj;
            } else {
              let pageIndexToInsert = stitchedDocObj?.getPageCount() + 1;
              await stitchedDocObj.insertPages(
                docObj,
                doc.pages,
                pageIndexToInsert
              );
            }
          });
          if (docCount === documentlist.length && redlineSinglePkg === "N") {
            requestStitchObject[division] = stitchedDocObj;
          }
        }
      } else {
        if (incompatableList[division]["incompatibleFiles"].length > 0) {
          requestStitchObject[division] = null;
        }
      }
      if (redlineSinglePkg === "Y" && stitchedDocObj != null) {
        requestStitchObject["0"] = stitchedDocObj;
      }
      if (divCount === noofdivision) {
        setRedlineStitchObject(requestStitchObject);
      }
      if (redlineSinglePkg === "N") {
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
    console.log("STITCH SINGLE");
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
    console.log("MERGE");
    for (const filerow of sliceDoclist) {
      try {
        await createDocument(filerow.s3path_load, {
          useDownloader: false, // Added to fix BLANK page issue
          loadAsPDF: true, // Added to fix jpeg/pdf stitiching issue #2941
        }).then(async (newDoc) => {
          docCount++;
          if (isIgnoredDocument(filerow, newDoc, divisionDocuments) === false) {
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
          }
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

  const saveRedlineDocument = async (
    layertype,
    incompatibleFiles,
    documentList,
    pageMappedDocs
  ) => {
    toastId.current = toast(`Start saving redline...`, {
      autoClose: false,
      closeButton: false,
      isLoading: true,
    });
    console.log("save redline");
    const divisionFilesList = [...documentList, ...incompatibleFiles];
    const divisions = getDivisionsForSaveRedline(divisionFilesList);
    const divisionDocuments = getDivisionDocumentMappingForRedline(
      divisions,
      documentList,
      incompatibleFiles
    );
    const documentids = documentList.map((obj) => obj.documentid);
    getFOIS3DocumentRedlinePreSignedUrl(
      foiministryrequestid,
      divisionDocuments,
      async (res) => {
        toast.update(toastId.current, {
          render: `Start saving redline...`,
          isLoading: true,
        });
        let stitchDoc = {};
        prepareRedlinePageMapping(
          res["divdocumentList"],
          res.issingleredlinepackage,
          pageMappedDocs
        );
        let incompatableList = prepareRedlineIncompatibleMapping(res);
        setIncompatableList(incompatableList);
        fetchDocumentRedlineAnnotations(
          foiministryrequestid,
          documentids,
          currentLayer.name.toLowerCase()
        );

        let stitchDocuments = {};
        let documentsObjArr = [];
        let divisionstitchpages = [];
        let divCount = 0;
        for (let div of res.divdocumentList) {
          divCount++;
          let docCount = 0;
          let _isValidRedlineDivisionDownload = isValidRedlineDivisionDownload(
            div.divisionid,
            divisionDocuments
          );
          if (
            res.issingleredlinepackage === "Y" ||
            (res.issingleredlinepackage === "N" &&
              _isValidRedlineDivisionDownload)
          ) {
            for (let doc of div.documentlist) {
              docCount++;
              documentsObjArr.push(doc);
              if (docCount === div.documentlist.length) {
                if (pageMappedDocs != undefined) {
                  let divisionsdocpages = Object.values(
                    pageMappedDocs.redlineDocIdLookup
                  )
                    .filter((obj) => {
                      return obj.division.includes(div.divisionid);
                    })
                    .map((obj) => {
                      return obj.pageMappings;
                    });
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
            res.issingleredlinepackage === "Y" &&
            divCount === res.divdocumentList.length
          ) {
            let sorteddocIds = [];
            /** sort based on sortorder as the sortorder added based on the LastModified */
            let sorteddocuments = sortBySortOrder(documentsObjArr);
            stitchDocuments["0"] = setStitchDetails(sorteddocuments);
            for (const element of sorteddocuments) {
              sorteddocIds.push(element["documentid"]);
            }
            stitchDoc["0"] = {
              documentids: sorteddocIds,
              s3path: res.s3path_save,
              stitchpages: divisionstitchpages,
              bcgovcode: res.bcgovcode,
            };
          }
          if (
            res.issingleredlinepackage !== "Y" &&
            docCount === div.documentlist.length
          ) {
            let divdocumentids = [];
            // sort based on sortorder as the sortorder added based on the LastModified
            let sorteddocuments = sortBySortOrder(div.documentlist);
            stitchDocuments[div.divisionid] = setStitchDetails(sorteddocuments);

            for (const element of sorteddocuments) {
              divdocumentids.push(element["documentid"]);
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
        });
        if (res.issingleredlinepackage === "Y" || divisions.length === 1) {
          stitchSingleDivisionRedlineExport(
            docInstance,
            divisionDocuments,
            stitchDocuments,
            res.issingleredlinepackage
          );
        } else {
          stitchForRedlineExport(
            docInstance,
            divisionDocuments,
            stitchDocuments,
            res.issingleredlinepackage,
            incompatableList
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
    console.log("CHECK SAVE REDLINE");
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
    console.log("CHECK SAVE OIPC");
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
    return stitchAnnotation.join();
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
    return updatedXML.join();
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
      xmlObj.attributes.color.toLowerCase() + "ff"
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
          ?.[xmlObj.attributes.inreplyto].attributes.color.toLowerCase() + "ff"
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
          if (sections.some((item) => item.section === "s. 14")) {
            sectionStamps[parentRedactionId] =
              annotationpagenumbers[parentRedactionId];
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

  useEffect(() => {
    const StitchAndUploadDocument = async () => {
      const { PDFNet } = docInstance.Core;
      const downloadType = "pdf";
      const divisionCountForToast = Object.keys(redlineStitchObject).length;
      for (const [key, value] of Object.entries(redlineStitchObject)) {
        toast.update(toastId.current, {
          render:
            isSingleRedlinePackage === "N"
              ? `Saving redline PDF for ${divisionCountForToast} divisions to Object Storage...`
              : `Saving redline PDF to Object Storage...`,
          isLoading: true,
          autoClose: 5000,
        });

        let divisionid = key;
        let stitchObject = redlineStitchObject[key];
        if (stitchObject == null) {
          triggerRedlineZipper(
            redlineIncompatabileMappings[divisionid],
            redlineStitchInfo[divisionid]["s3path"],
            divisionCountForToast,
            isSingleRedlinePackage
          );
        } else {
          let formattedAnnotationXML = formatAnnotationsForRedline(
            redlineDocumentAnnotations,
            redlinepageMappings["divpagemappings"][divisionid],
            redlineStitchInfo[divisionid]["documentids"]
          );
          if(redlineCategory !== "oipcreview") {  
            await stampPageNumberRedline(
            stitchObject,
            PDFNet,
            redlineStitchInfo[divisionid]["stitchpages"],
            isSingleRedlinePackage
            );
          }
          if (
            redlinepageMappings["pagestoremove"][divisionid] &&
            redlinepageMappings["pagestoremove"][divisionid].length > 0
          ) {
            await stitchObject.removePages(
              redlinepageMappings["pagestoremove"][divisionid]
            );
          }
          if (redlineCategory === "redline") {
            await addWatermarkToRedline(
              stitchObject,
              redlineWatermarkPageMapping,
              key
            );
          }
          
          let xfdfString =
            '<?xml version="1.0" encoding="UTF-8" ?><xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve"><annots>' +
            formattedAnnotationXML +
            "</annots></xfdf>";

          //OIPC - Special Block (Redact S.14) : Begin
          if(redlineCategory === "oipcreview") {
            const rarr = []; 
            let annotationManager = docInstance?.Core.annotationManager;
            let s14_sectionStamps = await annotationSectionsMapping(xfdfString, formattedAnnotationXML);
            let rects = [];
            for (const [key, value] of Object.entries(s14_sectionStamps)) {
              let s14annoation = annotationManager.getAnnotationById(key);
                  if ( s14annoation.Subject === "Redact") { 
                          rects = rects.concat( 
                          s14annoation.getQuads().map((q) => {
                            return {
                                pageno: s14_sectionStamps[key],
                                recto: q.toRect(),
                                vpageno: s14annoation.getPageNumber()
                              };
                            })
                          );
                      }
                
              
            }
            for (const rect of rects) {
              let height = docViewer.getPageHeight(rect.vpageno);
              rarr.push(await PDFNet.Redactor.redactionCreate(rect.pageno, (await PDFNet.Rect.init(rect.recto.x1,height-rect.recto.y1,rect.recto.x2,height-rect.recto.y2)), false, ''));
            }
            if (rarr.length > 0) {
              const app = {};
              app.redaction_overlay = true;
              app.border = false;
              app.show_redacted_content_regions = false;
              const doc = await stitchObject.getPDFDoc();
              await PDFNet.Redactor.redact(doc, rarr, app);
            }
            await stampPageNumberRedline(
              stitchObject,
              PDFNet,
              redlineStitchInfo[divisionid]["stitchpages"],
              isSingleRedlinePackage
            );
          }
          //OIPC - Special Block : End
        
          

          stitchObject
            .getFileData({
              // saves the document with annotations in it
              xfdfString: xfdfString,
              downloadType: downloadType,
              //flatten: true, //commented this as part of #4862
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
    };

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
    saveRedlineDocument,
    enableSavingOipcRedline,
    enableSavingRedline,
    checkSavingRedline,
    checkSavingOIPCRedline,
    setRedlineCategory,
    setFilteredComments,
  };
};

export default useSaveRedlineForSignoff;
