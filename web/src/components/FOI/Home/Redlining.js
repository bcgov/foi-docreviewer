import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import React, { useRef, useEffect,useState,useImperativeHandle } from 'react';
import {useDispatch, useSelector} from "react-redux";
import WebViewer from '@pdftron/webviewer';
import XMLParser from 'react-xml-parser';
import ReactModal from 'react-modal-resizable-draggable';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';
import CloseIcon from '@material-ui/icons/Close';
import IconButton from "@material-ui/core/IconButton";
import Switch, { SwitchProps } from '@mui/material/Switch';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';
import {ReactComponent as EditLogo} from "../../../assets/images/icon-pencil-line.svg";
import { fetchAnnotations, fetchAnnotationsInfo, saveAnnotation, deleteRedaction,
  deleteAnnotation, fetchSections, fetchPageFlag } from '../../../apiManager/services/docReviewerService';
import { getFOIS3DocumentRedlinePreSignedUrl, saveFilesinS3 } from '../../../apiManager/services/foiOSSService';
//import { element } from 'prop-types';
import {PDFVIEWER_DISABLED_FEATURES} from  '../../../constants/constants'
import {faArrowUp, faArrowDown} from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { useAppSelector } from '../../../hooks/hook';

const Redlining = React.forwardRef(({
  user,
  requestid,
  docsForStitcing,
  currentDocument,
  stitchedDoc,
  setStitchedDoc,
  individualDoc,
  pageMappedDocs,
  setPageMappedDocs
}, ref) =>{

  const pageFlags = useAppSelector((state) => state.documents?.pageFlags);
  const redactionInfo = useSelector((state)=> state.documents?.redactionInfo);
  const sections = useSelector((state) => state.documents?.sections);

  const viewer = useRef(null);
  const saveButton = useRef(null);

  const documentList = useAppSelector((state) => state.documents?.documentList);
  //const [pdffile, setpdffile] = useState((currentPageInfo.file['filepath']));
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
  const [saveDisabled, setSaveDisabled]= useState(true);
  const [redactionType, setRedactionType]= useState(null);
  const [pageSelections, setPageSelections] = useState([]);
  const [modalSortNumbered, setModalSortNumbered]= useState(false);
  const [modalSortAsc, setModalSortAsc]= useState(true);
  const [fetchAnnotResponse, setFetchAnnotResponse] = useState({})
  const [merge, setMerge] = useState(false);
  const [mapper, setMapper] = useState([]);
  const [isSavingMenuOpen, setIsSavingMenuOpen] = useState(false);
  //xml parser
  const parser = new XMLParser();

  const isReadyForSignOff = () => {
    let pageFlagArray = [];
    let stopLoop = false;

    documentList.every(docInfo => {
      pageFlags?.every(pageFlagInfo => {
        if (docInfo.documentid == pageFlagInfo?.documentid) {
          if (docInfo.pagecount > pageFlagInfo.pageflag.length) { // not all page has flag set
            stopLoop = true;
            return false;
          } else {
            // artial Disclosure, Full Disclosure, Withheld in Full, Duplicate, Not Responsive
            pageFlagArray = pageFlagInfo.pageflag?.filter((flag) => [1,2,3,5,6].includes(flag.flagid));
            if(pageFlagArray.length != pageFlagInfo.pageflag.length) {
              stopLoop = true;
              return false;
            }
          }
        }
        return true;
      });

      if(stopLoop)
        return false;

      return true;
    });

    return !stopLoop;
  };
  const [enableSavingRedline, setEnableSavingRedline] = useState(isReadyForSignOff());

  // const [storedannotations, setstoreannotations] = useState(localStorage.getItem("storedannotations") || [])
  // if using a class, equivalent of componentDidMount
  useEffect(() => {
    //let currentDocumentS3Url = localStorage.getItem("currentDocumentS3Url");
    //localStorage.setItem("isDocumentStitched", "false");
    //console.log("Doc Stitched - Set as FALSE!")

    let currentDocumentS3Url = currentDocument?.currentDocumentS3Url;
    fetchSections(
      requestid,
      (error)=> console.log(error)
    );

    WebViewer(
      {
        path: '/webviewer',
        preloadWorker: 'pdf',
        // initialDoc: currentPageInfo.file['filepath'] + currentPageInfo.file['filename'],
        initialDoc: currentDocumentS3Url,
        fullAPI: true,
        enableRedaction: true,
        useDownloader: false,
        disabledElements: ['modalRedactButton', 'annotationRedactButton'],
        css: '/stylesheets/webviewer.css'
      },
      viewer.current,
    ).then((instance) => {
      const { documentViewer, annotationManager, Annotations,  PDFNet, Search, Math, createDocument } = instance.Core;
      instance.UI.disableElements(PDFVIEWER_DISABLED_FEATURES.split(','))

      //customize header - insert a dropdown button
      const document = instance.UI.iframeWindow.document;
      instance.UI.setHeaderItems(header => {
        const parent = documentViewer.getScrollViewElement().parentElement;
  
        const menu = document.createElement('div');
        menu.classList.add('Overlay');
        menu.classList.add('FlyoutMenu');
        menu.id = 'saving_menu';
  
        const createRecordsPackageBtn = document.createElement('button');
        createRecordsPackageBtn.textContent = 'Create Records Package';
        createRecordsPackageBtn.style.backgroundColor = 'transparent';
        createRecordsPackageBtn.style.border = 'none';
        createRecordsPackageBtn.style.padding = '8px 8px 8px 10px';
        createRecordsPackageBtn.style.cursor= 'pointer';
        createRecordsPackageBtn.style.alignItems= 'left';
        // createRecordsPackageBtn.style.color = '#069';

        createRecordsPackageBtn.onclick = () => {
          // Download
          // console.log("Create Records Package");
        };
  
        menu.appendChild(createRecordsPackageBtn);
  
        const redlineForSignOffBtn = document.createElement('button');
        redlineForSignOffBtn.textContent = 'Redline for Sign Off';
        redlineForSignOffBtn.id = 'redline_for_sign_off';
        redlineForSignOffBtn.className = 'redline_for_sign_off';
        redlineForSignOffBtn.style.backgroundColor = 'transparent';
        redlineForSignOffBtn.style.border = 'none';
        redlineForSignOffBtn.style.padding = '8px 8px 8px 10px';
        redlineForSignOffBtn.style.cursor = 'pointer';
        redlineForSignOffBtn.style.alignItems = 'left';
        redlineForSignOffBtn.disabled = !enableSavingRedline;
        // redlineForSignOffBtn.style.color = '#069';

        redlineForSignOffBtn.onclick = () => {
          // Save to s3
          setRedlineModalOpen(true);
        };
  
        menu.appendChild(redlineForSignOffBtn);
  
        const responsePackageBtn = document.createElement('button');
        responsePackageBtn.textContent = 'Response Package for Application';
        responsePackageBtn.style.backgroundColor = 'transparent';
        responsePackageBtn.style.border = 'none';
        responsePackageBtn.style.padding = '8px 8px 8px 10px';
        responsePackageBtn.style.cursor= 'pointer';
        responsePackageBtn.style.alignItems= 'left';
        // responsePackageBtn.style.color = '#069';

        responsePackageBtn.onclick = () => {
          // Download
          // console.log("Response Package for Application");
        };
  
        menu.appendChild(responsePackageBtn);
  
        let isMenuOpen = false;
  
        const renderCustomMenu = () => {
          const menuBtn = document.createElement('button');
          menuBtn.textContent = 'Create Response PDF';
          menuBtn.id = 'create_response_pdf';

          menu.style.left = `${document.body.clientWidth - (menuBtn.clientWidth + 230)}px`;
          menu.style.right = 'auto';
          menu.style.top = '30px';
          menu.style.minWidth = '200px';
          menu.padding = '0px';
          menu.style.display = 'none';
          parent.appendChild(menu);
  
          menuBtn.onclick = async () => {
            if (isMenuOpen) {
              menu.style.display = 'none';
            } else {
              menu.style.display = 'flex';
            }
  
            isMenuOpen = !isMenuOpen;
          };
  
          return menuBtn;
        };
  
        const newCustomElement = {
          type: 'customElement',
          render: renderCustomMenu,
        };

        // header.push(newCustomElement);
        // insert dropdown button in front of search button
        header.headers.default.splice((header.headers.default.length-3), 0, newCustomElement);
      });


      const Edit = () => {
        let selectedAnnotations = annotationManager.getSelectedAnnotations();
        return (
          <button
            type="button"
            class="Button ActionButton"
            style={selectedAnnotations[0].Subject !== 'Redact' ? {cursor: "default"} : {}}
            onClick={() => {
              editAnnotation(annotationManager, annotationManager.exportAnnotations({annotList: selectedAnnotations, useDisplayAuthor: true}))
            }}
            disabled={selectedAnnotations[0].Subject !== 'Redact'}
          >
            <div class="Icon" style={selectedAnnotations[0].Subject !== 'Redact' ? {color: "#868e9587"} : {}}>
              <EditLogo/>
            </div>
          </button>
        );
      }
      instance.UI.annotationPopup.add({
        type: 'customElement',
        title: 'Edit',
        render: () => <Edit/>

      });
      setDocInstance(instance);


      PDFNet.initialize();
      documentViewer.getTool(instance.Core.Tools.ToolNames.REDACTION).setStyles(() => ({
        FillColor: new Annotations.Color(255, 255, 255)
      }));
      
      
      documentViewer.addEventListener('documentLoaded', () => {
        PDFNet.initialize(); // Only needs to be initialized once
        //update user info
        let newusername = user?.name || user?.preferred_username || "";
        let username = annotationManager.getCurrentUser();
        if(newusername && newusername !== username) annotationManager.setCurrentUser(newusername);

        //update isloaded flag
        //localStorage.setItem("isDocumentLoaded", "true");

        //let crrntDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
        let localDocumentInfo = currentDocument;
        if(Object.entries(individualDoc['file'])?.length <= 0 )
          individualDoc= localDocumentInfo;
        fetchAnnotations(
          requestid,
          (data) => {
            if(data)
              setMerge(true);
            setFetchAnnotResponse(data);
          },
          (error) => {
            console.log('Error:',error);
          }
        );

        fetchAnnotationsInfo(
          requestid,
          (error) => {
            console.log('Error:',error);
          }
        );

        setDocViewer(documentViewer);
        setAnnotManager(annotationManager);
        setAnnots(Annotations);
        setDocViewerMath(Math);

      });
        
    });

    // // add event listener for pop up saving menu
    // document.getElementById("create_response_pdf")?.addEventListener("click", () => {
    //   if(isSavingMenuOpen) {
    //     document.getElementById("saving_menu").style.display = 'none';
    //   } else {
    //     document.getElementById("saving_menu").style.display = 'block';
    //   }
    //   setIsSavingMenuOpen(!isSavingMenuOpen);
    // });

    // // add event listener for hiding saving menu
    // document.body.addEventListener("click", () => {
    //   if(isSavingMenuOpen) {
    //     document.getElementById("saving_menu")?.style.display = 'none';
    //     setIsSavingMenuOpen(!isSavingMenuOpen);
    //   }
    // });
  }, []);

  useEffect(() => {
    docInstance?.Core?.annotationManager.addEventListener('annotationChanged', (annotations, action, info) => {
      // If the event is triggered by importing then it can be ignored
      // This will happen when importing the initial annotations
      // from the server or individual changes from other users

      if (info.imported) return;
      let localDocumentInfo = currentDocument;
      annotations.forEach((annot) => {
        let displayedDoc= getDataFromMappedDoc(annot.getPageNumber());
        let individualPageNo = displayedDoc?.pageMappings?.find((elmt)=>elmt.stitchedPageNo == (annot.getPageNumber()))?.pageNo;                
        annot.setCustomData("originalPageNo", JSON.stringify(individualPageNo - 1))
      });
      let _annotationtring = docInstance.Core.annotationManager.exportAnnotations({annotList: annotations, useDisplayAuthor: true})
      _annotationtring.then(astr=>{
        //parse annotation xml
        let jObj = parser.parseFromString(astr);    // Assume xmlText contains the example XML
        let annots = jObj.getElementsByTagName("annots");
        setRedactionType(annotations[0]?.type);
        if(action === 'delete') {
          let annotObjs = []
          for (let annot of annots[0].children) {
            let displayedDoc= getDataFromMappedDoc(Number(annot.attributes.page)+1);
            let individualPageNo = displayedDoc?.pageMappings?.find((elmt)=>elmt.stitchedPageNo == Number(annot.attributes.page)+1)?.pageNo; 
            if (annot.name === 'redact') {
              annotObjs.push({page: annot.attributes.page, name: annot.attributes.name, type: annot.name});
            } else {
              if(annotations[0].getCustomData("trn-redaction-type") === 'fullPage'){
                deleteAnnotation(
                  requestid,
                  displayedDoc.docId,
                  displayedDoc.version,
                  annot.attributes.name,
                  (data)=>{
                    fetchPageFlag(
                      requestid,
                      (error) => console.log(error)
                    )
                  },
                  (error)=>{console.log(error)},
                  individualPageNo
                );
              }
              else{
                deleteAnnotation(
                  requestid,
                  displayedDoc.docId,
                  displayedDoc.version,
                  annot.attributes.name,
                  (data)=>{},
                  (error)=>{console.log(error)}
                );
              }
            }
          }
          setDeleteQueue(annotObjs);
        }
        else if (action === 'add') {
          //let localInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
          let displayedDoc;
          let individualPageNo;
          if (annotations[0].Subject === 'Redact') {
            let pageSelectionList= [...pageSelections];
            // setRedactionType(annotations[0]?.type);
            annots[0].children?.forEach((annotatn, i)=> {
              displayedDoc= getDataFromMappedDoc(Number(annotatn.attributes.page)+1);
              individualPageNo = displayedDoc?.pageMappings?.find((elmt)=>elmt.stitchedPageNo == (Number(annotatn.attributes.page)+1))?.pageNo;
              if(annotations[i]?.type === 'fullPage') {
                //annotations[i].setCustomData("trn-redaction-type", "fullPage");

                pageSelectionList.push(
                  {
                  "page": Number(individualPageNo),
                  "flagid":3
                  });
              } else {
                pageSelectionList.push(
                  {
                  "page": Number(individualPageNo),
                  "flagid":1
                  });
              }
            })
            setPageSelections(pageSelectionList);
            let annot = annots[0].children[0];
            setNewRedaction({pages: annot.attributes.page, name: annot.attributes.name, astr: astr, type: annot.name});
          } else {
            displayedDoc= getDataFromMappedDoc(Number(annotations[0]?.PageNumber));
            let sections = annotations[0].getCustomData("sections")
            let sectn;
            if (sections) {
              sectn = {
                "foiministryrequestid": requestid
              }
            }
            setSelectedSections([]);
            saveAnnotation(
              requestid,
              displayedDoc.docId,
              displayedDoc.version,
              astr,
              (data)=>{},
              (error)=>{console.log(error)},
              [],
              sectn,
              //pageSelections
            );
          }
        }
      })
      setAnnots(docInstance.Core.Annotations);
    });
  }, [pageMappedDocs]);

  useImperativeHandle(ref, () => ({
    addFullPageRedaction(pageNumber) {
      let height = docViewer.getPageHeight(pageNumber)
      let width = docViewer.getPageWidth(pageNumber)
      let quads = [new docViewerMath.Quad(
        0,
        height,
        width,
        height,
        width,
        0,
        0,
        0,
      )]
      const annot = new annots.RedactionAnnotation({
        PageNumber: pageNumber,
        Quads: quads,
        FillColor: new annots.Color(255, 255, 255),
        IsText: false, // Create either a text or rectangular redaction
        Author: user?.name || user?.preferred_username || ""
      });
      annot.type = "fullPage";
      annot.setCustomData("trn-redaction-type", "fullPage");
      annotManager.addAnnotation(annot);
      annotManager.redrawAnnotation(annot);
      // setModalOpen(true)
    }
  }));


  const checkSavingRedlineButton = (_instance) => {
    let _enableSavingRedline = isReadyForSignOff();

    setEnableSavingRedline(_enableSavingRedline);
    if(_instance) {
      const document = _instance.UI.iframeWindow.document;
      document.getElementById("redline_for_sign_off").disabled = !_enableSavingRedline;
    }
  };

  useEffect(() => {
    checkSavingRedlineButton(docInstance);
  }, [pageFlags]);

  const stitchDocumentsFunc = async (doc) => {
    let docCopy = [...docsForStitcing];
    let removedFirstElement = docCopy?.shift();
    let mappedDocArray = [];
    let mappedDoc = {"docId": 0, "version":0, "division": "", "pageMappings":[] };
    let domParser = new DOMParser()
    for(let i = 0; i < removedFirstElement.file.pagecount; i++){
      let firstDocMappings= {"pageNo": i+1, "stitchedPageNo" : i+1};
      mappedDoc.pageMappings.push(firstDocMappings);
    }
    mappedDocArray.push({"docId": removedFirstElement.file.documentid, "version":removedFirstElement.file.version,
      "division": removedFirstElement.file.divisions[0].divisionid, "pageMappings":mappedDoc.pageMappings});
    assignAnnotations(removedFirstElement.file.documentid, mappedDoc, domParser)
    for (let file of docCopy) {
      mappedDoc = {"docId": 0, "version":0, "division": "", "pageMappings":[ {"pageNo": 0, "stitchedPageNo" : 0} ] };      
      await docInstance.Core.createDocument(file.s3url, {} /* , license key here */).then(async newDoc => {
      const pages = [];
      mappedDoc = {"pageMappings":[ ] };
      let stitchedPageNo= 0;
      for (let i = 0; i < newDoc.getPageCount(); i++) {
        pages.push(i + 1);
        let pageNo = i+1;
        stitchedPageNo= (doc.getPageCount() + (i+1));
        let pageMappings= {"pageNo": pageNo, "stitchedPageNo" : stitchedPageNo};
        mappedDoc.pageMappings.push(pageMappings);
      }
      // Insert (merge) pages
      await doc.insertPages(newDoc, pages);
      mappedDocArray.push({"docId": file.file.documentid, "version":file.file.version,
      "division": file.file.divisions[0].divisionid, "pageMappings":mappedDoc.pageMappings});
      assignAnnotations(file.file.documentid, mappedDoc, domParser)
      })
    }
    setPageMappedDocs(mappedDocArray);
    //setMapper(mappedDocArray);
    //localStorage.setItem("mappedDocArray", JSON.stringify(mappedDocArray));
    // doc?.getFileData()?.then(data => {
    //   const arr = new Uint8Array(data);
    //   const blob = new Blob([arr], { type: doc?.type });
    //   setStitchedDoc(blob);
    // })
    
  }

  const assignAnnotations= async(documentid, mappedDoc, domParser) => {
    if (fetchAnnotResponse[documentid]) {
      let xml = parser.parseFromString(fetchAnnotResponse[documentid]);
      for (let annot of xml.getElementsByTagName("annots")[0].children) {
        let txt = domParser.parseFromString(annot.getElementsByTagName('trn-custom-data')[0].attributes.bytes, 'text/html')
        let customData = JSON.parse(txt.documentElement.textContent);
        let originalPageNo = customData.originalPageNo;
        annot.attributes.page = (mappedDoc.pageMappings.find(p => p.pageNo - 1 === Number(originalPageNo))?.stitchedPageNo - 1)?.toString()
      }
      xml = parser.toString(xml)
      const _annotations = await annotManager.importAnnotations(xml)
      _annotations.forEach(_annotation => {
        annotManager.redrawAnnotation(_annotation);
      });
    }
  }

  useEffect(() => {
    if(docsForStitcing.length > 0 && merge && docViewer){
      const doc = docViewer.getDocument();
      stitchDocumentsFunc(doc);
    }
  }, [docsForStitcing, fetchAnnotResponse, docViewer])


  useEffect(() => {
    //update user name
    let newusername = user?.name || user?.preferred_username || "";
    let username = docViewer?.getAnnotationManager()?.getCurrentUser();
    if(newusername !== username) docViewer?.getAnnotationManager()?.setCurrentUser(newusername);
  }, [user])


  useEffect(() => {
    docViewer?.displayPageLocation(individualDoc['page'], 0, 0);
  }, [individualDoc])


  const saveRedaction = () => {
    setModalOpen(false);
    setSaveDisabled(true);
    let redactionObj= editAnnot? editAnnot : newRedaction;
    let displayedDoc= getDataFromMappedDoc(Number(redactionObj['pages'])+1);
    let individualPageNo = displayedDoc?.pageMappings?.find((elmt)=>elmt.stitchedPageNo == (Number(redactionObj['pages'])+1))?.pageNo;
    let childAnnotation;
    let childSection ="";
    let i = redactionInfo?.findIndex(a => a.annotationname === redactionObj?.name);
    if(i >= 0){
      childSection = redactionInfo[i]?.sections.annotationname;
      childAnnotation = annotManager.getAnnotationById(childSection);

    }
    if(editAnnot){
      let redactionSectionsIds = selectedSections;
      let redactionSections = sections.filter(s => redactionSectionsIds.indexOf(s.id) > -1).map(s => s.section).join(", ");
      childAnnotation.setContents(redactionSections);
      const doc = docViewer.getDocument();
      const pageNumber = parseInt(editAnnot.page) + 1;
      const pageInfo = doc.getPageInfo(pageNumber);
      const pageMatrix = doc.getPageMatrix(pageNumber);
      const pageRotation = doc.getPageRotation(pageNumber);
      childAnnotation.fitText(pageInfo, pageMatrix, pageRotation);
      childAnnotation.setCustomData("sections", JSON.stringify(sections.filter(s => redactionSectionsIds.indexOf(s.id) > -1).map((s) => ({"id":s.id, "section":s.section}))))
      annotManager.redrawAnnotation(childAnnotation);
      let _annotationtring = annotManager.exportAnnotations({annotList: [childAnnotation], useDisplayAuthor: true})
      let sectn = {
        "foiministryrequestid": 1,
      }
      _annotationtring.then(astr=>{
        //parse annotation xml
        let jObj = parser.parseFromString(astr);    // Assume xmlText contains the example XML
        let annots = jObj.getElementsByTagName("annots");
        let annot = annots[0].children[0];
        saveAnnotation(
          requestid,
          // localInfo['file']['documentid'],
          // localInfo['file']['version'],
          individualPageNo.docId,
          1,
          astr,
          (data)=>{},
          (error)=>{console.log(error)},
          [],
          sectn
        );
        setSelectedSections([]);
        redactionInfo.find(r => r.annotationname === redactionObj.name).sections.ids = redactionSectionsIds;
        setEditAnnot(null);
      })
    }
    else {
      saveAnnotation(
        requestid,
        displayedDoc.docId,
        displayedDoc.version,
        newRedaction.astr,
        (data)=>{
          fetchPageFlag(
          requestid,
          (error) => console.log(error)
        )},
        (error)=>{console.log(error)},
        pageSelections
      );
    //}
      // add section annotation
      let astr = parser.parseFromString(redactionObj.astr);
      var sectionAnnotations = [];
      for (const node of astr.getElementsByTagName("annots")[0].children) {
        let redaction = annotManager.getAnnotationById(node.attributes.name);
        let coords = node.attributes.coords;
        let X = coords?.substring(0, coords.indexOf(","));
        const annot = new annots.FreeTextAnnotation();
        annot.PageNumber = redaction?.getPageNumber()
        annot.X = X || redaction.X;
        annot.Y = redaction.Y;
        annot.FontSize = redaction.FontSize;
        annot.Color = 'red';
        annot.StrokeThickness = 0;
        annot.Author = user?.name || user?.preferred_username || "";
        let redactionSectionsIds = defaultSections.length > 0 ? defaultSections : selectedSections
        let redactionSections = sections.filter(s => redactionSectionsIds.indexOf(s.id) > -1);
        let redactionSectionsString = redactionSections.map(s => s.section).join(", ");
        annot.setAutoSizeType('auto');
        annot.setContents(redactionSectionsString);
        annot.setCustomData("parentRedaction", redaction.Id)
        annot.setCustomData("sections", JSON.stringify(redactionSections.map((s) => ({"id":s.id, "section":s.section}))))
        const doc = docViewer.getDocument();
        const pageInfo = doc.getPageInfo(annot.PageNumber);
        const pageMatrix = doc.getPageMatrix(annot.PageNumber);
        const pageRotation = doc.getPageRotation(annot.PageNumber);
        annot.fitText(pageInfo, pageMatrix, pageRotation);
        if(redaction.type == 'fullPage')
          annot.setCustomData("trn-redaction-type", "fullPage");

        sectionAnnotations.push(annot);
        // annotManager.addAnnotation(annot);
        // annotManager.redrawAnnotation(annot)

        // setNewRedaction(null)
        redactionInfo.push({annotationname: redactionObj.name, sections: {annotationname: annot.Id, ids: redactionSectionsIds}});
        for(let section of redactionSections) {
          section.count++;
        }
      }
      annotManager.addAnnotations(sectionAnnotations);
      // Always redraw annotation
      sectionAnnotations.forEach(a => annotManager.redrawAnnotation(a));
    }
    setNewRedaction(null)
  }

  const editAnnotation = (annotationManager, selectedAnnot) =>{
    selectedAnnot.then(astr=>{
      //parse annotation xml
      let jObj = parser.parseFromString(astr);    // Assume xmlText contains the example XML
      let annots = jObj.getElementsByTagName("annots");
      let annot = annots[0].children[0];
      setEditAnnot({page: annot.attributes.page, name: annot.attributes.name, astr: astr, type: annot.name});
    })
    setAnnotManager(annotationManager);
  }

  useEffect(() => {
    if (editAnnot) {
      setSelectedSections(redactionInfo.find(redaction => redaction.annotationname === editAnnot.name).sections?.ids?.map(id => id))
      setModalOpen(true);
    }
  }, [editAnnot])

  const getDataFromMappedDoc = (page) => {
    //let localMappedDocArray = JSON.parse(localStorage.getItem("mappedDocArray"));
    //let doc = pageMappedDocs?.find((mappedDoc)=>{
    let doc = pageMappedDocs?.find((mappedDoc)=>{
      return mappedDoc.pageMappings?.find((mappedPage)=>mappedPage.stitchedPageNo == page)
    });
    return doc;
  }

  useEffect(() => {
    while (deleteQueue?.length > 0) {
      let annot = deleteQueue.pop();
      if (annot && annot.name !== newRedaction?.name) {
        //let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
        //let localDocumentInfo = currentDocument;
        let displayedDoc= getDataFromMappedDoc(Number(annot.page)+1);
        deleteRedaction(
          requestid,
          displayedDoc.docId,
          displayedDoc.version,
          annot.name,
          (data)=>{
            fetchPageFlag(
              requestid,
              (error) => console.log(error)
            )
          },
          (error)=>{console.log(error)},
          (Number(annot.page))+1
        );

        if (annot.type === 'redact' && redactionInfo) {
          let i = redactionInfo.findIndex(a => a.annotationname === annot.name);
          if(i >= 0){
            let childSections = redactionInfo[i].sections?.annotationname;
            let sectionids = redactionInfo[i].sections?.ids;
            if(sectionids){
              for(let id of sectionids) {
                sections.find(s => s.id === id).count--;
              }
            }
            redactionInfo.splice(i, 1);
            annotManager.deleteAnnotation(annotManager.getAnnotationById(childSections));
          }
        }
      }
      setNewRedaction(null)
    }
  }, [deleteQueue, newRedaction])


  const cancelRedaction = () => {
    setModalOpen(false);
    setSelectedSections([]);
    setSaveDisabled(true);
    if(newRedaction != null) {
      // annotManager.deleteAnnotation(annotManager.getAnnotationById(newRedaction.name));
      let astr = parser.parseFromString(newRedaction.astr,"text/xml");
      for (const node of astr.getElementsByTagName("annots")[0].children) {
        annotManager.deleteAnnotation(annotManager.getAnnotationById(node.attributes.name));
      }
    }
    setEditAnnot(null);
    // setDeleteAnnot(newRedaction)
  }

  const saveDefaultSections = () => {
    setModalOpen(false);
    setDefaultSections(selectedSections);
  }

  const clearDefaultSections = () => {
    setDefaultSections([]);
  }

  useEffect(() => {
    if (newRedaction) {
      if (defaultSections.length > 0) {
        saveRedaction();
      } else {
        setModalOpen(true);
      }
    }
  }, [defaultSections, newRedaction])

  const handleSectionSelected = (e) => {
    let sectionID = e.target.getAttribute('data-sectionid');
    if (e.target.checked) {
      selectedSections.push(Number(sectionID));
    } else {
      selectedSections.splice(selectedSections.indexOf(Number(sectionID)), 1);
    }
    setSaveDisabled(selectedSections.length === 0);
  }

  const AntSwitch = styled(Switch)(({ theme }) => ({
    width: 28,
    height: 16,
    padding: 0,
    display: 'flex',
    '&:active': {
      '& .MuiSwitch-thumb': {
        width: 15,
      },
      '& .MuiSwitch-switchBase.Mui-checked': {
        transform: 'translateX(9px)',
      },
    },
    '& .MuiSwitch-switchBase': {
      padding: 2,
      '&.Mui-checked': {
        transform: 'translateX(12px)',
        color: '#fff',
        '& + .MuiSwitch-track': {
          opacity: 1,
          backgroundColor: theme.palette.mode === 'dark' ? '#177ddc' : '#38598a',
        },
      },
    },
    '& .MuiSwitch-thumb': {
      boxShadow: '0 2px 4px 0 rgb(0 35 11 / 20%)',
      width: 12,
      height: 12,
      borderRadius: 6,
      transition: theme.transitions.create(['width'], {
        duration: 200,
      }),
    },
    '& .MuiSwitch-track': {
      borderRadius: 16 / 2,
      opacity: 1,
      backgroundColor:
        theme.palette.mode === 'dark' ? '#177ddc' : '#38598a',
      boxSizing: 'border-box',
    },
  }));

  const changeModalSort = (e) => {
    setModalSortNumbered(e.target.checked)
    // setSections(sections.sort((a, b) => e.target.checked ? (modalSortAsc ? a.id - b.id : b.id - a.id) : b.count - a.count))
  }

  const changeSortOrder = (e) => {
    if (modalSortNumbered) {
      setModalSortAsc(!modalSortAsc)
      // setSections(sections.sort((a, b) => !modalSortAsc ? a.id - b.id : b.id - a.id))
    }
  }

  const saveRedlineDocument = (_instance) => {
    let arr = [];
    const divisions = [...new Map(documentList.reduce((acc, file) => [...acc, ...new Map(file.divisions.map((division) => [division.divisionid, division]))], arr)).values()];
    const downloadType = 'pdf';
    // console.log("divisions: ", divisions);

    let newDocList = [];
    for(let div of divisions) {
      let divDocList = documentList.filter(doc => doc.divisions.map(d => d.divisionid).includes(div.divisionid));
      let newDivObj = {"divisionid": div.divisionid, "documentlist": divDocList};
      newDocList.push(newDivObj);
    }
    // console.log("divDocList: ", newDocList);

    getFOIS3DocumentRedlinePreSignedUrl(
      requestid,
      newDocList,
      async (res) => {
        // console.log("getFOIS3DocumentRedlinePreSignedUrl: ", res);

        let domParser = new DOMParser()
        for(let divObj of res.divdocumentList) {
          let stitchedDocObj = null;
          let stitchedDocPath = divObj.s3path_save;
          let stitchedXMLArray = [];

          let docCount = 0;
          let totalPageCount = 0;
          for(let doc of divObj.documentlist) {
            docCount++;

            // update annotation xml
            if(divObj.annotationXML[doc.documentid]) {
              let updatedXML = divObj.annotationXML[doc.documentid].map(x => {
                // get original/individual page num
                let customfield = parser.parseFromString(x).children.find(xmlfield => xmlfield.name == 'trn-custom-data');
                let txt = domParser.parseFromString(customfield.attributes.bytes, 'text/html');
                let customData = JSON.parse(txt.documentElement.textContent);
                let originalPageNo = parseInt(customData.originalPageNo);

                // page num from annot xml
                let y = x.split('page="');
                let z = y[1].split('"');
                let oldPageNum = 'page="'+z[0]+'"';
                let newPage = 'page="'+(originalPageNo+totalPageCount)+'"';
                x = x.replace(oldPageNum, newPage);
                return x;
              });

              stitchedXMLArray.push(updatedXML.join());
            }
            totalPageCount += doc.pagecount;

            await _instance.Core.createDocument(doc.s3path_load, {loadAsPDF:true}).then(async docObj => {

              // ************** starts here ****************
              if(docCount == 1) {
                stitchedDocObj = docObj;
              } else {
                // create an array containing 1…N
                let pages = Array.from({ length: doc.pagecount }, (v, k) => k + 1);
                let pageIndexToInsert = stitchedDocObj?.getPageCount() + 1;
                await stitchedDocObj.insertPages(docObj, pages, pageIndexToInsert);
              }
  
              // save to s3 once all doc stitched
              if(docCount == divObj.documentlist.length) {
                // console.log("s3path_save", stitchedDocPath);
                let xfdfString = '<?xml version="1.0" encoding="UTF-8" ?><xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve"><annots>'+stitchedXMLArray.join()+'</annots></xfdf>';
                stitchedDocObj.getFileData({
                  // saves the document with annotations in it
                  "xfdfString": xfdfString,
                  "downloadType": downloadType
                }).then(async _data => {
                  const _arr = new Uint8Array(_data);
                  const _blob = new Blob([_arr], { type: 'application/pdf' });
                  // const url = URL.createObjectURL(blob);
                  // window.open(url);
      
                  await saveFilesinS3(
                    {filepath: stitchedDocPath},
                    _blob,
                    (_res) => {
                      // ######### call another process for zipping and generate download here ##########
                      // console.log(_res);
                    },
                    (_err) => {
                      console.log(_err);
                    }
                  );
                });
              }

            });
          }
        }
      },
      (error) => {
          console.log('Error fetching document:',error);
      }
    );
  }

  const saveRedlineDoc = () => {
    setRedlineModalOpen(false);
    saveRedlineDocument(docInstance);
  }

  const cancelSaveRedlineDoc = () => {
    setRedlineModalOpen(false);
  }

  return (
    <div>
    {/* <button onClick={gotopage}>Click here</button> */}
    <div className="webviewer" ref={viewer}></div>
    <ReactModal
        initWidth={650}
        initHeight={700}
        minWidth ={400}
        minHeight ={200}
        className={"state-change-dialog"}
        onRequestClose={cancelRedaction}
        isOpen={modalOpen}>
        <DialogTitle disableTypography id="state-change-dialog-title">
          <h2 className="state-change-header">FOIPPA Sections</h2>
          <IconButton className="title-col3" onClick={cancelRedaction}>
            <i className="dialog-close-button">Close</i>
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent className={'dialog-content-nomargin'}>
          <DialogContentText id="state-change-dialog-description" component={'span'} >
            <Stack direction="row-reverse" spacing={1} alignItems="center">
              <button onClick={changeSortOrder} style={{border: "none", backgroundColor: "white", padding: 0}} disabled={!modalSortNumbered}>
                {modalSortAsc ?
                  <FontAwesomeIcon icon={faArrowUp} size='1x' color="#666666"/> :
                  <FontAwesomeIcon icon={faArrowDown} size='1x' color="#666666"/>
                }
              </button>
              <Typography>Numbered Order</Typography>
              <AntSwitch
              onChange={changeModalSort}
               checked={modalSortNumbered}
                inputProps={{ 'aria-label': 'ant design' }} />
              <Typography>Most Used</Typography>
            </Stack>
            <div style={{overflowY: 'scroll'}}>
              <List className="section-list">
                {sections?.sort((a, b) => modalSortNumbered ? (modalSortAsc ? a.id - b.id : b.id - a.id) : b.count - a.count).map((section, index) =>
                  <ListItem key={"list-item" + section.id}>
                    <input
                        type="checkbox"
                        className="section-checkbox"
                        key={"section-checkbox" + section.id}
                        id={"section" + section.id}
                        data-sectionid={section.id}
                        onChange={handleSectionSelected}
                        defaultChecked={selectedSections.includes(section.id)}
                    />
                    <label key={"list-label" + section.id} className="check-item">
                      {section.section + ' - ' + section.description}
                    </label>
                  </ListItem>
                )}
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
            onClick={saveRedaction}
            disabled={saveDisabled}
          >
            Select Code(s)
          </button>
          {defaultSections.length > 0 ?
            <button className="btn-bottom btn-cancel" onClick={clearDefaultSections}>
              Clear Defaults
            </button>
            :
            <button className="btn-bottom btn-cancel" onClick={saveDefaultSections}>
              Save as Default
            </button>
          }
          <button className="btn-bottom btn-cancel" onClick={cancelRedaction}>
            Cancel
          </button>
        </DialogActions>
    </ReactModal>
    <ReactModal
        initWidth={800}
        initHeight={300}
        minWidth ={600}
        minHeight ={250}
        className={"state-change-dialog"}
        onRequestClose={cancelRedaction}
        isOpen={redlineModalOpen}>
        <DialogTitle disableTypography id="state-change-dialog-title">
          <h2 className="state-change-header">Redline for Sign Off</h2>
          <IconButton className="title-col3" onClick={cancelSaveRedlineDoc}>
            <i className="dialog-close-button">Close</i>
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent className={'dialog-content-nomargin'}>
          <DialogContentText id="state-change-dialog-description" component={'span'} >
            <span className="confirmation-message">
              Are you sure want to create the redline PDF for ministry sign off? <br></br>
            </span>
          </DialogContentText>
        </DialogContent>
        <DialogActions className="foippa-modal-actions">
          <button className="btn-bottom btn-save btn" onClick={saveRedlineDoc} disabled={!enableSavingRedline}>
            Create Redline PDF
          </button>
          <button className="btn-bottom btn-cancel" onClick={cancelSaveRedlineDoc}>
            Cancel
          </button>
        </DialogActions>
    </ReactModal>
  </div>
  );
})

export default Redlining;