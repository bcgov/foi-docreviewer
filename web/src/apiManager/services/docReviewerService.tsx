 /* istanbul ignore file */
import { httpGETRequest, httpGETBigRequest, httpPOSTRequest,httpGETRequestSOLR } from "../httpRequestHandler";
import API from "../endpoints";
import UserService from "../../services/UserService";
import { setRedactionInfo, setIsPageLeftOff, setSections, 
  setDocumentList, setRequestStatus, setRedactionLayers, incrementLayerCount, setRequestNumber, setRequestInfo, setDeletedPages,
  setFOIPersonalSections, setFOIPersonalPeople, setFOIPersonalFiletypes, setFOIPersonalVolumes, setPublicBodies,setPIIJSONList,
  setSOLRAuth
} from "../../actions/documentActions";
import { store } from "../../services/StoreService";
 export const fetchDocuments = (
     foiministryrequestid: number,
     callback: any,
     errorCallback: any,
     documentSetId?: number
 ) => {
     let apiUrlGet: string = `${API.DOCREVIEWER_DOCUMENT}/${foiministryrequestid}`

     if (documentSetId !== undefined && documentSetId !== null) {
         apiUrlGet += `?documentsetid=${documentSetId}`;
     }

     httpGETRequest(apiUrlGet, {}, UserService.getToken())
         .then((res:any) => {
             const getFileExt = (filepath: any) => {
                 const parts = filepath.split(".")
                 const fileExt = parts.pop()
                 return fileExt
             }
             if (res.data) {
                 // res.data.documents has all documents including the incompatible ones, below code is to filter out the incompatible ones
                 const __files = res.data.documents.filter((d: any) => {
                     const isPdfFile = getFileExt(d.filepath) === "pdf"
                     const isCompatible = !d.attributes.incompatible || isPdfFile
                     return isCompatible
                 });
                 store.dispatch(setDocumentList(__files) as any);
                 store.dispatch(setRequestNumber(res.data.requestnumber) as any);
                 store.dispatch(setRequestStatus(res.data.requeststatuslabel) as any);
                 store.dispatch(setRequestInfo(res.data.requestinfo) as any);
                 callback(res.data.documents, res.data.documentdivisions, res.data.requestinfo);
             } else {
                 throw new Error();
             }
         })
         .catch((error:any) => {
             console.log(error);
             errorCallback("Error in fetching documents for a request");
         });
 };


import { pageFlagTypes } from "../../constants/enum";

export const saveRotateDocumentPage = (
  foiministryrequestid: number,
  documentmasterid: number,
  rotatedpage: any,
  callback: any,
  errorCallback: any
) => {
  let apiUrlPost: string = `${API.DOCREVIEWER_UPDATE_DOCUMENT_ATTRIBUTES}`
  let requestJSON = {ministryrequestid: foiministryrequestid, documentmasterids: [documentmasterid], rotatedpages: rotatedpage}
  
  httpPOSTRequest({url: apiUrlPost, data: requestJSON, token: UserService.getToken() ?? '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        errorCallback("Error in saving rotated page");
        throw new Error(`Error while saving rotated page`);
      }
    })
    .catch((error:any) => {
      errorCallback("Error in saving rotated page");
    });
};

export const fetchAnnotationsByPagination = (
  ministryrequestid: number,
  activepage: number,
  size: number,
  callback: any,
  errorCallback: any,
  redactionlayer: string = "redline",
  timeout: number = 60000
) => {
  
  let apiUrlGet: string = `${API.DOCREVIEWER_ANNOTATION}/${ministryrequestid}/${redactionlayer}/${activepage}/${size}`
  
  httpGETBigRequest(apiUrlGet, {}, UserService.getToken(), timeout)
    .then((res:any) => {
      if (res.data || res.data === "") {
        callback(res.data);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      errorCallback("Error in fetching annotations for a document");
    });
};

export const fetchDocumentAnnotations = (
  ministryrequestid: number,
  redactionlayer: string,
  documentid: number,
  callback: any,
  errorCallback: any,
  timeout: number = 300000
) => {
  let apiUrlGet: string = `${API.DOCREVIEWER_ANNOTATION}/${ministryrequestid}/${redactionlayer}/document/${documentid}`
  
  httpGETBigRequest(apiUrlGet, {}, UserService.getToken(), timeout)
    .then((res:any) => {
      if (res.data || res.data === "") {
        callback(res.data);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      errorCallback("Error in fetching annotations for a document");
    });
};
export const fetchAnnotationsInfo = (
  ministryrequestid: number,
  redactionlayer: string,
  //callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = `${API.DOCREVIEWER_ANNOTATION}/${ministryrequestid}/${redactionlayer}/info`

  httpGETRequest(apiUrlGet, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data) {
        store.dispatch(setRedactionInfo(res.data) as any);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      errorCallback("Error in fetching annotations for a document");
    });
};

export const saveAnnotation = (
  requestid: string,
  annotation: string = "",
  callback: any,
  errorCallback: any,
  redactionLayer?: number,
  pageFlags?: object,
  sections?: object,
) => {
  let apiUrlPost: string = `${API.DOCREVIEWER_ANNOTATION}`;
  let requestJSON = {};
  if (sections && pageFlags) {
    requestJSON = {
      "xml": annotation,
      "sections": sections,
      "pageflags":pageFlags,
      "redactionlayerid": redactionLayer
      } 
  } else if (sections) {
    requestJSON = {
      "xml": annotation,
      "sections": sections,
      "redactionlayerid": redactionLayer
      } 
  } else {
    requestJSON = {
      "xml": annotation,
      "pageflags":pageFlags,
      "foiministryrequestid":requestid,
      "redactionlayerid": redactionLayer
    }
  }
  httpPOSTRequest({url: apiUrlPost, data: requestJSON, token: UserService.getToken() ?? '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        if (redactionLayer) {
          store.dispatch(incrementLayerCount(redactionLayer) as any);
        }
        callback(res.data);
      } else {
        throw new Error(`Error while saving an annotation`);
      }
    })
    .catch((error:any) => {
      errorCallback("Error in saving an annotation");
    });
};

export const deleteAnnotation = (
  requestid: string,
  redactionlayerid: number,
  annotations: any,
  callback: any,
  errorCallback: any,
) => {

let apiUrlPost: string = `${API.DOCREVIEWER_ANNOTATION}/${requestid}/${redactionlayerid}`;
const data = {annotations: annotations};
httpPOSTRequest({url: apiUrlPost, data: data, token: UserService.getToken() ?? '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error(`Error while deleting annotations for (requestid# ${requestid}, redactionlayerid ${redactionlayerid})`);            
      }
    })
    .catch((error:any) => {
      errorCallback("Error in deleting annotations");
    });
};

export const createOipcLayer= (
  requestid: string,
  callback?: any,
  errorCallback?: any,
) => {
  const oipcLayerId = 3;
  let apiUrlPost: string = `${API.DOCREVIEWER_ANNOTATION}/${requestid}/copy/${oipcLayerId}`;
  let requestJSON = {};
  httpPOSTRequest({url: apiUrlPost, data: requestJSON, token: UserService.getToken() ?? '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        store.dispatch(incrementLayerCount(oipcLayerId) as any);
        if (callback) callback(res.data);
      } else {
        throw new Error(`Error while copying annotations to OIPC layer`);
      }
    })
    .catch((error:any) => {
      if (errorCallback) {
        errorCallback("Error while copying annotations to OIPC layer");
      } else {
        throw new Error(`Error while copying annotations to OIPC layer`);
      }
    });
}

export const deleteRedaction = (
  requestid: string,
  redactionlayerid: number,
  redactions: any,
  callback: any,
  errorCallback: any,
) => {
  let apiUrlPost: string = `${API.DOCREVIEWER_REDACTION}/${requestid}/${redactionlayerid}`;
  const data = {annotations: redactions}
  httpPOSTRequest({url: apiUrlPost, data: data, token: UserService.getToken() ?? '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error(`Error while deleting redactions for (requestid# ${requestid}, redactionlayerid ${redactionlayerid})`);            
      }
    })
    .catch((error:any) => {
      errorCallback("Error in deleting redactions");
    });
};

export const fetchSections = (
  foiministryrquestid: number,
  currentlayername: string,
  callback: any,
  errorCallback: any
) => {
  let apiUrl: string  = replaceUrl(API.DOCREVIEWER_SECTIONS, '<ministryrequestid>', foiministryrquestid);
  
  httpGETRequest(apiUrl+"/"+currentlayername, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data || res.data === "") {
        store.dispatch(setSections(res.data) as any);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      errorCallback("Error in fetching annotations for a document");
    });
}

export const fetchPageFlagsMasterData = (
  foiministryrquestid:string,
  redactionlayer:string,
  callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = replaceUrl(
    API.DOCREVIEWER_GET_ALL_PAGEFLAGS+ "/"+redactionlayer,
    "<requestid>",
    foiministryrquestid
  );
  
  httpGETRequest(apiUrlGet, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data || res.data === "") {
        callback(res.data);
        store.dispatch(setPublicBodies(res.data.find((flag: any) => flag.name === 'Consult').programareas));
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      errorCallback("Error in fetching pageflags master data");
    });
};

export const savePageFlag = (
  foiministryrquestid: string,
  flagid: number,
  callback: any,
  errorCallback: any,
  data?: any
) => {
  let apiUrlPost: string = replaceUrl(
    API.DOCREVIEWER_POST_PAGEFLAGS,
    "<requestid>",
    foiministryrquestid
  )
  httpPOSTRequest({url: apiUrlPost, data: data, token: UserService.getToken() ?? '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data, flagid);
      } else {
        throw new Error(`Error while saving page flag for requestid ${foiministryrquestid}`);
      }
    })
    .catch((error:any) => {
      errorCallback("Error in saving an page flag");
    });
};

export const fetchPageFlag = (
  foiministryrquestid: string,
  redactionlayer: string,
  documentids: Array<any>,  
  callback: any,
  errorCallback: any
) => {

    let requestjson={"documentids":documentids}
    let apiUrlPost: string = replaceUrl(
      API.DOCREVIEWER_GET_PAGEFLAGS,
      "<requestid>",
      foiministryrquestid
    ) + "/" +  redactionlayer;
    httpPOSTRequest({url: apiUrlPost, data: requestjson, token: UserService.getToken() ?? '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
        /** Checking if BOOKMARK set for package */
        let bookmarkedDoc= res.data?.filter((element:any) => {
          return element?.pageflag?.some((obj: any) =>(obj.flagid === pageFlagTypes["Page Left Off"]));
        })
        store.dispatch(setIsPageLeftOff(bookmarkedDoc?.length >0) as any);
      } else {
        throw new Error("Error while triggering download redline");
      }
    })
    .catch((error:any) => {
      errorCallback("Error in triggering download redline:",error);
    });
};


export const fetchKeywordsMasterData = (
  callback: any,
  errorCallback: any
) => {
  httpGETRequest(API.DOCREVIEWER_GET_ALL_KEYWORDS, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data || res.data === "") {
        callback(res.data);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      errorCallback("Error in fetching keywords master data:",error);
    });
};

export const fetchRedactionLayerMasterData = (
  mininstryrequestid: number,
  callback: any,
  errorCallback: any
) => {
  httpGETRequest(API.DOCREVIEWER_GET_REDACTION_LAYERS + "/" + mininstryrequestid, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data || res.data === "") {
        store.dispatch(setRedactionLayers(res.data));
        callback(res.data);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      errorCallback("Error in fetching layers master data:",error);
    });
};

const replaceUrl = (URL: string, key: string, value: any) => {
  return URL.replace(key, value);
};


export const triggerDownloadRedlines = (
  requestJSON: any,
  callback: any,
  errorCallback: any
) => {
  let apiUrlPost: string = `${API.DOCREVIEWER_REDLINE}`;
  httpPOSTRequest({url: apiUrlPost, data: requestJSON, token: UserService.getToken() ?? '', isBearer: true})
  .then((res:any) => {
    if (res.data) {
      callback(res.data);
    } else {
      throw new Error("Error while triggering download redline");
    }
  })
  .catch((error:any) => {
    errorCallback("Error in triggering download redline:",error);
  });
};

export const triggerDownloadFinalPackage = (
  requestJSON: any,
  callback: any,
  errorCallback: any
) => {
  let apiUrlPost: string = `${API.DOCREVIEWER_FINALPACKAGE}`;
  httpPOSTRequest({url: apiUrlPost, data: requestJSON, token: UserService.getToken() ?? '', isBearer: true})
  .then((res:any) => {
    if (res.data) {
      callback(res.data);
    } else {
      throw new Error("Error while triggering download final package");
    }
  })
  .catch((error:any) => {
    errorCallback("Error in triggering download final package:",error);
  });
};

export const fetchPDFTronLicense = (
  callback: any,
  errorCallback: any
) => {
  let apiUrlPost: string = `${API.DOCREVIEWER_LICENSE}`;
  let response = httpGETRequest(apiUrlPost, {}, UserService.getToken() ?? '')
  response
  .then((res:any) => {
    if (res.data) {
      callback(res.data);
    } else {
      throw new Error("Error in fetching PDFTronLicense");
    }
  })
  .catch((error:any) => {
    errorCallback("Error in fetching PDFTronLicense:",error);
    return "";
  });
  return response;
};

export const deleteDocumentPages = (
  requestid: string,
  pagesDeleted: any,
  callback: any,
  errorCallback: any,
) => {

  let apiUrlPost: string = replaceUrl(
    API.DOCREVIEWER_DOCUMENT_PAGE_DELETE,
    "<ministryrequestid>",
    requestid
  );

httpPOSTRequest({url: apiUrlPost, data: pagesDeleted, token: UserService.getToken() ?? '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error(`Error while deleting document pages for (requestid# ${requestid})`);            
      }
    })
    .catch((error:any) => {
      errorCallback("Error in deleting document pages");
    });
};

export const fetchDeletedDocumentPages = (
  mininstryrequestid: number,
  callback: any,
  errorCallback: any
) => {

  let apiUrlGet: string = replaceUrl(
    API.DOCREVIEWER_DOCUMENT_PAGE_DELETE,
    "<ministryrequestid>",
    mininstryrequestid
  );

  httpGETRequest(apiUrlGet, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data || res.data === "") {
        store.dispatch(setDeletedPages(res.data));
        callback(res.data);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      errorCallback("Error in fetching deleted pages:",error);
    });
};

export const fetchPersonalAttributes = (
  bcgovcode: string,
  errorCallback: any
) => {
  let apiUrlGet: string = `${API.FOI_GET_PERSONALTAG}/${bcgovcode}`
  
  httpGETRequest(apiUrlGet, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data) {
        store.dispatch(setFOIPersonalPeople(res.data) as any);
        store.dispatch(setFOIPersonalFiletypes(res.data) as any);
        store.dispatch(setFOIPersonalVolumes(res.data) as any);
        store.dispatch(setFOIPersonalSections(res.data) as any);
        // callback(res.data);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      console.log(error);
      errorCallback("Error in fetching personal attributes");
    });
};

export const editPersonalAttributes = (
  foiministryrquestid: string,
  callback: any,
  errorCallback: any,
  data?: any
) => {
  let apiUrlPost: string = replaceUrl(
    API.DOCREVIEWER_EDIT_PERSONAL_ATTRIBUTES,
    "<requestid>",
    foiministryrquestid
  )
  httpPOSTRequest({url: apiUrlPost, data: data, token: UserService.getToken() ?? '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error(`Error while editing personal attributes for requestid ${foiministryrquestid}`);
      }
    })
    .catch((error:any) => {
      errorCallback("Error in editing personal attributes");
    });
};

 export const getsolrauth = () => {

  return httpGETRequest(
     API.FOI_SOLR_API_AUTH_URL,
      {},
   UserService.getToken()
)
    .then((res) => {
      if (res.data) {
        return res.data; // ✅ Return the result for further use
      } else {
        console.log("No response from SOLR AUTH API");
      }
    })
    .catch((error) => {
     
      console.log(error);
      throw error; // 
    });
};

//SOLR FETCH PIIs by pagenum and documentid
export const fetchPIIByPageNumDocumentID = (
  pagenum: string,
  documentid: string,
  solrauthToken:any,
  numsolrrows:number,
  callback:any,
  errorCallback: any
) => {   
  let apiUrlGet: string = replaceUrl(replaceUrl(API.SOLR_API_URL,"<pagenum>",pagenum),"<documentid>",documentid) + "&rows=" + numsolrrows; 
  httpGETRequestSOLR(apiUrlGet, {}, solrauthToken)
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
        store.dispatch(setPIIJSONList(res.data) as any);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      console.log(error);
      errorCallback("Error in fetching PII values in service, fetchPIIByPageNumDocumentID");
    });
  
 
};

export const checkIDIR = (  
  callback: any,
  errorCallback: any,
  data:any
) => {
  let apiURL: string = `${API.IDIR_CHECK_URL}`;
  
  httpPOSTRequest({url: apiURL, data: data, token: UserService.getToken() ?? '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      console.log(error);
      errorCallback("Error in checking IDIR");
    });
  }

  export const saveRedlineContent = (
  foiministryrquestid: string,
  data: any,
  callback: any,
  errorCallback: any
) => {
  let apiUrlPost: string = replaceUrl(
    API.DOCREVIEWER_SAVE_REDLINECONTENT,
    "<ministryrequestid>",
    foiministryrquestid
  )
  
  httpPOSTRequest({
    url: apiUrlPost,
    data: data,
    token: UserService.getToken() ?? '',
    isBearer: true
  })
    .then((res: any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error("Error while posting redline content");
      }
    })
    .catch((error: any) => {
      errorCallback("Error in posting redline content");
    });
};