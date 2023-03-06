import { DOCREVIEWER_BASE_API_URL } from "./config";

const API = {
    FOI_GET_S3DOCUMENT_PRESIGNEDURL:`${DOCREVIEWER_BASE_API_URL}/api/foiflow/oss/presigned`,
    DOCREVIEWER_ANNOTATION:`${DOCREVIEWER_BASE_API_URL}/api/annotation`,
    DOCREVIEWER_DOCUMENT:`${DOCREVIEWER_BASE_API_URL}/api/document`,
    DOCREVIEWER_SECTIONS:`${DOCREVIEWER_BASE_API_URL}/api/sections/ministryrequest/<ministryrequestid>`
};
export default API;
