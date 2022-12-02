import { httpGETRequest } from "../httpRequestHandler";
import API from "../endpoints";
import UserService from "../../services/UserService";

export const getFOIS3DocumentPreSignedUrl = (
    documentid: number,
    callback: any,
    errorCallback: any
) => {
    const apiurl = API.FOI_GET_S3DOCUMENT_PRESIGNEDURL + "/" + documentid
    console.log("##Apiurl:",apiurl);
    httpGETRequest(apiurl, {}, UserService.getToken())
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