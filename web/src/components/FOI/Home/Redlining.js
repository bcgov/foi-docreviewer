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
import { getFOIS3DocumentPreSignedUrl } from '../../../apiManager/services/foiOSSService';
import { element } from 'prop-types';
import {PDFVIEWER_DISABLED_FEATURES} from  '../../../constants/constants'
import {faArrowUp, faArrowDown} from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';

const Redlining = React.forwardRef(({
  currentPageInfo,
  user,
  requestid,
}, ref) =>{
  const redactionInfo = useSelector(state=> state.documents?.redactionInfo);
  const sections = useSelector(state => state.documents?.sections);

  const viewer = useRef(null);
  const saveButton = useRef(null);

  // const pdffile = '/files/PDFTRON_about.pdf';
  // const [pdffile, setpdffile] = useState((currentPageInfo.file['filepath'] + currentPageInfo.file['filename']));
  const [pdffile, setpdffile] = useState((currentPageInfo.file['filepath']));
  const [docViewer, setDocViewer] = useState(null);
  const [annotManager, setAnnotManager] = useState(null);
  const [annots, setAnnots] = useState(null);
  const [docViewerMath, setDocViewerMath] = useState(null);
  const [docInstance, setDocInstance] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [newRedaction, setNewRedaction] = useState(null);
  const [saveAnnot, setSaveAnnot] = useState(null);
  const [deleteQueue, setDeleteQueue] = useState([]);
  const [selectedSections, setSelectedSections] = useState([]);
  const [defaultSections, setDefaultSections] = useState([]);
  const [editAnnot, setEditAnnot] = useState(null);
  const [saveDisabled, setSaveDisabled]= useState(true);
  const [redactionType, setRedactionType]= useState(null);
  const [pageSelections, setPageSelections] = useState([]);
  const [modalSortNumbered, setModalSortNumbered]= useState(false);
  const [modalSortAsc, setModalSortAsc]= useState(true);
  //xml parser
  const parser = new XMLParser();


  // const [storedannotations, setstoreannotations] = useState(localStorage.getItem("storedannotations") || [])
  // if using a class, equivalent of componentDidMount
  useEffect(() => {
    let currentDocumentS3Url = localStorage.getItem("currentDocumentS3Url");

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
        disabledElements: ['modalRedactButton', 'annotationRedactButton']
      },
      viewer.current,
    ).then((instance) => {
      const { documentViewer, annotationManager, Annotations,  PDFNet, Search, Math } = instance.Core;
      instance.UI.disableElements(PDFVIEWER_DISABLED_FEATURES.split(','))

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
          (error) => {
            console.log('error');
          }
        );

        setDocViewer(documentViewer);
        setAnnotManager(annotationManager);
        setAnnots(Annotations);
        setDocViewerMath(Math);


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
          setRedactionType(annotations[0]?.type);
          if(action === 'delete') {
            let annotObjs = []
            for (let annot of annots[0].children) {
              if (annot.name === 'redact') {
                annotObjs.push({page: annot.attributes.page, name: annot.attributes.name, type: annot.name});
              } else {
                if(annotations[0]?.type === 'fullPage'){
                  deleteAnnotation(
                    requestid,
                    localDocumentInfo['file']['documentid'],
                    localDocumentInfo['file']['version'],
                    annot.attributes.name,
                    (data)=>{
                      fetchPageFlag(
                        requestid,
                        (error) => console.log(error)
                      )
                    },
                    (error)=>{console.log(error)},
                    (Number(annot.attributes.page))+1
                  );
                }
                else{
                  deleteAnnotation(
                    requestid,
                    localDocumentInfo['file']['documentid'],
                    localDocumentInfo['file']['version'],
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
            if (annotations[0].Subject === 'Redact') {
              let pageSelectionList= [...pageSelections];
              // setRedactionType(annotations[0]?.type);
              annots[0].children?.forEach((annotatn, i)=> {
                if(annotations[i]?.type === 'fullPage') {
                  pageSelectionList.push(
                    {
                    "page":(Number(annotatn.attributes.page))+1,
                    "flagid":3
                    });
                } else {
                  pageSelectionList.push(
                    {
                    "page":(Number(annotatn.attributes.page))+1,
                    "flagid":1
                    });
                }
              })
              setPageSelections(pageSelectionList);
              let annot = annots[0].children[0];
              setNewRedaction({pages: annot.attributes.page, name: annot.attributes.name, astr: astr, type: annot.name});
            } else {
              let sections = annotations[0].getCustomData("sections")
              let sectn;
              if (sections) {
                sectn = {
                  "foiministryrequestid": requestid,
                  "ids": JSON.parse(sections),
                  "redactannotation": annotations[0].getCustomData("parentRedaction")
                }
              }
              setSelectedSections([]);
              saveAnnotation(
                requestid,
                localDocumentInfo['file']['documentid'],
                localDocumentInfo['file']['version'],
                annotations[0].Id,
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
        setAnnots(Annotations);
      });
    });
  }, []);


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
    setSaveDisabled(true);
    let redactionObj= editAnnot? editAnnot : newRedaction;
    let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
    let childAnnotation;
    let childSection ="";
    let i = redactionInfo?.findIndex(a => a.annotationname === redactionObj?.name);
    if(i >= 0){
      childSection = redactionInfo[i]?.sections.annotationname;
      childAnnotation = annotManager.getAnnotationById(childSection);

    }
    if(editAnnot){
      let redactionSectionsIds = (defaultSections.length > 0 ? defaultSections : selectedSections);
      let redactionSections = sections.filter(s => redactionSectionsIds.indexOf(s.id) > -1).map(s => s.section).join(", ");
      childAnnotation.setContents(redactionSections);
      const doc = docViewer.getDocument();
      const pageNumber = parseInt(editAnnot.page) + 1;
      const pageInfo = doc.getPageInfo(pageNumber);
      const pageMatrix = doc.getPageMatrix(pageNumber);
      const pageRotation = doc.getPageRotation(pageNumber);
      childAnnotation.fitText(pageInfo, pageMatrix, pageRotation);
      annotManager.redrawAnnotation(childAnnotation);
      let _annotationtring = annotManager.exportAnnotations({annotList: [childAnnotation], useDisplayAuthor: true})
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
          requestid,
          localDocumentInfo['file']['documentid'],
          localDocumentInfo['file']['version'],
          childSection,
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
        localDocumentInfo['file']['documentid'],
        localDocumentInfo['file']['version'],
        newRedaction.name,
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
      let parser = new DOMParser();
      let astr = parser.parseFromString(redactionObj.astr,"text/xml");
      for (const node of astr.getElementsByTagName("annots")[0].childNodes) {
        let redaction = annotManager.getAnnotationById(node.attributes.getNamedItem('name').value);
        let coords = node.attributes.getNamedItem('coords')?.value;
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

        annotManager.addAnnotation(annot);
        // Always redraw annotation
        annotManager.redrawAnnotation(annot);
        // setNewRedaction(null)
        redactionInfo.push({annotationname: redactionObj.name, sections: {annotationname: annot.Id, ids: redactionSectionsIds}});
        for(let section of redactionSections) {
          section.count++;
        }
      }
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

  useEffect(() => {
    while (deleteQueue?.length > 0) {
      let annot = deleteQueue.pop();
      if (annot && annot.name !== newRedaction?.name) {
        let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));

        deleteRedaction(
          requestid,
          localDocumentInfo['file']['documentid'],
          localDocumentInfo['file']['version'],
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

  useEffect(() => {
    if (saveAnnot) {
      // if new redaction is not null, that means it is a section annotation
      let localDocumentInfo = JSON.parse(localStorage.getItem("currentDocumentInfo"));
      if (newRedaction === null) {
        if (saveAnnot.type === 'redact') {
          setNewRedaction(saveAnnot);
          if (defaultSections.length === 0) { // newRedaction effect hook automatically calls saveRedaction if defaultSections is set
            setModalOpen(true);
          }
        } else {
          saveAnnotation(
            requestid,
            localDocumentInfo['file']['documentid'],
            localDocumentInfo['file']['version'],
            saveAnnot.name,
            saveAnnot.astr,
            (data)=>{
              fetchPageFlag(
                requestid,
                (error) => console.log(error)
              )
            },
            (error)=>{console.log(error)},
            pageSelections,
          );
        }
      } else {
      }
    }
    setSaveAnnot(null);
  }, [saveAnnot])

  const cancelRedaction = () => {
    setModalOpen(false);
    setSelectedSections([]);
    setSaveDisabled(true);
    if(newRedaction != null)
      annotManager.deleteAnnotation(annotManager.getAnnotationById(newRedaction.name));
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
  </div>
  );
})

export default Redlining;