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
import { useDispatch, useSelector } from "react-redux";
import WebViewer from "@pdftron/webviewer";
import XMLParser from "react-xml-parser";
import ReactModal from "react-modal-resizable-draggable";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import CloseIcon from "@mui/icons-material/Close";
import IconButton from "@mui/material/IconButton";
import Switch, { SwitchProps } from "@mui/material/Switch";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { ReactComponent as EditLogo } from "../../../assets/images/icon-pencil-line.svg";
import {
  fetchAnnotationsByPagination,
  fetchAnnotationsInfo,
  saveAnnotation,
  deleteRedaction,
  deleteAnnotation,
  fetchSections,
  fetchPageFlag,
  fetchKeywordsMasterData,
  fetchPDFTronLicense,
  triggerDownloadRedlines,
  triggerDownloadFinalPackage,
} from "../../../apiManager/services/docReviewerService";
import {
  getFOIS3DocumentRedlinePreSignedUrl,
  saveFilesinS3,
  getResponsePackagePreSignedUrl,
} from "../../../apiManager/services/foiOSSService";
import {
  PDFVIEWER_DISABLED_FEATURES,
  ANNOTATION_PAGE_SIZE,
  REDACTION_SELECT_LIMIT,
} from "../../../constants/constants";
import { errorToast } from "../../../helper/helper";
import { faArrowUp, faArrowDown } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { useAppSelector } from "../../../hooks/hook";
import { toast } from "react-toastify";
import { pageFlagTypes, RequestStates } from "../../../constants/enum";
import {
  getStitchedPageNoFromOriginal,
  createPageFlagPayload,
  sortByLastModified,
  createRedactionSectionsString,
  getSections,
  getValidSections,
  updatePageFlags,
} from "./utils";
import { Edit, MultiSelectEdit } from "./Edit";
import _, { forEach } from "lodash";

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
    },
    ref
  ) => {
    // to enable save final package button - request status needs to be 14 (Response)
    const requestStatus = useAppSelector(
      (state) => state.documents?.requeststatus
    );

    const requestnumber = useAppSelector(
      (state) => state.documents?.requestnumber
    );

    const pageFlags = useAppSelector((state) => state.documents?.pageFlags);
    const redactionInfo = useSelector(
      (state) => state.documents?.redactionInfo
    );
    const sections = useSelector((state) => state.documents?.sections);
    const currentLayer = useSelector((state) => state.documents?.currentLayer);

    const viewer = useRef(null);
    const saveButton = useRef(null);

    const documentList = useAppSelector(
      (state) => state.documents?.documentList
    );

    const [docViewer, setDocViewer] = useState(null);
    const [annotManager, setAnnotManager] = useState(null);
    const [annots, setAnnots] = useState(null);
    const [docViewerMath, setDocViewerMath] = useState(null);
    const [docInstance, setDocInstance] = useState(null);
    const [modalOpen, setModalOpen] = useState(false);
    const [redlineModalOpen, setRedlineModalOpen] = useState(false);
    const [newRedaction, setNewRedaction] = useState(null);
    const [deleteQueue, setDeleteQueue] = useState([]);
    const [selectedSections, setSelectedSections] = useState([]);
    const [defaultSections, setDefaultSections] = useState([]);
    const [editAnnot, setEditAnnot] = useState(null);
    const [saveDisabled, setSaveDisabled] = useState(true);
    const [redactionType, setRedactionType] = useState(null);
    const [pageSelections, setPageSelections] = useState([]);
    const [modalSortNumbered, setModalSortNumbered] = useState(false);
    const [modalSortAsc, setModalSortAsc] = useState(true);
    const [fetchAnnotResponse, setFetchAnnotResponse] = useState(false);
    const [merge, setMerge] = useState(false);
    const [searchKeywords, setSearchKeywords] = useState("");
    const [iframeDocument, setIframeDocument] = useState(null);
    const [modalFor, setModalFor] = useState("");
    const [modalTitle, setModalTitle] = useState("");
    const [modalMessage, setModalMessage] = useState([""]);
    const [modalButtonLabel, setModalButtonLabel] = useState("");
    const [redlineSaving, setRedlineSaving] = useState(false);

    // State variables for Bulk Edit using Multi Selection option
    const [editRedacts, setEditRedacts] = useState(null);
    const [multiSelectFooter, setMultiSelectFooter] = useState(null);
    const [enableMultiSelect, setEnableMultiSelect] = useState(false);
    const [errorMessage, setErrorMessage] = useState(null);

    //xml parser
    const parser = new XMLParser();

    const isReadyForSignOff = () => {
      let pageFlagArray = [];
      let stopLoop = false;

      if (
        documentList.length > 0 &&
        documentList.length === pageFlags?.length
      ) {
        documentList.every((docInfo) => {
          if (pageFlags?.length > 0) {
            pageFlags.every((pageFlagInfo) => {
              if (docInfo.documentid == pageFlagInfo?.documentid) {
                if (docInfo.pagecount > pageFlagInfo.pageflag.length) {
                  // not all page has flag set
                  stopLoop = true;
                  return false; //stop loop
                } else {
                  // artial Disclosure, Full Disclosure, Withheld in Full, Duplicate, Not Responsive
                  pageFlagArray = pageFlagInfo.pageflag?.filter((flag) =>
                    [
                      pageFlagTypes["Partial Disclosure"],
                      pageFlagTypes["Full Disclosure"],
                      pageFlagTypes["Withheld in Full"],
                      pageFlagTypes["Duplicate"],
                      pageFlagTypes["Not Responsive"],
                    ].includes(flag.flagid)
                  );
                  if (pageFlagArray.length != pageFlagInfo.pageflag.length) {
                    stopLoop = true;
                    return false; //stop loop
                  }
                }
              }
              return true; //continue loop
            });
          } else {
            stopLoop = true;
          }

          if (stopLoop) return false; //stop loop

          return true; //continue loop
        });
      } else {
        return false;
      }

      return !stopLoop;
    };
    const [enableSavingRedline, setEnableSavingRedline] = useState(
      isReadyForSignOff() &&
        [
          RequestStates["Records Review"],
          RequestStates["Ministry Sign Off"],
          RequestStates["Peer Review"],
        ].includes(requestStatus)
    );
    const [enableSavingFinal, setEnableSavingFinal] = useState(
      isReadyForSignOff() && requestStatus == RequestStates["Response"]
    );

    // const [storedannotations, setstoreannotations] = useState(localStorage.getItem("storedannotations") || [])
    // if using a class, equivalent of componentDidMount
    useEffect(() => {
      let initializeWebViewer = async () => {
        let currentDocumentS3Url = currentDocument?.currentDocumentS3Url;
        fetchSections(requestid, (error) => console.log(error));
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
            disableVirtualDisplayMode: true,
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
            Search,
            Math,
            createDocument,
          } = instance.Core;
          instance.UI.disableElements(PDFVIEWER_DISABLED_FEATURES.split(","));
          instance.UI.enableElements(["attachmentPanelButton"]);
          documentViewer.setToolMode(
            documentViewer.getTool(instance.Core.Tools.ToolNames.REDACTION)
          );
          //customize header - insert a dropdown button
          const document = instance.UI.iframeWindow.document;
          setIframeDocument(document);
          instance.UI.setHeaderItems((header) => {
            const parent = documentViewer.getScrollViewElement().parentElement;

            const menu = document.createElement("div");
            menu.classList.add("Overlay");
            menu.classList.add("FlyoutMenu");
            menu.id = "saving_menu";

            const redlineForSignOffBtn = document.createElement("button");
            redlineForSignOffBtn.textContent = "Redline for Sign Off";
            redlineForSignOffBtn.id = "redline_for_sign_off";
            redlineForSignOffBtn.className = "redline_for_sign_off";
            redlineForSignOffBtn.style.backgroundColor = "transparent";
            redlineForSignOffBtn.style.border = "none";
            redlineForSignOffBtn.style.padding = "8px 8px 8px 10px";
            redlineForSignOffBtn.style.cursor = "pointer";
            redlineForSignOffBtn.style.alignItems = "left";
            redlineForSignOffBtn.disabled = !enableSavingRedline;
            // redlineForSignOffBtn.style.color = '#069';

            redlineForSignOffBtn.onclick = () => {
              // Save to s3
              setModalFor("redline");
              setModalTitle("Redline for Sign Off");
              setModalMessage([
                "Are you sure want to create the redline PDF for ministry sign off?",
                <br />,
                <br />,
                <span>
                  When you create the redline PDF, your web browser page will
                  automatically refresh
                </span>,
              ]);
              setModalButtonLabel("Create Redline PDF");
              setRedlineModalOpen(true);
            };

            menu.appendChild(redlineForSignOffBtn);

            const finalPackageBtn = document.createElement("button");
            finalPackageBtn.textContent = "Final Package for Applicant";
            finalPackageBtn.id = "final_package";
            finalPackageBtn.className = "final_package";
            finalPackageBtn.style.backgroundColor = "transparent";
            finalPackageBtn.style.border = "none";
            finalPackageBtn.style.padding = "8px 8px 8px 10px";
            finalPackageBtn.style.cursor = "pointer";
            finalPackageBtn.style.alignItems = "left";
            // finalPackageBtn.style.color = '#069';
            finalPackageBtn.disabled = !enableSavingFinal;

            finalPackageBtn.onclick = () => {
              // Download
              // console.log("Response Package for Application");
              setModalFor("responsepackage");
              setModalTitle("Create Package for Applicant");
              setModalMessage([
                "This should only be done when all redactions are finalized and ready to ",
                <b>
                  <i>be</i>
                </b>,
                " sent to the ",
                <b>
                  <i>Applicant</i>
                </b>,
                ". This will ",
                <b>
                  <i>permanently</i>
                </b>,
                " apply the redactions and automatically create page stamps.",
              ]);
              setModalButtonLabel("Create Applicant Package");
              setRedlineModalOpen(true);
              // saveResponsePackage(documentViewer, annotationManager);
            };

            menu.appendChild(finalPackageBtn);

            const renderCustomMenu = () => {
              const menuBtn = document.createElement("button");
              menuBtn.textContent = "Create Response PDF";
              menuBtn.id = "create_response_pdf";

              menu.style.right = "auto";
              menu.style.top = "30px";
              menu.style.minWidth = "200px";
              menu.padding = "0px";
              menu.style.display = "none";
              parent.appendChild(menu);

              menuBtn.onclick = async () => {
                if (menu.style.display == "flex") {
                  menu.style.display = "none";
                } else {
                  menu.style.left = `${
                    document.body.clientWidth - (menuBtn.clientWidth + 96)
                  }px`;
                  menu.style.display = "flex";
                }
              };

              return menuBtn;
            };

            const newCustomElement = {
              type: "customElement",
              render: renderCustomMenu,
            };

            // header.push(newCustomElement);
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
          documentViewer.addEventListener("documentLoaded", async () => {
            PDFNet.initialize(); // Only needs to be initialized once
            //Commenting the preset search code now- might need in later release
            // fetchKeywordsMasterData(
            //   (data) => {
            //     if (data) {
            //       let keywordArray = data.map((elmnt) => elmnt.keyword);
            //       var regexFromMyArray = new String(keywordArray.join("|"));
            //       setSearchKeywords(regexFromMyArray);
            //       instance.UI.searchTextFull(regexFromMyArray, {
            //         wholeWord: true,
            //         regex: true,
            //       });
            //     }
            //   },
            //   (error) => console.log(error)
            // );
            //update user info
            let newusername = user?.name || user?.preferred_username || "";
            let username = annotationManager.getCurrentUser();
            if (newusername && newusername !== username)
              annotationManager.setCurrentUser(newusername);

            //update isloaded flag
            //localStorage.setItem("isDocumentLoaded", "true");

            //let crrntDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
            let localDocumentInfo = currentDocument;
            if (Object.entries(individualDoc["file"])?.length <= 0)
              individualDoc = localDocumentInfo;

            fetchAnnotationsInfo(requestid, (error) => {
              console.log("Error:", error);
            });

            setDocViewer(documentViewer);
            setAnnotManager(annotationManager);
            setAnnots(Annotations);
            setDocViewerMath(Math);
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

    useEffect(() => {
      const changeLayer = async () => {
        if (currentLayer) {
          if (currentLayer.name.toLowerCase() === "response package") {
            // Manually create white boxes to simulate redaction because apply redaction is permanent

            const existingAnnotations = annotManager.getAnnotationsList();
            const redactions = existingAnnotations.filter(
              (a) => a.Subject === "Redact"
            );
            var rects = [];
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
            // await annotManager.deleteAnnotations(redactions, {
            //   imported: true,
            //   force: true,
            //   source: "layerchange",
            // });
            var newAnnots = [];
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
              currentLayer.name,
              1,
              ANNOTATION_PAGE_SIZE,
              async (data) => {
                let meta = data["meta"];
                if (!fetchAnnotResponse) {
                  setMerge(true);
                  setFetchAnnotResponse(data);
                } else {
                  annotManager.disableReadOnlyMode();
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
              }
            );
            fetchPageFlag(requestid, currentLayer.redactionlayerid, (error) =>
              console.log(error)
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

    const annotationChangedHandler = useCallback(
      (annotations, action, info) => {
        // If the event is triggered by importing then it can be ignored
        // This will happen when importing the initial annotations
        // from the server or individual changes from other users

        if (info.source !== "redactionApplied") {
          //ignore annots/redact changes made by applyRedaction
          if (info.imported) return;
          //do not run if redline is saving
          if (redlineSaving) return;
          if (currentLayer.name.toLowerCase() === "response package") return;
          let localDocumentInfo = currentDocument;
          annotations.forEach((annot) => {
            let displayedDoc =
              pageMappedDocs.stitchedPageLookup[annot.getPageNumber()];
            let individualPageNo = displayedDoc.page;
            annot.setCustomData("originalPageNo", `${individualPageNo - 1}`);
          });
          let _annotationtring =
            docInstance.Core.annotationManager.exportAnnotations({
              annotationList: annotations,
              useDisplayAuthor: true,
            });
          _annotationtring.then(async (astr) => {
            //parse annotation xml
            let jObj = parser.parseFromString(astr); // Assume xmlText contains the example XML
            let annots = jObj.getElementsByTagName("annots");
            setRedactionType(annotations[0]?.type);
            if (annotations[0].IsText) {
              annotManager.deleteAnnotation(
                annotManager.getAnnotationById(annotations[0].Id)
              );
              return;
            }
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
                  let individualPageNo = displayedDoc.page;
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
                  (data) => {},
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
                      currentLayer.redactionlayerid,
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
                    if (!!_selectedAnnotations) {
                      parentRedaction = allAnnotations?.find(
                        (r) =>
                          r.Subject === "Redact" &&
                          r.InReplyTo === _selectedAnnotations?.Id
                      );
                    }
                    if (!!parentRedaction) {
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
                  annot.NoMove = true;
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
                  (data) => {},
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
                newRedaction.astr.includes(annotations[0].Id) // if we are grouping the newly created annotations do not save
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
                      fetchPageFlag(
                        requestid,
                        currentLayer.redactionlayerid,
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
                        currentLayer.redactionlayerid,
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
              console.log("reached max - deselect");
              annotManager?.deselectAnnotations(annotations);
              setWarningModalOpen(true);
            }
          }
          // else if (action === 'deselected') {
          //   console.log('annotation deselection');
          // }

          // console.log('annotation list', annotations);
          // console.log('full annotation list', annotManager?.getSelectedAnnotations());

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
    ]);

    useImperativeHandle(ref, () => ({
      addFullPageRedaction(pageNumbers) {
        var newAnnots = [];
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

    const checkSavingRedlineButton = (_instance) => {
      let _enableSavingRedline = isReadyForSignOff();

      setEnableSavingRedline(
        _enableSavingRedline &&
          [
            RequestStates["Records Review"],
            RequestStates["Ministry Sign Off"],
            RequestStates["Peer Review"],
          ].includes(requestStatus)
      );
      setEnableSavingFinal(
        _enableSavingRedline && requestStatus == RequestStates["Response"]
      );
      if (_instance) {
        const document = _instance.UI.iframeWindow.document;
        document.getElementById("redline_for_sign_off").disabled =
          !_enableSavingRedline ||
          ![
            RequestStates["Records Review"],
            RequestStates["Ministry Sign Off"],
            RequestStates["Peer Review"],
          ].includes(requestStatus);
        document.getElementById("final_package").disabled =
          !_enableSavingRedline || requestStatus !== RequestStates["Response"];
      }
    };

    useEffect(() => {
      checkSavingRedlineButton(docInstance);
    }, [pageFlags, isStitchingLoaded]);

    const stitchDocumentsFunc = async (doc) => {
      let docCopy = [...docsForStitcing];
      let removedFirstElement = docCopy?.shift();
      let mappedDocs = { stitchedPageLookup: {}, docIdLookup: {} };
      let mappedDoc = { docId: 0, version: 0, division: "", pageMappings: [] };
      let domParser = new DOMParser();
      for (let i = 0; i < removedFirstElement.file.pagecount; i++) {
        let firstDocMappings = { pageNo: i + 1, stitchedPageNo: i + 1 };
        mappedDocs["stitchedPageLookup"][i + 1] = {
          docid: removedFirstElement.file.documentid,
          docversion: removedFirstElement.file.version,
          page: i + 1,
        };
        mappedDoc.pageMappings.push(firstDocMappings);
      }
      mappedDocs["docIdLookup"][removedFirstElement.file.documentid] = {
        docId: removedFirstElement.file.documentid,
        version: removedFirstElement.file.version,
        division: removedFirstElement.file.divisions[0].divisionid,
        pageMappings: mappedDoc.pageMappings,
      };

      for (let file of docCopy) {
        mappedDoc = {
          docId: 0,
          version: 0,
          division: "",
          pageMappings: [{ pageNo: 0, stitchedPageNo: 0 }],
        };

        let newDoc = await docInstance.Core.createDocument(
          file.s3url,
          { loadAsPDF: true } /* , license key here */
        );
        const pages = [];
        mappedDoc = { pageMappings: [] };
        let stitchedPageNo = 0;
        for (let i = 0; i < newDoc.getPageCount(); i++) {
          pages.push(i + 1);
          let pageNo = i + 1;
          stitchedPageNo = doc.getPageCount() + (i + 1);
          if (stitchedPageNo > 61) {
            //console.log("here");
          }
          let pageMappings = {
            pageNo: pageNo,
            stitchedPageNo: stitchedPageNo,
          };
          mappedDoc.pageMappings.push(pageMappings);
          mappedDocs["stitchedPageLookup"][stitchedPageNo] = {
            docid: file.file.documentid,
            docversion: file.file.version,
            page: pageNo,
          };
        }
        // Insert (merge) pages
        await doc.insertPages(newDoc, pages);
        mappedDocs["docIdLookup"][file.file.documentid] = {
          docId: file.file.documentid,
          version: file.file.version,
          division: file.file.divisions[0].divisionid,
          pageMappings: mappedDoc.pageMappings,
        };
      }
      setPageMappedDocs(mappedDocs);
      setIsStitchingLoaded(true);
      if (fetchAnnotResponse) {
        assignAnnotationsPagination(
          mappedDocs,
          fetchAnnotResponse["data"],
          domParser
        );
        let meta = fetchAnnotResponse["meta"];
        if (meta["has_next"] === true) {
          fetchandApplyAnnotations(
            mappedDocs,
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
          currentLayer.name,
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
          }
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
          _annotation.NoMove = true;
          if (_annotation.Subject === "Redact") {
            _annotation.IsHoverable = false;

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
      if (docsForStitcing.length > 0 && merge && docViewer) {
        const doc = docViewer.getDocument();
        stitchDocumentsFunc(doc);
      }
    }, [docsForStitcing, fetchAnnotResponse, docViewer]);

    useEffect(() => {
      //update user name
      let newusername = user?.name || user?.preferred_username || "";
      let username = docViewer?.getAnnotationManager()?.getCurrentUser();
      if (newusername !== username)
        docViewer?.getAnnotationManager()?.setCurrentUser(newusername);
    }, [user]);

    useEffect(() => {
      docViewer?.displayPageLocation(individualDoc["page"], 0, 0);
    }, [individualDoc]);

    //START: Save updated redactions to BE part of Bulk Edit using Multi Select Option
    const saveRedactions = () => {
      setModalOpen(false);
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
          Math.min(parseInt(_redact.FontSize), 12) + "pt";
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
        const doc = docViewer.getDocument();
        let pageNumber = parseInt(node.attributes.page) + 1;

        const pageInfo = doc.getPageInfo(pageNumber);
        const pageMatrix = doc.getPageMatrix(pageNumber);
        const pageRotation = doc.getPageRotation(pageNumber);
        childAnnotation.fitText(pageInfo, pageMatrix, pageRotation);
        var rect = childAnnotation.getRect();
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
            setPageSelections([]);
            fetchPageFlag(requestid, currentLayer.redactionlayerid, (error) =>
              console.log(error)
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
      setSaveDisabled(true);
      let redactionObj = getRedactionObj(newRedaction, editAnnot, _resizeAnnot); //newRedaction? newRedaction:  (editAnnot ? editAnnot :_resizeAnnot);
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
            let jObj = parser.parseFromString(astr); // Assume xmlText contains the example XML
            let annots = jObj.getElementsByTagName("annots");
            let annot = annots[0].children[0];
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
                  setPageSelections([]);
                  fetchPageFlag(
                    requestid,
                    currentLayer.redactionlayerid,
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
              // redactionInfo.find(
              //   (r) => r.annotationname === redactionObj.name
              // ).sections.ids = redactionSectionsIds;
            }
            setEditAnnot(null);
          });
        }
      } else {
        var pageFlagSelections = pageSelections;
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
        var sectionAnnotations = [];
        let annotationsToDelete = [];
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
          var rect = annot.getRect();
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
        // annotManager.deleteAnnotations(annotationsToDelete, {
        //     force: true,
        //   });
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
            setPageSelections([]);
            fetchPageFlag(requestid, currentLayer.redactionlayerid, (error) =>
              console.log(error)
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
      _annot.FontSize = Math.min(parseInt(_redaction.FontSize), 12) + "pt";
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
          let stitchedPageNo = Number(annot.page) + 1;
          let displayedDoc = pageMappedDocs.stitchedPageLookup[stitchedPageNo];

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
      setSelectedSections([]);
      setSaveDisabled(true);
      if (newRedaction != null) {
        let astr = parser.parseFromString(newRedaction.astr, "text/xml");
        for (const node of astr.getElementsByTagName("annots")[0].children) {
          annotManager.deleteAnnotation(
            annotManager.getAnnotationById(node.attributes.name)
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

    useEffect(() => {
      if (newRedaction) {
        if (newRedaction.names?.length > REDACTION_SELECT_LIMIT) {
          setWarningModalOpen(true);
          cancelRedaction();
        } else {
          if (defaultSections.length > 0) {
            saveRedaction();
          } else {
            setModalOpen(true);
          }
        }
      }
    }, [defaultSections, newRedaction]);

    const handleSectionSelected = (e) => {
      let sectionID = e.target.getAttribute("data-sectionid");
      var newSelectedSections;
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

    const prepareMessageForRedlineZipping = (
      divObj,
      divisionCountForToast,
      zipServiceMessage,
      stitchedDocPath = ""
    ) => {
      const zipDocObj = {
        divisionid: divObj.divisionid,
        divisionname: divObj.divisionname,
        files: [],
      };
      if (stitchedDocPath) {
        const stitchedDocPathArray = stitchedDocPath?.split("/");
        let fileName =
          stitchedDocPathArray[stitchedDocPathArray.length - 1].split("?")[0];
        fileName = divObj.divisionname + "/" + decodeURIComponent(fileName);
        const file = {
          filename: fileName,
          s3uripath: decodeURIComponent(stitchedDocPath?.split("?")[0]),
        };
        zipDocObj.files.push(file);
      }
      if (divObj.incompatableList.length > 0) {
        const divIncompatableFiles = divObj.incompatableList
          .filter((record) =>
            record.divisions.some(
              (division) => division.divisionid === divObj.divisionid
            )
          )
          .map((record) => {
            return {
              filename: divObj.divisionname + "/" + record.filename,
              s3uripath: record.filepath,
            };
          });
        zipDocObj.files = [...zipDocObj.files, ...divIncompatableFiles];
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
      divisionsdocpages
    ) => {
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

          await s.stampText(
            doc,
            `${requestnumber} , Page ${
              divisionsdocpages[pagecount - 1].stitchedPageNo
            } of ${docViewer.getPageCount()}`,
            pgSet
          );
        });
      }
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
            await s.setTextAlignment(
              PDFNet.Stamper.TextAlignment.e_align_right
            );
            await s.setAsBackground(false);
            const pgSet = await PDFNet.PageSet.createRange(
              pagecount,
              pagecount
            );

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

    const saveRedlineDocument = (_instance) => {
      let arr = [];
      const divisionFilesList = [...documentList, ...incompatibleFiles];
      const divisions = [
        ...new Map(
          divisionFilesList.reduce(
            (acc, file) => [
              ...acc,
              ...new Map(
                file.divisions.map((division) => [
                  division.divisionid,
                  division,
                ])
              ),
            ],
            arr
          )
        ).values(),
      ];
      const downloadType = "pdf";

      let currentDivisionCount = 0;
      const toastID = toast.loading("Start saving redline...");

      let newDocList = [];
      for (let div of divisions) {
        let divDocList = documentList.filter((doc) =>
          doc.divisions.map((d) => d.divisionid).includes(div.divisionid)
        );
        divDocList = sortByLastModified(divDocList);
        let incompatableList = incompatibleFiles.filter((doc) =>
          doc.divisions.map((d) => d.divisionid).includes(div.divisionid)
        );
        let totalPageCount = 0;
        let totalPagesToRemove = 0;
        for (let doc of divDocList) {
          totalPageCount += doc.pagecount;
          for (let flagInfo of doc.pageFlag) {
            if (
              flagInfo.flagid === pageFlagTypes["Duplicate"] ||
              flagInfo.flagid === pageFlagTypes["Not Responsive"]
            ) {
              totalPagesToRemove++;
            }
          }
        }
        let newDivObj = {
          divisionid: div.divisionid,
          divisionname: div.name,
          documentlist: divDocList,
          incompatableList: incompatableList,
          totalPageCount: totalPageCount,
          totalPagesToRemove: totalPagesToRemove,
        };
        newDocList.push(newDivObj);
      }
      let zipServiceMessage = {
        ministryrequestid: requestid,
        category: "redline",
        attributes: [],
        requestnumber: "",
        bcgovcode: "",
      };

      getFOIS3DocumentRedlinePreSignedUrl(
        requestid,
        newDocList,
        async (res) => {
          let domParser = new DOMParser();
          zipServiceMessage.requestnumber = res.requestnumber;
          zipServiceMessage.bcgovcode = res.bcgovcode;

          const filteredDivDocumentlist = res.divdocumentList.filter(
            (divObj) => divObj.totalPageCount !== divObj.totalPagesToRemove
          );
          const divisionCountForToast = filteredDivDocumentlist.length;
          for (let divObj of filteredDivDocumentlist) {
            let pageMappingsByDivisions = {};

            currentDivisionCount++;
            toast.update(toastID, {
              render: `Generating redline PDF for ${currentDivisionCount} of ${divisionCountForToast} divisions...`,
              isLoading: true,
            });

            let stitchedDocObj = null;
            let stitchedDocPath = divObj.s3path_save;
            let stitchedXMLArray = [];

            let docCount = 0;
            let totalPageCount = 0;
            let totalPageCountIncludeRemoved = 0;
            let pagesToRemove = []; //for each stitched division pdf
            if (!stitchedDocPath) {
              prepareMessageForRedlineZipping(
                divObj,
                divisionCountForToast,
                zipServiceMessage,
                stitchedDocPath
              );
            }
            for (let doc of divObj.documentlist) {
              docCount++;
              pageMappingsByDivisions[doc.documentid] = {};
              let pagesToRemoveEachDoc = [];

              //gather pages that need to be removed
              doc.pageFlag.sort((a, b) => a.page - b.page); //sort pageflag by page #
              for (const flagInfo of doc.pageFlag) {
                if (
                  flagInfo.flagid === pageFlagTypes["Duplicate"] ||
                  flagInfo.flagid === pageFlagTypes["Not Responsive"]
                ) {
                  pagesToRemoveEachDoc.push(flagInfo.page);
                  pagesToRemove.push(
                    flagInfo.page + totalPageCountIncludeRemoved
                  );
                } else {
                  pageMappingsByDivisions[doc.documentid][flagInfo.page] =
                    flagInfo.page +
                    totalPageCount -
                    pagesToRemoveEachDoc.length;
                }
              }

              // update annotation xml
              if (divObj.annotationXML[doc.documentid]) {
                let updatedXML = [];
                for (let annotxml of divObj.annotationXML[doc.documentid]) {
                  // get original/individual page num
                  let xmlObj = parser.parseFromString(annotxml);
                  if (xmlObj.name === "redact" || xmlObj.name === "freetext") {
                    let customfield = xmlObj.children.find(
                      (xmlfield) => xmlfield.name == "trn-custom-data"
                    );
                    let txt = domParser.parseFromString(
                      customfield.attributes.bytes,
                      "text/html"
                    );
                    let customData = JSON.parse(
                      txt.documentElement.textContent
                    );
                    let originalPageNo = parseInt(customData.originalPageNo);

                    if (
                      pageMappingsByDivisions[doc.documentid][
                        originalPageNo + 1
                      ]
                    ) {
                      //skip pages that need to be removed
                      // page num from annot xml
                      let y = annotxml.split('page="');
                      let z = y[1].split('"');
                      let oldPageNum = 'page="' + z[0] + '"';
                      let newPage =
                        'page="' +
                        (pageMappingsByDivisions[doc.documentid][
                          originalPageNo + 1
                        ] -
                          1) +
                        '"';
                      annotxml = annotxml.replace(oldPageNum, newPage);

                      if (
                        xmlObj.name === "redact" ||
                        customData["parentRedaction"]
                      ) {
                        updatedXML.push(annotxml);
                      }
                    }
                  }
                }

                stitchedXMLArray.push(updatedXML.join());
              }
              totalPageCount += Object.keys(
                pageMappingsByDivisions[doc.documentid]
              ).length;
              totalPageCountIncludeRemoved += doc.pagecount;
              const { PDFNet } = _instance.Core;
              PDFNet.initialize();
              await _instance.Core.createDocument(doc.s3path_load, {
                loadAsPDF: true,
              }).then(async (docObj) => {
                // ************** starts here ****************
                if (docCount == 1) {
                  stitchedDocObj = docObj;
                } else {
                  // create an array containing 1…N
                  let pages = Array.from(
                    { length: doc.pagecount },
                    (v, k) => k + 1
                  );
                  let pageIndexToInsert = stitchedDocObj?.getPageCount() + 1;
                  await stitchedDocObj.insertPages(
                    docObj,
                    pages,
                    pageIndexToInsert
                  );
                }

                // save to s3 once all doc stitched
                if (docCount == divObj.documentlist.length) {
                  if (pageMappedDocs != undefined) {
                    let divisionstichpages = [];
                    let divisionsdocpages = Object.values(
                      pageMappedDocs.docIdLookup
                    )
                      .filter((obj) => {
                        return obj.division === divObj.divisionid;
                      })
                      .map((obj) => {
                        return obj.pageMappings;
                      });
                    divisionsdocpages.forEach(function (_arr) {
                      _arr.forEach(function (value) {
                        divisionstichpages.push(value);
                      });
                    });

                    divisionstichpages.sort((a, b) =>
                      a.stitchedPageNo > b.stitchedPageNo
                        ? 1
                        : b.stitchedPageNo > a.stitchedPageNo
                        ? -1
                        : 0
                    );
                    await stampPageNumberRedline(
                      stitchedDocObj,
                      PDFNet,
                      divisionstichpages
                    );
                  }

                  // remove duplicate and not responsive pages
                  await stitchedDocObj.removePages(pagesToRemove);

                  // console.log("s3path_save", stitchedDocPath);
                  let xfdfString =
                    '<?xml version="1.0" encoding="UTF-8" ?><xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve"><annots>' +
                    stitchedXMLArray.join() +
                    "</annots></xfdf>";
                  stitchedDocObj
                    .getFileData({
                      // saves the document with annotations in it
                      xfdfString: xfdfString,
                      downloadType: downloadType,
                      flatten: true,
                    })
                    .then(async (_data) => {
                      const _arr = new Uint8Array(_data);
                      const _blob = new Blob([_arr], {
                        type: "application/pdf",
                      });

                      toast.update(toastID, {
                        render: `Saving redline PDF for ${currentDivisionCount} of ${divisionCountForToast} divisions to Object Storage...`,
                        isLoading: true,
                      });

                      saveFilesinS3(
                        { filepath: stitchedDocPath },
                        _blob,
                        (_res) => {
                          // ######### call another process for zipping and generate download here ##########
                          toast.update(toastID, {
                            render: `${currentDivisionCount} of ${divisionCountForToast} divisions are saved to Object Storage`,
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
                          prepareMessageForRedlineZipping(
                            divObj,
                            divisionCountForToast,
                            zipServiceMessage,
                            stitchedDocPath
                          );
                        },
                        (_err) => {
                          console.log(_err);
                          toast.update(toastID, {
                            render:
                              "Failed to save redline pdf to Object Storage",
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
              });
            }
          }
        },
        (error) => {
          console.log("Error fetching document:", error);
        }
      );
    };

    const saveDoc = () => {
      setRedlineModalOpen(false);
      setRedlineSaving(true);
      switch (modalFor) {
        case "redline":
          saveRedlineDocument(docInstance);
          break;
        case "responsepackage":
          saveResponsePackage(docViewer, annotManager, docInstance);
          break;
        default:
      }
    };

    const cancelSaveRedlineDoc = () => {
      setRedlineModalOpen(false);
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

    const saveResponsePackage = async (
      documentViewer,
      annotationManager,
      _instance
    ) => {
      const downloadType = "pdf";

      let zipServiceMessage = {
        ministryrequestid: requestid,
        category: "responsepackage",
        attributes: [],
        requestnumber: "",
        bcgovcode: "",
      };

      getResponsePackagePreSignedUrl(
        requestid,
        documentList[0],
        async (res) => {
          // console.log("getResponsePackagePreSignedUrl: ", res);
          // res.s3path_save;
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
                if (
                  customData?.attributes?.bytes?.includes("parentRedaction")
                ) {
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
                  FontSize: Math.min(parseInt(annot.FontSize), 12) + "pt",
                });
              }
            }
            annotManager.ungroupAnnotations(annotList);

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
            let results = await annotationManager.applyRedactions(); // must apply redactions before removing pages
            await doc.removePages(pagesToRemove);

            const { PDFNet } = _instance.Core;
            PDFNet.initialize();
            await stampPageNumberResponse(documentViewer, PDFNet);

            //apply redaction and save to s3
            doc
              .getFileData({
                // saves the document with annotations in it
                downloadType: downloadType,
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
                      render: "Final package is saved to Object Storage",
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
                  {sections
                    ?.sort((a, b) =>
                      modalSortNumbered
                        ? modalSortAsc
                          ? a.id - b.id
                          : b.id - a.id
                        : b.count - a.count
                    )
                    .map((section, index) => (
                      <ListItem key={"list-item" + section.id}>
                        <input
                          type="checkbox"
                          className="section-checkbox"
                          key={"section-checkbox" + section.id}
                          id={"section" + section.id}
                          data-sectionid={section.id}
                          onChange={handleSectionSelected}
                          disabled={
                            selectedSections.length > 0 &&
                            (section.id === 25
                              ? !selectedSections.includes(25)
                              : selectedSections.includes(25))
                          }
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
          className={"state-change-dialog"}
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
              <span className="confirmation-message">
                {modalMessage} <br></br>
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
      </div>
    );
  }
);

export default Redlining;
