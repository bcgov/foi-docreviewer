import { useAppSelector } from '../../../hooks/hook';
import React, { useRef, useEffect, useState } from 'react';
import "../../../styles.scss";
import "../App.scss"
import DocumentSelector from './DocumentSelector';
import Redlining from './Redlining';
import Grid from "@material-ui/core/Grid";
import WebViewer from '@pdftron/webviewer';

import { fetchDocuments } from '../../../apiManager/services/docReviewerService';

function Home() {

  const user = useAppSelector((state) => state.user.userDetail);
  const [files, setFiles] = useState([])
  const [currentPageInfo, setCurrentPageInfo] = useState({'file': {}, 'page': 0})

  const foiministryrequestid = 1;
  useEffect(() => {
    fetchDocuments(
      foiministryrequestid,
      (data: any) => {
        console.log("docs:");
        setFiles(data);
        setCurrentPageInfo({'file': data[0], 'page': 1})
        console.log(data);
      },
      (error: any) => {
        console.log(error);
      }
    );
  }, [])

  return (
    <div className="App">
      <Grid container spacing={1}>
        <Grid item xs={3} style={{maxWidth: "350px"}}>
          { (files.length > 0) ? <DocumentSelector documents={files} currentPageInfo={currentPageInfo} setCurrentPageInfo={setCurrentPageInfo} /> : <div>Loading</div> }
        </Grid>
        <Grid item xs={true}>
          { ((user?.name || user?.preferred_username) && (currentPageInfo?.page > 0)) ? <Redlining currentPageInfo={currentPageInfo} user={user} setCurrentPageInfo={setCurrentPageInfo}/> : <div>Loading</div> }
        </Grid>
      </Grid>
    </div>
  );
}

export default Home;
