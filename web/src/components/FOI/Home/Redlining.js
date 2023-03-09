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
import {ReactComponent as EditLogo} from "../../../assets/images/icon-pencil-line.svg";
import { fetchAnnotations, fetchAnnotationsInfo, saveAnnotation, deleteAnnotation, fetchSections } from '../../../apiManager/services/docReviewerService';
import { getFOIS3DocumentPreSignedUrl } from '../../../apiManager/services/foiOSSService';
import { element } from 'prop-types';

const Redlining = ({
  currentPageInfo,
  user,
  requestid
}) =>{

  const viewer = useRef(null);
  const saveButton = useRef(null);
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
  const [defaultSections, setDefaultSections] = useState([]);
  const [parentAnnotation, setParentAnnotation] = useState("");
  const [editAnnot, setEditAnnot] = useState(null);
  const [redactionInfo, setRedactionInfo] = useState([]);
  const [saveDisabled, setSaveDisabled]= useState(true);
  //xml parser
  const parser = new XMLParser();

  // const [storedannotations, setstoreannotations] = useState(localStorage.getItem("storedannotations") || [])
  // if using a class, equivalent of componentDidMount
  useEffect(() => {
    let currentDocumentS3Url = localStorage.getItem("currentDocumentS3Url");

    fetchSections(
      requestid,
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
      instance.UI.disableElements(['toolbarGroup-Edit']);
      instance.UI.disableElements(['toolbarGroup-Insert']);
      instance.UI.disableElements(['toolbarGroup-Forms']);
      instance.UI.disableElements(['toolbarGroup-FillAndSign']);
      instance.UI.disableElements([ 'thumbDelete' ]);
      instance.UI.disableElements([ 'deletePage' ]);
      instance.UI.disableElements([ 'replacePage' ]);
      instance.UI.disableElements([ 'insertPage' ]);
      
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
      documentViewer.getTool(instance.Core.Tools.ToolNames.REDACTION).setStyles(currentStyle => ({
        FillColor: new Annotations.Color(255, 255, 255)
      }));
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

        let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
        let _annotationtring = annotationManager.exportAnnotations({annotList: annotations, useDisplayAuthor: true})
        _annotationtring.then(astr=>{
          //parse annotation xml
          let jObj = parser.parseFromString(astr);    // Assume xmlText contains the example XML
          let annots = jObj.getElementsByTagName("annots");
          let annot = annots[0].children[0];

          if(action === 'delete') {
            setDeleteAnnot({page: annot.attributes.page, name: annot.attributes.name, type: annot.name});
          } 
          else if (action === 'add') {
            setSaveAnnot({page: annot.attributes.page, name: annot.attributes.name, astr: astr, type: annot.name});
          }
        })
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
              docInstance?.UI?.loadDocument(data);
          },
          (error) => {
              console.log('Error fetching document:',error);
          }
        );
    }
    //change page from document selector
    let isDocLoaded = localStorage.getItem("isDocumentLoaded");
    if(isDocLoaded === 'true')
      docViewer?.displayPageLocation(currentPageInfo['page'], 0, 0);
  }, [currentPageInfo])

  const saveRedaction = () => {
    setModalOpen(false);
    let redactionObj= editAnnot? editAnnot : newRedaction;
    let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
    let redaction = annotManager.getAnnotationById(redactionObj.name);
    let childRedaction;
    let childSection ="";
    let i = redactionInfo.findIndex(a => a.annotationname === redactionObj.name);
    if(i >= 0){
      childSection = redactionInfo[i].sections.annotationname;
      childRedaction = annotManager.getAnnotationById(childSection);

    }
    if(editAnnot){
      let redactionSectionsIds = (defaultSections.length > 0 ? defaultSections : selectedSections);
      var redactionSections = sections.filter(s => redactionSectionsIds.indexOf(s.id) > -1).map(s => s.section).join(", ");
      childRedaction.setContents(redactionSections);
      const doc = docViewer.getDocument();
      const pageNumber = parseInt(editAnnot.page) + 1;
      const pageInfo = doc.getPageInfo(pageNumber);
      const pageMatrix = doc.getPageMatrix(pageNumber);
      const pageRotation = doc.getPageRotation(pageNumber);
      childRedaction.fitText(pageInfo, pageMatrix, pageRotation);
      annotManager.redrawAnnotation(childRedaction);
      let _annotationtring = annotManager.exportAnnotations({annotList: [childRedaction], useDisplayAuthor: true})
      let sectn = {
        "foiministryrequestid": 1,
        "ids": sections.filter(s => (defaultSections.length > 0 ? defaultSections : selectedSections).indexOf(s.id) > -1).map((s) => ({"id":s.id, "section":s.section})),
        "redactannotation": editAnnot.name
      }
      _annotationtring.then(astr=>{
        //parse annotation xml
        let jObj = parser.parseFromString(astr);    // Assume xmlText contains the example XML
        let annots = jObj.getElementsByTagName("annots");
        let annot = annots[0].children[0];
        saveAnnotation(
          localDocumentInfo['file']['documentid'],
          localDocumentInfo['file']['version'],
          childRedaction.page,
          childSection,
          astr,
          (data)=>{console.log(data)},
          (error)=>{console.log(error)},
          sectn
        );
        setSelectedSections([]);
        redactionInfo.find(r => r.annotationname === redactionObj.name).sections.ids = redactionSectionsIds;
        setEditAnnot(null);
      })
    }
    else {
      saveAnnotation(
        localDocumentInfo['file']['documentid'],
        localDocumentInfo['file']['version'],
        newRedaction.page,
        newRedaction.name,
        newRedaction.astr,
        (data)=>{console.log(data)},
        (error)=>{console.log(error)}
      );
    //}
    // add section annotation
    let parser = new DOMParser();
    var astr = parser.parseFromString(redactionObj.astr,"text/xml");
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
    let redactionSectionsIds = (defaultSections.length > 0 ? defaultSections : selectedSections);
    var redactionSections = sections.filter(s => redactionSectionsIds.indexOf(s.id) > -1).map(s => s.section).join(", ");
    annot.setAutoSizeType('auto');
    annot.setContents(redactionSections);
    const doc = docViewer.getDocument();
    const pageInfo = doc.getPageInfo(annot.PageNumber);
    const pageMatrix = doc.getPageMatrix(annot.PageNumber);
    const pageRotation = doc.getPageRotation(annot.PageNumber);
    annot.fitText(pageInfo, pageMatrix, pageRotation);

    annotManager.addAnnotation(annot);
    // Always redraw annotation
    annotManager.redrawAnnotation(annot);
    // setNewRedaction(null)
    redactionInfo.push({annotationname: redactionObj.name, sections: {annotationname: annot.Id, ids: redactionSectionsIds}});    
    for(let id of redactionSectionsIds) {
      sections.find(s => s.id === id).count++;
    }
    }
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
          let sectionids = redactionInfo[i].sections.ids;
          for(let id of sectionids) {
            sections.find(s => s.id === id).count--;
          }
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
          if (defaultSections.length === 0) { // newRedaction effect hook automatically calls saveRedaction if defaultSections is set
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
        let sectn = {
          "foiministryrequestid": requestid,
          "ids": sections.filter(s => (defaultSections.length > 0 ? defaultSections : selectedSections).indexOf(s.id) > -1).map((s) => ({"id":s.id, "section":s.section})),
          "redactannotation": parentAnnotation
        }
        // add the parent annotation info to section annotation
        setNewRedaction(null)
        setSelectedSections([]);
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
    setSelectedSections([]);
    if(newRedaction != null)
      annotManager.deleteAnnotation(annotManager.getAnnotationById(newRedaction.name));
    setNewRedaction(null);
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
    if (defaultSections.length > 0 && newRedaction) {
      saveRedaction();
    }
  }, [defaultSections, newRedaction])

  const handleSectionSelected = (e) => {
    var sectionID = e.target.getAttribute('data-sectionid');
    if (e.target.checked) {
      selectedSections.push(Number(sectionID));
    } else {
      selectedSections.splice(selectedSections.indexOf(Number(sectionID)), 1);
    }
    setSaveDisabled(selectedSections.length === 0);
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
              {/* <div style={{overflowY: 'scroll', height: 'calc(100% - 318px)'}}> */}
                <List className="section-list">
                  {sections.sort((a, b) => b.count - a.count).map((section, index) =>
                    <ListItem key={section.id}>
                      <input
                          type="checkbox"
                          className="section-checkbox"
                          key={section.id}
                          id={"section" + section.id}
                          data-sectionid={section.id}
                          onChange={handleSectionSelected}
                          defaultChecked={selectedSections.includes(section.id)}
                      />
                      <label key={index} className="check-item">
                        {section.section + ' - ' + section.description}
                      </label>
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
    </div>
  );

}

export default Redlining;