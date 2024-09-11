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
import {
  POLYGON_REDACTION_APPROX_DEPTH
} from "../../../../constants/constants";

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

  const prepareresponseredlinesummarylist = (documentlist, bcgovcode) => {
    let summarylist = [];
    let alldocuments = [];
    console.log("\ndocumentlist:", documentlist);
    let sorteddocids = [];
    if (bcgovcode?.toLowerCase() === 'mcf') {
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
    pageFlags
  ) => {
    const downloadType = "pdf";
    let zipServiceMessage = {
      ministryrequestid: foiministryrequestid,
      category: "responsepackage",
      attributes: [],
      requestnumber: "",
      bcgovcode: "",
      summarydocuments: {} ,
      redactionlayerid: currentLayer.redactionlayerid,
    };
    getResponsePackagePreSignedUrl(
      foiministryrequestid,
      documentList[0],
      async (res) => {
        const toastID = toast.loading("Start generating final package...");
        zipServiceMessage.requestnumber = res.requestnumber;
        zipServiceMessage.bcgovcode = res.bcgovcode;
        zipServiceMessage.summarydocuments= prepareresponseredlinesummarylist(documentList,zipServiceMessage.bcgovcode)
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
        // handle polygon redactions
        toast.update(toastID, {
          render: "Handling polygon redactions...",
          isLoading: true,
        });
        for (const annot of annotList) {
          if (annot.Subject === 'Polygon' && annot.getCustomData('isPolygonRedaction') === 'true') {
            console.log("creating redaction on page no." + annot.PageNumber)
            createRedactedPolygon(annot, _instance)
            console.log("finished redaction on page no." + annot.PageNumber)
            annotationManager.deleteAnnotation(annot);
          }
        }
        let doc = documentViewer.getDocument();
        await annotationManager.applyRedactions();
        /**must apply redactions before removing pages*/
        if (pagesToRemove.length > 0) {
          await doc.removePages(pagesToRemove);
        }   
        const { PDFNet } = _instance.Core;
        PDFNet.initialize();
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
                // setTimeout(() => {
                //   window.location.reload(true);
                // }, 3000);
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
  const checkSavingFinalPackage = (redlineReadyAndValid, instance) => {
    const validFinalPackageStatus = requestStatus === RequestStates["Response"];
    setEnableSavingFinal(true)
    //setEnableSavingFinal(redlineReadyAndValid && validFinalPackageStatus);
    if (instance) {
      const document = instance.UI.iframeWindow.document;
      document.getElementById("final_package").disabled =
        !redlineReadyAndValid || !validFinalPackageStatus;
    }
  };

  //polygon redact functions

  let quads = [];

  const createRedactedPolygon = (polygon, instance) => {
    const polyPoints = polygon.getPath();
    const largestRectangle = getPolygonBoundingRectangle(polyPoints);
    const depth = POLYGON_REDACTION_APPROX_DEPTH;

    const rectFullyWithinPoly = isRectFullyWithinPolygon(largestRectangle, polygon);
    if (rectFullyWithinPoly) {
      return;
    }

    splitRectangle(largestRectangle, polygon, polyPoints, depth, instance);

    const annot = new instance.Core.Annotations.RedactionAnnotation({
      PageNumber: polygon.PageNumber,
      Quads: quads,
      StrokeColor: new instance.Core.Annotations.Color(255, 0, 0, 1),
      FillColor: new instance.Core.Annotations.Color(255, 255, 255, 1),
      IsText: true,
    });

    instance.Core.annotationManager.addAnnotation(annot);
    instance.Core.annotationManager.redrawAnnotation(annot);
    quads = []
  }

  const splitRectangle = (rectangle, polygon, polyPoints, depth, instance) => {
    if (depth === 0) {
      return;
    }

    const midX = (rectangle.x1 + rectangle.x2) / 2;
    const midY = (rectangle.y1 + rectangle.y2) / 2;

    const rect1 = {
      x1: rectangle.x1,
      y1: rectangle.y1,
      x2: midX,
      y2: midY
    };

    const rect2 = {
      x1: midX,
      y1: rectangle.y1,
      x2: rectangle.x2,
      y2: midY
    };

    const rect3 = {
      x1: rectangle.x1,
      y1: midY,
      x2: midX,
      y2: rectangle.y2
    };

    const rect4 = {
      x1: midX,
      y1: midY,
      x2: rectangle.x2,
      y2: rectangle.y2
    };

    const rects = [rect1, rect2, rect3, rect4];

    // For each split rectangle we need to check if is is fully within the polygon
    for (let i = 0; i < rects.length; i++) {
      const rectFullyWithinPoly = isRectFullyWithinPolygon(rects[i], polygon);
      if (rectFullyWithinPoly) {
        // createRedactionAnnotation(rects[i], polygon, instance);
        // convert Rect to Quad
        const padding = 2
        const quad = new instance.Core.Annotations.Quad(
          rects[i].x1 - padding, rects[i].y1 -padding,
          rects[i].x2 + padding, rects[i].y1 - padding, 
          rects[i].x2 + padding, rects[i].y2 + padding, 
          rects[i].x1 - padding, rects[i].y2 + padding
        );
        quads.push(quad);
      }
      if (!rectFullyWithinPoly) {
        splitRectangle(rects[i], polygon, polyPoints, depth - 1, instance);
      }
    }
  }

  // This gets the rectangle that surrounds the entire polygon
  const getPolygonBoundingRectangle = (polygonPoints) => {
    const highestPoint = polygonPoints.reduce((acc, point) => {
      return point.y < acc.y ? point : acc;
    })

    const lowestPoint = polygonPoints.reduce((acc, point) => {
      return point.y > acc.y ? point : acc;
    });

    const leftMostPoint = polygonPoints.reduce((acc, point) => {
      return point.x < acc.x ? point : acc;
    });

    const rightMostPoint = polygonPoints.reduce((acc, point) => {
      return point.x > acc.x ? point : acc;
    });

    const points = {
      x1: leftMostPoint.x,
      y1: highestPoint.y,
      x2: rightMostPoint.x,
      y2: lowestPoint.y

    }
    return points;
  }

  // Checks if the rectangle is fully within the polygon
  const isRectFullyWithinPolygon = (rectangle, polygon) => {
    const polyPoints = polygon.getPath();
    const rectPoints = [
      { x: rectangle.x1, y: rectangle.y1 },
      { x: rectangle.x2, y: rectangle.y1 },
      { x: rectangle.x2, y: rectangle.y2 },
      { x: rectangle.x1, y: rectangle.y2 }
    ];

    for (let i = 0; i < rectPoints.length; i++) {
      if (!isPointWithinPolygon(rectPoints[i], polyPoints)) {
        return false;
      }
    }

    return true;
  }

  // Checks if a given point is within a set of polygon points
  const isPointWithinPolygon = (point, polyPoints) => {
    let isInside = false;
    for (let i = 0, j = polyPoints.length - 1; i < polyPoints.length; j = i++) {
      if ((polyPoints[i].y > point.y) !== (polyPoints[j].y > point.y) &&
        (point.x < (polyPoints[j].x - polyPoints[i].x) * (point.y - polyPoints[i].y) / (polyPoints[j].y - polyPoints[i].y) + polyPoints[i].x)) {
        isInside = !isInside;
      }
    }
    return isInside;
  }

  const createRedactionAnnotation = (points, polygon, instance) => {
    const annot = new instance.Core.Annotations.RedactionAnnotation({
      PageNumber: polygon.PageNumber,
      Rect: points,
      StrokeColor: new instance.Core.Annotations.Color(255, 0, 0, 1),
      FillColor: new instance.Core.Annotations.Color(255, 255, 255, 1),
      IsText: true,
    });
    
    instance.Core.annotationManager.addAnnotation(annot);
    instance.Core.annotationManager.redrawAnnotation(annot);
  };

  return {
    saveResponsePackage,
    checkSavingFinalPackage,
    enableSavingFinal,
  };
};

export default useSaveResponsePackage;
