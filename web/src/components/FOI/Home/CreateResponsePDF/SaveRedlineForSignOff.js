import React, { useState } from "react";
import { useAppSelector } from "../../../../hooks/hook";
import { toast } from "react-toastify";
import {
  getStitchedPageNoFromOriginal,
  getSliceSetDetails,
  sortBySortOrder,
} from "../utils";
import { getFOIS3DocumentRedlinePreSignedUrl } from "../../../../apiManager/services/foiOSSService";
import { fetchDocumentAnnotations } from "../../../../apiManager/services/docReviewerService";
import { isValidRedlineDivisionDownload } from "./DownloadResponsePDF";
import { pageFlagTypes } from "../../../../constants/enum";
import { useParams } from "react-router-dom";

const SaveRedlineForSignoff = () => {
  const currentLayer = useAppSelector((state) => state.documents?.currentLayer);
  const deletedDocPages = useAppSelector(
    (state) => state.documents?.deletedDocPages
  );
  const { foiministryrequestid } = useParams();

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
  const [stichedfilesForRedline, setstichedfilesForRedline] = useState(null);
  const [redlineStitchObject, setRedlineStitchObject] = useState(null);

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
    toastId
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
    setSkipDeletePages
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
            setSkipDeletePages
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
    setSkipDeletePages
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
                setSkipDeletePages(true);  //to DO TALK TO DIVYA AS I DON THINK WE NEED THIS -> ALREADY SET IN ABOVE TO TRUE AND BEING SET TO TRUE AGAIN IN SAVEREDLINESIGNOFF
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
    incompatibleFiles, // create redux state
    documentList, //use redux state
    pageMappedDocs,
    setSkipDeletePages
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
      foiministryrequestid,
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
          ministryrequestid: foiministryrequestid,
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
            setSkipDeletePages
          );
        } else {
          stitchForRedlineExport(
            _instance,
            divisionDocuments,
            stitchDocuments,
            res.issingleredlinepackage,
            IncompatableList,
            toastId
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
  
  //TO DO: Adjust this function to take in less args (use redux if avail or move state here) 
  // + TEST ALL PACKAGES AND ALL FEATURES +
  // finally refactor+rengineering functions for perofrmance (reduce dble loops + try aparnas local storage + be logic )

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
    includeNRPages,
    includeDuplicatePages,
    stichedfilesForRedline,
    setstichedfilesForRedline,
    redlineStitchObject,
    setRedlineStitchObject,
    setIncludeDuplicatePages,
    setIncludeNRPages,
    saveRedlineDocument,
  };
};

export default SaveRedlineForSignoff;
