import { useAppSelector } from '../../../hooks/hook';
import React, { useRef, useEffect, useState, MutableRefObject } from 'react';
import "../../../styles.scss";
import "../App.scss"
import DocumentSelector from './DocumentSelector';
import Redlining from './Redlining';
import Grid from "@material-ui/core/Grid";
import { fetchDocuments, fetchPageFlag } from '../../../apiManager/services/docReviewerService';
import { getFOIS3DocumentPreSignedUrl } from '../../../apiManager/services/foiOSSService';
import { useParams } from 'react-router-dom';
import { docSorting } from './utils';

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
  const [individualDoc, setIndividualDoc] = useState({'file': {}, 'page': 0});
  const [pageMappedDocs, setPageMappedDocs] = useState([]);


  const redliningRef = useRef();

   useEffect(() => {
    setS3UrlReady(false);
    let documentObjs=[];
    let totalPageCountVal = 0;
    let presignedurls = []
    fetchDocuments(
      parseInt(foiministryrequestid),
      async (data) => {
        setFiles(data);
        setCurrentPageInfo({'file': data[0] || {}, 'page': 1})
        //localStorage.setItem("currentDocumentInfo", JSON.stringify({'file': data[0] || {}, 'page': 1}));
        // setCurrentDocument(JSON.stringify({'file': data[0] || {}, 'page': 1}));
        if (data.length > 0) {
          let urlPromises = [];
          data.forEach((file, index) => {
            let documentObj={ file: {}, s3url: "" };
            let filePageCount = file?.pagecount;
            totalPageCountVal +=filePageCount;
            urlPromises.push(getFOIS3DocumentPreSignedUrl(
              file.documentid,
              (s3data) => {
                  presignedurls.push(s3data)                    
                  documentObj.file = file;
                  documentObj.s3url = s3data;
                  documentObjs.push(documentObj);
              },
              (error) => {
                  console.log(error);
              }
            ));
          });
          await Promise.all(urlPromises);
          let doclist=documentObjs?.sort(docSorting);
          setCurrentDocument({'file': doclist[0].file || {}, 'page': 1,"currentDocumentS3Url": doclist[0].s3url});
          // localStorage.setItem("currentDocumentS3Url", s3data);
          setS3Url(doclist[0].s3url);
          setS3UrlReady(true);
          setDocsForStitcing(doclist);
          setTotalPageCount(totalPageCountVal);
        }
      },
      (error) => {
        console.log(error);
      }
      
    );
    fetchPageFlag(
      parseInt(foiministryrequestid),
      (error) => console.log(error)
    )
  }, [])


  const openFOIPPAModal = (pageNos) => {
    redliningRef?.current?.addFullPageRedaction(pageNos);
  }

  return (
    <div className="App">
      <Grid container>
        <Grid item xs={3} style={{maxWidth: "350px"}}>
        {/* <button className="btn-bottom btn-cancel" onClick={openFOIPPAModal}>open modal</button> */}
          { (files.length > 0) ? 
          <DocumentSelector openFOIPPAModal={openFOIPPAModal} requestid={foiministryrequestid} documents={files} totalPageCount={totalPageCount} 
          setCurrentPageInfo={setCurrentPageInfo} setIndividualDoc={setIndividualDoc} pageMappedDocs={pageMappedDocs} /> 
          : <div>Loading</div> }
        </Grid>
        <Grid item xs={true}>
          { ( (user?.name || user?.preferred_username) && (currentPageInfo?.page > 0) && s3UrlReady && s3Url ) ? 
          <Redlining ref={redliningRef} user={user} requestid={foiministryrequestid} docsForStitcing={docsForStitcing} 
          currentDocument={currentDocument} stitchedDoc={stitchedDoc} setStitchedDoc={setStitchedDoc} individualDoc={individualDoc} 
          pageMappedDocs={pageMappedDocs} setPageMappedDocs={setPageMappedDocs} /> : <div>Loading</div> }
        </Grid>
      </Grid>
    </div>
  );
}

export default Home;
