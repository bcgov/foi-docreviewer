import { useAppSelector } from "../../../hooks/hook";
import React, { useRef, useEffect, useState, MutableRefObject } from "react";
import "../../../styles.scss";
import "../App.scss";
import DocumentSelector from "./DocumentSelector";
import Redlining from "./Redlining";
import Grid from "@mui/material/Grid";
import {
  fetchDocuments,
  fetchRedactionLayerMasterData,
} from "../../../apiManager/services/docReviewerService";
import { getFOIS3DocumentPreSignedUrls } from "../../../apiManager/services/foiOSSService";
import { useParams } from "react-router-dom";
import { docSorting } from "./utils";
import { store } from "../../../services/StoreService";
import { setCurrentLayer } from "../../../actions/documentActions";
import DocumentLoader from "../../../containers/DocumentLoader";
import ReactModal from "react-modal-resizable-draggable";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import CloseIcon from "@mui/icons-material/Close";
import IconButton from "@mui/material/IconButton";

function Home() {
  const user = useAppSelector((state) => state.user.userDetail);
  const [files, setFiles] = useState([]);
  // added incompatibleFiles to capture incompatible files for download redline
  const [incompatibleFiles, setIncompatibleFiles] = useState([]);

  const [currentPageInfo, setCurrentPageInfo] = useState({ file: {}, page: 0 });
  const [s3UrlReady, setS3UrlReady] = useState(false);
  const [s3Url, setS3Url] = useState("");
  const { foiministryrequestid } = useParams();
  const [totalPageCount, setTotalPageCount] = useState(0);
  const [currentDocument, setCurrentDocument] = useState({});
  const [docsForStitcing, setDocsForStitcing] = useState([]);
  const [stitchedDoc, setStitchedDoc] = useState();
  const [individualDoc, setIndividualDoc] = useState({ file: {}, page: 0 });
  const [pageMappedDocs, setPageMappedDocs] = useState([]);
  const [isStitchingLoaded, setIsStitchingLoaded] = useState(false);
  const [warningModalOpen, setWarningModalOpen] = useState(false);

  const redliningRef = useRef();

  useEffect(() => {
    setS3UrlReady(false);
    let documentObjs = [];
    let totalPageCountVal = 0;
    let presignedurls = [];
    fetchDocuments(
      parseInt(foiministryrequestid),
      async (data) => {
        // New code added to get the incompatable files for download redline
        // data has all the files including incompatable ones
        // _files has all files except incompatable ones
        const _incompatableFiles = data.filter(
          (d) => d.attributes.incompatible
        );
        setIncompatibleFiles(_incompatableFiles);
        const _files = data.filter((d) => !d.attributes.incompatible);
        setFiles(_files);
        setCurrentPageInfo({ file: _files[0] || {}, page: 1 });
        if (_files.length > 0) {
          let urlPromises = [];
          _files.forEach((file, index) => {
            documentObjs.push({ file: file, s3url: "" });
            let filePageCount = file?.pagecount;
            totalPageCountVal += filePageCount;
          });

          let doclist = [];
          getFOIS3DocumentPreSignedUrls(
            documentObjs,
            (newDocumentObjs) => {
              doclist = newDocumentObjs?.sort(docSorting);
              //prepareMapperObj will add sortorder, stitchIndex and totalPageCount to doclist
              //and prepare the PageMappedDocs object
              prepareMapperObj(doclist);
              setCurrentDocument({
                file: doclist[0]?.file || {},
                page: 1,
                currentDocumentS3Url: doclist[0]?.s3url,
              });
              // localStorage.setItem("currentDocumentS3Url", s3data);
              setS3Url(doclist[0]?.s3url);
              setS3UrlReady(true);
              setDocsForStitcing(doclist);
              setTotalPageCount(totalPageCountVal);
            },
            (error) => {
              console.log(error);
            }
          );
        }
      },
      (error) => {
        console.log(error);
      }
    );
    fetchRedactionLayerMasterData(
      foiministryrequestid,
      (data) => {
        let redline = data.find((l) => l.name === "Redline");
        let oipc = data.find((l) => l.name === "OIPC");
        let currentLayer = oipc.count > 0 ? oipc : redline;
        store.dispatch(setCurrentLayer(currentLayer));
      },
      (error) => console.log(error)
    );
  }, []);

  const prepareMapperObj = (doclistwithSortOrder) => {
    let mappedDocs = { stitchedPageLookup: {}, docIdLookup: {}, redlineDocIdLookup: {} };
    let mappedDoc = { docId: 0, version: 0, division: "", pageMappings: [] };

    let index = 0;
    let stitchIndex = 1;
    let totalPageCount = 0;
    doclistwithSortOrder.forEach((sortedDoc, _index) => {
      mappedDoc = { pageMappings: [] };
      let j = 0;
      const pages = [];
      for (let i = index + 1; i <= index + sortedDoc.file.pagecount; i++) {
        j++;
        let pageMapping = {
          pageNo: j,
          stitchedPageNo: i,
        };
        mappedDoc.pageMappings.push(pageMapping);
        mappedDocs["stitchedPageLookup"][i] = {
          docid: sortedDoc.file.documentid,
          docversion: sortedDoc.file.version,
          page: j,
        };
        totalPageCount = i;
      }
      mappedDocs["docIdLookup"][sortedDoc.file.documentid] = {
        docId: sortedDoc.file.documentid,
        version: sortedDoc.file.version,
        division: sortedDoc.file.divisions[0].divisionid,
        pageMappings: mappedDoc.pageMappings,
      };
      let fileDivisons = [];
      for (let div of sortedDoc.file.divisions) {
        fileDivisons.push(div.divisionid)
      }
      mappedDocs["redlineDocIdLookup"][sortedDoc.file.documentid] = {
        docId: sortedDoc.file.documentid,
        version: sortedDoc.file.version,
        division: fileDivisons,
        pageMappings: mappedDoc.pageMappings,
      };

      for (let i = 0; i < sortedDoc.file.pagecount; i++) {
        pages.push(i + 1);
      }
      index = index + sortedDoc.file.pagecount;
      sortedDoc.sortorder = _index + 1;
      sortedDoc.stitchIndex = stitchIndex;
      sortedDoc.pages = pages;
      stitchIndex += sortedDoc.file.pagecount;
    });
    doclistwithSortOrder.totalPageCount = totalPageCount;
    setPageMappedDocs(mappedDocs);
  };

  const openFOIPPAModal = (pageNos) => {
    redliningRef?.current?.addFullPageRedaction(pageNos);
  };

  const closeWarningMessage = () => {
    setWarningModalOpen(false);
  };

  return (
    <div className="App">
      <Grid container>
        <Grid item xs={3} style={{ maxWidth: "350px" }}>
          {
            files.length > 0 && (
              <DocumentSelector
                openFOIPPAModal={openFOIPPAModal}
                requestid={foiministryrequestid}
                documents={files}
                totalPageCount={totalPageCount}
                setCurrentPageInfo={setCurrentPageInfo}
                setIndividualDoc={setIndividualDoc}
                pageMappedDocs={pageMappedDocs}
                setWarningModalOpen={setWarningModalOpen}
              />
            )
            // : <div>Loading</div>
          }
        </Grid>
        <Grid item xs={true}>
          {
            (user?.name || user?.preferred_username) &&
              currentPageInfo?.page > 0 &&
              s3UrlReady &&
              s3Url && (
                <Redlining
                  ref={redliningRef}
                  user={user}
                  requestid={foiministryrequestid}
                  docsForStitcing={docsForStitcing}
                  currentDocument={currentDocument}
                  stitchedDoc={stitchedDoc}
                  setStitchedDoc={setStitchedDoc}
                  individualDoc={individualDoc}
                  pageMappedDocs={pageMappedDocs}
                  setPageMappedDocs={setPageMappedDocs}
                  setIsStitchingLoaded={setIsStitchingLoaded}
                  isStitchingLoaded={isStitchingLoaded}
                  incompatibleFiles={incompatibleFiles}
                  setWarningModalOpen={setWarningModalOpen}
                />
              )
            // : <div>Loading</div>
          }
          {!isStitchingLoaded && (
            <div className="merging-overlay">
              <div>
                <DocumentLoader />
              </div>
            </div>
          )}
        </Grid>
      </Grid>
      <ReactModal
        initWidth={800}
        initHeight={300}
        minWidth={600}
        minHeight={250}
        className={"state-change-dialog"}
        isOpen={warningModalOpen}
      >
        <DialogTitle disableTypography id="state-change-dialog-title">
          <h2 className="state-change-header"></h2>
          <IconButton className="title-col3" onClick={closeWarningMessage}>
            <i className="dialog-close-button">Close</i>
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent className={"dialog-content-nomargin"}>
          <DialogContentText
            id="state-change-dialog-description"
            component={"span"}
          >
            <span className="confirmation-message">
              Selected pages or redactions reached the limit. <br></br>
            </span>
          </DialogContentText>
        </DialogContent>
      </ReactModal>
    </div>
  );
}

export default Home;
