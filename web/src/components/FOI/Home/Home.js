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
  fetchDeletedDocumentPages,
} from "../../../apiManager/services/docReviewerService";
import { getFOIS3DocumentPreSignedUrls } from "../../../apiManager/services/foiOSSService";
import { useParams } from "react-router-dom";
import { sortDocList, getDocumentPages } from "./utils";
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
  const validoipcreviewlayer = useAppSelector((state) => state.documents?.requestinfo?.validoipcreviewlayer);
  const redactionLayers = useAppSelector((state) => state.documents?.redactionLayers);
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
  const selectorRef = useRef();

  useEffect(() => {
    setS3UrlReady(false);
    let documentObjs = [];
    let totalPageCountVal = 0;
    let presignedurls = [];
    let deletedDocPages = [];

    fetchDeletedDocumentPages(
      foiministryrequestid, 
      (deletedPages) => {
        deletedDocPages = deletedPages;
      }, 
      (error) =>
        console.log(error)
    );

    fetchDocuments(
      parseInt(foiministryrequestid),
      async (data) => {

        const getFileExt = (filepath) => {
          const parts = filepath.split(".")
          const fileExt = parts.pop()
          return fileExt
        }
        // New code added to get the incompatable files for download redline
        // data has all the files including incompatable ones
        // _files has all files except incompatable ones
        const _incompatableFiles = data.filter(
          (d) => {
            const isPdfFile = getFileExt(d.filepath) === "pdf"
            if (isPdfFile) {
              return false
            } else {
              return d.attributes.incompatible
            }
          }
        );
        setIncompatibleFiles(_incompatableFiles);
        const _files = data.filter((d) => {
          const isPdfFile = getFileExt(d.filepath) === "pdf"
          const isCompatible = !d.attributes.incompatible || isPdfFile
          return isCompatible
        });
        let sortedFiles = []
        sortDocList(_files, null, sortedFiles);
        // setFiles(sortedFiles);
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
              sortDocList(newDocumentObjs, null, doclist);
              //prepareMapperObj will add sortorder, stitchIndex and totalPageCount to doclist
              //and prepare the PageMappedDocs object
              prepareMapperObj(doclist, deletedDocPages);
              const currentDoc = getCurrentDocument(doclist)              
              setCurrentDocument({
                file: currentDoc?.file || {},
                page: 1,
                currentDocumentS3Url: currentDoc?.s3url,
              });
              setS3Url(currentDoc?.s3url);
              setS3UrlReady(true);
              setDocsForStitcing(doclist);
              //files will have [pages] added
              setFiles(doclist.map(_doc => _doc.file));
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
  }, []);

  const getCurrentDocument = (doclist) => {    
    return doclist.find(item => item.file.pagecount > 0);    
  }

  useEffect(() => {
    fetchRedactionLayerMasterData(
      foiministryrequestid,
      (data) => {
        let redline = data.find((l) => l.name === "Redline");
        let currentLayer = redline;
        store.dispatch(setCurrentLayer(currentLayer));
      },
      (error) => console.log(error)
    );
  }, [])

  //useEffect to manage and apply oipc layer to current layer
  useEffect(() => {
    const oipcLayer = redactionLayers.find((layer) => layer.name === "OIPC")
    if(validoipcreviewlayer && oipcLayer?.count > 0) {
      store.dispatch(setCurrentLayer(oipcLayer));
    }
  }, [validoipcreviewlayer, redactionLayers])

  const prepareMapperObj = (doclistwithSortOrder, deletedDocPages) => {
    let mappedDocs = { stitchedPageLookup: {}, docIdLookup: {}, redlineDocIdLookup: {} };
    let mappedDoc = { docId: 0, version: 0, division: "", pageMappings: [] };

    let index = 0;
    let stitchIndex = 1;
    let totalPageCount = 0;
    doclistwithSortOrder.forEach((sortedDoc, _index) => {
      mappedDoc = { pageMappings: [] };
      const documentId = sortedDoc.file.documentid;
      // pages array by removing deleted pages
      let pages = getDocumentPages(documentId, deletedDocPages, sortedDoc.file.originalpagecount);      
      let j = 0;

      for (let i = index + 1; i <= index + sortedDoc.file.pagecount; i++) {        
        let pageMapping = {
          pageNo: pages[j],
          stitchedPageNo: i,
        };
        mappedDoc.pageMappings.push(pageMapping);
        mappedDocs["stitchedPageLookup"][i] = {
          docid: documentId,
          docversion: sortedDoc.file.version,
          page: pages[j],
        };
        totalPageCount = i;
        j++;
      }
      mappedDocs["docIdLookup"][documentId] = {
        docId: documentId,
        version: sortedDoc.file.version,
        division: sortedDoc.file.divisions[0].divisionid,
        pageMappings: mappedDoc.pageMappings,
      };
      let fileDivisons = [];
      for (let div of sortedDoc.file.divisions) {
        fileDivisons.push(div.divisionid)
      }
      mappedDocs["redlineDocIdLookup"][documentId] = {
        docId: documentId,
        version: sortedDoc.file.version,
        division: fileDivisons,
        pageMappings: mappedDoc.pageMappings,
      };

       // added to iterate through the non deleted pages for the left panel functionalities
      sortedDoc.file.pages = pages;
      sortedDoc.pages = pages;
      if (sortedDoc.file.pagecount > 0) {
        index = index + sortedDoc.file.pagecount;
        //added sortorder to fix the sorting issue for redlining stitching
        sortedDoc.file.sortorder = _index + 1; 
        sortedDoc.sortorder = _index + 1;
        sortedDoc.stitchIndex = stitchIndex;     
        stitchIndex += sortedDoc.file.pagecount;
      }
    });
    doclistwithSortOrder.totalPageCount = totalPageCount;
    setPageMappedDocs(mappedDocs);
  };

  const openFOIPPAModal = (pageNos, flagId) => {
    redliningRef?.current?.addFullPageRedaction(pageNos, flagId);
  };

  const scrollLeftPanel = (pageNo) => {
    selectorRef?.current?.scrollToPage(pageNo);
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
                ref={selectorRef}
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
                  scrollLeftPanel={scrollLeftPanel}
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
