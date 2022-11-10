import { useAppSelector } from '../../../hooks/hook';
import React, { useRef, useEffect,useState } from 'react';
import "../../../styles.scss";
import "../App.scss"
import DocumentSelector from './DocumentSelector';
import Redlining from './Redlining';
import Grid from "@material-ui/core/Grid";
import WebViewer from '@pdftron/webviewer';

import { fetchDocuments } from '../../../apiManager/services/docReviewerService';

function Home() {

  const user = useAppSelector((state) => state.user.userDetail);
  const [currentPage, setCurrentPage] = useState(0)
  const [currentDoc, setCurrentDoc] = useState(0)
  const [files, setFiles] = useState(null)

  const foiministryrequestid = 1;
  fetchDocuments(
    foiministryrequestid,
    (data: any) => {
      console.log("docs:");
      setFiles(data);
      console.log(data);
    },
    (error: any) => {
      console.log(error);
    }
  );

  return (
    <div className="App">
      <Grid container spacing={1}>
        <Grid item xs={3} style={{maxWidth: "350px"}}>
          <DocumentSelector documents={files} setCurrentPage={setCurrentPage} setCurrentDoc={setCurrentDoc} />
        </Grid>
        <Grid item xs={true}>
          { (user?.name || user?.preferred_username) ? <Redlining currentPage={currentPage} user={user}/> : <div>Loading</div> }
          {/* <header className="app-header">
            <span className="navbar-text" style={{}}> Hi {user.name || user.preferred_username || ""}</span>
          </header> */}
        </Grid>
      </Grid>
    </div>
  );
}

export default Home;
