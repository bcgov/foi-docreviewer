 /* istanbul ignore file */
import { httpGETRequest, httpPOSTRequest, httpDELETERequest } from "../httpRequestHandler";
import API from "../endpoints";
import UserService from "../../services/UserService";

export const fetchDocuments = (
  foiministryrequestid: number = 1,
  callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = `${API.DOCREVIEWER_DOCUMENT}/${foiministryrequestid}`
  
  httpGETRequest(apiUrlGet, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data) {
        console.log(res.data);
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

export const fetchAnnotations = (
  documentid: number = 1,
  documentversion: number = 1,
  callback: any,
  errorCallback: any
) => {
  let apiUrlGet: string = `${API.DOCREVIEWER_ANNOTATION}/${documentid}/${documentversion}`
  
  httpGETRequest(apiUrlGet, {}, UserService.getToken())
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error();
      }
    })
    .catch((error:any) => {
      errorCallback("Error in fetching annotations for a document");
    });
};

export const saveAnnotation = (
  documentid: number = 1,
  documentversion: number = 1,
  pagenumber: number = 0,
  annotationname: string = "",
  annotation: string = "",
  callback: any,
  errorCallback: any
) => {
  let apiUrlPost: string = `${API.DOCREVIEWER_ANNOTATION}/${documentid}/${documentversion}/${pagenumber}/${annotationname}`;
  let requestJSON = {xml: annotation}

  httpPOSTRequest({url: apiUrlPost, data: requestJSON, token: UserService.getToken() || '', isBearer: true})
    .then((res:any) => {
      if (res.data) {
        callback(res.data);
      } else {
        throw new Error(`Error while saving an annotation for (doc# ${documentid}, annotationname ${annotationname})`);            
      }
    })
    .catch((error:any) => {
      errorCallback("Error in saving an annotation");
    });
};

export const deleteAnnotation = (
  documentid: number = 1,
  documentversion: number = 1,
  pagenumber: number = 0,
  annotationname: string = "",
  callback: any,
  errorCallback: any
) => {
  let apiUrlDelete: string = `${API.DOCREVIEWER_ANNOTATION}/${documentid}/${documentversion}/${pagenumber}/${annotationname}`;

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
