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
import { toast } from "react-toastify";
import {
  fetchAnnotationsByPagination,
  fetchAnnotationsInfo,
  saveAnnotation,
  deleteRedaction,
  deleteAnnotation,
  fetchSections,
  fetchPageFlag,
  fetchPDFTronLicense,
  saveRotateDocumentPage,
  deleteDocumentPages,
  savePageFlag,
  saveRedlineContent
} from "../../../apiManager/services/docReviewerService";
import {
  PDFVIEWER_DISABLED_FEATURES,
  ANNOTATION_PAGE_SIZE,
  REDACTION_SELECT_LIMIT,
  BIG_HTTP_GET_TIMEOUT,
  REDLINE_OPACITY,
  REDACTION_SECTION_BUFFER
} from "../../../constants/constants";
import { errorToast } from "../../../helper/helper";
import { useAppSelector } from "../../../hooks/hook";
import { pageFlagTypes, RedactionTypes } from "../../../constants/enum";
import {
  createPageFlagPayload,
  createRedactionSectionsString,
  getSections,
  getValidSections,
  updatePageFlags,
  getSliceSetDetails,
  sortDocObjects,
  getDocumentsForStitching,
  constructPageFlags,
  isObjectNotEmpty,
  getValidObject,
  updatePageFlagOnPage,
  getJoinedSections,
} from "./utils";
import { Edit, MultiSelectEdit } from "./Edit";
import _ from "lodash";
import { 
  createFinalPackageSelection, 
  createOIPCForReviewSelection, 
  createRedlineForSignOffSelection, 
  createResponsePDFMenu,
  createConsultPackageSelection, 
  handleFinalPackageClick, 
  handleRedlineForOipcClick, 
  handleRedlineForSignOffClick,
  handleConsultPackageClick,
  renderCustomButton,
  isValidRedlineDownload,
  isReadyForSignOff } from "./CreateResponsePDF/CreateResponsePDF";
import useSaveRedlineForSignoff from "./CreateResponsePDF/useSaveRedlineForSignOff";
import useSaveResponsePackage from "./CreateResponsePDF/useSaveResponsePackage";
import {ConfirmationModal} from "./ConfirmationModal";
import { FOIPPASectionsModal } from "./FOIPPASectionsModal";
import { NRWarningModal } from "./NRWarningModal";
import FeeOverrideModal from "./FeeOverrideModal";

const Redlining = React.forwardRef(
  (
    {
      user,
      requestid,
      docsForStitcing,
      currentDocument,
      individualDoc,
      pageMappedDocs,
      setIsStitchingLoaded,
      isStitchingLoaded,
      incompatibleFiles,
      setWarningModalOpen,
      scrollLeftPanel,
      isBalanceFeeOverrode,
      outstandingBalance,
      pageFlags, 
      syncPageFlagsOnAction,
      isPhasedRelease,
      isAnnotationsLoading,
      setIsAnnotationsLoading,
      areAnnotationsRendered,
      setAreAnnotationsRendered,
    },
    ref
  ) => {
    const alpha = REDLINE_OPACITY;
    const requestnumber = useAppSelector(
      (state) => state.documents?.requestnumber
    );

    document.title = requestnumber + " - FOI Document Reviewer"

    const redactionInfo = useSelector(
      (state) => state.documents?.redactionInfo
    );
    const sections = useSelector((state) => state.documents?.sections);
    const currentLayer = useSelector((state) => state.documents?.currentLayer);
    const deletedDocPages = useAppSelector((state) => state.documents?.deletedDocPages);
    const validoipcreviewlayer = useAppSelector((state) => state.documents?.requestinfo?.validoipcreviewlayer);
    const requestType = useAppSelector((state) => state.documents?.requestinfo?.requesttype);
    const viewer = useRef(null);
    const [documentList, setDocumentList] = useState([]);
    
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
    const [fetchAnnotResponse, setFetchAnnotResponse] = useState(false);
    const [merge, setMerge] = useState(false);
    const [iframeDocument, setIframeDocument] = useState(null);
    const [redlineSaving, setRedlineSaving] = useState(false);
    /** State variables for Bulk Edit using Multi Selection option*/
    const [editRedacts, setEditRedacts] = useState(null);
    const [multiSelectFooter, setMultiSelectFooter] = useState(null);
    const [enableMultiSelect, setEnableMultiSelect] = useState(false);
    const [errorMessage, setErrorMessage] = useState(null);

    const [pdftronDocObjects, setpdftronDocObjects] = useState([]);
    const [stichedfiles, setstichedfiles] = useState([]);
    const [stitchPageCount, setStitchPageCount] = useState(0);
    const [skipDeletePages, setSkipDeletePages] = useState(false);
    const [modalData, setModalData] = useState(null);
    const [enableRedactionPanel, setEnableRedactionPanel] = useState(false);
    const [clickRedactionPanel, setClickRedactionPanel] = useState(false);

    const [pagesRemoved, setPagesRemoved] = useState([]);
    const [redlineModalOpen, setRedlineModalOpen] = useState(false);
    const [isDisableNRDuplicate, setIsDisableNRDuplicate] = useState(false);
    const [pageSelectionsContainNRDup, setPageSelectionsContainNRDup] = useState(false);
    const [outstandingBalanceModal, setOutstandingBalanceModal] = useState(false);
    const [isOverride, setIsOverride]= useState(false);
    const [feeOverrideReason, setFeeOverrideReason]= useState("");   
    const [isWatermarkSet, setIsWatermarkSet] = useState(false);
    const [assignedPhases, setAssignedPhases] = useState(null);
    const [redlinePhase, setRedlinePhase] = useState(null);
    const [annottext,setannottext]=useState([])
    //xml parser
    const parser = new XMLParser();
    /**Response Package && Redline download and saving logic (react custom hooks)*/
    const { 
      includeComments,
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
    } = useSaveRedlineForSignoff(docInstance, docViewer,redlinePhase);
    const {
      saveResponsePackage,
      checkSavingFinalPackage,
      enableSavingFinal,
    } = useSaveResponsePackage(redlinePhase);

    const [isRedlineOpaque, setIsRedlineOpaque] = useState(localStorage.getItem('isRedlineOpaque') === 'true')
  

    useEffect(() => {
      if (annotManager) {
        let annotations = annotManager.getAnnotationsList();
        for (let annotation of annotations) {
          if (annotation.Subject === 'Redact') {
            annotation.FillDisplayColor = new docInstance.Core.Annotations.Color(
              255,
              255,
              255,
              isRedlineOpaque ? alpha : 0
            );
            annotManager.redrawAnnotation(annotation)
          }
        }
        localStorage.setItem('isRedlineOpaque', isRedlineOpaque)
      }

    }, [isRedlineOpaque])

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
            backendType:'ems'
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
          instance.UI.enableNoteSubmissionWithEnter();
          let redactionTool = documentViewer.getTool(instance.Core.Tools.ToolNames.REDACTION)
          documentViewer.getTool(instance.Core.Tools.ToolNames.RECTANGLE).setStyles({
            StrokeColor: new Annotations.Color(255, 205, 69)
          });
          documentViewer.setToolMode(redactionTool);
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
            const finalPackageBtn = createFinalPackageSelection(document, enableSavingFinal, areAnnotationsRendered);
            const consultPackageButton = createConsultPackageSelection(document, enableSavingConsults);
            redlineForOipcBtn.onclick = () => {
              handleRedlineForOipcClick(updateModalData, setRedlineModalOpen);
            };
            redlineForSignOffBtn.onclick = () => {
              handleRedlineForSignOffClick(updateModalData, setRedlineModalOpen);
            };
            finalPackageBtn.onclick = () => {
              handleFinalPackageClick(updateModalData, setRedlineModalOpen, outstandingBalance, 
                isBalanceFeeOverrode,setOutstandingBalanceModal,setIsOverride);
            };
            consultPackageButton.onclick = () => {
              handleConsultPackageClick(updateModalData, setRedlineModalOpen, setIncludeDuplicatePages, setIncludeNRPages)
            };
            menu.appendChild(redlineForOipcBtn);
            menu.appendChild(redlineForSignOffBtn);
            menu.appendChild(finalPackageBtn);
            menu.appendChild(consultPackageButton);
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

            
            const opacityToggle = {
              type: 'customElement',
              render: () => (
                <>
                <input
                  style={{"float": "left"}}
                  type="checkbox"
                  onChange={(e) => {
                      setIsRedlineOpaque(e.target.checked)
                    } 
                  }
                  defaultChecked={isRedlineOpaque}
                  id="isRedlineOpaqueToggle"
                >
                </input>
                <label 
                  for="isRedlineOpaqueToggle"
                  style={{"top": "1px", "position": "relative", "margin-right": 10}}
                >
                  Toggle Opacity
                </label>
                </>
              )
            };

            header.headers.default.splice(
              header.headers.default.length - 4,
              0,
              opacityToggle
            );

            const textSelectorToggle = {
              type: 'customElement',
              render: () => (
                <>
                <input
                  style={{"float": "left"}}
                  type="checkbox"
                  onChange={(e) => {
                      if (e.target.checked) {
                        redactionTool.cursor = "crosshair"
                        instance.Core.Tools.RedactionCreateTool.disableAutoSwitch();
                      } else {
                        instance.Core.Tools.RedactionCreateTool.enableAutoSwitch();
                      }
                    } 
                  }
                  defaultChecked={false}
                  id="textSelectorToggle"
                >
                </input>
                <label 
                  for="textSelectorToggle"
                  style={{"top": "1px", "position": "relative", "margin-right": 10}}
                >
                  Disable Text Selection
                </label>
                </>
              )
            };

            header.headers.default.splice(
              header.headers.default.length - 5,
              0,
              textSelectorToggle
            );
          });

          instance.UI.setHeaderItems(header => {
            header.getHeader('toolbarGroup-Redact')
            .get('undoButton').insertBefore({
              type: 'actionButton',
              dataElement: 'customRedactionPanel',
              img: '<svg viewBox="-1 -1 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" clip-rule="evenodd" d="M16 2H2L2 16H16V2ZM2 0C0.895431 0 0 0.89543 0 2V16C0 17.1046 0.89543 18 2 18H16C17.1046 18 18 17.1046 18 16V2C18 0.895431 17.1046 0 16 0H2Z"></path><path d="M12 1H13.5V17H12V1Z"></path><path d="M4 4H10V5.75H4V4Z"></path><path d="M4 7.5H10V9.25H4V7.5Z"></path><path fill-rule="evenodd" clip-rule="evenodd" d="M6.29815 13.6088L7.53553 14.8462L8.5962 13.7855L7.35881 12.5482L8.59619 11.3108L7.53553 10.2501L6.29815 11.4875L5.06066 10.25L4 11.3107L5.23749 12.5482L4 13.7856L5.06066 14.8463L6.29815 13.6088Z"></path></svg>',
              onClick: () => {
                setClickRedactionPanel(true);
              }
            });
          });

          instance.UI.annotationPopup.add({
            type: "customElement",
            title: "Edit",
            render: () => (
              <Edit instance={instance} editAnnotation={editAnnotation} />
            ),
          });
          setDocInstance(instance);

          //PDFNet.initialize();
          const redactionToolNames = [
            instance.Core.Tools.ToolNames.REDACTION,
            instance.Core.Tools.ToolNames.REDACTION2,
            instance.Core.Tools.ToolNames.REDACTION3,
            instance.Core.Tools.ToolNames.REDACTION4
          ];
          redactionToolNames.forEach(toolName => {
            documentViewer
              .getTool(toolName)
              .setStyles({
                FillColor: new Annotations.Color(255, 255, 255),
              });
          });
          documentViewer.addEventListener("documentLoaded", async () => {
            PDFNet.initialize(); // Only needs to be initialized once
            let params = new URLSearchParams(window?.location?.search);
            let crossTextSearchKeywords = params?.get("query");
            // if(crossTextSearchKeywords?.length >0){
            //   const formattedKeywords = crossTextSearchKeywords?.replace(/,/g, "|");
            //   console.log("\nformattedKeywords:",formattedKeywords)
            //   instance.UI.searchTextFull(formattedKeywords, {
            //     regex: true
            //   });
            // }
            if (crossTextSearchKeywords?.length > 0) {
              // Match words inside quotes OR individual words
              const keywordsArray = crossTextSearchKeywords.match(/"([^"]+)"|\S+/g); 
              const quotesRemoved = keywordsArray.map(keyword => keyword.replace(/"/g, "")); 
              // Join the keywords with | while keeping spaces inside quotes
              const formattedKeywords = quotesRemoved.join("|");
              instance.UI.searchTextFull(formattedKeywords, {
                regex: true,
                wholeWord:true
              });
            }
            //Search Document Logic (for multi-keyword search and etc)
            const originalSearch = instance.UI.searchTextFull;
            //const pipeDelimittedRegexString = "/\w+(\|\w+)*/g"
            instance.UI.overrideSearchExecution((searchPattern, options) => {
              options.ambientString=true;
              if (searchPattern.includes("|")) {
                options.regex = true;
                /** Conditional that ensures that there is no blank string after | and inbetween ().
                 * When regex is on, a character MUST follow | and must be inbetween () or 
                 * else the regex search breaks as it is not a valid regex expression **/
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
            applyRotations(documentViewer.getDocument(), docsForStitcing[0].file.attributes.rotatedpages)
            let localDocumentInfo = currentDocument;
            if (Object.entries(individualDoc["file"])?.length <= 0)
              individualDoc = localDocumentInfo;            
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
          
          var x = 0, y = 0
          documentViewer.addEventListener("mouseRightDown", async (event) => {            
            x = event.pageX;
            y = event.pageY;
          });

          documentViewer.addEventListener("mouseRightUp", async (event) => {
            if (window.Math.abs(event.pageX - x) < 2 && window.Math.abs(event.pageY - y) < 2) {
              scrollLeftPanel(event, documentViewer.getCurrentPage());              
            }
            x = 0
            y = 0
          });

          instance.UI.addEventListener("selectedThumbnailChanged", event => {
            if (event.detail.length > 1) {
              instance.UI.disableElements(["thumbnailsControlRotateClockwise", "thumbnailsControlRotateCounterClockwise", "rotatePageCounterClockwise", "rotatePageClockwise"]);
            } else {
              instance.UI.enableElements(["thumbnailsControlRotateClockwise", "thumbnailsControlRotateCounterClockwise", "rotatePageCounterClockwise", "rotatePageClockwise"]);
            }
          })

          let root = null;

    // add event listener for hiding saving menu
    document.body.addEventListener(
      "click",
      (e) => {
        document.getElementById("saving_menu").style.display = "none"; 
        
        // toggle between notesPanel and redactionPanel handled here
        const toggleNotesButton = document.querySelector(
          '[data-element="toggleNotesButton"]'
        );
        if (toggleNotesButton) {
          toggleNotesButton?.addEventListener("click", function () {
            handleRedactionPanelClick(true, instance);
            const isActive = toggleNotesButton?.classList.contains("active");
            if (!isActive) {
                toggleNotesButton.classList.add("active");
                instance.UI.enableElements(["notesPanel"]);
              }
          });
        }

        const customRedactionPanel = document.querySelector(
          '[data-element="customRedactionPanel"]'
        );
        if (customRedactionPanel) {
          customRedactionPanel?.addEventListener("click", function () {
            if (toggleNotesButton) {
              const isActive = toggleNotesButton?.classList.contains("active");                    
              if (isActive) {
                toggleNotesButton.classList.remove("active");
                instance.UI.closeElements(['notesPanel']);
                instance.UI.disableElements(["notesPanel"]);
              }
            }
          });
        }

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

    const updateModalData = (newModalData) => {
      setRedlineCategory(newModalData.modalFor);
      setModalData(newModalData);
    };

    const applyRotations = (document, rotatedpages) => {
      for (let page in rotatedpages) {            
        let existingrotation = document.getPageRotation(page);     
        let rotation = (rotatedpages[page] - existingrotation + 360) / 90;
        document.rotatePages([page], rotation);
      }
    }

    useEffect(() =>{
        if (clickRedactionPanel) {
          handleRedactionPanelClick(enableRedactionPanel, docInstance);
          setClickRedactionPanel(false);
        }
      
    }, [clickRedactionPanel, enableRedactionPanel])


    const handleRedactionPanelClick = (isOpen, instance) => {
      if (instance) {
        switch (isOpen) {
          case true:
            instance.UI.closeElements(['redactionPanel']);
            instance.UI.disableElements(['redactionPanel']);
            setEnableRedactionPanel(false)
            break;
          case false:
            instance.UI.enableElements(['redactionPanel']);
            instance.UI.openElements(['redactionPanel']);
            setEnableRedactionPanel(true);
            break;
        }
      }
    }

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
          applyRotations(newDoc, filerow.file.attributes.rotatedpages);
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
            setIsAnnotationsLoading(true);
            fetchAnnotationsByPagination(
              requestid,
              1,
              ANNOTATION_PAGE_SIZE,
              async (data) => {
                let meta = data["meta"];
                if (meta["has_next"] === false) { 
                  setIsAnnotationsLoading(false);
                }
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
                setIsAnnotationsLoading(false);
              },
              currentLayer.name.toLowerCase(),
              BIG_HTTP_GET_TIMEOUT
            );
            fetchPageFlag(
              requestid,
              currentLayer.name.toLowerCase(),
              getDocumentsForStitching(docsForStitcing)?.map(d => d.file.documentid),
              (data) => {
                syncPageFlagsOnAction(data)
              },
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

      let extractedTexts = [];
  
    const  extractRedlineText = async function _extractRedlineText(annotations) {
      
      if(annotations)
      {
          
          for (const annotation of annotations) {
          var annotpageNumber = annotation.PageNumber
          var actualpagenum = pageMappedDocs?.stitchedPageLookup[annotpageNumber].page
          var docid =   pageMappedDocs?.stitchedPageLookup[annotpageNumber].docid            
          if(annotation.Subject === "Redact")
          {
            const rect = annotation.getRect();
            const text =  await docViewer.getDocument().getTextByPageAndRect(annotpageNumber, rect);                           
            extractedTexts.push({
                type: "RedlineContent",
                text: text,
                page: actualpagenum,
                documentid: docid,
                annotationid:annotation.Id,
                category:annotation.type              
              });
            setannottext(extractedTexts);
          }
          else if(annotation.Subject === "Free Text")
          {
            let _annottext=''           
            //console.log(_annottext)
            annottext?.push({
              type: "RedlineContentSection",
              text: annotation.getContents(),
              page: actualpagenum,
              documentid: docid,
              annotationid:annotation.Id
            });
            
          }
        }
        if (annottext.some(item => item.type === "RedlineContentSection")) {
            saveRedlineContent(
              requestid,
              annottext,
              (data) => {
                console.log("Redline content posted successfully", data);
              },
              (err) => {
                console.error("Error posting redline content", err);
              }
            );
            setannottext([]);
          }
        // console.log(`extractedTexts: ${annottext}`)
       
      }
    }

    const annotationChangedHandler = useCallback(
      (annotations, action, info) => {
        // If the event is triggered by importing then it can be ignored
        // This will happen when importing the initial annotations
        // from the server or individual changes from other users


        /**Fix for lengthy section cutoff issue with response pkg 
         * download - changed overlaytext to freetext annotations after 
         * redaction applied*/

        /**Fix for lengthy section cutoff issue with response pkg 
         * download - changed overlaytext to freetext annotations after 
         * redaction applied*/
        if (info['source'] === 'redactionApplied') {
          annotations.forEach((annotation) => {
            if(annotation.Subject == "Free Text"){
              docInstance?.Core?.annotationManager.addAnnotation(annotation);              
            }
          });
        }

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
          const exisitngAnnotations = annotManager.getAnnotationsList();
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
              let pageFlagObj = [];
              
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
                    let contents = annot?.children?.find(
                      (element) => element.name == "contents"
                    );
                    let customData = annot.children.find(
                      (element) => element.name == "trn-custom-data"
                    );
                    const isFullPage = customData?.attributes?.bytes?.includes("fullPage")
                    let annotationsInfo = {
                      stitchpage: annot.attributes.page,                      
                      type: annot.name,
                      section: contents?.value,
                      docid: displayedDoc.docid,
                      docversion: displayedDoc.docversion,
                      isFullPage: isFullPage
                    }
                    const pageFlagsUpdated = constructPageFlags(annotationsInfo, exisitngAnnotations, pageMappedDocs, pageFlagTypes, RedactionTypes, "delete", pageFlags);
                    if (pageFlagsUpdated) {
                      pageFlagObj.push(pageFlagsUpdated);
                    }                    
                  }
                }
              }
              let pageFlagData = {};
                if (isObjectNotEmpty(pageFlagObj)) {
                  pageFlagData = createPageFlagPayload(pageFlagObj, currentLayer.redactionlayerid)
                }
              const validObj=getValidObject(pageFlagData)
              if (annotObjs?.length > 0) {
                deleteAnnotation(
                  requestid,
                  currentLayer.redactionlayerid,
                  annotObjs,
                  (data) => {
                    savePageFlag(
                      requestid, 
                      0, 
                      (data) => {
                        if(data.status == true){
                          const updatedPageFlags = updatePageFlagOnPage(data.updatedpageflag, pageFlags)
                          if(updatedPageFlags?.length > 0)
                            syncPageFlagsOnAction(updatedPageFlags);
                        }
                        // fetchPageFlag(
                        //   requestid,
                        //   currentLayer.name.toLowerCase(),
                        //   documentList?.map(d => d.documentid),
                        //   (error) => console.log(error)
                        // );
                      }, 
                      (error) => console.log('error: ', error),
                      validObj
                    )
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
                    // fetchPageFlag(
                    //   requestid,
                    //   currentLayer.name.toLowerCase(),
                    //   documentList?.map(d => d.documentid),
                    //   (error) => console.log(error)
                    // );
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

              //await removeRedactAnnotationDocContent(annotations);
               await extractRedlineText(annotations);
              
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
                  annotations[i].FillDisplayColor = new docInstance.Core.Annotations.Color(255, 255, 255, isRedlineOpaque ? alpha : 0);
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
                let pageFlagObj = [];
                for (let annot of annotations) {
                  displayedDoc =
                    pageMappedDocs.stitchedPageLookup[Number(annot.PageNumber)];
                  const _sections = annot.getCustomData("sections");
                  const joinedSections = getJoinedSections(_sections);
                  let redactionType = annot.getCustomData("trn-redaction-type");
                  let annotationsInfo = {
                    stitchpage: Number(annot.PageNumber) - 1,                      
                    type: annot.Subject,
                    section: joinedSections,
                    redactiontype: redactionType,
                    docid: displayedDoc.docid,
                    docversion: displayedDoc.docversion,
                  }
                  const pageFlagsUpdated = constructPageFlags(annotationsInfo, exisitngAnnotations, pageMappedDocs, pageFlagTypes, RedactionTypes, "add", pageFlags);
                  if (pageFlagsUpdated) {
                    pageFlagObj.push(pageFlagsUpdated);
                  }
                  
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
                let pageFlagData = {};
                if (isObjectNotEmpty(pageFlagObj)) {
                  pageFlagData = createPageFlagPayload(pageFlagObj, currentLayer.redactionlayerid)
                }
                const validObj=getValidObject(pageFlagData)
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
                    if(data.status == true){
                      const updatedPageFlags = updatePageFlagOnPage(data.updatedpageflag,pageFlags)
                      if(updatedPageFlags?.length > 0)
                        syncPageFlagsOnAction(updatedPageFlags);
                    }
                  },
                  (error) => {
                    console.log(error);
                  },
                  currentLayer.redactionlayerid,
                  validObj,
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
                      // fetchPageFlag(
                      //   requestid,
                      //   currentLayer.name.toLowerCase(),
                      //   documentList?.map(d => d.documentid),
                      //   (error) => console.log(error)
                      // );
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
                      // fetchPageFlag(
                      //   requestid,
                      //   currentLayer.name.toLowerCase(),
                      //   documentList?.map(d => d.documentid),
                      //   (error) => console.log(error)
                      // );
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
        multiSelectFooter,
        enableMultiSelect,
        isStitchingLoaded,
      ]
    );

    const rotationChangedHandler = useCallback(async (changes) => {
      if (isStitchingLoaded && changes.rotationChanged) {
        let payloads = {};
        for (let page of changes.rotationChanged) {
          let originalpage = pageMappedDocs.stitchedPageLookup[page];
          let documentmasterid = documentList.find(d => d.documentid === originalpage.docid).documentmasterid;
          let rotation = docViewer.getDocument().getPageRotation(page)
          payloads[documentmasterid] = {...payloads[documentmasterid], [String(originalpage.page)]: rotation}
        }
        for (let documentmasterid in payloads) {            
          saveRotateDocumentPage(
            requestid,
            documentmasterid,
            payloads[documentmasterid],
            (data) => {},
            (error) => {
              errorToast(error);
            }
          )
        }
      }
    },
    [
      pageMappedDocs,
      currentLayer,
      newRedaction,
      pageSelections,
      redlineSaving,
      multiSelectFooter,
      enableMultiSelect,
      isStitchingLoaded,
    ]);

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
      docViewer?.removeEventListener("pagesUpdated", rotationChangedHandler)      
      docViewer?.addEventListener("pagesUpdated", rotationChangedHandler)
      return () => {
        annotManager?.removeEventListener(
          "annotationChanged",
          annotationChangedHandler
        );
        docViewer?.removeEventListener(
          "pagesUpdated",
          rotationChangedHandler
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
      triggerSetWatermarks() {
        setWatermarks();
      }
    }));

    const disableNRDuplicate = () => {
      let isDisabled = false;
      if (pageFlags?.length > 0) {
        let duplicateNRflags = [];
        for (const flagInfo of pageFlags) {                  
          duplicateNRflags = duplicateNRflags.concat(flagInfo.pageflag.filter(flag => flag.flagid === pageFlagTypes["Duplicate"] || flag.flagid === pageFlagTypes["Not Responsive"])
          .map(flag => flag.flagid));
        }
        if (docsForStitcing.totalPageCount === duplicateNRflags.length) {
          isDisabled = true;
        }        
      }
      setIsDisableNRDuplicate(isDisabled);
      /** ToDo: Check if this condition is needed
       * as it was not in dev branch
       */
      if (isDisabled) {
        setIncludeNRPages(isDisabled)
        setIncludeDuplicatePages(isDisabled);
      }
    }

    const checkSavingRedlineButton = (_instance) => {
      disableNRDuplicate();
      const readyForSignOff = isReadyForSignOff(documentList, pageFlags);
      const validRedlineDownload = isValidRedlineDownload(pageFlags);
      const redlineReadyAndValid = readyForSignOff && validRedlineDownload;
      const oipcRedlineReadyAndValid = (validoipcreviewlayer === true && currentLayer.name.toLowerCase() === "oipc") && readyForSignOff;
      if (!validoipcreviewlayer && isPhasedRelease) {
        const phasesOnRequest = findAllPhases();
        const phaseCompletionObj = checkPhaseCompletion(phasesOnRequest);
        setAssignedPhases(phaseCompletionObj);
        const phasedRedlineReadyAndValid = phaseCompletionObj.some(phase => phase.valid);
        checkSavingRedline(phasedRedlineReadyAndValid, _instance);
        checkSavingFinalPackage(phasedRedlineReadyAndValid, _instance);
      } else {
        checkSavingRedline(redlineReadyAndValid, _instance);
        checkSavingFinalPackage(redlineReadyAndValid, _instance);
      }
      checkSavingConsults(documentList, _instance);
      checkSavingOIPCRedline(oipcRedlineReadyAndValid, _instance, readyForSignOff);
    };

    //useEffect to handle validation of all Response Package downloads
    useEffect(() => {
      const handleCreateResponsePDFClick = () => {
        checkSavingRedlineButton(docInstance);
      }
      if (docInstance && documentList.length > 0) {
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

    useEffect(() => {      
      if (docInstance && documentList.length > 0 && !isWatermarkSet && docViewer && pageMappedDocs && pageFlags) {
        setWatermarks();
        setIsWatermarkSet(true)
      }
    }, [pageFlags, isStitchingLoaded, isWatermarkSet]);


    const setWatermarks = () => {
      docViewer.setWatermark({
        // Draw custom watermark in middle of the document
        custom: (ctx, pageNumber, pageWidth, pageHeight) => {
          // ctx is an instance of CanvasRenderingContext2D
          // https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D
          // Hence being able to leverage those properties
          let originalPage = pageMappedDocs['stitchedPageLookup'][pageNumber]
          let doc = pageFlags.find(d => d.documentid === originalPage.docid);
          let pageFlag = doc?.pageflag?.find(f => f.page === originalPage.page);
          if (pageFlag?.flagid === pageFlagTypes["Duplicate"]) {
            ctx.fillStyle = "#ff0000";
            ctx.font = "20pt Arial";
            ctx.globalAlpha = 0.4;

            ctx.save();
            ctx.translate(pageWidth / 2, pageHeight / 2);
            ctx.rotate(-Math.PI / 4);
            ctx.fillText("DUPLICATE", 0, 0);
            ctx.restore();
          }

          if (pageFlag?.flagid === pageFlagTypes["Not Responsive"]) {
            ctx.fillStyle = "#ff0000";
            ctx.font = "20pt Arial";
            ctx.globalAlpha = 0.4;

            ctx.save();
            ctx.translate(pageWidth / 2, pageHeight / 2);
            ctx.rotate(-Math.PI / 4);
            ctx.fillText("NOT RESPONSIVE", 0, 0);
            ctx.restore();
          }
        },
      });
      docViewer.refreshAll();
      docViewer.updateView();
    }

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

    const applyAnnotationsFunc = async () => {
      let domParser = new DOMParser();
      if (fetchAnnotResponse) {
        assignAnnotationsPagination(
          pageMappedDocs,
          fetchAnnotResponse["data"],
          domParser
        );
        let meta = fetchAnnotResponse["meta"];
        if (meta["has_next"] === true) {
          await fetchandApplyAnnotations(
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
      setIsAnnotationsLoading(true);
      const fetchPromises = [];
      for (let i = startPageIndex; i <= lastPageIndex; i++) {
        const promise = new Promise((resolve, reject) => {
          fetchAnnotationsByPagination(
          requestid,
          i,
          ANNOTATION_PAGE_SIZE,
          async (data) => {
            assignAnnotationsPagination(mappedDocs, data["data"], domParser);
            resolve();
          },
          (error) => {
            console.log("Error:", error);
            setErrorMessage(
              "Error occurred while fetching redaction details, please refresh browser and try again"
            );
            reject(error);
          },
          currentLayer.name.toLowerCase(),
          BIG_HTTP_GET_TIMEOUT
          );
        });
        fetchPromises.push(promise);
      }
      try {
        await Promise.all(fetchPromises);
        setIsAnnotationsLoading(false);
      }
      catch(err) {
        console.error("Error:", err);
        setErrorMessage("Error in fetching and applying all annotations, please refresh browser and try again");
        setIsAnnotationsLoading(false);
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
        // import redactions first, free text later, so translucent redaction won't cover free text
        let xmlAnnotsChildren_redaction = [];
        let xmlAnnotsChildren_others = [];
        for (let annot of xml.getElementsByTagName("annots")[0].children) {
          let txt = domParser.parseFromString(
            annot.getElementsByTagName("trn-custom-data")[0].attributes.bytes,
            "text/html"
          );
          let customData = JSON.parse(txt.documentElement.textContent);
          let originalPageNo = customData.originalPageNo;
          let mappedDoc = pageMappedDocs?.docIdLookup[entry];
          annot.attributes.page = (
            mappedDoc?.pageMappings.find(
              (p) => p.pageNo - 1 === Number(originalPageNo)
            )?.stitchedPageNo - 1
          )?.toString();
          if(annot.attributes.subject === "Redact") {
            xmlAnnotsChildren_redaction.push(annot);
          } else {
            xmlAnnotsChildren_others.push(annot);
          }
          xml.getElementsByTagName("annots")[0].children = [...xmlAnnotsChildren_redaction, ...xmlAnnotsChildren_others];
        }
        xml = parser.toString(xml);
        const _annotations = await annotManager.importAnnotations(xml);
        _annotations.forEach((_annotation) => {
          // _annotation.NoMove = true; //All annotations except redactions shouldn't be restricted, hence commented this code.
          if (_annotation.Subject === "Redact") {
            _annotation.IsHoverable = false;
            _annotation.NoMove = true;
            _annotation.FillDisplayColor = new annots.Color(255, 255, 255, isRedlineOpaque ? alpha : 0);

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

    //useEffect that ensures that all annotations are rendered to FE Object after all annotations are fetched from BE and documents stitched
    useEffect(() => {
      if (!docViewer) return;
      setAreAnnotationsRendered(false);
      if (!isAnnotationsLoading && isStitchingLoaded) {
        const toastNotification = toast.loading("Annotations fetched and are now rendering...", {
          className: "file-upload-toast-annots",
          isLoading: true,
          hideProgressBar: true,
          // draggable: true,
          closeOnClick: true,
          closeButton: true,
        });
        docViewer.getAnnotationsLoadedPromise().then(() => {
          toast.dismiss(toastNotification);
          toast.success("Annotations successfully rendered. Response Package creation enabled", {
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
          setAreAnnotationsRendered(true);
        })
        .catch((err) => {
          toast.dismiss(toastNotification);
          toast.error("Error in rendering annotations, please refresh browser and try again", {
            type: "error",
            className: "file-upload-toast",
            isLoading: false,
            autoClose: 4000,
            hideProgressBar: true,
            closeOnClick: true,
            pauseOnHover: true,
            draggable: true,
            closeButton: true,
          });
        })
      }
    }, [docViewer, setAreAnnotationsRendered, isAnnotationsLoading, isStitchingLoaded]);

    useEffect(() => {
      const handleSingleFileDocumentLoaded = async () => {
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
          
          await applyAnnotationsFunc();
          setIsStitchingLoaded(true);
          setpdftronDocObjects([]);
          setstichedfiles([]);
        }
      }
    }
    handleSingleFileDocumentLoaded();
    }, [
      pdftronDocObjects,
      docsForStitcing,
      stichedfiles,
      fetchAnnotResponse,
      docViewer,
    ]);

    useEffect(() => {
      const handleDivisionFileDocumentLoad = async () => {
      if (stitchPageCount === docsForStitcing.totalPageCount) {
        console.log(`Download and Stitching completed.... ${new Date()}`);

        if (stitchPageCount > 800) {
          docInstance.UI.setLayoutMode(docInstance.UI.LayoutMode.Single);
        }
        await applyAnnotationsFunc();
        setIsStitchingLoaded(true);
        setPagesRemoved([]);
        setSkipDeletePages(false);
        setpdftronDocObjects([]);
        setstichedfiles([]);
      }
    }
    handleDivisionFileDocumentLoad();
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
      const pageFlagObj = [];
      const exisitngAnnotations = annotManager.getAnnotationsList();
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
        // childAnnotation.X = _redact.X;
        // childAnnotation.Y = _redact.Y;
        // childAnnotation.FontSize =
        //   Math.min(parseInt(_redact.FontSize), 9) + "pt";
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
        let redactionSections = "";
        if (redactionSectionsIds.length > 0) {
          redactionSections = createRedactionSectionsString(
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

        let annotationsInfo = {
          stitchpage: node.attributes.page,                      
          type: _redact?.Subject,
          section: redactionSections,
          redactiontype: fullpageredaction,
          docid: displayedDoc.docid,
          docversion: displayedDoc.docversion,
        }
        const pageFlagsUpdated = constructPageFlags(annotationsInfo, exisitngAnnotations, pageMappedDocs, pageFlagTypes, RedactionTypes, "edit", pageFlags);
        if (pageFlagsUpdated) {
          pageFlagObj.push(pageFlagsUpdated);
        }
        // const doc = docViewer?.getDocument();
        // let pageNumber = parseInt(node.attributes.page) + 1;

        // const pageInfo = doc.getPageInfo(pageNumber);
        // const pageMatrix = doc.getPageMatrix(pageNumber);
        // const pageRotation = doc.getPageRotation(pageNumber);
        // childAnnotation.fitText(pageInfo, pageMatrix, pageRotation);
        // let rect = childAnnotation.getRect();
        // rect.x2 = Math.ceil(rect.x2);
        // childAnnotation.setRect(rect);
        childAnnotation = getCoordinates(childAnnotation, _redact)
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
        let pageFlagData = {};
        if (isObjectNotEmpty(pageFlagObj)) {
          pageFlagData = createPageFlagPayload(pageFlagObj, currentLayer.redactionlayerid)
        }
        const validObj=getValidObject(pageFlagData)
        saveAnnotation(
          requestid,
          astr,
          (data) => {
            setPageSelections([]);
            if(data.status == true){
              const updatedPageFlags = updatePageFlagOnPage(data.updatedpageflag,pageFlags)
              if(updatedPageFlags?.length > 0)
                syncPageFlagsOnAction(updatedPageFlags);
            }       
            // fetchPageFlag(
            //   requestid,
            //   currentLayer.name.toLowerCase(),
            //   documentList?.map(d => d.documentid),
            //   (error) => console.log(error)
            // );
          },
          (error) => {
            console.log(error);
          },
          currentLayer.redactionlayerid,
          validObj,
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
      const exisitngAnnotations = annotManager.getAnnotationsList();
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

          let redactionSectionsIds = selectedSections;
          let redactionSections = "";
          if (redactionSectionsIds.length > 0) {
            redactionSections = createRedactionSectionsString(
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
          let annotationsInfo = {
            stitchpage: pageNumber - 1,                      
            type: redaction?.Subject,
            section: redactionSections,
            redactiontype: fullpageredaction,
            docid: displayedDoc.docid,
            docversion: displayedDoc.docversion,
          }
          // const pageInfo = doc.getPageInfo(pageNumber);
          // const pageMatrix = doc.getPageMatrix(pageNumber);
          // const pageRotation = doc.getPageRotation(pageNumber);
          // childAnnotation.fitText(pageInfo, pageMatrix, pageRotation);
          // childAnnotation.NoMove = true;
          // let rect = childAnnotation.getRect();
          // rect.x2 = Math.ceil(rect.x2);
          // childAnnotation.setRect(rect);
          childAnnotation = getCoordinates(childAnnotation, redaction);
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
              const pageFlagObj = [];              
              const pageFlagsUpdated = constructPageFlags(annotationsInfo, exisitngAnnotations, pageMappedDocs, pageFlagTypes, RedactionTypes, "edit", pageFlags);
                  if (pageFlagsUpdated) {
                    pageFlagObj.push(pageFlagsUpdated);
                  }
              let pageFlagData = {};
              if (isObjectNotEmpty(pageFlagObj)) {
                pageFlagData = createPageFlagPayload(pageFlagObj, currentLayer.redactionlayerid)
              }
              const validObj=getValidObject(pageFlagData)
              saveAnnotation(
                requestid,
                astr,
                (data) => {
                  setPageSelections([]);
                  if(data.status == true){
                    const updatedPageFlags = updatePageFlagOnPage(data.updatedpageflag,pageFlags)
                    if(updatedPageFlags?.length > 0)
                      syncPageFlagsOnAction(updatedPageFlags);
                  }
                  // fetchPageFlag(
                  //   requestid,
                  //   currentLayer.name.toLowerCase(),
                  //   documentList?.map(d => d.documentid),
                  //   (error) => console.log(error)
                  // );
                },
                (error) => {
                  console.log(error);
                },
                currentLayer.redactionlayerid,
                validObj,
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
          (defaultSections.length > 0 && defaultSections[0] === blankID) ||
          selectedSections[0] === blankID
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
          let annot = new annots.FreeTextAnnotation();
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
          annot = getCoordinates(annot, redaction);
          // const doc = docViewer.getDocument();
          // const pageInfo = doc.getPageInfo(annot.PageNumber);
          // const pageMatrix = doc.getPageMatrix(annot.PageNumber);
          // const pageRotation = doc.getPageRotation(annot.PageNumber);
          // annot.NoMove = true;
          // annot.fitText(pageInfo, pageMatrix, pageRotation);
          // let rect = annot.getRect();
          // rect.x2 = Math.ceil(rect.x2);
          // annot.setRect(rect);
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
            setPageSelections([]);
          },
          (error) => {
            console.log(error);
          },
          currentLayer.redactionlayerid,
          null
        );
        annotManager.addAnnotations(sectionAnnotations, { autoFocus: false });
        // Always redraw annotation
        sectionAnnotations.forEach((a) => annotManager.redrawAnnotation(a));
        setNewRedaction(null);
      }
    };

    const getCoordinates = (_annot, _redaction, X) => {
      _annot.PageNumber = _redaction?.getPageNumber();
      // let rect = _redaction.getQuads()[0].toRect();
      let quad = _redaction.getQuads()[0];
      var buffer = Number(REDACTION_SECTION_BUFFER);
      let rect = new docInstance.Core.Math.Rect(quad.x1 + buffer, quad.y3 + buffer, quad.x2 + buffer, quad.y2 + buffer);
      const doc = docViewer.getDocument();
      const pageInfo = doc.getPageInfo(_annot.PageNumber);
      const pageMatrix = doc.getPageMatrix(_annot.PageNumber);
      const pageRotation = doc.getPageRotation(_annot.PageNumber);
      _annot.FontSize = Math.min(parseInt(_redaction.FontSize), 9) + "pt";
      _annot.Rotation = 0; // reset rotation before resizing
      _annot.fitText(pageInfo, pageMatrix, pageRotation);
      let annotrect = _annot.getRect();
      annotrect.x2 = Math.ceil(annotrect.x2);
      _annot.setRect(annotrect);
      if (pageRotation === 0 || _redaction.IsText) {
        // _annot.X = X || rect.x1;
        // _annot.Y = rect.y1;        
        _annot.setRect(new docViewerMath.Rect(rect.x1, rect.y1, rect.x1 + _annot.Width, rect.y1 + _annot.Height));  
        // let annotrect = _annot.getRect();
        // annotrect.x2 = Math.ceil(annotrect.x2);
        // _annot.setRect(annotrect);
      } else if (pageRotation === 90) {
        _annot.setRect(new docViewerMath.Rect(rect.x1, rect.y2 - _annot.Width, rect.x1 + _annot.Height, rect.y2));  
        _annot.Rotation = pageRotation;
        // _annot.X = rect.x1;
        // _annot.Y = rect.y2;
      } else if (pageRotation === 180) {
        _annot.setRect(new docViewerMath.Rect(rect.x2 - _annot.Width, rect.y2 - _annot.Height, rect.x2, rect.y2));
        _annot.Rotation = pageRotation;
        // _annot.X = rect.x2;
        // _annot.Y = rect.y2;  
      } else if (pageRotation === 270) {
        _annot.setRect(new docViewerMath.Rect(rect.x2 - _annot.Height, rect.y1, rect.x2, rect.y1 + _annot.Width));  
        _annot.Rotation = pageRotation;
        // _annot.X = rect.x2;
        // _annot.Y = rect.y1;   
      } 
      _annot.NoMove = true;
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
      if(outstandingBalance > 0 && !isBalanceFeeOverrode){
        setIsOverride(false)
        setOutstandingBalanceModal(false)
      }
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
        setNewRedaction(null)
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
      updateModalData({
        modalTitle: "Not Responsive Default",
        modalMessage: [
          <div>You have 'Not Responsive' selected as a default section.
            <ul>
              <li className="modal-message-list-item">To flag this page as 'Withheld in Full', remove the default section.</li>
              <li className="modal-message-list-item">To flag this full page as 'Not Responsive', use the 'Not Responsive' page flag.</li>
            </ul>
          </div>,
        ],
      });
      setMessageModalOpen(true);
    }

    const setMessageModalForNrDuplicatePriority = () => {
      updateModalData({
        modalTitle: "Selected page(s) currently have NR or Duplicate flag applied",
        modalMessage: [
            <ul>
              <li className="modal-message-list-item">Please note, your redaction(s) have been applied on your selected page(s). However, to flag your selected page(s) as Withheld In Full, you must first change your selected page(s) flags to In Progress.</li>
              <li className="modal-message-list-item">After your selected page(s) are flagged as In Progress you may proceed to mark them as Withheld in Full.</li>
            </ul>
        ],
      });
    }

    useEffect(() => {
      if (!newRedaction) return;
      const astrType = decodeAstr(newRedaction.astr)['trn-redaction-type'] || '';
      const hasFullPageRedaction = astrType === "fullPage";
      // logic to alert the user that a withheld in full pageflag/redaction was applied to a page with an existing duplicate or nr pageflag.
      let hasNROrDuplicateFlag = false;
      if (selectedPageFlagId === pageFlagTypes["Withheld in Full"] || hasFullPageRedaction) {
        const pageFlagsMap = new Map();
        for (let docPageFlags of pageFlags) {
          pageFlagsMap.set(docPageFlags.documentid, docPageFlags.pageflag);
        }
        for (let pageObj of pageSelections) {
          if (hasNROrDuplicateFlag) {
            break;
          }
          const pageFlagList = pageFlagsMap.get(pageObj.docid);
          if (pageFlagList) {
            for (let flagObj of pageFlagList) {
              if (flagObj.page === pageObj.page && (flagObj.flagid === pageFlagTypes["Not Responsive"] || flagObj.flagid === pageFlagTypes["Duplicate"])) {
                hasNROrDuplicateFlag = true;
                break;
              }
            }
          }
        }
      }
      setPageSelectionsContainNRDup(hasNROrDuplicateFlag);

      if (newRedaction.names?.length > REDACTION_SELECT_LIMIT) {
        setWarningModalOpen(true);
        cancelRedaction();
      } else if (defaultSections.length > 0 && !defaultSections.includes(NRID)) {
        saveRedaction();
      } else if (defaultSections.length == 0 && !hasFullPageRedaction) {
        setModalOpen(true);
      } else if (hasNROrDuplicateFlag) {
        setModalOpen(true);
        setMessageModalForNrDuplicatePriority();
      } else if (selectedPageFlagId === pageFlagTypes["Withheld in Full"] && defaultSections.length > 0) {
        setMessageModalForNotResponsive();
      } else if (hasFullPageRedaction) {
        if (defaultSections.length != 0) setMessageModalForNotResponsive();
        setModalOpen(true)
      } else if (defaultSections.includes(NRID) && selectedPageFlagId != pageFlagTypes["Withheld in Full"]) {
        saveRedaction();
      } else {
        setModalOpen(true);
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

    const cancelSaveRedlineDoc = () => {
      disableNRDuplicate();
      setRedlineModalOpen(false);
      setSelectedPublicBodyIDs([]);
      setConsultApplyRedactions(false);
      setConsultApplyRedlines(false);
      if(outstandingBalance > 0 && !isBalanceFeeOverrode){
        setOutstandingBalanceModal(false)
        setIsOverride(false)
      }
      else
        setRedlineModalOpen(false);
    };
  
    const handleIncludeComments = (e) => {
      setIncludeComments(e.target.checked);
    };
    const handleIncludeNRPages = (e) => {
      setIncludeNRPages(e.target.checked);
    };
  
    const handleIncludeDuplicantePages = (e) => {
      setIncludeDuplicatePages(e.target.checked);
    };

    const handleApplyRedactions = (e) => {
      setConsultApplyRedactions(e.target.checked);
    }

    const handleApplyRedlines = (e) => {
      setConsultApplyRedlines(e.target.checked);
      if (consultApplyRedactions) {
        setConsultApplyRedactions(false);
      }
    }

    const handleSelectedPublicBodies = (e) => {
      let publicBodyId = !isNaN(parseInt(e.target.value)) ? parseInt(e.target.value) : e.target.value;
      if (selectedPublicBodyIDs.includes(publicBodyId)) {
        setSelectedPublicBodyIDs((prev) => {
          return [...prev.filter(id => id !== publicBodyId)]
        });
      }
      else {
        setSelectedPublicBodyIDs((prev) => {
          return [...prev, publicBodyId]
        });
      }
    }

    // Phase Redline Package Functions
    const findAllPhases = () => {
      const docsWithPhaseFlag = pageFlags.filter((flagObj) =>
        flagObj.pageflag?.some((obj) => obj.flagid === pageFlagTypes['Phase'])
      );
      if (docsWithPhaseFlag.length > 0) {
        const phases = docsWithPhaseFlag.flatMap((obj) => 
          obj.pageflag
              ? obj.pageflag
                    .filter((flag) => flag.flagid === pageFlagTypes['Phase'])
                    .flatMap((flag) => flag.phase) 
              : []
        );
        return [...new Set(phases)];
      }
    }
    const checkPhaseCompletion  = (requestPhases) => {
      const phaseResults = [];
      const docsWithPhaseFlag = pageFlags.filter((docObj) =>
        docObj.pageflag?.some((obj) => obj.flagid === pageFlagTypes['Phase'])
      );
      const phasePageMap = {};
      if (docsWithPhaseFlag.length > 0) {
        //Phase:Pages Map
        for (let docObj of pageFlags) {
          for (let flag of docObj.pageflag) {
            if (flag.flagid === pageFlagTypes["Phase"]) {
              for (let phase of flag.phase) {
                if (!phasePageMap[phase]) {
                  phasePageMap[phase] = {};
                }
                if (!phasePageMap[phase][docObj.documentid]) {
                  phasePageMap[phase][docObj.documentid] = new Set();
                }
                phasePageMap[phase][docObj.documentid].add(flag.page);
              }
            }
          }
        }
        for (let activePhase of requestPhases) {
          let totalPhasedPagesWithFlags = 0;
          let phasedPagesCount = 0;
          // Extract pages that have the phase flag for active phases
          const phasedPages = phasePageMap[activePhase];
          phasedPagesCount = Object.values(phasedPages).reduce((count, pages) => count + pages.size, 0);
          pageFlags.forEach((docObj) => {
            const docid = docObj.documentid
            docObj.pageflag?.forEach((flag) => {
              if (phasedPages[docid]?.has(flag.page) &&
                ![
                  pageFlagTypes["Phase"],
                  pageFlagTypes["Consult"],
                  pageFlagTypes["In Progress"],
                  pageFlagTypes["Page Left Off"]
                ].includes(flag.flagid) // Page does NOT have excluded flags
              ) {
                totalPhasedPagesWithFlags += 1
              }
            });
          });
          // const completion = totalPhasedPagesWithFlags > 0 && phasedPagesCount > 0 ? Math.floor((totalPhasedPagesWithFlags / phasedPagesCount) * 100) : 0;
          const valid = totalPhasedPagesWithFlags > 0 && phasedPagesCount > 0 && totalPhasedPagesWithFlags === phasedPagesCount;
          phaseResults.push({activePhase: parseInt(activePhase), valid});
        }
      }
      return phaseResults;
    }

    const saveDoc = () => {
      setIsOverride(false)
      setOutstandingBalanceModal(false)
      setRedlineModalOpen(false);
      setRedlineSaving(true);
      let modalFor= modalData? modalData.modalFor : ""
      setRedlineCategory(modalFor);
      // skip deletePages API call for all removePages related to Redline/Response package creation
      setSkipDeletePages(true);
      switch (modalFor) {
        case "oipcreview":
        case "redline":
        case "consult":
          // Key phase logic: Phased redlines must filter and map pages over docs with NO PAGE FLAGS, therefore a document must have a pageFlag array to filter/map over.
          let docList = redlinePhase && modalFor === "redline" ? documentList.map(doc => {
            let docCopy = {...doc}
            if (!docCopy.pageFlag) docCopy.pageFlag = [];
            return docCopy;
          }) : documentList;
          saveRedlineDocument(
            docInstance,
            modalFor,
            incompatibleFiles,
            docList,
            pageMappedDocs,
            applyRotations
          );
          break;
        case "responsepackage":
          // Key phase logic: Phased packages must filter and map pages over docs with NO PAGE FLAGS, therefore a data set must include all docs (incl. ones with no page flags).
          let docPageFlags = redlinePhase ? documentList.map(doc => ({"documentversion": doc.version, "documentid": doc.documentid, "pageflag": doc.pageFlag ? doc.pageFlag : []})) : pageFlags;
          saveResponsePackage(
            docViewer,
            annotManager,
            docInstance,
            documentList,
            pageMappedDocs,
            docPageFlags,
            feeOverrideReason,
            requestType,
          );
          break;
        default:
      }
      // setIncludeDuplicatePages(false);
      // setIncludeNRPages(false);
    };

    const decodeAstr = (astr) => {
      const parser = new DOMParser()
      const xmlDoc = parser.parseFromString(astr, "text/xml")
      const trnCustomDataXml = xmlDoc.getElementsByTagName("trn-custom-data");
      const trnCustomDataJsonString = trnCustomDataXml[0].attributes[0].value
      const trnCustomData = JSON.parse(trnCustomDataJsonString)
      return trnCustomData
    }

    const NRID = sections?.find(s => s.section === "NR")?.id;
    const blankID = sections?.find(s => s.section === "")?.id;

    const sectionIsDisabled = (sectionid) => {
      let isDisabled = false;
      let hasFullPageRedaction = false;
      if (newRedaction) hasFullPageRedaction = decodeAstr(newRedaction.astr)['trn-redaction-type'] === "fullPage"
      // For sections
      if (selectedSections.length > 0 && !selectedSections.includes(blankID) && !selectedSections.includes(NRID)) {
        isDisabled = (sectionid === blankID || sectionid === NRID)
      // For Blank Code
      } else if (selectedSections.length > 0 && selectedSections.includes(blankID)) {
        isDisabled = sectionid !== blankID
      } else if (hasFullPageRedaction) {
        isDisabled = sectionid == NRID
      // For Not Responsive
      } else if (selectedSections.length > 0 && selectedSections.includes(NRID)) {
        isDisabled = sectionid !== NRID
      } else if (selectedPageFlagId === pageFlagTypes["Withheld in Full"] && selectedSections?.length === 0) {
        isDisabled = sectionid == NRID
      } else if (editAnnot) {
        const trnCustomData = decodeAstr(editAnnot.astr)
        const isFullPage = trnCustomData['trn-redaction-type'] === "fullPage"
        isDisabled = isFullPage && sectionid == NRID
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
        isDisabled = hasFullPageRedaction && sectionid == NRID
      }
      return isDisabled
    }

    const overrideOutstandingBalance = () => {
      setIsOverride(true)
    }
    const handleOverrideReasonChange = (event) => {
      setFeeOverrideReason(event.target.value);
    };
    
    return (
      <div>
        <div className="webviewer" ref={viewer}></div>
          <FOIPPASectionsModal
            cancelRedaction={cancelRedaction}
            modalOpen={modalOpen}
            sections={sections}
            sectionIsDisabled={sectionIsDisabled}
            selectedSections={selectedSections}
            handleSectionSelected={handleSectionSelected}
            editRedacts={editRedacts}
            saveRedactions={saveRedactions}
            pageSelectionsContainNRDup={pageSelectionsContainNRDup}
            setMessageModalOpen={setMessageModalOpen}
            saveDisabled={saveDisabled}
            saveRedaction={saveRedaction}
            defaultSections={defaultSections}
            saveDefaultSections={saveDefaultSections}
            clearDefaultSections={clearDefaultSections} 
          />
        {redlineModalOpen && 
          <ConfirmationModal 
          cancelRedaction={cancelRedaction}
          redlineModalOpen={redlineModalOpen}
          cancelSaveRedlineDoc={cancelSaveRedlineDoc}
          includeComments={includeComments}
          handleIncludeComments={handleIncludeComments}
          includeNRPages={includeNRPages}
          handleIncludeNRPages={handleIncludeNRPages}
          includeDuplicatePages={includeDuplicatePages}
          handleIncludeDuplicantePages={handleIncludeDuplicantePages}
          isDisableNRDuplicate={isDisableNRDuplicate}
          saveDoc={saveDoc}
          modalData={modalData}
          documentPublicBodies={documentPublicBodies}
          handleSelectedPublicBodies={handleSelectedPublicBodies}
          selectedPublicBodyIDs={selectedPublicBodyIDs}
          consultApplyRedactions={consultApplyRedactions}
          handleApplyRedactions={handleApplyRedactions}
          handleApplyRedlines={handleApplyRedlines}
          consultApplyRedlines={consultApplyRedlines}
          setRedlinePhase={setRedlinePhase}
          redlinePhase={redlinePhase}
          assignedPhases={assignedPhases}
          validoipcreviewlayer={validoipcreviewlayer}
        />
        }
        {messageModalOpen &&
          <NRWarningModal 
          cancelRedaction={cancelRedaction}
          messageModalOpen={messageModalOpen}
          modalData={modalData}
          />
        }
        <FeeOverrideModal
          modalData={modalData}
          cancelRedaction={cancelRedaction}
          outstandingBalanceModal={outstandingBalanceModal}
          cancelSaveRedlineDoc={cancelSaveRedlineDoc}
          isOverride={isOverride}
          feeOverrideReason={feeOverrideReason}
          handleOverrideReasonChange={handleOverrideReasonChange}
          saveDoc={saveDoc}
          overrideOutstandingBalance={overrideOutstandingBalance}
        />
      </div>
    );
  }
);

export default React.memo(Redlining);
