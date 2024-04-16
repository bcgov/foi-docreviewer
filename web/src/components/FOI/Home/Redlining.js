import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import React, {
  useRef,
  useEffect,
  useState,
  useImperativeHandle,
  useCallback,
} from "react";
import { createRoot } from "react-dom/client";
import { useSelector } from "react-redux";
import WebViewer from "@pdftron/webviewer";
import XMLParser from "react-xml-parser";
import ReactModal from "react-modal-resizable-draggable";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import CloseIcon from "@mui/icons-material/Close";
import IconButton from "@mui/material/IconButton";
import Switch from "@mui/material/Switch";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import {
  fetchAnnotationsByPagination,
  fetchAnnotationsInfo,
  saveAnnotation,
  deleteRedaction,
  deleteAnnotation,
  fetchSections,
  fetchPageFlag,
  fetchPDFTronLicense,
  deleteDocumentPages,
  savePageFlag,
} from "../../../apiManager/services/docReviewerService";
import {
  PDFVIEWER_DISABLED_FEATURES,
  ANNOTATION_PAGE_SIZE,
  REDACTION_SELECT_LIMIT,
} from "../../../constants/constants";
import { errorToast } from "../../../helper/helper";
import { faArrowUp, faArrowDown } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { useAppSelector } from "../../../hooks/hook";
import { pageFlagTypes } from "../../../constants/enum";
import {
  createPageFlagPayload,
  createRedactionSectionsString,
  getSections,
  getValidSections,
  updatePageFlags,
  getSliceSetDetails,
  sortDocObjects,
  getDocumentsForStitching,
} from "./utils";
import { Edit, MultiSelectEdit } from "./Edit";
import _ from "lodash";
import { 
  createFinalPackageSelection, 
  createOIPCForReviewSelection, 
  createRedlineForSignOffSelection, 
  createResponsePDFMenu, 
  handleFinalPackageClick, 
  handleRedlineForOipcClick, 
  handleRedlineForSignOffClick,
  renderCustomButton,
  isValidRedlineDownload,
  isReadyForSignOff } from "./CreateResponsePDF/CreateResponsePDF";
import useSaveRedlineForSignoff from "./CreateResponsePDF/useSaveRedlineForSignOff";
import useSaveResponsePackage from "./CreateResponsePDF/useSaveResponsePackage";

const Redlining = React.forwardRef(
  (
    {
      user,
      requestid,
      docsForStitcing,
      currentDocument,
      stitchedDoc,
      setStitchedDoc,
      individualDoc,
      pageMappedDocs,
      setPageMappedDocs,
      incompatibleFiles,
      setIsStitchingLoaded,
      isStitchingLoaded,
      licenseKey,
      setWarningModalOpen,
      scrollLeftPanel
    },
    ref
  ) => {
    const requestnumber = useAppSelector(
      (state) => state.documents?.requestnumber
    );

    document.title = requestnumber + " - FOI Document Reviewer"

    const pageFlags = useAppSelector((state) => state.documents?.pageFlags);
    const redactionInfo = useSelector(
      (state) => state.documents?.redactionInfo
    );
    const [redactionInfoIsLoaded, setRedactionInfoIsLoaded] = useState(false);
    const sections = useSelector((state) => state.documents?.sections);
    const currentLayer = useSelector((state) => state.documents?.currentLayer);
    const deletedDocPages = useAppSelector((state) => state.documents?.deletedDocPages);
    const viewer = useRef(null);
    const [documentList, setDocumentList] = useState([]);

    const validoipcreviewlayer = useAppSelector((state) => state.documents?.requestinfo?.validoipcreviewlayer);
    
    const [docViewer, setDocViewer] = useState(null);
    const [annotManager, setAnnotManager] = useState(null);
    const [annots, setAnnots] = useState(null);
    const [docViewerMath, setDocViewerMath] = useState(null);
    const [docInstance, setDocInstance] = useState(null);
    const [modalOpen, setModalOpen] = useState(false);
    const [messageModalOpen, setMessageModalOpen] = useState(false)

    const [newRedaction, setNewRedaction] = useState(null);
    const [deleteQueue, setDeleteQueue] = useState([]);
    const [selectedSections, setSelectedSections] = useState([]);
    const [defaultSections, setDefaultSections] = useState([]);
    const [selectedPageFlagId, setSelectedPageFlagId] = useState(null);
    const [editAnnot, setEditAnnot] = useState(null);
    const [saveDisabled, setSaveDisabled] = useState(true);
    const [pageSelections, setPageSelections] = useState([]);
    const [modalSortNumbered, setModalSortNumbered] = useState(false);
    const [modalSortAsc, setModalSortAsc] = useState(true);
    const [fetchAnnotResponse, setFetchAnnotResponse] = useState(false);
    const [merge, setMerge] = useState(false);
    const [iframeDocument, setIframeDocument] = useState(null);
    const [modalFor, setModalFor] = useState("");
    const [modalTitle, setModalTitle] = useState("");
    const [modalMessage, setModalMessage] = useState([""]);
    const [modalButtonLabel, setModalButtonLabel] = useState("");
    // State variables for Bulk Edit using Multi Selection option
    const [editRedacts, setEditRedacts] = useState(null);
    const [multiSelectFooter, setMultiSelectFooter] = useState(null);
    const [enableMultiSelect, setEnableMultiSelect] = useState(false);
    const [errorMessage, setErrorMessage] = useState(null);

    const [pdftronDocObjects, setpdftronDocObjects] = useState([]);
    const [stichedfiles, setstichedfiles] = useState([]);
    const [stitchPageCount, setStitchPageCount] = useState(0);
    const [skipDeletePages, setSkipDeletePages] = useState(false);
    const [pagesRemoved, setPagesRemoved] = useState([]);
    //xml parser
    const parser = new XMLParser();

    const [redlineSaving, setRedlineSaving] = useState(false);
    const [redlineModalOpen, setRedlineModalOpen] = useState(false);
    const [isDisableNRDuplicate, setIsDisableNRDuplicate] = useState(false);

    // Response Package && Redline download and saving logic (react custom hooks)
    const { 
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
    } = useSaveRedlineForSignoff(docInstance, docViewer);
    const {
      saveResponsePackage,
      checkSavingFinalPackage,
      enableSavingFinal,
    } = useSaveResponsePackage();

    // if using a class, equivalent of componentDidMount
    useEffect(() => {
      let initializeWebViewer = async () => {
        let currentDocumentS3Url = currentDocument?.currentDocumentS3Url;
        fetchSections(requestid, currentLayer.name.toLowerCase(), (error) => console.log(error));
        let response = await fetchPDFTronLicense(null, (error) =>
          console.log(error)
        );
        WebViewer(
          {
            licenseKey: response.data.license,
            path: "/webviewer",
            preloadWorker: "pdf",
            // initialDoc: currentPageInfo.file['filepath'] + currentPageInfo.file['filename'],
            initialDoc: currentDocumentS3Url,
            fullAPI: true,
            enableRedaction: true,
            useDownloader: false,
            css: "/stylesheets/webviewer.css",
            loadAsPDF: true,
          },
          viewer.current
        ).then((instance) => {
          const {
            documentViewer,
            annotationManager,
            Annotations,
            PDFNet,
            Math,
          } = instance.Core;
          instance.UI.disableElements(PDFVIEWER_DISABLED_FEATURES.split(","));
          instance.UI.enableElements(["attachmentPanelButton"]);
          documentViewer.setToolMode(
            documentViewer.getTool(instance.Core.Tools.ToolNames.REDACTION)
          );
          const UIEvents = instance.UI.Events;
   
          //customize header - insert a dropdown button
          const document = instance.UI.iframeWindow.document;
          setIframeDocument(document);
          instance.UI.setHeaderItems((header) => {
            //Create custom Create Reseponse PDF button
            const parent = documentViewer.getScrollViewElement().parentElement;
            const menu = createResponsePDFMenu(document);
            const redlineForSignOffBtn = createRedlineForSignOffSelection(document, enableSavingRedline);
            const redlineForOipcBtn = createOIPCForReviewSelection(document, enableSavingOipcRedline);
            const finalPackageBtn = createFinalPackageSelection(document, enableSavingFinal);
            redlineForOipcBtn.onclick = () => {
              handleRedlineForOipcClick(setModalFor, setModalTitle, setModalMessage, setModalButtonLabel, setRedlineModalOpen);
            };
            redlineForSignOffBtn.onclick = () => {
              handleRedlineForSignOffClick(setModalFor, setModalTitle, setModalMessage, setModalButtonLabel, setRedlineModalOpen);
            };
            finalPackageBtn.onclick = () => {
              handleFinalPackageClick(setModalFor, setModalTitle, setModalMessage, setModalButtonLabel, setRedlineModalOpen);
            };
            menu.appendChild(redlineForOipcBtn);
            menu.appendChild(redlineForSignOffBtn);
            menu.appendChild(finalPackageBtn);
            parent.appendChild(menu);

            //Create render function to render custom Create Reseponse PDF button
            const newCustomElement = {
              type: "customElement",
              render: () => renderCustomButton(document, menu)
            };
            // insert dropdown button in front of search button
            header.headers.default.splice(
              header.headers.default.length - 3,
              0,
              newCustomElement
            );
          });

          instance.UI.annotationPopup.add({
            type: "customElement",
            title: "Edit",
            render: () => (
              <Edit instance={instance} editAnnotation={editAnnotation} />
            ),
          });
          setDocInstance(instance);

          PDFNet.initialize();
          documentViewer
            .getTool(instance.Core.Tools.ToolNames.REDACTION)
            .setStyles(() => ({
              FillColor: new Annotations.Color(255, 255, 255),
            }));
          documentViewer
            .getTool(instance.Core.Tools.ToolNames.REDACTION2)
            .setStyles(() => ({
              FillColor: new Annotations.Color(255, 255, 255),
            }));
          documentViewer
            .getTool(instance.Core.Tools.ToolNames.REDACTION3)
            .setStyles(() => ({
              FillColor: new Annotations.Color(255, 255, 255),
            }));
          documentViewer
            .getTool(instance.Core.Tools.ToolNames.REDACTION4)
            .setStyles(() => ({
              FillColor: new Annotations.Color(255, 255, 255),
            }));
          documentViewer.addEventListener("documentLoaded", async () => {
            PDFNet.initialize(); // Only needs to be initialized once
            //Search Document Logic (for multi-keyword search and etc)
            const originalSearch = instance.UI.searchTextFull;
            //const pipeDelimittedRegexString = "/\w+(\|\w+)*/g"
            instance.UI.overrideSearchExecution((searchPattern, options) => {
              options.ambientString=true;
              if (searchPattern.includes("|")) {
                options.regex = true;
                //Conditional that ensures that there is no blank string after | and inbetween (). When regex is on, a character MUST follow | and must be inbetween () or else the regex search breaks as it is not a valid regex expression
                if (!searchPattern.split("|").includes("") && !searchPattern.split("()").includes("")) {
                  originalSearch.apply(this, [searchPattern, options]);
                }
              } else {
                options.regex = false;
                originalSearch.apply(this, [searchPattern, options]);
              }
            });

            //update user info
            let newusername = user?.name || user?.preferred_username || "";
            let username = annotationManager.getCurrentUser();
            if (newusername && newusername !== username)
              annotationManager.setCurrentUser(newusername);

            setDocViewer(documentViewer);
            setAnnotManager(annotationManager);
            setAnnots(Annotations);
            setDocViewerMath(Math);

            //update isloaded flag
            //localStorage.setItem("isDocumentLoaded", "true");

            let localDocumentInfo = currentDocument;
            if (Object.entries(individualDoc["file"])?.length <= 0)
              individualDoc = localDocumentInfo;            
            // let doclistCopy = [...docsForStitcing];
            let doclistCopy = getDocumentsForStitching([...docsForStitcing])
            
            //Disable the delete Icon if only 1 page for a request
            const disableDelete = doclistCopy.length === 1 && doclistCopy[0]?.file?.pagecount === 1;
            if (disableDelete) {
              instance.UI.disableElements(["thumbDelete","deletePage"]);
            }

            let slicerdetails = await getSliceSetDetails(
              doclistCopy.length,
              true
            );

            // Handle deletePages for the first document
            let _firstdoc = documentViewer.getDocument();
            const deletedPages = getDeletedPagesBeforeStitching(currentDocument?.file?.documentid);
            if (deletedPages.length > 0) {
              setSkipDeletePages(true);
              await _firstdoc.removePages(deletedPages);
            }

            if(doclistCopy.length > 1) {
              doclistCopy?.shift();
              let setCount = slicerdetails.setcount;
              let slicer = slicerdetails.slicer;            
              let objpreptasks = new Array(setCount);
              for (let slicecount = 1; slicecount <= setCount; slicecount++) {
                let sliceDoclist = doclistCopy.splice(0, slicer);
                objpreptasks.push(
                  mergeObjectsPreparation(
                    instance.Core.createDocument,
                    sliceDoclist,
                    slicecount
                  )
                );
              }
              Promise.all(objpreptasks);              
            }
            let setCount = slicerdetails.setcount;
            let slicer = slicerdetails.slicer;            
            let objpreptasks = new Array(setCount);
            for (let slicecount = 1; slicecount <= setCount; slicecount++) {
              let sliceDoclist = doclistCopy.splice(0, slicer);
              objpreptasks.push(
                mergeObjectsPreparation(
                  instance.Core.createDocument,
                  sliceDoclist,
                  slicecount
                )
              );
            }

            Promise.all(objpreptasks);

            fetchAnnotationsInfo(requestid, currentLayer.name.toLowerCase(), (error) => {
              console.log("Error:", error);
            });
          });

          instance.UI.addEventListener(UIEvents.ANNOTATION_FILTER_CHANGED, e => {
          e.detail.types = e.detail.types.map(type => {
            switch (type) {
              case "stickyNote":
                return "text";
              case "rectangle":
                return "square";
              case "freehand":
              case "other":
                return "ink";
              case "ellipse":
                return "circle";
              default:
                return type;
            }
          });
          setFilteredComments(e.detail);
          });
          //Triggered when the layout has changed because pages have permanently been added, removed, moved or changed in some other way.
          documentViewer.addEventListener("pagesUpdated", change => {
            if (change.removed.length > 0) {
              setPagesRemoved(change.removed)
            }
          })
          
          documentViewer.addEventListener("click", async () => {
            scrollLeftPanel(documentViewer.getCurrentPage());
          });

          let root = null;

          // add event listener for hiding saving menu
          document.body.addEventListener(
            "click",
            (e) => {
              document.getElementById("saving_menu").style.display = "none";

              //START: Bulk Edit using Multi Select Option
              //remove MultiSelectedAnnotations on click of multiDeleteButton because post that nothing will be selected.
              const multiDeleteButton = document.querySelector(
                '[data-element="multiDeleteButton"]'
              );
              if (multiDeleteButton) {
                multiDeleteButton?.addEventListener("click", function () {
                  root = null;
                  setMultiSelectFooter(root);
                  setEnableMultiSelect(false);
                });
              }

              //remove MultiSelectedAnnotations on click of multi-select-footer close button
              const closeButton = document.querySelector(".close-container");
              if (closeButton) {
                closeButton?.addEventListener("click", function () {
                  root = null;
                  setMultiSelectFooter(root);
                  setEnableMultiSelect(false);
                });
              }
              //remove MultiSelectedAnnotations on click of Delete WarningModalSignButton
              const warningButton = document.querySelector(
                '[data-element="WarningModalSignButton"]'
              );
              warningButton?.addEventListener("click", function () {
                root = null;
                setMultiSelectFooter(root);
                setEnableMultiSelect(false);
              });

              //remove MultiSelectedAnnotations on click of multi-select-button
              const button = document.querySelector(
                '[data-element="multiSelectModeButton"]'
              );

              button?.addEventListener("click", function () {
                const isActive = button?.classList.contains("active");
                if (isActive) {
                  root = null;
                  setMultiSelectFooter(root);
                  setEnableMultiSelect(false);
                }
              });

              const isButtonActive = button?.classList.contains("active");
              if (isButtonActive) {
                const _multiSelectFooter = document.querySelector(
                  ".multi-select-footer"
                );
                let editButton = document.querySelector(".edit-button");
                if (!editButton) {
                  editButton = document.createElement("div");
                  editButton.classList.add("edit-button");
                  _multiSelectFooter?.insertBefore(
                    editButton,
                    _multiSelectFooter.firstChild
                  );
                }
                const listItems =
                  document.querySelectorAll('[role="listitem"]');
                listItems.forEach((listItem) => {
                  let checkbox = listItem.querySelector(
                    'input[type="checkbox"]'
                  );
                  if (checkbox) {
                    if (root === null) {
                      root = createRoot(editButton);
                      setMultiSelectFooter(root);
                    }
                    checkbox.addEventListener("click", function () {
                      setEnableMultiSelect(true);
                    });
                  }
                });
                //END: Bulk Edit using Multi Select Option
              }
            },
            true
          );
        });
      };
      initializeWebViewer();
    }, []);

    // Get deletePages based on documentid
    const getDeletedPagesBeforeStitching = (documentid) => {
      let deletedPages = [];
      if (deletedDocPages) {
        deletedPages = deletedDocPages[documentid] || [];
      }
      return deletedPages;
    }

    useEffect(() => {
      // API call to save Deleted Pages to the BE
      if (pagesRemoved.length > 0 && pageMappedDocs?.docIdLookup && !skipDeletePages) {
        const results = {};     
        for (const [docId, obj] of Object.entries(pageMappedDocs.docIdLookup)) {
            const { pageMappings } = obj;
            for (const mapping of pageMappings) {
                if (pagesRemoved.includes(mapping.stitchedPageNo)) {
                    if (!results[docId]) {
                        results[docId] = { docid: parseInt(docId), pages: [] };
                    }
                    results[docId].pages.push(mapping.pageNo);
                }
            }
        }
        const finalResults = { 
          redactionlayer: currentLayer?.name,
          documentpages: Object.values(results) };
        
        deleteDocumentPages(
          requestid,
          finalResults,
          (data) => {
            window.location.reload();
          },
          (error) => {
            console.log(error);
          },
        );        
    }
    
    },[pagesRemoved, skipDeletePages, pageMappedDocs])

    const mergeObjectsPreparation = async (
      createDocument,
      slicedsetofdoclist,
      set
    ) => {
      slicedsetofdoclist.forEach(async (filerow) => {
        await createDocument(filerow.s3url, {
            useDownloader: false, // Added to fix BLANK page issue
            loadAsPDF: true, // Added to fix jpeg/pdf stitiching issue #2941
        }).then(async (newDoc) => {
          setpdftronDocObjects((_arr) => [
            ..._arr,
            {
              file: filerow,
              sortorder: filerow.sortorder,
              pages: filerow.pages,
              pdftronobject: newDoc,
              stitchIndex: filerow.stitchIndex,
              set: set,
              totalsetcount: slicedsetofdoclist.length,
            },
          ]);
        });
      });
    };

    useEffect(() => {
      const changeLayer = async () => {
        if (currentLayer) {
          if (currentLayer.name.toLowerCase() === "response package") {
            // Manually create white boxes to simulate redaction because apply redaction is permanent

            const existingAnnotations = annotManager.getAnnotationsList();
            const redactions = existingAnnotations.filter(
              (a) => a.Subject === "Redact"
            );
            let rects = [];
            for (const redaction of redactions) {
              rects = rects.concat(
                redaction.getQuads().map((q) => {
                  return {
                    page: redaction.getPageNumber(),
                    rect: new docViewerMath.Rect(q.x1, q.y3, q.x2, q.y1),
                  };
                })
              );
            }
            await annotManager.ungroupAnnotations(existingAnnotations);
            await annotManager.hideAnnotations(redactions);
            let newAnnots = [];
            for (const rect of rects) {
              const annot = new annots.RectangleAnnotation();
              annot.setRect(rect.rect);
              annot.FillColor = new annots.Color(255, 255, 255, 1);
              annot.Color = new annots.Color(255, 255, 255, 1);
              annot.setPageNumber(rect.page);
              newAnnots.push(annot);
            }
            annotManager.addAnnotations(newAnnots, {
              imported: true,
              source: "layerchange",
            });
            for (const annot of newAnnots) {
              annotManager.bringToBack(annot);
            }
            annotManager.drawAnnotationsFromList(newAnnots);
            annotManager.enableReadOnlyMode();
          } else {
            fetchAnnotationsByPagination(
              requestid,
              1,
              ANNOTATION_PAGE_SIZE,
              async (data) => {
                let meta = data["meta"];
                if (!fetchAnnotResponse) {
                  setMerge(true);
                  setFetchAnnotResponse(data);
                } else {
                  //oipc changes - begin
                  //Set to read only if oipc layer exists
                  if (validoipcreviewlayer && currentLayer.name.toLowerCase() === "redline") {
                    annotManager.enableReadOnlyMode();
                  } else {
                    annotManager.disableReadOnlyMode();
                  }
                  //oipc changes - end
                  docInstance?.UI.setToolbarGroup("toolbarGroup-Redact");
                  const existingAnnotations = annotManager.getAnnotationsList();
                  await annotManager.deleteAnnotations(existingAnnotations, {
                    imported: true,
                    force: true,
                    source: "layerchange",
                  });
                  let domParser = new DOMParser();
                  assignAnnotationsPagination(
                    pageMappedDocs,
                    data["data"],
                    domParser
                  );
                  if (meta["has_next"] === true) {
                    fetchandApplyAnnotations(
                      pageMappedDocs,
                      domParser,
                      meta["next_num"],
                      meta["pages"]
                    );
                  }
                }
              },
              (error) => {
                console.log("Error:", error);
              },
              currentLayer.name.toLowerCase()
            );
            fetchPageFlag(
              requestid,
              currentLayer.name.toLowerCase(),
              getDocumentsForStitching(docsForStitcing)?.map(d => d.file.documentid),
              (error) => console.log(error)
            );
          }
        }
      };
      changeLayer();
    }, [currentLayer]);

    useEffect(() => {
      // add event listener for hiding saving menu
      if (iframeDocument) {
        document.body.addEventListener(
          "click",
          () => {
            iframeDocument.getElementById("saving_menu").style.display = "none";
          },
          true
        );
      }
    }, [iframeDocument]);

    const removeRedactAnnotationDocContent = async (annotations) => {
      annotations.forEach((_redactionannot) => {
        if (_redactionannot.Subject === "Redact") {
          let redactcontent = _redactionannot.getContents();
          _redactionannot?.setContents("");
          _redactionannot?.setCustomData("trn-annot-preview", "");
        }
      });
    };

    const annotationChangedHandler = useCallback(
      (annotations, action, info) => {
        // If the event is triggered by importing then it can be ignored
        // This will happen when importing the initial annotations
        // from the server or individual changes from other users

        //oipc changes - begin
        if (validoipcreviewlayer && currentLayer.name.toLowerCase() === "redline") {
          return;
        }
        //oipc changes - end

        if (
          info.source !== "redactionApplied" &&
          info.source !== "cancelRedaction"
        ) {
          //ignore annots/redact changes made by applyRedaction
          if (info.imported) return;
          //do not run if redline is saving
          if (redlineSaving) return;
          if (currentLayer.name.toLowerCase() === "response package") return;
          annotations.forEach((annot) => {
            let displayedDoc =
              pageMappedDocs.stitchedPageLookup[annot.getPageNumber()];
            let individualPageNo = displayedDoc.page;
            annot.setCustomData("originalPageNo", `${individualPageNo - 1}`);
          });
          let _annotationtring =
            docInstance?.Core.annotationManager.exportAnnotations({
              annotationList: annotations,
              useDisplayAuthor: true,
            });
          _annotationtring.then(async (astr) => {
            //parse annotation xml
            let jObj = parser.parseFromString(astr); // Assume xmlText contains the example XML
            let annots = jObj.getElementsByTagName("annots");
            if (action === "delete") {
              let redactObjs = [];
              let annotObjs = [];
              for (let annot of annots[0].children) {
                let customData = annot.children.find(
                  (element) => element.name == "trn-custom-data"
                );
                if (!customData?.attributes?.bytes?.includes("isDelete")) {
                  let displayedDoc =
                    pageMappedDocs.stitchedPageLookup[
                      Number(annot.attributes.page) + 1
                    ];
                  if (annot.name === "redact") {
                    redactObjs.push({
                      page: Number(displayedDoc.page),
                      name: annot.attributes.name,
                      type: annot.name,
                      docid: displayedDoc.docid,
                      docversion: displayedDoc.docversion,
                    });
                  } else {
                    annotObjs.push({
                      page: Number(displayedDoc.page),
                      name: annot.attributes.name,
                      type: annot.name,
                      docid: displayedDoc.docid,
                      docversion: displayedDoc.docversion,
                    });
                  }
                }
              }
              if (annotObjs?.length > 0) {
                deleteAnnotation(
                  requestid,
                  currentLayer.redactionlayerid,
                  annotObjs,
                  (data) => {
                    fetchAnnotationsInfo(requestid, currentLayer.name.toLowerCase(), (error) => {
                      console.log("Error:", error);
                    });
                  },
                  (error) => {
                    console.log(error);
                  }
                );
              }
              if (redactObjs?.length > 0) {
                deleteRedaction(
                  requestid,
                  currentLayer.redactionlayerid,
                  redactObjs,
                  (data) => {
                    fetchPageFlag(
                      requestid,
                      currentLayer.name.toLowerCase(),
                      documentList?.map(d => d.documentid),
                      (error) => console.log(error)
                    );
                  },
                  (error) => {
                    console.log(error);
                  }
                );
              }
              setDeleteQueue(redactObjs);
            } else if (action === "add") {
              let displayedDoc;
              let individualPageNo;

              await removeRedactAnnotationDocContent(annotations);

              if (annotations[0].Subject === "Redact") {
                let pageSelectionList = [...pageSelections];
                annots[0].children?.forEach((annotatn, i) => {
                  displayedDoc =
                    pageMappedDocs.stitchedPageLookup[
                      Number(annotatn.attributes.page) + 1
                    ];
                  individualPageNo = displayedDoc.page;
                  if (annotations[i]?.type === "fullPage") {
                    annotations[i].NoResize = true;
                    pageSelectionList.push({
                      page: Number(individualPageNo),
                      flagid: pageFlagTypes["Withheld in Full"],
                      docid: displayedDoc.docid,
                    });
                    annotManager.bringToBack(annotations[i]);

                    let parentRedaction;
                    let allAnnotations =
                      docInstance.Core.annotationManager.getAnnotationsList();
                    let _selectedAnnotations = allAnnotations.find(
                      (annot) =>
                        annot.Subject == "Free Text" &&
                        annot.getCustomData("trn-redaction-type") ==
                          "fullPage" &&
                        annot.PageNumber == Number(annotatn.attributes.page) + 1
                    );
                    if (_selectedAnnotations) {
                      parentRedaction = allAnnotations?.find(
                        (r) =>
                          r.Subject === "Redact" &&
                          r.InReplyTo === _selectedAnnotations?.Id
                      );
                    }
                    if (parentRedaction) {
                      annotations[i].setCustomData(
                        "existingId",
                        `${parentRedaction?.Id}`
                      );
                      annotations[i].setCustomData(
                        "existingFreeTextId",
                        `${_selectedAnnotations?.Id}`
                      );
                    }
                  } else {
                    pageSelectionList.push({
                      page: Number(individualPageNo),
                      flagid: pageFlagTypes["Partial Disclosure"],
                      docid: displayedDoc.docid,
                    });
                  }
                  annotations[i].NoMove = true;
                  annotations[i].setCustomData(
                    "docid",
                    `${displayedDoc.docid}`
                  );
                  annotations[i].setCustomData(
                    "docversion",
                    `${displayedDoc.docversion}`
                  );
                  annotations[i].setCustomData(
                    "redactionlayerid",
                    `${currentLayer.redactionlayerid}`
                  );
                  annotations[i].IsHoverable = false;
                });
                setPageSelections(pageSelectionList);
                let annot = annots[0].children[0];
                let astr =
                  await docInstance.Core.annotationManager.exportAnnotations({
                    annotationList: annotations,
                    useDisplayAuthor: true,
                  });
                setNewRedaction({
                  pages: annot.attributes.page,
                  names: annots[0].children.map((a) => a.attributes.name),
                  astr: astr,
                  type: annot.name,
                });
              } else {
                for (let annot of annotations) {
                  displayedDoc =
                    pageMappedDocs.stitchedPageLookup[Number(annot.PageNumber)];
                  annot.setCustomData("docid", `${displayedDoc.docid}`);
                  annot.setCustomData(
                    "docversion",
                    `${displayedDoc.docversion}`
                  );
                  annot.setCustomData(
                    "redactionlayerid",
                    `${currentLayer.redactionlayerid}`
                  );
                  // annot.NoMove = true; //All annotations except redactions shouldn't be restricted, hence commented this code.
                }

                let astr =
                  await docInstance.Core.annotationManager.exportAnnotations({
                    annotationList: annotations,
                    useDisplayAuthor: true,
                  });

                let sections = annotations[0].getCustomData("sections");
                let sectn;
                if (sections) {
                  sectn = {
                    foiministryrequestid: requestid,
                  };
                }
                setSelectedSections([]);
                saveAnnotation(
                  requestid,
                  astr,
                  (data) => {
                    fetchAnnotationsInfo(requestid, currentLayer.name.toLowerCase(), (error) => {
                      console.log("Error:", error);
                    });
                  },
                  (error) => {
                    console.log(error);
                  },
                  currentLayer.redactionlayerid,
                  null,
                  sectn
                  //pageSelections
                );
              }
            } else if (action === "modify") {
              if (
                info.source === "group" &&
                newRedaction?.astr.includes(annotations[0].Id) // if we are grouping the newly created annotations do not save
              ) {
                return;
              }
              // handles saving modify actions
              let selectedAnnotations =
                docInstance.Core.annotationManager.getSelectedAnnotations();
              let username = docViewer
                ?.getAnnotationManager()
                ?.getCurrentUser();
              let jObj = parser.parseFromString(astr); // Assume xmlText contains the example XML
              let annots = jObj.getElementsByTagName("annots");
              const isRedactFound = selectedAnnotations?.find(
                (a) => a.Subject === "Redact"
              );
              for (let annot of annots[0].children) {
                //Redaction resize handled here
                if (
                  selectedAnnotations.length > 0 &&
                  isRedactFound &&
                  annot.name === "redact"
                ) {
                  // save redact astr
                  saveAnnotation(
                    requestid,
                    astr,
                    (data) => {
                      fetchAnnotationsInfo(requestid, currentLayer.name.toLowerCase(), (error) => {
                        console.log("Error:", error);
                      });
                      fetchPageFlag(
                        requestid,
                        currentLayer.name.toLowerCase(),
                        documentList?.map(d => d.documentid),
                        (error) => console.log(error)
                      );
                    },
                    (error) => {
                      console.log(error);
                    },
                    currentLayer.redactionlayerid,
                    null
                  );
                  const _resizeAnnot = {
                    pages: annot.attributes.page,
                    names: [annot.attributes.name],
                    astr: astr,
                    type: annot.name,
                  };
                  // save resized section here
                  saveRedaction(_resizeAnnot);
                }
                //Other Annotations resize handled here
                else if (
                  (selectedAnnotations.length === 0 &&
                    annot.name === "redact") ||
                  (selectedAnnotations.length > 0 &&
                    selectedAnnotations[0].Subject !== "Redact" &&
                    selectedAnnotations[0].Author === username)
                ) {
                  saveAnnotation(
                    requestid,
                    astr,
                    (data) => {
                      fetchPageFlag(
                        requestid,
                        currentLayer.name.toLowerCase(),
                        documentList?.map(d => d.documentid),
                        (error) => console.log(error)
                      );
                    },
                    (error) => {
                      console.log(error);
                    },
                    currentLayer.redactionlayerid,
                    null
                  );
                }
              }
            }
          });
          docInstance.Core.Annotations.NoMove = true;
          setAnnots(docInstance.Core.Annotations);
        }
      },
      [
        pageMappedDocs,
        currentLayer,
        newRedaction,
        pageSelections,
        redlineSaving,
        isStitchingLoaded,
      ]
    );

    useEffect(() => {
      annotManager?.addEventListener(
        "annotationSelected",
        (annotations, action) => {
          if (action === "selected") {
            if (
              annotManager?.getSelectedAnnotations().length >
              REDACTION_SELECT_LIMIT * 2
            ) {
              annotManager?.deselectAnnotations(annotations);
              setWarningModalOpen(true);
            }
          }
          if (multiSelectFooter && enableMultiSelect) {
            multiSelectFooter.render(
              <MultiSelectEdit
                docInstance={docInstance}
                editRedactions={editRedactions}
              />
            );
          }
        }
      );

      annotManager?.removeEventListener(
        "annotationChanged",
        annotationChangedHandler
      );
      annotManager?.addEventListener(
        "annotationChanged",
        annotationChangedHandler
      );
      return () => {
        annotManager?.removeEventListener(
          "annotationChanged",
          annotationChangedHandler
        );
      };
    }, [
      pageMappedDocs,
      currentLayer,
      newRedaction,
      pageSelections,
      redlineSaving,
      multiSelectFooter,
      enableMultiSelect,
      isStitchingLoaded,
    ]);

    useImperativeHandle(ref, () => ({
      addFullPageRedaction(pageNumbers, flagId) {
        if (flagId) setSelectedPageFlagId(flagId)
        let newAnnots = [];
        for (let pageNumber of pageNumbers) {
          let height = docViewer.getPageHeight(pageNumber);
          let width = docViewer.getPageWidth(pageNumber);
          let quads = [
            new docViewerMath.Quad(0, height, width, height, width, 0, 0, 0),
          ];
          const annot = new annots.RedactionAnnotation({
            PageNumber: pageNumber,
            Quads: quads,
            FillColor: new annots.Color(255, 255, 255),
            IsText: false, // Create either a text or rectangular redaction
            Author: user?.name || user?.preferred_username || "",
          });
          annot.type = "fullPage";
          annot.NoResize = true;
          annot.NoMove = true;
          annot.setCustomData("trn-redaction-type", "fullPage");
          newAnnots.push(annot);
        }
        annotManager.addAnnotations(newAnnots);
        annotManager.drawAnnotationsFromList(newAnnots);
      },
    }));

    const disableNRDuplicate = () => {
      let isDisabled = false;
      if (pageFlags?.length > 0) {        
        if (incompatibleFiles.length > 0) {
          isDisabled = false;
        }        
        else {
            let duplicateNRflags = [];
            for (const flagInfo of pageFlags) {                  
              duplicateNRflags = duplicateNRflags.concat(flagInfo.pageflag.filter(flag => flag.flagid === pageFlagTypes["Duplicate"] || flag.flagid === pageFlagTypes["Not Responsive"])
              .map(flag => flag.flagid));
            }
            if (docsForStitcing.totalPageCount === duplicateNRflags.length) {
              isDisabled = true;
            }
          }
        }
      setIsDisableNRDuplicate(isDisabled);
      if (isDisabled) {
        setIncludeNRPages(isDisabled)
        setIncludeDuplicatePages(isDisabled);
      }
    }

    const checkSavingRedlineButton = (_instance) => {
      console.log("checksavingredlinebutton")
      disableNRDuplicate();
      const readyForSignOff = isReadyForSignOff(documentList, pageFlags);
      const validRedlineDownload = isValidRedlineDownload(pageFlags);
      const redlineReadyAndValid = readyForSignOff && validRedlineDownload;
      const oipcRedlineReadyAndValid = (validoipcreviewlayer === true && currentLayer.name.toLowerCase() === "oipc") && readyForSignOff;
      checkSavingRedline(redlineReadyAndValid, _instance);
      checkSavingOIPCRedline(oipcRedlineReadyAndValid, _instance, readyForSignOff);
      checkSavingFinalPackage(redlineReadyAndValid, _instance);
    };

    //useEffect to handle validation of Response Package downloads
    useEffect(() => {
      const handleCreateResponsePDFClick = () => {
        checkSavingRedlineButton(docInstance);
      }
      if (docInstance && documentList.length > 0) {
        console.log("EVNT LISTINER")
        const document = docInstance?.UI.iframeWindow.document;
        document.getElementById("create_response_pdf").addEventListener("click", handleCreateResponsePDFClick);
      }
      //Cleanup Function: removes previous event listeiner to ensure handleCreateResponsePDFClick event is not called multiple times on click
      return () => {
        if (docInstance && documentList.length > 0) {
          const document = docInstance?.UI.iframeWindow.document;
          document.getElementById("create_response_pdf").removeEventListener("click", handleCreateResponsePDFClick)
        }
      };
    }, [pageFlags, isStitchingLoaded]);

    const stitchPages = (_doc, pdftronDocObjs) => {
      for (let filerow of pdftronDocObjs) {
        let _exists = stichedfiles.filter(
          (_file) => _file.file.file.documentid === filerow.file.file.documentid
        );
        if (_exists?.length === 0) {
          let index = filerow.stitchIndex;
          _doc
            .insertPages(filerow.pdftronobject, filerow.pages, index)
            .then(() => {
              const pageCount = docViewer.getPageCount();
              if (pageCount === docsForStitcing.totalPageCount) {
                setStitchPageCount(pageCount);
              }
            })
            .catch((error) => {
              console.error("An error occurred during page insertion:", error);
            });
          setstichedfiles((_arr) => [..._arr, filerow]);
        }
      }
    };

    const applyAnnotationsFunc = () => {
      let domParser = new DOMParser();
      if (fetchAnnotResponse) {
        assignAnnotationsPagination(
          pageMappedDocs,
          fetchAnnotResponse["data"],
          domParser
        );
        let meta = fetchAnnotResponse["meta"];
        if (meta["has_next"] === true) {
          fetchandApplyAnnotations(
            pageMappedDocs,
            domParser,
            meta["next_num"],
            meta["pages"]
          );
        }
      }
    };

    const fetchandApplyAnnotations = async (
      mappedDocs,
      domParser,
      startPageIndex = 1,
      lastPageIndex = 1
    ) => {
      for (let i = startPageIndex; i <= lastPageIndex; i++) {
        fetchAnnotationsByPagination(
          requestid,
          i,
          ANNOTATION_PAGE_SIZE,
          async (data) => {
            assignAnnotationsPagination(mappedDocs, data["data"], domParser);
          },
          (error) => {
            console.log("Error:", error);
            setErrorMessage(
              "Error occurred while fetching redaction details, please refresh browser and try again"
            );
          },
          currentLayer.name.toLowerCase()
        );
      }
    };

    useEffect(() => {
      if (errorMessage) {
        errorToast(errorMessage);
      }
    }, [errorMessage]);

    const assignAnnotationsPagination = async (
      pageMappedDocs,
      annotData,
      domParser
    ) => {
      let username = docViewer?.getAnnotationManager()?.getCurrentUser();
      for (const entry in annotData) {
        let xml = parser.parseFromString(annotData[entry]);
        for (let annot of xml.getElementsByTagName("annots")[0].children) {
          let txt = domParser.parseFromString(
            annot.getElementsByTagName("trn-custom-data")[0].attributes.bytes,
            "text/html"
          );
          let customData = JSON.parse(txt.documentElement.textContent);
          let originalPageNo = customData.originalPageNo;
          let mappedDoc = pageMappedDocs?.docIdLookup[entry];
          annot.attributes.page = (
            mappedDoc.pageMappings.find(
              (p) => p.pageNo - 1 === Number(originalPageNo)
            )?.stitchedPageNo - 1
          )?.toString();
        }
        xml = parser.toString(xml);
        const _annotations = await annotManager.importAnnotations(xml);
        _annotations.forEach((_annotation) => {
          // _annotation.NoMove = true; //All annotations except redactions shouldn't be restricted, hence commented this code.
          if (_annotation.Subject === "Redact") {
            _annotation.IsHoverable = false;
            _annotation.NoMove = true;

            if (_annotation.type === "fullPage") {
              _annotation.NoResize = true;
              annotManager.bringToBack(_annotation);
            }
          }
          annotManager.redrawAnnotation(_annotation);

          annotManager.setPermissionCheckCallback((author, _annotation) => {
            if (_annotation.Subject !== "Redact" && author !== username) {
              _annotation.NoResize = true;
            }
            if (author !== username) {
              _annotation.LockedContents = true;
            }
            return true;
          });
        });
      }
    };

    useEffect(() => {
      if (docsForStitcing.length > 0) {
        setDocumentList(getDocumentsForStitching([...docsForStitcing])?.map(docs => docs.file));
      }
      if (
        pdftronDocObjects?.length > 0 &&
        docsForStitcing.length > 0 &&
        merge &&
        docViewer
      ) {
        // let doclistCopy = [...docsForStitcing];
        let doclistCopy = getDocumentsForStitching([...docsForStitcing])
        if(doclistCopy.length > 1){
          doclistCopy?.shift(); //remove first document from the list
          let _pdftronDocObjects = sortDocObjects(pdftronDocObjects, doclistCopy);

          const _doc = docViewer.getDocument();
          if (_doc && _pdftronDocObjects.length > 0) {
            stitchPages(_doc, _pdftronDocObjects);
          }
        }
        else if (doclistCopy.length === 1){
          
          applyAnnotationsFunc();
          setIsStitchingLoaded(true);
          setpdftronDocObjects([]);
          setstichedfiles([]);
        }
      }
    }, [
      pdftronDocObjects,
      docsForStitcing,
      stichedfiles,
      fetchAnnotResponse,
      docViewer,
    ]);

    useEffect(() => {
      if (stitchPageCount === docsForStitcing.totalPageCount) {
        console.log(`Download and Stitching completed.... ${new Date()}`);

        if (stitchPageCount > 800) {
          docInstance.UI.setLayoutMode(docInstance.UI.LayoutMode.Single);
        }
        applyAnnotationsFunc();
        setIsStitchingLoaded(true);
        setPagesRemoved([]);
        setSkipDeletePages(false);
        setpdftronDocObjects([]);
        setstichedfiles([]);
      }
    }, [stitchPageCount]);

    useEffect(() => {
      //update user name
      let newusername = user?.name || user?.preferred_username || "";
      let username = docViewer?.getAnnotationManager()?.getCurrentUser();
      if (newusername !== username)
        docViewer?.getAnnotationManager()?.setCurrentUser(newusername);
    }, [user]);

    useEffect(() => {
      docViewer?.setCurrentPage(individualDoc["page"], false);
    }, [individualDoc]);

    // This updates the page flag based on the annotations on the page
    useEffect(() => {
      // only update page flags after initial load
      if (!redactionInfo || redactionInfo.length == 0) return;
      if (!redactionInfoIsLoaded) {
        setRedactionInfoIsLoaded(true);
        return;
      }
      const hasUpdated = updatePageFlagsByPage(redactionInfo);
      if (!hasUpdated) {
        fetchPageFlag(
          requestid,
          currentLayer.name.toLowerCase(),
          docsForStitcing.map(d => d.file.documentid),
          (error) => console.log(error)
        );
      }
    }, [redactionInfo])

    // This updates the page flags for pages where all the annotations have the same section
    const updatePageFlagsByPage = (redactionInfo) => {
      let hasUpdated = false;
      const getSectionIdsMap = (redactionInfo) => {
        let sectionIdsMap = {}
        for (let annot of redactionInfo) {
          for (let id of annot.sections.ids) {
            if (sectionIdsMap?.[annot.documentid]?.[annot.pagenumber + 1]) {
              sectionIdsMap[annot.documentid][annot.pagenumber + 1].push(id)
            } else if (sectionIdsMap?.[annot.documentid]) {
              sectionIdsMap[annot.documentid][annot.pagenumber + 1] = [id]
            } else {
              sectionIdsMap[annot.documentid] = {}
              sectionIdsMap[annot.documentid][annot.pagenumber + 1] = [id]
            }
          }
        }
        return sectionIdsMap;
      }

      const setFlagsForPagesToUpdate = (redactionInfo) => {
        let pagesToUpdate = []
        let sectionIdsMap = getSectionIdsMap(redactionInfo)
        for (let doc in sectionIdsMap) {
          for (let page in sectionIdsMap[doc]) {
            if (sectionIdsMap[doc][page].every(id => id >= 25) && sectionIdsMap[doc][page].includes(25)) {
              pagesToUpdate.push({ docid: doc, page: page, flagid: pageFlagTypes["In Progress"]})
            } else if (sectionIdsMap[doc][page].every(id => id == 26)) {
              pagesToUpdate.push({ docid: doc, page: page, flagid: pageFlagTypes["Full Disclosure"]})
            }
          }
        }
        return pagesToUpdate
      }
      
      let pagesToUpdate = setFlagsForPagesToUpdate(redactionInfo)
      if (pagesToUpdate.length > 0) {
        savePageFlag(
          requestid, 
          0, 
          (data) => {
            fetchPageFlag(
              requestid,
              currentLayer.name.toLowerCase(),
              docsForStitcing.map(d => d.file.documentid),
              (error) => console.log(error)
            );
          }, 
          (error) => console.log('error: ', error), 
          createPageFlagPayload(pagesToUpdate, currentLayer.redactionlayerid)
        )
        hasUpdated = true;
      }
      return hasUpdated;
    }

    //START: Save updated redactions to BE part of Bulk Edit using Multi Select Option
    const saveRedactions = () => {
      setModalOpen(false);
      setSelectedPageFlagId(null);
      setSaveDisabled(true);
      let redactionObj = editRedacts;
      let astr = parser.parseFromString(redactionObj.astr);
      let childAnnotations = [];
      let redactionSectionsIds = selectedSections;
      let redactionIds = [];
      let pageSelectionList = [];
      for (const node of astr.getElementsByTagName("annots")[0].children) {
        let _redact = annotManager
          .getAnnotationsList()
          .find(
            (r) =>
              r.Subject === "Redact" && r.InReplyTo === node.attributes.name
          );
        redactionIds.push(_redact.Id);
        let childAnnotation = annotManager.getAnnotationById(
          node.attributes.name
        );
        childAnnotation.PageNumber = _redact?.getPageNumber();
        childAnnotation.X = _redact.X;
        childAnnotation.Y = _redact.Y;
        childAnnotation.FontSize =
          Math.min(parseInt(_redact.FontSize), 9) + "pt";
        const fullpageredaction = _redact.getCustomData("trn-redaction-type");
        const displayedDoc =
          pageMappedDocs.stitchedPageLookup[Number(node.attributes.page) + 1];

        //page flag updates
        updatePageFlags(
          defaultSections,
          selectedSections,
          fullpageredaction,
          pageFlagTypes,
          displayedDoc,
          pageSelectionList
        );

        if (redactionSectionsIds.length > 0) {
          let redactionSections = createRedactionSectionsString(
            sections,
            redactionSectionsIds
          );
          childAnnotation.setContents(redactionSections);

          childAnnotation.setCustomData(
            "sections",
            JSON.stringify(getSections(sections, redactionSectionsIds))
          );
          childAnnotation.setCustomData("docid", `${displayedDoc.docid}`);
          childAnnotation.setCustomData(
            "docversion",
            `${displayedDoc.docversion}`
          );
        }
        const doc = docViewer?.getDocument();
        let pageNumber = parseInt(node.attributes.page) + 1;

        const pageInfo = doc.getPageInfo(pageNumber);
        const pageMatrix = doc.getPageMatrix(pageNumber);
        const pageRotation = doc.getPageRotation(pageNumber);
        childAnnotation.fitText(pageInfo, pageMatrix, pageRotation);
        let rect = childAnnotation.getRect();
        rect.x2 = Math.ceil(rect.x2);
        childAnnotation.setRect(rect);
        annotManager.redrawAnnotation(childAnnotation);
        childAnnotations.push(childAnnotation);
      }
      let _annotationtring = annotManager.exportAnnotations({
        annotationList: childAnnotations,
        useDisplayAuthor: true,
      });
      let sectn = {
        foiministryrequestid: requestid,
      };
      _annotationtring.then((astr) => {
        saveAnnotation(
          requestid,
          astr,
          (data) => {
            fetchAnnotationsInfo(requestid, currentLayer.name.toLowerCase(), (error) => {
              console.log("Error:", error);
            });
            setPageSelections([]);
            fetchPageFlag(
              requestid,
              currentLayer.name.toLowerCase(),
              documentList?.map(d => d.documentid),
              (error) => console.log(error)
            );
          },
          (error) => {
            console.log(error);
          },
          currentLayer.redactionlayerid,
          createPageFlagPayload(
            pageSelectionList,
            currentLayer.redactionlayerid
          ),
          sectn
        );

        if (redactionSectionsIds.length > 0) {
          redactionIds.forEach((_id) => {
            redactionInfo.find((r) => r.annotationname === _id).sections.ids =
              redactionSectionsIds;
          });
        }
        setSelectedSections([]);
        setEnableMultiSelect(false);
        setMultiSelectFooter(null);
        setEditRedacts(null);
      });

      setNewRedaction(null);
    };
    //END: Save updated redactions to BE part of Bulk Edit using Multi Select Option

    const getRedactionObj = (newRedaction, editAnnot, _resizeAnnot) => {
      if (newRedaction) return newRedaction;
      else if (editAnnot) return editAnnot;
      else return _resizeAnnot;
    };

    const saveRedaction = async (_resizeAnnot = {}) => {
      setModalOpen(false);
      setSelectedPageFlagId(null);
      setSaveDisabled(true);
      let redactionObj = getRedactionObj(newRedaction, editAnnot, _resizeAnnot);
      let astr = parser.parseFromString(redactionObj.astr);

      if (editAnnot || _resizeAnnot?.type === "redact") {
        let childAnnotation;
        let childSection = "";
        let i = redactionInfo?.findIndex(
          (a) => a.annotationname === redactionObj?.names[0]
        );
        if (i >= 0) {
          childSection = redactionInfo[i]?.sections.annotationname;
          childAnnotation = annotManager.getAnnotationById(childSection);
        }
        const displayedDoc =
          pageMappedDocs.stitchedPageLookup[Number(redactionObj["pages"]) + 1];
        let pageSelectionList = [...pageSelections];
        for (const node of astr.getElementsByTagName("annots")[0].children) {
          let redaction = annotManager.getAnnotationById(node.attributes.name);
          redaction.NoMove = true;
          const fullpageredaction =
            redaction.getCustomData("trn-redaction-type");
          let coords = node.attributes.coords;
          let X = coords?.substring(0, coords.indexOf(","));
          childAnnotation = getCoordinates(childAnnotation, redaction, X);

          let redactionSectionsIds = selectedSections;
          if (redactionSectionsIds.length > 0) {
            let redactionSections = createRedactionSectionsString(
              sections,
              redactionSectionsIds
            );
            childAnnotation.setContents(redactionSections);

            childAnnotation.setCustomData(
              "sections",
              JSON.stringify(getSections(sections, redactionSectionsIds))
            );
            childAnnotation.setCustomData("docid", `${displayedDoc.docid}`);
            childAnnotation.setCustomData(
              "docversion",
              `${displayedDoc.docversion}`
            );
          }
          const doc = docViewer.getDocument();
          let pageNumber = 0;
          if (editAnnot) {
            pageNumber = parseInt(editAnnot.pages) + 1;
          } else if (_resizeAnnot?.type === "redact") {
            pageNumber = parseInt(_resizeAnnot.pages) + 1;
          }
          const pageInfo = doc.getPageInfo(pageNumber);
          const pageMatrix = doc.getPageMatrix(pageNumber);
          const pageRotation = doc.getPageRotation(pageNumber);
          childAnnotation.fitText(pageInfo, pageMatrix, pageRotation);
          childAnnotation.NoMove = true;
          let rect = childAnnotation.getRect();
          rect.x2 = Math.ceil(rect.x2);
          childAnnotation.setRect(rect);
          annotManager.redrawAnnotation(childAnnotation);
          let _annotationtring = annotManager.exportAnnotations({
            annotationList: [childAnnotation],
            useDisplayAuthor: true,
          });
          let sectn = {
            foiministryrequestid: requestid,
          };
          _annotationtring.then((astr) => {
            //parse annotation xml
            if (_resizeAnnot?.type === "redact") {
              saveAnnotation(
                requestid,
                astr,
                (data) => {},
                (error) => {
                  console.log(error);
                },
                currentLayer.redactionlayerid,
                null,
                sectn
              );
            } else {
              //page flag updates
              updatePageFlags(
                defaultSections,
                selectedSections,
                fullpageredaction,
                pageFlagTypes,
                displayedDoc,
                pageSelectionList
              );
              saveAnnotation(
                requestid,
                astr,
                (data) => {
                  fetchAnnotationsInfo(requestid, currentLayer.name.toLowerCase(), (error) => {
                    console.log("Error:", error);
                  });
                  setPageSelections([]);
                  fetchPageFlag(
                    requestid,
                    currentLayer.name.toLowerCase(),
                    documentList?.map(d => d.documentid),
                    (error) => console.log(error)
                  );
                },
                (error) => {
                  console.log(error);
                },
                currentLayer.redactionlayerid,
                createPageFlagPayload(
                  pageSelectionList,
                  currentLayer.redactionlayerid
                ),
                sectn
              );
            }
            setSelectedSections([]);
            if (redactionSectionsIds.length > 0) {
              redactionObj.names?.forEach((name) => {
                const info = redactionInfo.find(
                  (r) => r.annotationname === name
                );
                if (info) {
                  info.sections.ids = redactionSectionsIds;
                }
              });
            }
            setEditAnnot(null);
          });
        }
      } else {
        let pageFlagSelections = pageSelections;
        if (
          (defaultSections.length > 0 && defaultSections[0] === 25) ||
          selectedSections[0] === 25
        ) {
          pageFlagSelections = pageFlagSelections.map((flag) => {
            flag.flagid = pageFlagTypes["In Progress"];
            return flag;
          });
        }

        // add section annotation
        let sectionAnnotations = [];
        for (const node of astr.getElementsByTagName("annots")[0].children) {
          let annotationsToDelete = [];
          let redaction = annotManager.getAnnotationById(node.attributes.name);
          let coords = node.attributes.coords;
          let X = coords?.substring(0, coords.indexOf(","));
          let annot = new annots.FreeTextAnnotation();
          annot = getCoordinates(annot, redaction, X);
          annot.Color = "red";
          annot.StrokeThickness = 0;
          annot.Author = user?.name || user?.preferred_username || "";
          let redactionSectionsIds =
            defaultSections.length > 0 ? defaultSections : selectedSections;
          let redactionSections = createRedactionSectionsString(
            sections,
            redactionSectionsIds
          );
          annot.setAutoSizeType("auto");
          annot.setContents(redactionSections);
          annot.setCustomData("parentRedaction", `${redaction.Id}`);
          annot.setCustomData(
            "sections",
            JSON.stringify(getSections(sections, redactionSectionsIds))
          );
          const doc = docViewer.getDocument();
          const pageInfo = doc.getPageInfo(annot.PageNumber);
          const pageMatrix = doc.getPageMatrix(annot.PageNumber);
          const pageRotation = doc.getPageRotation(annot.PageNumber);
          annot.NoMove = true;
          annot.fitText(pageInfo, pageMatrix, pageRotation);
          let rect = annot.getRect();
          rect.x2 = Math.ceil(rect.x2);
          annot.setRect(rect);
          if (redaction.type == "fullPage") {
            annot.NoResize = true;
            annot.setCustomData("trn-redaction-type", "fullPage");
            let txt = new DOMParser().parseFromString(
              node.getElementsByTagName("trn-custom-data")[0].attributes.bytes,
              "text/html"
            );
            let customData = JSON.parse(txt.documentElement.textContent);
            annot.setCustomData(
              "existingId",
              `${customData.existingFreeTextId}`
            );
            //Setting the existing annotationId in the new annotations for deleting
            //from backend.
            let existingFreeTextAnnot = annotManager.getAnnotationById(
              customData.existingFreeTextId
            );
            let existingRedactAnnot = annotManager.getAnnotationById(
              customData.existingId
            );
            if (!!existingFreeTextAnnot && !!existingRedactAnnot) {
              existingFreeTextAnnot.setCustomData("isDelete", `${true}`);
              existingRedactAnnot.setCustomData("isDelete", `${true}`);
              annotationsToDelete.push(existingFreeTextAnnot);
              annotationsToDelete.push(existingRedactAnnot);
            }
          }
          sectionAnnotations.push(annot);
          for (let redactObj of redactionObj.names) {
            let annotAdded = redactionInfo?.find(
              (redaction) => redaction.annotationname == redactObj
            );
            let sectionAdded = redactionInfo?.find(
              (redaction) => redaction.sections.annotationname == annot.Id
            );
            if (!sectionAdded && !annotAdded) {
              redactionInfo.push({
                annotationname: redactObj,
                sections: {
                  annotationname: annot.Id,
                  ids: redactionSectionsIds,
                },
              });
            }
          }

          for (let section of getValidSections(
            sections,
            redactionSectionsIds
          )) {
            section.count++;
          }
          //delete if there are existing fullpage redactions
          if (annotationsToDelete?.length > 0) {
            annotManager.deleteAnnotations(annotationsToDelete, {
              force: true,
            });
          }
          // grouping the section annotation with the redaction will trigger a modify event, which will also save the redaction
          await annotManager.groupAnnotations(annot, [redaction]);
        }
        let annotationList = [];
        for (let name of newRedaction.names) {
          annotationList.push(annotManager.getAnnotationById(name));
        }
        astr = await annotManager.exportAnnotations({
          annotationList: annotationList,
          useDisplayAuthor: true,
        });
        saveAnnotation(
          requestid,
          astr,
          (data) => {
            fetchAnnotationsInfo(requestid, currentLayer.name.toLowerCase(), (error) => {
              console.log("Error:", error);
            });
            setPageSelections([]);
            fetchPageFlag(
              requestid,
              currentLayer.name.toLowerCase(),
              documentList?.map(d => d.documentid),
              (error) => console.log(error)
            );
          },
          (error) => {
            console.log(error);
          },
          currentLayer.redactionlayerid,
          createPageFlagPayload(
            pageFlagSelections,
            currentLayer.redactionlayerid
          )
        );
        annotManager.addAnnotations(sectionAnnotations, { autoFocus: false });

        // Always redraw annotation
        sectionAnnotations.forEach((a) => annotManager.redrawAnnotation(a));
        setNewRedaction(null);
      }
    };

    const getCoordinates = (_annot, _redaction, X) => {
      _annot.PageNumber = _redaction?.getPageNumber();
      _annot.X = X || _redaction.X;
      _annot.Y = _redaction.Y;
      _annot.FontSize = Math.min(parseInt(_redaction.FontSize), 9) + "pt";
      return _annot;
    };

    const editAnnotation = (annotationManager, selectedAnnot) => {
      selectedAnnot.then((astr) => {
        //parse annotation xml
        let jObj = parser.parseFromString(astr); // Assume xmlText contains thesetEditRedacts example XML
        let annots = jObj.getElementsByTagName("annots");
        let annot = annots[0].children[0];
        setEditAnnot({
          pages: annot.attributes.page,
          names: [annot.attributes.name],
          astr: astr,
          type: annot.name,
        });
      });
      setAnnotManager(annotationManager);
    };

    //START: Bulk Edit using Multi Select Option
    const editRedactions = (annotationManager, selectedAnnot) => {
      selectedAnnot.then((astr) => {
        //parse annotation xml
        let jObj = parser.parseFromString(astr); // Assume xmlText contains the example XML
        let annots = jObj.getElementsByTagName("annots");
        setEditRedacts({ annots: annots, astr: astr });
      });

      setAnnotManager(annotationManager);
    };

    useEffect(() => {
      if (editRedacts) {
        setModalOpen(true);
      }
    }, [editRedacts]);

    //END: Bulk Edit using Multi Select Option
    useEffect(() => {
      if (editAnnot) {
        setSelectedSections(
          redactionInfo
            .find(
              (redaction) => redaction.annotationname === editAnnot.names[0]
            )
            .sections?.ids?.map((id) => id)
        );
        setModalOpen(true);
      }
    }, [editAnnot]);

    useEffect(() => {
      while (deleteQueue?.length > 0) {
        let annot = deleteQueue.pop();
        if (annot && !newRedaction?.names.includes(annot.name)) {
          if (annot.type === "redact" && redactionInfo) {
            let i = redactionInfo.findIndex(
              (a) => a.annotationname === annot.name
            );
            if (i >= 0) {
              let childSections = redactionInfo[i].sections?.annotationname;
              let sectionids = redactionInfo[i].sections?.ids;
              if (sectionids) {
                for (let id of sectionids) {
                  sections.find((s) => s.id === id).count--;
                }
              }
              redactionInfo.splice(i, 1);
              annotManager.deleteAnnotation(
                annotManager.getAnnotationById(childSections)
              );
            }
          }
        }
        setNewRedaction(null);
      }
    }, [deleteQueue, newRedaction]);

    const cancelRedaction = () => {
      setModalOpen(false);
      setMessageModalOpen(false);
      setSelectedPageFlagId(null);
      setSelectedSections([]);
      setSaveDisabled(true);
      setPageSelections([]);
      if (newRedaction != null) {
        let astr = parser.parseFromString(newRedaction.astr, "text/xml");
        for (const node of astr.getElementsByTagName("annots")[0].children) {
          annotManager.deleteAnnotation(
            annotManager.getAnnotationById(node.attributes.name),
            {
              imported: true,
              force: true,
              source: "cancelRedaction",
            }
          );
        }
      }
      setEditAnnot(null);
    };

    const saveDefaultSections = () => {
      setModalOpen(false);
      setDefaultSections(selectedSections);
      if (editAnnot || editRedacts) {
        // saving default sections for new redaction will be handled by the useEffect below
        saveRedaction();
      }
    };

    const clearDefaultSections = () => {
      setDefaultSections([]);
    };

    const setMessageModalForNotResponsive = () => {
      setModalTitle("Not Responsive Default");
          setModalMessage(
          <div>You have 'Not Responsive' selected as a default section.
            <ul>
              <li className="modal-message-list-item">To flag this page as 'Withheld in Full', remove the default section.</li>
              <li className="modal-message-list-item">To flag this full page as 'Not Responsive', use the 'Not Responsive' page flag.</li>
            </ul>
          </div>);
          setMessageModalOpen(true)
    }

    useEffect(() => {
      if (newRedaction) {
        let hasFullPageRedaction = decodeAstr(newRedaction?.astr)['trn-redaction-type'] === "fullPage" || false
        if (newRedaction.names?.length > REDACTION_SELECT_LIMIT) {
          setWarningModalOpen(true);
          cancelRedaction();
        } else if (defaultSections.length > 0 && !defaultSections.includes(26)) {
          saveRedaction();
        } else if (defaultSections.length == 0 && !hasFullPageRedaction) {
          setModalOpen(true);
        } else if (selectedPageFlagId === pageFlagTypes["Withheld in Full"] && defaultSections.length > 0) {
          setMessageModalForNotResponsive();
        } else if (hasFullPageRedaction) {
          if (defaultSections.length != 0) setMessageModalForNotResponsive();
          setModalOpen(true)
        } else if (defaultSections.includes(26) && selectedPageFlagId != pageFlagTypes["Withheld in Full"]) {
          saveRedaction();
        } else {
          setModalOpen(true);
        }
      }
    }, [defaultSections, newRedaction]);

    const handleSectionSelected = (e) => {
      let sectionID = e.target.getAttribute("data-sectionid");
      let newSelectedSections;
      if (e.target.checked) {
        newSelectedSections = [...selectedSections, Number(sectionID)];
      } else {
        newSelectedSections = selectedSections.filter(
          (s) => s !== Number(sectionID)
        );
      }
      setSelectedSections(newSelectedSections);
      setSaveDisabled(
        newSelectedSections.length === 0 ||
          _.isEqual(
            redactionInfo.find(
              (redaction) => redaction.annotationname === editAnnot?.name
            )?.sections.ids,
            newSelectedSections
          )
      );
    };

    const AntSwitch = styled(Switch)(({ theme }) => ({
      width: 28,
      height: 16,
      padding: 0,
      display: "flex",
      "&:active": {
        "& .MuiSwitch-thumb": {
          width: 15,
        },
        "& .MuiSwitch-switchBase.Mui-checked": {
          transform: "translateX(9px)",
        },
      },
      "& .MuiSwitch-switchBase": {
        padding: 2,
        "&.Mui-checked": {
          transform: "translateX(12px)",
          color: "#fff",
          "& + .MuiSwitch-track": {
            opacity: 1,
            backgroundColor:
              theme.palette.mode === "dark" ? "#177ddc" : "#38598a",
          },
        },
      },
      "& .MuiSwitch-thumb": {
        boxShadow: "0 2px 4px 0 rgb(0 35 11 / 20%)",
        width: 12,
        height: 12,
        borderRadius: 6,
        transition: theme.transitions.create(["width"], {
          duration: 200,
        }),
      },
      "& .MuiSwitch-track": {
        borderRadius: 16 / 2,
        opacity: 1,
        backgroundColor: theme.palette.mode === "dark" ? "#177ddc" : "#38598a",
        boxSizing: "border-box",
      },
    }));

    const changeModalSort = (e) => {
      setModalSortNumbered(e.target.checked);
    };

    const changeSortOrder = (e) => {
      if (modalSortNumbered) {
        setModalSortAsc(!modalSortAsc);
      }
    };

    const normalizeforPdfStitchingReq = (documentlist) => {
      const normalizedDocumentlist = JSON.parse(JSON.stringify(documentlist));
      for (let divsionentry of normalizedDocumentlist) {
        for (let docentry of divsionentry["documentlist"]) {
          if (docentry["pageFlag"]) {
            delete docentry["pageFlag"];
          }
        }
      }
      return normalizedDocumentlist;
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
    
    const saveDoc = () => {
      console.log("savedoc");
      console.log("MODAL", modalFor)
      setRedlineModalOpen(false);
      setRedlineSaving(true);
      setRedlineCategory(modalFor);
      // skip deletePages API call for all removePages related to Redline/Response package creation
      setSkipDeletePages(true);
      switch (modalFor) {
        case "oipcreview":
        case "redline":
          saveRedlineDocument(
            modalFor,
            incompatibleFiles,
            documentList,
            pageMappedDocs
          );
          break;
        case "responsepackage":
          saveResponsePackage(
            docViewer,
            annotManager,
            docInstance,
            documentList,
            pageMappedDocs
          );
          break;
        default:
      }
      setIncludeDuplicatePages(false);
      setIncludeNRPages(false);
    };

    const compareValues = (a, b) => {
      if (modalSortNumbered) {
        if (modalSortAsc) {
          return a.id - b.id;
        } else {
          return b.id - a.id;
        }
      } else {
        return b.count - a.count;
      }
    };
    const decodeAstr = (astr) => {
      const parser = new DOMParser()
      const xmlDoc = parser.parseFromString(astr, "text/xml")
      const trnCustomDataXml = xmlDoc.getElementsByTagName("trn-custom-data");
      const trnCustomDataJsonString = trnCustomDataXml[0].attributes[0].value
      const trnCustomData = JSON.parse(trnCustomDataJsonString)
      return trnCustomData
    }

    const sectionIsDisabled = (sectionid) => {
      let isDisabled = false;
      let hasFullPageRedaction = false;
      if (newRedaction) hasFullPageRedaction = decodeAstr(newRedaction.astr)['trn-redaction-type'] === "fullPage"
      // For sections
      if (selectedSections.length > 0 && !selectedSections.includes(25) && !selectedSections.includes(26)) {
        isDisabled = (sectionid === 25 || sectionid === 26)
      // For Blank Code
      } else if (selectedSections.length > 0 && selectedSections.includes(25)) {
        isDisabled = sectionid !== 25
      } else if (hasFullPageRedaction) {
        isDisabled = sectionid == 26
      // For Not Responsive
      } else if (selectedSections.length > 0 && selectedSections.includes(26)) {
        isDisabled = sectionid !== 26
      } else if (selectedPageFlagId === pageFlagTypes["Withheld in Full"] && selectedSections?.length === 0) {
        isDisabled = sectionid == 26
      } else if (editAnnot) {
        const trnCustomData = decodeAstr(editAnnot.astr)
        const isFullPage = trnCustomData['trn-redaction-type'] === "fullPage"
        isDisabled = isFullPage && sectionid == 26
      } else if (editRedacts) {
        let hasFullPageRedaction = false;
        for (let annot of editRedacts.annots[0].children) {
          const trnCustomDataJsonString = annot.children[0].attributes.bytes
          const decodedJsonString = trnCustomDataJsonString.replace(/&quot;/g, '"');
          const trnCustomData = JSON.parse(decodedJsonString)
          if (trnCustomData['trn-redaction-type'] == 'fullPage') {
            hasFullPageRedaction = true;
          }
        }
        isDisabled = hasFullPageRedaction && sectionid == 26
      }
      return isDisabled
    }

    return (
      <div>
        <div className="webviewer" ref={viewer}></div>
        <ReactModal
          initWidth={650}
          initHeight={700}
          minWidth={400}
          minHeight={200}
          className={"state-change-dialog"}
          onRequestClose={cancelRedaction}
          isOpen={modalOpen}
        >
          <DialogTitle disableTypography id="state-change-dialog-title">
            <h2 className="state-change-header">FOIPPA Sections</h2>
            <IconButton className="title-col3" onClick={cancelRedaction}>
              <i className="dialog-close-button">Close</i>
              <CloseIcon />
            </IconButton>
          </DialogTitle>
          <DialogContent className={"dialog-content-nomargin"}>
            <DialogContentText
              id="state-change-dialog-description"
              component={"span"}
            >
              <Stack direction="row-reverse" spacing={1} alignItems="center">
                <button
                  onClick={changeSortOrder}
                  style={{
                    border: "none",
                    backgroundColor: "white",
                    padding: 0,
                  }}
                  disabled={!modalSortNumbered}
                >
                  {modalSortAsc ? (
                    <FontAwesomeIcon
                      icon={faArrowUp}
                      size="1x"
                      color="#666666"
                    />
                  ) : (
                    <FontAwesomeIcon
                      icon={faArrowDown}
                      size="1x"
                      color="#666666"
                    />
                  )}
                </button>
                <Typography>Numbered Order</Typography>
                <AntSwitch
                  onChange={changeModalSort}
                  checked={modalSortNumbered}
                  inputProps={{ "aria-label": "ant design" }}
                />
                <Typography>Most Used</Typography>
              </Stack>
              <div style={{ overflowY: "scroll" }}>
                <List className="section-list">
                  {sections?.sort(compareValues).map((section, index) => (
                    <ListItem key={"list-item" + section.id}>
                      <input
                        type="checkbox"
                        className="section-checkbox"
                        key={"section-checkbox" + section.id}
                        id={"section" + section.id}
                        data-sectionid={section.id}
                        onChange={handleSectionSelected}
                        disabled={sectionIsDisabled(section.id)}
                        defaultChecked={selectedSections.includes(section.id)}
                      />
                      <label
                        key={"list-label" + section.id}
                        className="check-item"
                      >
                        {section.section + " - " + section.description}
                      </label>
                    </ListItem>
                  ))}
                </List>
              </div>
              {/* <span className="confirmation-message">
                  Are you sure you want to delete the attachments from this request? <br></br>
                  <i>This will remove all attachments from the redaction app.</i>
                </span> */}
            </DialogContentText>
          </DialogContent>
          <DialogActions className="foippa-modal-actions">
            <button
              className={`btn-bottom btn-save btn`}
              onClick={editRedacts ? saveRedactions : saveRedaction}
              disabled={saveDisabled}
            >
              Select Code(s)
            </button>
            {defaultSections.length > 0 ? (
              <button
                className="btn-bottom btn-cancel"
                onClick={clearDefaultSections}
              >
                Clear Defaults
              </button>
            ) : (
              <button
                className={`btn-bottom btn-cancel ${
                  saveDisabled && "btn-disabled"
                }`}
                onClick={saveDefaultSections}
                disabled={saveDisabled}
              >
                Save as Default
              </button>
            )}
            <button className="btn-bottom btn-cancel" onClick={cancelRedaction}>
              Cancel
            </button>
          </DialogActions>
        </ReactModal>
        <ReactModal
          initWidth={800}
          initHeight={300}
          minWidth={600}
          minHeight={250}
          className={"state-change-dialog" + (modalFor == "redline"?" redline-modal":"")}
          onRequestClose={cancelRedaction}
          isOpen={redlineModalOpen}
        >
          <DialogTitle disableTypography id="state-change-dialog-title">
            <h2 className="state-change-header">{modalTitle}</h2>
            <IconButton className="title-col3" onClick={cancelSaveRedlineDoc}>
              <i className="dialog-close-button">Close</i>
              <CloseIcon />
            </IconButton>
          </DialogTitle>
          <DialogContent className={"dialog-content-nomargin"}>
            <DialogContentText
              id="state-change-dialog-description"
              component={"span"}
            >
              <span>
                {modalMessage} <br/><br/>
                {modalFor == "redline" && <>
                <input
                  type="checkbox"
                  style={{ marginRight: 10 }}
                  className="redline-checkmark"
                  id="nr-checkbox"
                  checked={includeNRPages}
                  onChange={handleIncludeNRPages}
                  disabled={isDisableNRDuplicate}
                />
                <label for="nr-checkbox">Include NR pages</label>
                <br/>
                <input
                  type="checkbox"
                  style={{ marginRight: 10 }}
                  className="redline-checkmark"
                  id="duplicate-checkbox"
                  checked={includeDuplicatePages}
                  onChange={handleIncludeDuplicantePages}
                  disabled={isDisableNRDuplicate}
                />
                <label for="duplicate-checkbox">Include Duplicate pages</label>
                </>}
              </span>
            </DialogContentText>
          </DialogContent>
          <DialogActions className="foippa-modal-actions">
            <button className="btn-bottom btn-save btn" onClick={saveDoc}>
              {modalButtonLabel}
            </button>
            <button
              className="btn-bottom btn-cancel"
              onClick={cancelSaveRedlineDoc}
            >
              Cancel
            </button>
          </DialogActions>
        </ReactModal>
        <ReactModal
          initWidth={800}
          initHeight={300}
          minWidth={600}
          minHeight={250}
          className={"state-change-dialog"}
          onRequestClose={cancelRedaction}
          isOpen={messageModalOpen}
        >
          <DialogTitle disableTypography id="state-change-dialog-title">
            <h2 className="state-change-header">{modalTitle}</h2>
            <IconButton className="title-col3" onClick={cancelRedaction}>
              <i className="dialog-close-button">Close</i>
              <CloseIcon />
            </IconButton>
          </DialogTitle>
          <DialogContent className={"dialog-content-nomargin"}>
            <DialogContentText
              id="state-change-dialog-description"
              component={"span"}
            >
              <span className="confirmation-message">
                {modalMessage} <br></br>
              </span>
            </DialogContentText>
          </DialogContent>
          <DialogActions className="foippa-modal-actions">
            <button
              className="btn-bottom btn-cancel"
              onClick={cancelRedaction}
            >
              Cancel
            </button>
          </DialogActions>
        </ReactModal>
      </div>
    );
  }
);

export default Redlining;
