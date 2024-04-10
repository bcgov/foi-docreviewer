import React, { useState } from "react";
import { useAppSelector } from "../../../../hooks/hook";
import { toast } from "react-toastify";
import {
  getStitchedPageNoFromOriginal,
  getSliceSetDetails,
  sortBySortOrder,
} from "../utils";
import {
  saveFilesinS3,
  getResponsePackagePreSignedUrl,
  getFOIS3DocumentRedlinePreSignedUrl,
} from "../../../../apiManager/services/foiOSSService";
import {
  fetchDocumentAnnotations,
  triggerDownloadFinalPackage,
} from "../../../../apiManager/services/docReviewerService";
import { isValidRedlineDivisionDownload } from "./DownloadResponsePDF";
import { pageFlagTypes } from "../../../../constants/enum";
import XMLParser from "react-xml-parser";

const SaveRedlineForSignoff = () => {
  //xml parser
  const parser = new XMLParser();
  const currentLayer = useAppSelector((state) => state.documents?.currentLayer);
  const deletedDocPages = useAppSelector(
    (state) => state.documents?.deletedDocPages
  );
  const pageFlags = useAppSelector((state) => state.documents?.pageFlags);
  const requestnumber = useAppSelector(
    (state) => state.documents?.requestnumber
  );

  const [redlineDocCount, setredlineDocCount] = useState(0);
  const [redlineSinglePackage, setRedlineSinglePackage] = useState(null);
  const [redlineStitchInfo, setRedlineStitchInfo] = useState(null);
  const [issingleredlinepackage, setIssingleredlinepackage] = useState(null);
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
  const [divisionDocList, setDivisionDocList] = useState([]);
  const [redlineStitchDivisionDetails, setRedlineStitchDivisionDetails] =
    useState({});
  const [pdftronDocObjectsForRedline, setPdftronDocObjectsForRedline] =
    useState([]);
  const [redlineZipperMessage, setRedlineZipperMessage] = useState(null);
  const [includeNRPages, setIncludeNRPages] = useState(false);
  const [includeDuplicatePages, setIncludeDuplicatePages] = useState(false);
  const [redlineModalOpen, setRedlineModalOpen] = useState(false);

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
    for (let divsionentry of divdocumentlist) {
      for (let docentry of divsionentry["documentlist"]) {
        if (doc.documentid == docentry.documentid) {
          for (const flagInfo of docentry.pageFlag) {
            if (
              flagInfo.flagid == pageFlagTypes["Duplicate"] ||
              flagInfo.flagid == pageFlagTypes["Not Responsive"]
            ) {
              removepagesCount++;
            }
          }
        }
      }
    }
    return pagecount == removepagesCount;
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
    if (redlineSinglePkg == "Y") {
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
          if (flagInfo.flagid == pageFlagTypes["Duplicate"]) {
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
          } else if (flagInfo.flagid == pageFlagTypes["Not Responsive"]) {
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
              pageIndex++;
            }
          }
          if (flagInfo.flagid !== pageFlagTypes["Consult"]) {
            pageIndex++;
          }
        }
        //End of pageMappingsByDivisions
        totalPageCount += Object.keys(pageMappings[doc.documentid]).length;
        totalPageCountIncludeRemoved += doc.pagecount;
      }
    }
    divPageMappings["0"] = pageMappings;
    removepages["0"] = pagesToRemove;
    duplicateWatermarkPages["0"] = duplicateWatermarkPagesEachDiv;
    NRWatermarksPages["0"] = NRWatermarksPagesEachDiv;
    setRedlinepageMappings({
      divpagemappings: divPageMappings,
      pagemapping: pageMappings,
      pagestoremove: removepages,
    });
    setRedlineWatermarkPageMapping({
      duplicatewatermark: duplicateWatermarkPages,
      NRwatermark: NRWatermarksPages,
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
            if (flagInfo.flagid == pageFlagTypes["Duplicate"]) {
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
            } else if (flagInfo.flagid == pageFlagTypes["Not Responsive"]) {
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
          //End of pageMappingsByDivisions
          totalPageCount += Object.keys(pageMappings[doc.documentid]).length;
          totalPageCountIncludeRemoved += doc.pagecount;
          //}
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
      divpagemappings: divPageMappings,
      pagemapping: pageMappings,
      pagestoremove: removepages,
    });
    setRedlineWatermarkPageMapping({
      duplicatewatermark: duplicateWatermarkPages,
      NRwatermark: NRWatermarksPages,
    });
  };
  const prepareRedlineIncompatibleMapping = (redlineAPIResponse) => {
    let divIncompatableMapping = {};
    let incompatibleFiles = [];
    let divCounter = 0;

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
              redlineAPIResponse.issingleredlinepackage == "N"
                ? divObj.divisionname + "/" + record.filename
                : record.filename;
            return {
              filename: fname,
              s3uripath: record.filepath,
            };
          });
        incompatibleFiles = incompatibleFiles.concat(divIncompatableFiles);
      }
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
        if (docCounter == documentids.length) {
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
    incompatableList,
    toastId,
    setRedlineStitchObject
  ) => {
    let requestStitchObject = {};
    let divCount = 0;
    const noofdivision = Object.keys(stitchlist).length;
    let stitchedDocObj = null;
    for (const [key, value] of Object.entries(stitchlist)) {
      divCount++;
      let docCount = 0;
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
      if (documentlist.length > 0) {
        for (let doc of documentlist) {
          await _instance.Core.createDocument(doc.s3path_load, {
            loadAsPDF: true,
            useDownloader: false, // Added to fix BLANK page issue
          }).then(async (docObj) => {
            //if (isIgnoredDocument(doc, docObj.getPageCount(), divisionDocuments) == false) {
            docCount++;
            if (docCount == 1) {
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
            //}
          });
          if (docCount == documentlist.length && redlineSinglePkg == "N") {
            requestStitchObject[division] = stitchedDocObj;
          }
        }
      } else {
        if (incompatableList[division]["incompatibleFiles"].length > 0) {
          requestStitchObject[division] = null;
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
    redlineSinglePkg,
    toastId,
    setSkipDeletePages,
    setstichedfilesForRedline
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
      setDivisionDocList(documentlist);
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
            stitchedDocObj,
            setSkipDeletePages,
            setstichedfilesForRedline
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
    stitchedDocObj,
    setSkipDeletePages,
    setstichedfilesForRedline
  ) => {
    for (const filerow of sliceDoclist) {
      try {
        await createDocument(filerow.s3path_load, {
          useDownloader: false, // Added to fix BLANK page issue
          loadAsPDF: true, // Added to fix jpeg/pdf stitiching issue #2941
        }).then(async (newDoc) => {
          docCount++;
          setredlineDocCount(docCount);
          if (isIgnoredDocument(filerow, newDoc, divisionDocuments) === false) {
            if (filerow.stitchIndex === 1) {
              // Delete pages from the first document
              const deletedPages = getDeletedPagesBeforeStitching(
                filerow?.documentid
              );
              if (deletedPages.length > 0) {
                setSkipDeletePages(true);
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
      // DO NOT setup the sortorder to 1 for 1st divisional document
      // as the sort order is used to sort the document irrespective of the division
      // sortedItem.sortorder = _index + 1;
      sortedItem.stitchIndex = stitchIndex;
      // No need to update the pages again as the pages are already updated while preparing prepareMapperObj
      // sortedItem.pages = pages;
      stitchIndex += sortedItem.pagecount;
    });
    return sortedList;
  };
  const saveRedlineDocument = async (
    _instance,
    layertype,
    toastId,

    //WORK ON GETT THE BELOW THINGS BEFORE THE SET STATE CALLS TO GLOBAL STATE?
    incompatibleFiles, // create redux state
    documentList, //use redux state
    requestid, //use redux state
    pageMappedDocs,

    setRedlineStitchObject,
    setSkipDeletePages,
    setstichedfilesForRedline
  ) => {
    toastId.current = toast(`Start saving redline...`, {
      autoClose: false,
      closeButton: false,
      isLoading: true,
    });
    const divisionFilesList = [...documentList, ...incompatibleFiles];
    const divisions = getDivisionsForSaveRedline(divisionFilesList);
    const divisionDocuments = getDivisionDocumentMappingForRedline(
      divisions,
      documentList,
      incompatibleFiles
    );
    const documentids = documentList.map((obj) => obj.documentid);
    getFOIS3DocumentRedlinePreSignedUrl(
      requestid,
      //normalizeforPdfStitchingReq(divisionDocuments),
      divisionDocuments,
      async (res) => {
        toast.update(toastId.current, {
          render: `Start saving redline...`,
          isLoading: true,
        });
        setRedlineSinglePackage(res.issingleredlinepackage);

        let stitchDoc = {};

        prepareRedlinePageMapping(
          res["divdocumentList"],
          res.issingleredlinepackage,
          pageMappedDocs
        );
        let IncompatableList = prepareRedlineIncompatibleMapping(res);
        setIncompatableList(IncompatableList);
        fetchDocumentRedlineAnnotations(
          requestid,
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
            divisionDocuments,
            includeDuplicatePages,
            includeNRPages
          );
          if (
            res.issingleredlinepackage == "Y" ||
            (res.issingleredlinepackage == "N" &&
              _isValidRedlineDivisionDownload)
          ) {
            for (let doc of div.documentlist) {
              docCount++;
              documentsObjArr.push(doc);
              if (docCount == div.documentlist.length) {
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
            res.issingleredlinepackage == "Y" &&
            divCount == res.divdocumentList.length
          ) {
            let sorteddocIds = [];
            // sort based on sortorder as the sortorder added based on the LastModified
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
            res.issingleredlinepackage != "Y" &&
            docCount == div.documentlist.length
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
        setIssingleredlinepackage(res.issingleredlinepackage);
        setRedlineZipperMessage({
          ministryrequestid: requestid,
          category: getzipredlinecategory(layertype),
          attributes: [],
          requestnumber: res.requestnumber,
          bcgovcode: res.bcgovcode,
          summarydocuments: prepareredlinesummarylist(stitchDocuments),
          redactionlayerid: currentLayer.redactionlayerid,
        });
        if (res.issingleredlinepackage == "Y" || divisions.length == 1) {
          stitchSingleDivisionRedlineExport(
            _instance,
            divisionDocuments,
            stitchDocuments,
            res.issingleredlinepackage,
            toastId,
            setSkipDeletePages,
            setstichedfilesForRedline
          );
        } else {
          stitchForRedlineExport(
            _instance,
            divisionDocuments,
            stitchDocuments,
            res.issingleredlinepackage,
            IncompatableList,
            toastId,
            setRedlineStitchObject
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
  const stampPageNumberResponse = async (_docViwer, PDFNet) => {
    for (
      let pagecount = 1;
      pagecount <= _docViwer.getPageCount();
      pagecount++
    ) {
      try {
        let doc = null;

        let _docmain = _docViwer.getDocument();
        doc = await _docmain.getPDFDoc();

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

          await s.stampText(
            doc,
            `${requestnumber} , Page ${pagecount} of ${_docViwer.getPageCount()}`,
            pgSet
          );
        });
      } catch (err) {
        console.log(err);
        throw err;
      }
    }
  };
  const prepareMessageForResponseZipping = (
    stitchedfilepath,
    zipServiceMessage
  ) => {
    const stitchedDocPathArray = stitchedfilepath.split("/");

    let fileName =
      stitchedDocPathArray[stitchedDocPathArray.length - 1].split("?")[0];
    fileName = decodeURIComponent(fileName);

    const file = {
      filename: fileName,
      s3uripath: decodeURIComponent(stitchedfilepath.split("?")[0]),
    };
    const zipDocObj = {
      files: [],
    };
    zipDocObj.files.push(file);

    zipServiceMessage.attributes.push(zipDocObj);
    triggerDownloadFinalPackage(zipServiceMessage, (error) => {
      console.log(error);
    });
  };
  const prepareresponseredlinesummarylist = (documentlist) => {
    let summarylist = [];
    let summary_division = {};
    let summary_divdocuments = [];
    let alldocuments = [];
    summary_division["divisionid"] = "0";
    for (let doc of documentlist) {
      summary_divdocuments.push(doc.documentid);
      alldocuments.push(doc);
    }
    summary_division["documentids"] = summary_divdocuments;
    summarylist.push(summary_division);

    let sorteddocids = [];
    // sort based on sortorder as the sortorder added based on the LastModified
    let sorteddocs = sortBySortOrder(alldocuments);
    for (const sorteddoc of sorteddocs) {
      sorteddocids.push(sorteddoc["documentid"]);
    }
    return { sorteddocuments: sorteddocids, pkgdocuments: summarylist };
  };
  const saveResponsePackage = async (
    documentViewer,
    annotationManager,
    _instance,
    requestid,
    documentList,
    pageMappedDocs
  ) => {
    const downloadType = "pdf";
    let zipServiceMessage = {
      ministryrequestid: requestid,
      category: "responsepackage",
      attributes: [],
      requestnumber: "",
      bcgovcode: "",
      summarydocuments: prepareresponseredlinesummarylist(documentList),
      redactionlayerid: currentLayer.redactionlayerid,
    };
    getResponsePackagePreSignedUrl(
      requestid,
      documentList[0],
      async (res) => {
        const toastID = toast.loading("Start generating final package...");
        zipServiceMessage.requestnumber = res.requestnumber;
        zipServiceMessage.bcgovcode = res.bcgovcode;

        // go through annotations and get all section stamps
        annotationManager.exportAnnotations().then(async (xfdfString) => {
          //parse annotation xml
          let jObj = parser.parseFromString(xfdfString); // Assume xmlText contains the example XML
          let annots = jObj.getElementsByTagName("annots");

          let sectionStamps = {};
          let stampJson = {};
          for (const annot of annots[0].children) {
            // get section stamps from xml
            if (annot.name == "freetext") {
              let customData = annot.children.find(
                (element) => element.name == "trn-custom-data"
              );
              if (customData?.attributes?.bytes?.includes("parentRedaction")) {
                //parse section info to json
                stampJson = JSON.parse(
                  customData.attributes.bytes
                    .replace(/&quot;\[/g, "[")
                    .replace(/\]&quot;/g, "]")
                    .replace(/&quot;/g, '"')
                    .replace(/\\/g, "")
                );
                sectionStamps[stampJson["parentRedaction"]] =
                  stampJson["trn-wrapped-text-lines"][0];
              }
            }
          }

          // add section stamps to redactions as overlay text
          let annotList = annotationManager.getAnnotationsList();
          toast.update(toastID, {
            render: "Saving section stamps...",
            isLoading: true,
          });
          for (const annot of annotList) {
            if (sectionStamps[annot.Id]) {
              annotationManager.setAnnotationStyles(annot, {
                OverlayText: sectionStamps[annot.Id],
                FontSize: Math.min(parseInt(annot.FontSize), 9) + "pt",
              });
            }
          }
          annotationManager.ungroupAnnotations(annotList);

          // remove duplicate and not responsive pages
          let pagesToRemove = [];
          for (const infoForEachDoc of pageFlags) {
            for (const pageFlagsForEachDoc of infoForEachDoc.pageflag) {
              // pageflag duplicate or not responsive
              if (
                pageFlagsForEachDoc.flagid === pageFlagTypes["Duplicate"] ||
                pageFlagsForEachDoc.flagid === pageFlagTypes["Not Responsive"]
              ) {
                pagesToRemove.push(
                  getStitchedPageNoFromOriginal(
                    infoForEachDoc.documentid,
                    pageFlagsForEachDoc.page,
                    pageMappedDocs
                  )
                );
              }
            }
          }

          let doc = documentViewer.getDocument();
          await annotationManager.applyRedactions(); // must apply redactions before removing pages
          await doc.removePages(pagesToRemove);
          const { PDFNet } = _instance.Core;
          PDFNet.initialize();
          await stampPageNumberResponse(documentViewer, PDFNet);

          //apply redaction and save to s3
          doc
            .getFileData({
              // saves the document with annotations in it
              downloadType: downloadType,
              flatten: true,
            })
            .then(async (_data) => {
              const _arr = new Uint8Array(_data);
              const _blob = new Blob([_arr], { type: "application/pdf" });

              toast.update(toastID, {
                render: "Saving final package to Object Storage...",
                isLoading: true,
              });
              saveFilesinS3(
                { filepath: res.s3path_save },
                _blob,
                (_res) => {
                  toast.update(toastID, {
                    render:
                      "Final package is saved to Object Storage. Page will reload in 3 seconds..",
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
                  prepareMessageForResponseZipping(
                    res.s3path_save,
                    zipServiceMessage
                  );
                  setTimeout(() => {
                    window.location.reload(true);
                  }, 3000);
                },
                (_err) => {
                  console.log(_err);
                  toast.update(toastID, {
                    render: "Failed to save final package to Object Storage",
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
      },
      (error) => {
        console.log("Error fetching document:", error);
      }
    );
  };
  const saveDoc = (
    docInstance,
    modalFor,
    toastId,
    docViewer,
    annotManager,

    incompatibleFiles,
    documentList,
    requestid,
    pageMappedDocs,

    setRedlineStitchObject,
    setSkipDeletePages,
    setRedlineSaving,
    setRedlineCategory,
    setstichedfilesForRedline
  ) => {
    console.log("savedoc");
    setRedlineModalOpen(false);
    setRedlineSaving(true);
    setRedlineCategory(modalFor);
    // skip deletePages API call for all removePages related to Redline/Response package creation
    setSkipDeletePages(true);
    switch (modalFor) {
      case "oipcreview":
      case "redline":
        saveRedlineDocument(
          docInstance,
          modalFor,
          toastId,
          incompatibleFiles,
          documentList,
          requestid,
          pageMappedDocs,
          setRedlineStitchObject,
          setSkipDeletePages,
          setstichedfilesForRedline
        );
        break;
      case "responsepackage":
        saveResponsePackage(
          docViewer,
          annotManager,
          docInstance,
          requestid,
          documentList,
          pageMappedDocs
        );
        break;
      default:
    }
    setIncludeDuplicatePages(false);
    setIncludeNRPages(false);
  };

  const cancelSaveRedlineDoc = () => {
    setIncludeDuplicatePages(false);
    setIncludeNRPages(false);
    setRedlineModalOpen(false);
  };

  const handleIncludeNRPages = (e) => {
    setIncludeNRPages(e.target.checked);
  };

  const handleIncludeDuplicantePages = (e) => {
    setIncludeDuplicatePages(e.target.checked);
  };

  return {
    redlineSinglePackage,
    redlineStitchInfo,
    issingleredlinepackage,
    redlinepageMappings,
    redlineWatermarkPageMapping,
    redlineIncompatabileMappings,
    redlineDocumentAnnotations,
    requestStitchObject,
    incompatableList,
    totalStitchList,
    redlineStitchDivisionDetails,
    pdftronDocObjectsForRedline,
    redlineZipperMessage,
    redlineModalOpen,
    handleIncludeDuplicantePages,
    handleIncludeNRPages,
    setRedlineModalOpen,
    cancelSaveRedlineDoc,
    includeNRPages,
    includeDuplicatePages,
    saveDoc,
  };

};

export default SaveRedlineForSignoff;