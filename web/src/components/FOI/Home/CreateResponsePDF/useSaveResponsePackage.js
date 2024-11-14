import { useState } from "react";
import { useAppSelector } from "../../../../hooks/hook";
import { toast } from "react-toastify";
import { getStitchedPageNoFromOriginal, sortBySortOrder } from "../utils";
import {
  saveFilesinS3,
  getResponsePackagePreSignedUrl,
} from "../../../../apiManager/services/foiOSSService";
import { triggerDownloadFinalPackage } from "../../../../apiManager/services/docReviewerService";
import { pageFlagTypes, RequestStates } from "../../../../constants/enum";
import { useParams } from "react-router-dom";

const useSaveResponsePackage = () => {
  const currentLayer = useAppSelector((state) => state.documents?.currentLayer);
  const requestnumber = useAppSelector(
    (state) => state.documents?.requestnumber
  );
  const requestStatus = useAppSelector(
    (state) => state.documents?.requeststatus
  );
  const { foiministryrequestid } = useParams();

  const [enableSavingFinal, setEnableSavingFinal] = useState(false);
  const [enablePublication, setEnablePublication] = useState(false);

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
        
        let docinfo = await doc.getDocInfo();
        docinfo.setTitle(requestnumber + ".pdf");
        docinfo.setAuthor("");
        
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
    zipServiceMessage,
    personalAttributes,
    documentid
  ) => {
    const stitchedDocPathArray = stitchedfilepath.split("/");
    let recordLabel = Object.keys(personalAttributes).length > 0 ? personalAttributes.person + ' - ' + 
      personalAttributes.filetype + ' - ' + 
      personalAttributes.trackingid :  "" ;
    if (personalAttributes.volume) {
      recordLabel += (' - ' + personalAttributes.volume)
    }

    let fileName =
      stitchedDocPathArray[stitchedDocPathArray.length - 1].split("?")[0];
    fileName = decodeURIComponent(fileName);

    const file = {
      filename: fileName,
      recordname:recordLabel,
      s3uripath: decodeURIComponent(stitchedfilepath.split("?")[0]),
      documentid: documentid,
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
  // const prepareresponseredlinesummarylist = (documentlist) => {
  //   let summarylist = [];
  //   let summary_division = {};
  //   let summary_divdocuments = [];
  //   let alldocuments = [];
  //   summary_division["divisionid"] = "0";
  //   for (let doc of documentlist) {
  //     summary_divdocuments.push(doc.documentid);
  //     alldocuments.push(doc);
  //   }
  //   summary_division["documentids"] = summary_divdocuments;
  //   summarylist.push(summary_division);

  //   let sorteddocids = [];
  //   // sort based on sortorder as the sortorder added based on the LastModified
  //   let sorteddocs = sortBySortOrder(alldocuments);
  //   for (const sorteddoc of sorteddocs) {
  //     sorteddocids.push(sorteddoc["documentid"]);
  //   }
  //   return { sorteddocuments: sorteddocids, pkgdocuments: summarylist };
  // };

  const prepareresponseredlinesummarylist = (documentlist, bcgovcode, requestType) => {
    let summarylist = [];
    let alldocuments = [];
    console.log("\ndocumentlist:", documentlist);
    let sorteddocids = [];
    if (bcgovcode?.toLowerCase() === 'mcf' && requestType == "personal") {
      let labelGroups = {};
      let alldocids = [];
  
      for (let file of documentlist) {
        var label = file.attributes.personalattributes.person == 'APPLICANT' ? 
                    (file.attributes.personalattributes.person + ' - ' +
                    file.attributes.personalattributes.filetype + ' - ' +
                    file.attributes.personalattributes.trackingid)
                    :
                    (file.attributes.personalattributes.filetype + ' - ' +
                    file.attributes.personalattributes.trackingid)
        if (file.attributes.personalattributes.volume) {
          label += (' - ' + file.attributes.personalattributes.volume);
        }
  
        if (!labelGroups[label]) {
          labelGroups[label] = [];
        }
        labelGroups[label].push(file.documentid);
        alldocids.push(file.documentid);
        alldocuments.push(file);
      }
  
      let divisionRecords = [];
      for (let label in labelGroups) {
        let record = {
          "recordname": label,
          "documentids": labelGroups[label]
        };
        divisionRecords.push(record);
      }
  
      let summary_division = {
        "divisionid": 0,
        "documentids":alldocids,
        "records": divisionRecords
      };
  
      summarylist.push(summary_division);
  
      // Sort based on sortorder as the sortorder added based on the LastModified
      let sorteddocs = sortBySortOrder(alldocuments);
      for (const sorteddoc of sorteddocs) {
        if (!sorteddocids.includes(sorteddoc['documentid'])) {
          sorteddocids.push(sorteddoc['documentid']);
        }
      }
    } else {
      let summary_division = {
        "divisionid": '0',
        "documentids": []
      };
  
      for (let doc of documentlist) {
        summary_division.documentids.push(doc.documentid);
        alldocuments.push(doc);
      }
      summarylist.push(summary_division);
  
      // Sort based on sortorder as the sortorder added based on the LastModified
      let sorteddocs = sortBySortOrder(alldocuments);
      for (const sorteddoc of sorteddocs) {
        if (!sorteddocids.includes(sorteddoc['documentid'])) {
          sorteddocids.push(sorteddoc['documentid']);
        }
      }
    }
  
    return {"sorteddocuments": sorteddocids, "pkgdocuments": summarylist};
  };
  

  const saveResponsePackage = async (
    documentViewer,
    annotationManager,
    _instance,
    documentList,
    pageMappedDocs,
    pageFlags,
    feeOverrideReason,
    requestType,
    downloadPackageType
  ) => {
    const downloadType = "pdf";
    let zipServiceMessage = {
      ministryrequestid: foiministryrequestid,
      category: downloadPackageType,
      attributes: [],
      requestnumber: "",
      bcgovcode: "",
      summarydocuments: {} ,
      redactionlayerid: currentLayer.redactionlayerid,
      pdfstitchjobattributes:{"feeoverridereason":""},
      requesttype: requestType
    };
    getResponsePackagePreSignedUrl(
      foiministryrequestid,
      documentList[0],
      downloadPackageType,
      async (res) => {
        const toastID = downloadPackageType == "publicationpackage" ?
          toast.loading("Start generating publication package..."): toast.loading("Start generating final package...");
        zipServiceMessage.requestnumber = res.requestnumber;
        zipServiceMessage.bcgovcode = res.bcgovcode;
        zipServiceMessage.summarydocuments= prepareresponseredlinesummarylist(documentList,zipServiceMessage.bcgovcode, requestType)
        zipServiceMessage.pdfstitchjobattributes= {"feeoverridereason":feeOverrideReason}
        let annotList = annotationManager.getAnnotationsList();
        annotationManager.ungroupAnnotations(annotList);
        /** remove duplicate and not responsive pages */
        let pagesToRemove = [];
        for (const infoForEachDoc of pageFlags) {
          for (const pageFlagsForEachDoc of infoForEachDoc.pageflag) {
            /** pageflag duplicate or not responsive */
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
        await annotationManager.applyRedactions();
        /**must apply redactions before removing pages*/
        if (pagesToRemove.length > 0) {
          await doc.removePages(pagesToRemove);
        }      
        doc.setWatermark({          
          diagonal: {
            text: ''
          }
        })
        const { PDFNet } = _instance.Core;
        PDFNet.initialize();
        
        // remove bookmarks
        var pdfdoc = await doc.getPDFDoc()
        var bookmark = await pdfdoc.getFirstBookmark();
        while (bookmark && await bookmark.isValid()) {
          bookmark.delete();
          bookmark = await pdfdoc.getFirstBookmark();
        }
        
        await stampPageNumberResponse(documentViewer, PDFNet);
        toast.update(toastID, {
          render: "Saving section stamps...",
          isLoading: true,
        });
        /**Fixing section cutoff issue in response pkg-
         * (For showing section names-freetext annotations are
         * added once redactions are applied in the annotationChangedHandler)
         * then export & filter freetext & widget annotations
         * after redactions applied.
         * (widget is needed for showing data from fillable pdfs).
         */
        let annotsAfterRedaction = await annotationManager.getAnnotationsList();
        const filteredAnnotations = annotsAfterRedaction.filter(
          (annotation) => {
            if (_instance.Core.Annotations) {
              return (
                annotation instanceof
                  _instance.Core.Annotations.FreeTextAnnotation ||
                annotation instanceof
                  _instance.Core.Annotations.WidgetAnnotation
              );
            }
            return false;
          }
        );
        const xfdfString = await annotationManager.exportAnnotations({
          annotationList: filteredAnnotations,
          widgets: true,
        });

        /** apply redaction and save to s3 - xfdfString is needed to display
         * the freetext(section name) on downloaded file.*/
        doc
          .getFileData({
            // saves the document with annotations in it
            xfdfString: xfdfString,
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
                  zipServiceMessage,
                  (Object.keys(res.attributes).length > 0 && 'personalattributes' in res.attributes && Object.keys(res.attributes?.personalattributes).length > 0) ? res.attributes.personalattributes: {},
                  res.documentid
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
      },
      (error) => {
        console.log("Error fetching document:", error);
      }
    );
  };
  const checkSavingFinalPackage = (redlineReadyAndValid, isOILayerSelected,instance) => {
    const validFinalPackageStatus = requestStatus === RequestStates["Response"];
    //setEnableSavingFinal(true)
    setEnableSavingFinal(redlineReadyAndValid && validFinalPackageStatus && !isOILayerSelected);
    if (instance) {
      const document = instance.UI.iframeWindow.document;
      document.getElementById("final_package").disabled =
        !redlineReadyAndValid || !validFinalPackageStatus || isOILayerSelected;
    }
  };

  const checkSavingPublicationPackage = (redlineReadyAndValid, isOILayerSelected, instance) =>{
    setEnablePublication(redlineReadyAndValid && isOILayerSelected)
    if (instance) {
      const document = instance.UI.iframeWindow.document;
      document.getElementById("publication_package").disabled =
        !redlineReadyAndValid || !isOILayerSelected;
    }
  }

  return {
    saveResponsePackage,
    checkSavingFinalPackage,
    enableSavingFinal,
    checkSavingPublicationPackage,
    enablePublication
  };
};

export default useSaveResponsePackage;
