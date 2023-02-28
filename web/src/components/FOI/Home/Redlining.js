import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import React, { useRef, useEffect,useState } from 'react';
import WebViewer from '@pdftron/webviewer';
import XMLParser from 'react-xml-parser';
import ReactModal from 'react-modal-resizable-draggable';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';
import CloseIcon from '@material-ui/icons/Close';
import IconButton from "@material-ui/core/IconButton";
import editLogo from "../../../assets/images/edit-icon.png";


import { fetchAnnotations, fetchAnnotationsInfo, saveAnnotation, deleteAnnotation, fetchSections } from '../../../apiManager/services/docReviewerService';
import { getFOIS3DocumentPreSignedUrl } from '../../../apiManager/services/foiOSSService';

const Redlining = ({
  currentPageInfo,
  user
}) =>{

  const viewer = useRef(null);
  // const pdffile = '/files/PDFTRON_about.pdf';
  // const [pdffile, setpdffile] = useState((currentPageInfo.file['filepath'] + currentPageInfo.file['filename']));
  const [pdffile, setpdffile] = useState((currentPageInfo.file['filepath']));
  const [docViewer, setDocViewer] = useState(null);
  const [annotManager, setAnnotManager] = useState(null);
  const [annots, setAnnots] = useState(null);
  const [docInstance, setDocInstance] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [newRedaction, setNewRedaction] = useState(null);
  const [saveAnnot, setSaveAnnot] = useState(null);
  const [deleteAnnot, setDeleteAnnot] = useState(null);
  const [sections, setSections] = useState([]);
  const [selectedSections, setSelectedSections] = useState([]);
  const [defaultSections, setDefaultSections] = useState(false);
  const [parentAnnotation, setParentAnnotation] = useState("");
  const [editAnnot, setEditAnnot] = useState(null);
  const [redactionInfo, setRedactionInfo] = useState([]);
  //xml parser
  const parser = new XMLParser();

  // const [storedannotations, setstoreannotations] = useState(localStorage.getItem("storedannotations") || [])
  // if using a class, equivalent of componentDidMount
  useEffect(() => {
    let currentDocumentS3Url = localStorage.getItem("currentDocumentS3Url");

    fetchSections(
      (data) => setSections(data),
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
      },
      viewer.current,
    ).then((instance) => {
      const { documentViewer, annotationManager, Annotations,  PDFNet, Search } = instance.Core;
      instance.UI.annotationPopup.add({
        type: 'actionButton',
        img: editLogo,
        onClick: () => editAnnotation(annotationManager, Annotations, annotationManager.exportAnnotations({annotList: annotationManager.getSelectedAnnotations(), useDisplayAuthor: true})),
      });
      setDocInstance(instance);


      //const { documentViewer, annotationManager, Annotations,  PDFNet, Search } = instance.Core;
      PDFNet.initialize();
      documentViewer.addEventListener('documentLoaded', () => {
        PDFNet.initialize(); // Only needs to be initialized once

        //update user info
        let newusername = user?.name || user?.preferred_username || "";
        let username = annotationManager.getCurrentUser();
        if(newusername && newusername !== username) annotationManager.setCurrentUser(newusername);

        //update isloaded flag
        localStorage.setItem("isDocumentLoaded", "true");

        let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
        fetchAnnotations(
          localDocumentInfo['file']['documentid'],
          localDocumentInfo['file']['version'],
          (data) => {
            if (data.length > 0) {
              const _annotations = annotationManager.importAnnotations(data)
              console.log("Check Annot:",_annotations)
              _annotations.then(_annotation => {
                annotationManager.redrawAnnotation(_annotation);
              });
              documentViewer.displayPageLocation(localDocumentInfo['page'], 0, 0)
            }
          },
          (error) => {
            console.log('error');
          }
        );

        fetchAnnotationsInfo(
          localDocumentInfo['file']['documentid'],
          localDocumentInfo['file']['version'],
          (data) => {
            if (data.length > 0) {
              setRedactionInfo(data);
            }
          },
          (error) => {
            console.log('error');
          }
        );

        setDocViewer(documentViewer);
      });



      // documentViewer.addEventListener('pageComplete', (pageNumber, canvas) => {
      //   // here it's guaranteed that page {pageNumber} is fully rendered
      //   // you can get or set pixels on the canvas, etc

      //   console.log(`Page Loaded # ${pageNumber}`)
      // })


      // //update current page
      // documentViewer.addEventListener('pageNumberUpdated', (pageNumber) => {
      //   console.log("current page:");
      //   console.log(pageNumber);
      //   setCurrentPageInfo({'file': currentPageInfo['file'], 'page': pageNumber});

      //   let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
      //   localDocumentInfo.page = pageNumber;
      //   localStorage.setItem("currentDocumentInfo", JSON.stringify(localDocumentInfo));
      // });


      // later save the annotation data as transaction command for every change
      annotationManager.addEventListener('annotationChanged', (annotations, action, info) => {
        // If the event is triggered by importing then it can be ignored
        // This will happen when importing the initial annotations
        // from the server or individual changes from other users
        if (info.imported) return;

        console.log(action)

        // annotations.forEach((annot) => {
        //   console.log('annotation page number', annot.PageNumber);
        //   console.log(annot)
        //   console.log(JSON.stringify(annot))
        // });

        let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));

        let _annotationtring = annotationManager.exportAnnotations({annotList: annotations, useDisplayAuthor: true})
        // let _annotationtring = annotationManager.exportAnnotationCommand()
        _annotationtring.then(astr=>{
          //parse annotation xml
          let jObj = parser.parseFromString(astr);    // Assume xmlText contains the example XML
          let annots = jObj.getElementsByTagName("annots");
          let annot = annots[0].children[0];
          console.log("annot",annot)
          
          if(action === 'delete') {      
            console.log("",annot.attributes)      
            setDeleteAnnot({page: annot.attributes.page, name: annot.attributes.name, type: annot.name});
          } else {            
            setSaveAnnot({page: annot.attributes.page, name: annot.attributes.name, astr: astr, type: annot.name});
          }
        })

        // let allannotations = annotationManager.exportAnnotations({annotList: annotationManager.getAnnotationsList(), useDisplayAuthor: true})
        // allannotations.then(astr=>{
        //   console.log(astr)
        //   // localStorage.setItem("savedannotations",astr)
        // })
        setAnnotManager(annotationManager);
        setAnnots(Annotations);

      });

    });

  }, []);

  useEffect(() => {
    //update user name
    let newusername = user?.name || user?.preferred_username || "";
    let username = docViewer?.getAnnotationManager()?.getCurrentUser();
    if(newusername !== username) docViewer?.getAnnotationManager()?.setCurrentUser(newusername);
  }, [user])

  useEffect(() => {
    //load a new document
    if(pdffile !== (currentPageInfo.file['filepath'])) {
      localStorage.setItem("isDocumentLoaded", "false");
      setpdffile(currentPageInfo.file['filepath']);

      let ministryrequestid = "1";
      getFOIS3DocumentPreSignedUrl(
          currentPageInfo.file['documentid'],
          (data) => {
              console.log("s3:");
              console.log(data);
              docInstance?.UI?.loadDocument(data);
          },
          (error) => {
              console.log('error123');
              console.log(error);
          }
        );
    }

    //change page from document selector
    //console.log("page changed")
    localStorage.setItem("isDocumentLoaded", "true");
    let isDocLoaded = localStorage.getItem("isDocumentLoaded");
    if(isDocLoaded === 'true')
      docViewer?.displayPageLocation(currentPageInfo['page'], 0, 0);
  }, [currentPageInfo])

  const saveRedaction = () => {
    setModalOpen(false);
    console.log("Inside Save Redaction Method!!",newRedaction)
    setParentAnnotation(newRedaction.name);
    let redaction = annotManager.getAnnotationById(newRedaction.name);
    console.log("redaction",redaction)
    let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
    // let sectn = {
    //   "foiministryrequestid": 1,
    //   "ids": sections.filter(s => selectedSections?.indexOf(s.sectionid.toString()) > -1).map((s) => ({"id":s.sectionid, "section":s.section})),
    //   "parts": [{"annotation":parentAnnotation}]    
    // }
    saveAnnotation(
      localDocumentInfo['file']['documentid'],
      localDocumentInfo['file']['version'],
      newRedaction.page,
      newRedaction.name,
      newRedaction.astr,
      (data)=>{console.log(data)},
      (error)=>{console.log(error)}
    );

    // add section annotation
    let parser = new DOMParser();
    var astr = parser.parseFromString(newRedaction.astr,"text/xml");
    console.log("redactt!",astr.getElementsByTagName("redact"))
    var coords = astr.getElementsByTagName("redact")[0]?.attributes.getNamedItem('coords')?.value;
    var X = coords?.substring(0, coords.indexOf(","));
    const annot = new annots.FreeTextAnnotation();
    annot.PageNumber = redaction.getPageNumber()
    annot.X = X || redaction.X;
    annot.Y = redaction.Y;
    annot.FontSize = redaction.FontSize;
    annot.Color = 'red';
    annot.StrokeThickness = 0;
    annot.Author = user?.name || user?.preferred_username || "";
    console.log("selectedSections",selectedSections)
    var redactionSections = sections.filter(s => selectedSections.indexOf(s.sectionid.toString()) > -1).map(s => s.section).join(", ");
    console.log("redactionSections",redactionSections)
    annot.setAutoSizeType('auto');
    annot.setContents(redactionSections);
    
    annotManager.addAnnotation(annot);
    // Always redraw annotation
    annotManager.redrawAnnotation(annot);
    // setNewRedaction(null)
    if (!defaultSections) {
      setSelectedSections([]);
    }
    redactionInfo.push({annotationname: newRedaction.name, sections: {annotationname: annot.Id}});
  }

  const editAnnotation = (annotationManager, Annotations, selectedAnnot) =>{
    setModalOpen(true);
    selectedAnnot.then(astr=>{
      //parse annotation xml
      let jObj = parser.parseFromString(astr);    // Assume xmlText contains the example XML
      let annots = jObj.getElementsByTagName("annots");
      let annot = annots[0].children[0];
      console.log("annot:",annot);
      setEditAnnot({page: annot.attributes.page, name: annot.attributes.name, astr: astr, type: annot.name});
    })
    setAnnotManager(annotationManager);
    setAnnots(Annotations);
  }

  useEffect(() => {
    console.log("editAnnot:",editAnnot);
    if (editAnnot)
      setNewRedaction(editAnnot)
  }, [editAnnot])

  useEffect(() => {
    if (deleteAnnot && deleteAnnot.name !== newRedaction?.name) {
      let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
      deleteAnnotation(
        localDocumentInfo['file']['documentid'],
        localDocumentInfo['file']['version'],
        deleteAnnot.name,
        (data)=>{console.log(data)},
        (error)=>{console.log(error)}
      );
      setNewRedaction(null)
      
      if (deleteAnnot.type === 'redact' && redactionInfo) {
        let i = redactionInfo.findIndex(a => a.annotationname === deleteAnnot.name);
        if(i >= 0){
          let childSections = redactionInfo[i].sections.annotationname;
          redactionInfo.splice(i, 1);
          annotManager.deleteAnnotation(annotManager.getAnnotationById(childSections));
        }
      }
    }
    setDeleteAnnot(null)
  }, [deleteAnnot, newRedaction])

  useEffect(() => {
    if (saveAnnot) {
      // if new redaction is not null, that means it is a section annotation
      let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
      if (newRedaction === null) {
        setParentAnnotation(saveAnnot.name);
        if (saveAnnot.type === 'redact') {
          setNewRedaction(saveAnnot);
          if (!defaultSections) { // newRedaction effect hook automatically calls saveRedaction if defaultSections is true
            setModalOpen(true);
          }
        } else {
          saveAnnotation(
            localDocumentInfo['file']['documentid'],
            localDocumentInfo['file']['version'],
            saveAnnot.page,
            saveAnnot.name,
            saveAnnot.astr,
            (data)=>{console.log(data)},
            (error)=>{console.log(error)}
          );
        }
      } else {
        console.log("SECTIONS:",sections);
        console.log("SELECTEDSECTIONS:",selectedSections);
        let sectn = {
          "foiministryrequestid": 1,
          "ids": sections.filter(s => selectedSections.indexOf(s.sectionid.toString()) > -1).map((s) => ({"id":s.sectionid, "section":s.section})),
          "redactannotation": parentAnnotation    
        }
        // add the parent annotation info to section annotation
        setNewRedaction(null)
        saveAnnotation(
          localDocumentInfo['file']['documentid'],
          localDocumentInfo['file']['version'],
          saveAnnot.page,
          saveAnnot.name,
          saveAnnot.astr,
          (data)=>{console.log(data)},
          (error)=>{console.log(error)},
          sectn
        );
      }
    }
    setSaveAnnot(null);
  }, [saveAnnot])

  const cancelRedaction = () => {
    setModalOpen(false);
    if (!defaultSections) {
      setSelectedSections([]);
    }
    console.log("saveAnnot in cancel:",saveAnnot)
    console.log("newRedaction in cancel:",newRedaction)
    if(newRedaction != null)
      annotManager.deleteAnnotation(annotManager.getAnnotationById(newRedaction.name));
    setNewRedaction(null)
    // setDeleteAnnot(newRedaction)
  }

  const saveDefaultSections = () => {
    setModalOpen(false);
    setDefaultSections(true);
  }

  useEffect(() => {
    if (defaultSections && newRedaction) {
      saveRedaction();
    }
  }, [defaultSections, newRedaction])

  const handleSectionSelected = (e) => {
    var sectionID = e.target.getAttribute('data-sectionid');
    if (e.target.checked) {
      selectedSections.push(sectionID);
    } else {
      selectedSections.splice(selectedSections.indexOf(sectionID), 1);
    }
  }


  return (
    <div>
      {/* <button onClick={gotopage}>Click here</button> */}
      <div className="webviewer" ref={viewer}></div>
      <ReactModal 
          initWidth={800} 
          initHeight={400} 
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
              {/* <div style={{overflowY: 'scroll', height: 'calc(100% - 318px)'}}> */}
                <List className="section-list">
                  {sections.map((section, index) => 
                    <ListItem key={section.sectionid}>
                      <label key={index} className="check-item">
                        <input id="section-checkbox"
                          type="checkbox"
                          className="checkmark"
                          key={section.sectionid}
                          data-sectionid={section.sectionid}
                          onChange={handleSectionSelected}
                          defaultChecked={selectedSections.includes(section.sectionid.toString())}
                        />
                      </label>
                      {section.section + ' - ' + section.description}
                    </ListItem>
                  )}
                </List>
              {/* </div> */}
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
            >
              Select Code(s)
            </button>
            <button className="btn-bottom btn-cancel" onClick={saveDefaultSections}>
              Save as Default
            </button>
            <button className="btn-bottom btn-cancel" onClick={cancelRedaction}>
              Cancel
            </button>
          </DialogActions>
      </ReactModal>
    </div>
  );

}

export default Redlining;