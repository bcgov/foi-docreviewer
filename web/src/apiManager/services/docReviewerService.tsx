 /* istanbul ignore file */
import { httpGETRequest, httpPOSTRequest } from "../httpRequestHandler";
import API from "../endpoints";
import UserService from "../../services/UserService";
import { setRedactionInfo, setIsPageLeftOff, setSections, setPageFlags,
  setDocumentList, setRequestStatus, setRedactionLayers, incrementLayerCount, setRequestNumber, setRequestInfo, setDeletedPages
} from "../../actions/documentActions";
import { store } from "../../services/StoreService";
import { number } from "yargs";


export const fetchDocuments = (
  foiministryrequestid: number,
  callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = `${API.DOCREVIEWER_DOCUMENT}/${foiministryrequestid}`
  
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
        callback(res.data);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      console.log(error);
      errorCallback("Error in fetching documents for a request");
    });
};

export const fetchAnnotationsByPagination = (
  ministryrequestid: number,
  activepage: number,
  size: number,
  callback: any,
  errorCallback: any,
  redactionlayer: string = "redline"
) => {
  
  let apiUrlGet: string = `${API.DOCREVIEWER_ANNOTATION}/${ministryrequestid}/${redactionlayer}/${activepage}/${size}`
  
  httpGETRequest(apiUrlGet, {}, UserService.getToken())
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
  errorCallback: any
) => {
  let apiUrlGet: string = `${API.DOCREVIEWER_ANNOTATION}/${ministryrequestid}/${redactionlayer}/document/${documentid}`
  
  httpGETRequest(apiUrlGet, {}, UserService.getToken())
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
        callback(res.data);
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
  //callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = replaceUrl(
    API.DOCREVIEWER_GET_PAGEFLAGS,
    "<requestid>",
    foiministryrquestid
  ) + "/" +  redactionlayer;
  
  httpGETRequest(apiUrlGet, {documentids: documentids}, UserService.getToken())
    .then((res:any) => {
      if (res.data || res.data === "") {
        store.dispatch(setPageFlags(res.data) as any);
        /** Checking if BOOKMARK set for package */
        let bookmarkedDoc= res.data?.filter((element:any) => {
          return element?.pageflag?.some((obj: any) =>(obj.flagid === 8));
        })
        store.dispatch(setIsPageLeftOff(bookmarkedDoc?.length >0) as any);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      errorCallback("Error in fetching pageflags for a document");
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