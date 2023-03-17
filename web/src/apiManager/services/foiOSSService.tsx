import { httpGETRequest, httpPOSTRequest } from "../httpRequestHandler";
import API from "../endpoints";
import UserService from "../../services/UserService";

export const getFOIS3DocumentPreSignedUrl = (
    documentid: number,
    callback: any,
    errorCallback: any
) => {
    const apiurl = API.FOI_GET_S3DOCUMENT_PRESIGNEDURL + "/" + documentid
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


// export const getOSSHeaderDetails = (
//     data: any
// ) => {
//     httpPOSTRequest(API.FOI_POST_OSS_HEADER, data, UserService.getToken())
//         .then((res) => {
//             if (res.data) {
//             done(null, res.data);
//             } else {
//             dispatch(serviceActionError(res));
//             done("Error in getting OSS Header information");
//             }
//       })
//       .catch((error) => {
//         dispatch(serviceActionError(error));
//         done("Error in getting OSS Header information");
//       });
//     return response;
// };


// export const saveFilesinS3 = (
//     headerDetails,
//     file,
//     dispatch,
//     ...rest
// ) => {
//     const done = fnDone(rest);
//     let requestOptions = {
//       headers: {
//         'X-Amz-Date': headerDetails.amzdate,
//         'Authorization': headerDetails.authheader,
//       }
//     };
//     return httpOSSPUTRequest(headerDetails.filepath, file, requestOptions)
//       .then((res) => {
//         if (res) {
//           done(null, res.status);
//         } else {
//           done("Error in saving files to S3");
//           dispatch(serviceActionError(res));
//         }
//       })
//       .catch((error) => {
//         dispatch(serviceActionError(error));
//         done("Error in saving files to S3");
//       });
// };