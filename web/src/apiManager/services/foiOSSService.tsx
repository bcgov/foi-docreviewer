import {
    httpPOSTRequest,
    httpGETRequest,
    httpOSSPUTRequest
} from "../httpRequestHandler";
import API from "../endpoints";
import UserService from "../../services/UserService";

export const getFOIS3DocumentPreSignedUrl = (
    documentid: number,
    callback: any,
    errorCallback: any
) => {
    const apiurl = API.FOI_GET_S3DOCUMENT_PRESIGNEDURL + "/" + documentid
    return httpGETRequest(apiurl, {}, UserService.getToken())
        .then((res:any) => {
            if (res.data) {
                callback(res.data);
            } else {
                throw new Error("fetch presigned s3 url with empty response");
            }
        })
        .catch((error:any) => {
            errorCallback(error);
        });
};

export const getFOIS3DocumentPreSignedUrls = (
    documentObjs: any,
    callback: any,
    errorCallback: any
) => {
    const apiurl = API.FOI_GET_S3DOCUMENT_PRESIGNEDURL;
    httpPOSTRequest({url: apiurl, data: {"documentobjs":documentObjs}, token: UserService.getToken() || ''})
    .then((res:any) => {
        if (res.data) {
            callback(res.data);
        } else {
            throw new Error("fetch presigned s3 url with empty response");
        }
    })
    .catch((error:any) => {
        errorCallback(error);
    });
};

export const getFOIS3DocumentRedlinePreSignedUrl = (
    ministryrequestID: any,
    requestType: any,
    documentList: any[],
    callback: any,
    errorCallback: any,
    layertype: any,
    layer: any,
    redlinePhase: any,
) => {	
    let apiurl;
    apiurl = API.FOI_GET_S3DOCUMENT_PRESIGNEDURL_REDLINE + "/" + layer.toLowerCase() + "/" + ministryrequestID;

    if (layertype === "oipcreview") {
        apiurl = apiurl + "/oipcreview"
    } else if (layertype === "consult") {
        apiurl = apiurl + "/consult"
    } else {
        apiurl = apiurl + "/" + layer
    }
    if (redlinePhase) {
        apiurl = apiurl + "/" + redlinePhase;
    }
    
    httpPOSTRequest({url: apiurl, data: {"divdocumentList":documentList,"requestType":requestType}, token: UserService.getToken() || ''})
        .then((res:any) => {
            if (res.data) {
                callback(res.data);
            } else {
                throw new Error("fetch presigned s3 url with empty response");
            }
        })
        .catch((error:any) => {
            errorCallback(error);
        });
};

export const saveFilesinS3 = (
    headerDetails: any,
    blob: any,
    callback: any,
    errorCallback: any
) => {
    httpOSSPUTRequest(headerDetails.filepath, blob, {})
        .then(
            (res: any) => {
                if (res) {
                    callback(res);
                } else {
                    throw new Error(`failed to save a file to s3`);
                }
            },
            (err: any) => {
                console.log(err);
                errorCallback(err);
            }
        )
        .catch((error: any) => {
            errorCallback(error)
        });
};

export const getResponsePackagePreSignedUrl = (
    ministryrequestID: any,
    firstDocInfo: any,
    phase:number,
    callback: any,
    errorCallback: any
) => {	
    const apiurl = API.FOI_GET_S3DOCUMENT_PRESIGNEDURL_RESPONSE_PACKAGE + "/" + ministryrequestID;

    httpPOSTRequest({url: apiurl, data: {"documentsInfo":firstDocInfo, "phase":phase}, token: UserService.getToken() || ''})
        .then((res:any) => {
            if (res.data) {
                callback(res.data);
            } else {
                throw new Error("fetch presigned s3 url with empty response");
            }
        })
        .catch((error:any) => {
            errorCallback(error);
        });
};
