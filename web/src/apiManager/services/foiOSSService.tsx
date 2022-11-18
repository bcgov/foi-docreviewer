import {
    httpPOSTRequest,
    httpGETRequest
  } from "../httpRequestHandler";
import API from "../endpoints";
import UserService from "../../services/UserService";


export const getFOIS3DocumentPreSignedUrl = (filepath: string, ministryrequestid: string, dispatch: any, ...rest:any[]) => {
    const done = rest.length ? rest[0] : "";
    const apiurl = API.FOI_GET_S3DOCUMENT_PRESIGNEDURL + "/" + (ministryrequestid == undefined ? "-1" : ministryrequestid) + "?filepath=" + filepath
    console.log("##Apiurl:",apiurl);
    const token = UserService.getToken();
    const response = httpGETRequest(apiurl, {}, token);
    response.then((res) => {
        if (res.data) {
            done(null, res.data);
        } else {
            console.log("No data!! ");
            //dispatch(serviceActionError(res));
            //done("Error in getFOIS3DocumentPreSignedUrl");
        }
    })
        .catch((error) => {
            console.log("Error in getFOIS3DocumentPreSignedUrl: ",error);
           //dispatch(serviceActionError(error));
            //done("Error in getFOIS3DocumentPreSignedUrl");
        });
    return response;
};