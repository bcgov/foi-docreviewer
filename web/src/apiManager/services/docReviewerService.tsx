 /* istanbul ignore file */
import { httpGETRequest, httpPOSTRequest } from "../httpRequestHandler";
import API from "../endpoints";
import UserService from "../../services/UserService";

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
