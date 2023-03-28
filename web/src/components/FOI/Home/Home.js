import { useAppSelector } from '../../../hooks/hook';
import React, { useRef, useEffect, useState } from 'react';
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
  const redliningRef = React.useRef();


  useEffect(() => {
    setS3UrlReady(false);
    fetchDocuments(
      parseInt(foiministryrequestid),
      (data) => {
        setFiles(data);
        setCurrentPageInfo({'file': data[0] || {}, 'page': 1})
        localStorage.setItem("currentDocumentInfo", JSON.stringify({'file': data[0] || {}, 'page': 1}));

        if (data.length > 0) {
          getFOIS3DocumentPreSignedUrl(
              data[0]?.documentid,
              (s3data) => {
                  localStorage.setItem("currentDocumentS3Url", s3data);
                  setS3Url(s3data);
                  setS3UrlReady(true);
              },
              (error) => {
                  console.log(error);
              }
            );
            let totalPageCountVal = 0;
            data.forEach((file) => {
                let filePageCount = file?.pagecount;
                totalPageCountVal +=filePageCount;
            });
            setTotalPageCount(totalPageCountVal);
        }
      },
      (error) => {
        console.log(error);
      }
    );
  }, [])

  const openFOIPPAModal = () => {
    console.log("test");
    redliningRef.current.log();
  }

  return (
    <div className="App">
      <Grid container>
        <Grid item xs={3} style={{maxWidth: "350px"}}>
          <button className="btn-bottom btn-cancel" onClick={openFOIPPAModal}>open modal</button>
          { (files.length > 0) ? <DocumentSelector requestid={foiministryrequestid} documents={files} totalPageCount={totalPageCount} currentPageInfo={currentPageInfo} setCurrentPageInfo={setCurrentPageInfo} /> : <div>Loading</div> }
        </Grid>
        <Grid item xs={true}>
          { ( (user?.name || user?.preferred_username) && (currentPageInfo?.page > 0) && s3UrlReady && s3Url ) ? <Redlining ref={redliningRef} currentPageInfo={currentPageInfo} user={user} requestid={foiministryrequestid} /> : <div>Loading</div> }
        </Grid>
      </Grid>
    </div>
  );
}

export default Home;
