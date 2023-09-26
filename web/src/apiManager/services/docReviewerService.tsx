 /* istanbul ignore file */
import { httpGETRequest, httpPOSTRequest, httpDELETERequest } from "../httpRequestHandler";
import API from "../endpoints";
import UserService from "../../services/UserService";
import { setRedactionInfo, setIsPageLeftOff, setSections, setPageFlags, setDocumentList, setRequestInfo } from "../../actions/documentActions";
import { store } from "../../services/StoreService";


export const fetchDocuments = (
  foiministryrequestid: number,
  callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = `${API.DOCREVIEWER_DOCUMENT}/${foiministryrequestid}`
  
  httpGETRequest(apiUrlGet, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data) {
        store.dispatch(setDocumentList(res.data.documents) as any);
        store.dispatch(setRequestInfo(res.data.requestinfo) as any);
        callback(res.data.documents);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      console.log(error);
      errorCallback("Error in fetching documents for a request");
    });
};

export const fetchAnnotations = (
  ministryrequestid: number,
  callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = `${API.DOCREVIEWER_ANNOTATION}/${ministryrequestid}`
  
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
  //callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = `${API.DOCREVIEWER_ANNOTATION}/${ministryrequestid}/info`

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
  documentid: number,
  documentversion: number = 1,
  annotation: string = "",
  callback: any,
  errorCallback: any,
  pageFlags?: Array<any>,
  sections?: object,
) => {
  let apiUrlPost: string = `${API.DOCREVIEWER_ANNOTATION}/${documentid}/${documentversion}`;
  let requestJSON = sections ?{
    "xml": annotation,
    "sections": sections,
    } : 
    {
      "xml": annotation,
      "pageflags":pageFlags,
      "foiministryrequestid":requestid
    }
  httpPOSTRequest({url: apiUrlPost, data: requestJSON, token: UserService.getToken() || '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error(`Error while saving an annotation for (doc# ${documentid})`);
      }
    })
    .catch((error:any) => {
      errorCallback("Error in saving an annotation");
    });
};

export const deleteAnnotation = (
  requestid: string,
  documentid: number,
  documentversion: number = 1,
  annotationname: string = "",
  callback: any,
  errorCallback: any,
  page?: number
) => {
  let apiUrlDelete: string = page?`${API.DOCREVIEWER_ANNOTATION}/${requestid}/${documentid}/${documentversion}/${annotationname}/${page}`:
  `${API.DOCREVIEWER_ANNOTATION}/${requestid}/${documentid}/${documentversion}/${annotationname}`;
  httpDELETERequest({url: apiUrlDelete, data: "", token: UserService.getToken() || '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error(`Error while deleting an annotation for (doc# ${documentid}, annotationname ${annotationname})`);            
      }
    })
    .catch((error:any) => {
      errorCallback("Error in deleting an annotation");
    });
};

export const deleteRedaction = (
  requestid: string,
  documentid: number,
  documentversion: number = 1,
  annotationname: string = "",
  callback: any,
  errorCallback: any,
  page: number
) => {
  let apiUrlDelete: string = `${API.DOCREVIEWER_REDACTION}/${requestid}/${documentid}/${documentversion}/${annotationname}/${page}`;
  httpDELETERequest({url: apiUrlDelete, data: "", token: UserService.getToken() || '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error(`Error while deleting a redaction for (doc# ${documentid}, annotationname ${annotationname})`);            
      }
    })
    .catch((error:any) => {
      errorCallback("Error in deleting a redaction");
    });
};

export const fetchSections = (
  foiministryrquestid: number,
  callback: any,
  errorCallback: any
) => {
  let apiUrl: string  = replaceUrl(API.DOCREVIEWER_SECTIONS, '<ministryrequestid>', foiministryrquestid);

  httpGETRequest(apiUrl, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data || res.data === "") {
        store.dispatch(setSections(res.data) as any);
        //callback(res.data);
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
  callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = replaceUrl(
    API.DOCREVIEWER_GET_ALL_PAGEFLAGS,
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
  documentid: number,
  documentversion: number = 1,
  pagenumber: number,
  flagid: number,
  callback: any,
  errorCallback: any,
  data?: any
) => {
  let apiUrlPost: string = replaceUrl(replaceUrl(replaceUrl(
    API.DOCREVIEWER_POST_PAGEFLAGS,
    "<requestid>",
    foiministryrquestid
  ), "<documentid>", documentid), "<documentversion>",documentversion);
  let requestJSON = data || {
    "page": pagenumber,
    "flagid": flagid,
    }
  httpPOSTRequest({url: apiUrlPost, data: requestJSON, token: UserService.getToken() || '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error(`Error while saving page flag for (doc# ${documentid}, requestid ${foiministryrquestid})`);            
      }
    })
    .catch((error:any) => {
      errorCallback("Error in saving an page flag");
    });
};

export const fetchPageFlag = (
  foiministryrquestid: string,
  //callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = replaceUrl(
    API.DOCREVIEWER_GET_PAGEFLAGS,
    "<requestid>",
    foiministryrquestid
  );
  
  httpGETRequest(apiUrlGet, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data || res.data === "") {
        store.dispatch(setPageFlags(res.data) as any);
        /** Checking if BOOKMARK set for package */
        let bookmarkedDoc= res.data?.filter((element:any) => {
          return element?.pageflag?.some((obj: any) =>(obj.flagid === 8));
        })
        store.dispatch(setIsPageLeftOff(bookmarkedDoc?.length >0) as any);
        //callback(res.data);
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
  //let apiUrlGet: string = API.DOCREVIEWER_GET_ALL_PAGEFLAGS;
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

const replaceUrl = (URL: string, key: string, value: any) => {
  return URL.replace(key, value);
};