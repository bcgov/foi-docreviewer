import { DOCREVIEWER_BASE_API_URL } from "./config";

const API = {
    FOI_GET_S3DOCUMENT_PRESIGNEDURL:`${DOCREVIEWER_BASE_API_URL}/api/foiflow/oss/presigned`,
    FOI_GET_S3DOCUMENT_PRESIGNEDURL_REDLINE:`${DOCREVIEWER_BASE_API_URL}/api/foiflow/oss/presigned`,
    FOI_GET_S3DOCUMENT_PRESIGNEDURL_RESPONSE_PACKAGE:`${DOCREVIEWER_BASE_API_URL}/api/foiflow/oss/presigned/responsepackage`,
    DOCREVIEWER_ANNOTATION:`${DOCREVIEWER_BASE_API_URL}/api/annotation`,
    DOCREVIEWER_REDACTION:`${DOCREVIEWER_BASE_API_URL}/api/redaction`,
    DOCREVIEWER_DOCUMENT:`${DOCREVIEWER_BASE_API_URL}/api/document`,
    DOCREVIEWER_SECTIONS:`${DOCREVIEWER_BASE_API_URL}/api/sections/ministryrequest/<ministryrequestid>`,
    DOCREVIEWER_GET_ALL_PAGEFLAGS:`${DOCREVIEWER_BASE_API_URL}/api/pageflags/ministryrequest/<requestid>`,
    DOCREVIEWER_POST_PAGEFLAGS:`${DOCREVIEWER_BASE_API_URL}/api/ministryrequest/<requestid>/pageflags`,
    DOCREVIEWER_GET_PAGEFLAGS:`${DOCREVIEWER_BASE_API_URL}/api/ministryrequest/<requestid>/pageflag`,
    DOCREVIEWER_GET_ALL_KEYWORDS:`${DOCREVIEWER_BASE_API_URL}/api/keywords`,
    DOCREVIEWER_GET_REDACTION_LAYERS:`${DOCREVIEWER_BASE_API_URL}/api/redactionlayers`,
    DOCREVIEWER_REDLINE:`${DOCREVIEWER_BASE_API_URL}/api/triggerdownloadredline`,
    DOCREVIEWER_FINALPACKAGE:`${DOCREVIEWER_BASE_API_URL}/api/triggerdownloadfinalpackage`,
    DOCREVIEWER_LICENSE:`${DOCREVIEWER_BASE_API_URL}/api/foiflow/webviewerlicense`,
    DOCREVIEWER_DOCUMENT_PAGE_DELETE:`${DOCREVIEWER_BASE_API_URL}/api/document/ministryrequest/<ministryrequestid>/<redactionlayer>/page/delete`,
};
export default API;
