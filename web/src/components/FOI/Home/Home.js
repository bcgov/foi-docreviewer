import { useAppSelector } from '../../../hooks/hook';
import React, { useRef, useEffect, useState, MutableRefObject } from 'react';
import "../../../styles.scss";
import "../App.scss"
import DocumentSelector from './DocumentSelector';
import Redlining from './Redlining';
import Grid from "@material-ui/core/Grid";
import WebViewer from '@pdftron/webviewer';

import { fetchDocuments } from '../../../apiManager/services/docReviewerService';
import { getFOIS3DocumentPreSignedUrl } from '../../../apiManager/services/foiOSSService';
import { useParams } from 'react-router-dom';

function Home() {

  const user = useAppSelector((state) => state.user.userDetail);
  const [files, setFiles] = useState([]);
  const [currentPageInfo, setCurrentPageInfo] = useState({'file': {}, 'page': 0});
  const [s3UrlReady, setS3UrlReady] = useState(false);
  const [s3Url, setS3Url] = useState('');
  const { foiministryrequestid } = useParams();
  const [totalPageCount, setTotalPageCount] = useState(0);
  const [currentDocument, setCurrentDocument] = useState({});
  const [docsForStitcing, setDocsForStitcing] = useState([]);
  const [stitchedDoc, setStitchedDoc] = useState();
  const [loadPage, setLoadPage] = useState(0);

  const redliningRef = useRef();

   useEffect(() => {
    setS3UrlReady(false);
    let documentObjs=[];
    let totalPageCountVal = 0;
    let presignedurls = []
    fetchDocuments(
      parseInt(foiministryrequestid),
      (data) => {
        setFiles(data);
        setCurrentPageInfo({'file': data[0] || {}, 'page': 1})
        localStorage.setItem("currentDocumentInfo", JSON.stringify({'file': data[0] || {}, 'page': 1}));
        // setCurrentDocument(JSON.stringify({'file': data[0] || {}, 'page': 1}));
        if (data.length > 0) {
          data.forEach((file, index) => {
            let documentObj={ file: {}, s3url: "" };
            let filePageCount = file?.pagecount;
            totalPageCountVal +=filePageCount;
            getFOIS3DocumentPreSignedUrl(
              file.documentid,
              (s3data) => {
                  if(index == 0){
                    setCurrentDocument({'file': file || {}, 'page': 1,"currentDocumentS3Url": s3data});
                    // localStorage.setItem("currentDocumentS3Url", s3data);
                    setS3Url(s3data);
                    setS3UrlReady(true);
                  }
                  presignedurls.push(s3data)                    
                  localStorage.setItem("foireviewdocslist", JSON.stringify(presignedurls));
                  documentObj.file = file;
                  documentObj.s3url = s3data;
                  documentObjs.push(documentObj);
                  // setDocsForStitcing(documentObjs);
              },
              (error) => {
                  console.log(error);
              }
            );
          });
          setDocsForStitcing(documentObjs);
          // getFOIS3DocumentPreSignedUrl(
          //     data[0]?.documentid,
          //     (s3data) => {
          //         localStorage.setItem("currentDocumentS3Url", s3data);
          //         setS3Url(s3data);
          //         setS3UrlReady(true);
          //     },
          //     (error) => {
          //         console.log(error);
          //     }
          //   );

            // data.forEach((file) => {
            //     let filePageCount = file?.pagecount;
            //     totalPageCountVal +=filePageCount;
            //     getFOIS3DocumentPreSignedUrl(
            //       file.documentid,
            //       (_s3data) => {
            //         if(_arrindex > 0)
            //         {
            //           presignedurls.push(_s3data)                    
            //           localStorage.setItem("foireviewdocslist", JSON.stringify(presignedurls));
            //         }
            //         _arrindex++;
            //       },
            //       (error) => {
            //           console.log(error);
            //       }
            //     );
            // });
            setTotalPageCount(totalPageCountVal);
        }
      },
      (error) => {
        console.log(error);
      }
      
    );
  }, [])


  const openFOIPPAModal = (pageNo) => {
    redliningRef?.current?.addFullPageRedaction(pageNo);
  }

  return (
    <div className="App">
      <Grid container>
        <Grid item xs={3} style={{maxWidth: "350px"}}>
        {/* <button className="btn-bottom btn-cancel" onClick={openFOIPPAModal}>open modal</button> */}
          { (files.length > 0) ? 
          <DocumentSelector openFOIPPAModal={openFOIPPAModal} requestid={foiministryrequestid} documents={files} totalPageCount={totalPageCount} 
          currentPageInfo={currentPageInfo} setCurrentPageInfo={setCurrentPageInfo} setCurrentDocument={setCurrentDocument} 
          stitchedDoc={stitchedDoc} setLoadPage={setLoadPage}/> 
          : <div>Loading</div> }
        </Grid>
        <Grid item xs={true}>
          { ( (user?.name || user?.preferred_username) && (currentPageInfo?.page > 0) && s3UrlReady && s3Url ) ? 
          <Redlining ref={redliningRef} currentPageInfo={currentPageInfo} user={user} requestid={foiministryrequestid} docsForStitcing={docsForStitcing} 
          currentDocument={currentDocument} stitchedDoc={stitchedDoc} setStitchedDoc={setStitchedDoc} loadPage={loadPage} /> : <div>Loading</div> }
        </Grid>
      </Grid>
    </div>
  );
}

export default Home;
