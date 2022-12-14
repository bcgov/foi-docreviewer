import React, { useRef, useEffect,useState } from 'react';
import WebViewer from '@pdftron/webviewer';
import XMLParser from 'react-xml-parser';

import { fetchAnnotations, saveAnnotation, deleteAnnotation } from '../../../apiManager/services/docReviewerService';
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
  const [docInstance, setDocInstance] = useState(null);
  
  //xml parser
  const parser = new XMLParser();

  // const [storedannotations, setstoreannotations] = useState(localStorage.getItem("storedannotations") || [])
  // if using a class, equivalent of componentDidMount
  useEffect(() => {
    let currentDocumentS3Url = localStorage.getItem("currentDocumentS3Url");
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
      setDocInstance(instance);

      const { documentViewer, annotationManager, Annotations,  PDFNet, Search } = instance.Core;
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
            const _annotations = annotationManager.importAnnotations(data)
            _annotations.then(_annotation => {
              annotationManager.redrawAnnotation(_annotation);
            });
            documentViewer.displayPageLocation(localDocumentInfo['page'], 0, 0)
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
          // console.log(astr)

          //parse annotation xml
          let jObj = parser.parseFromString(astr);    // Assume xmlText contains the example XML
          let annots = jObj.getElementsByTagName("annots");
          let annot = annots[0].children[0];
          
          if(action === 'delete') {
            deleteAnnotation(
              localDocumentInfo['file']['documentid'],
              localDocumentInfo['file']['version'],
              annot.attributes.page,
              annot.attributes.name,
              (data)=>{console.log(data)},
              (error)=>{console.log(error)}
            );
          } else {
            saveAnnotation(
              localDocumentInfo['file']['documentid'],
              localDocumentInfo['file']['version'],
              annot.attributes.page,
              annot.attributes.name,
              astr,
              (data)=>{console.log(data)},
              (error)=>{console.log(error)}
            );
          }
        })

        // let allannotations = annotationManager.exportAnnotations({annotList: annotationManager.getAnnotationsList(), useDisplayAuthor: true})
        // allannotations.then(astr=>{
        //   console.log(astr)
        //   // localStorage.setItem("savedannotations",astr)
        // })

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
    console.log("page changed")
    let isDocLoaded = localStorage.getItem("isDocumentLoaded");
    if(isDocLoaded === 'true')
      docViewer?.displayPageLocation(currentPageInfo['page'], 0, 0);
  }, [currentPageInfo])



  return (
    <div>
      {/* <button onClick={gotopage}>Click here</button> */}
      <div className="webviewer" ref={viewer}></div>
    </div>
  );

}

export default Redlining;