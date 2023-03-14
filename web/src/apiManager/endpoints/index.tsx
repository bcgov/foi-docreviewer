import { DOCREVIEWER_BASE_API_URL } from "./config";

const API = {
    FOI_GET_S3DOCUMENT_PRESIGNEDURL:`${DOCREVIEWER_BASE_API_URL}/api/foiflow/oss/presigned`,
    DOCREVIEWER_ANNOTATION:`${DOCREVIEWER_BASE_API_URL}/api/annotation`,
    DOCREVIEWER_DOCUMENT:`${DOCREVIEWER_BASE_API_URL}/api/document`,
    DOCREVIEWER_SECTIONS:`${DOCREVIEWER_BASE_API_URL}/api/sections/ministryrequest/<ministryrequestid>`,
    DOCREVIEWER_GET_ALL_PAGEFLAGS:`${DOCREVIEWER_BASE_API_URL}/api/pageflags/ministryrequest/<requestid>`,
    DOCREVIEWER_POST_PAGEFLAGS:`${DOCREVIEWER_BASE_API_URL}/api/ministryrequest/<requestid>/document/<documentid>/version/<documentversion>/pageflag`,
    DOCREVIEWER_GET_PAGEFLAGS:`${DOCREVIEWER_BASE_API_URL}/api/ministryrequest/<requestid>/pageflag`,
};
export default API;
