//keycloak
export const Keycloak_Client =
    window._env_?.REACT_APP_KEYCLOAK_CLIENT ??
    process.env.REACT_APP_KEYCLOAK_CLIENT ??
    "foi-document-redaction";
export const KEYCLOAK_REALM =
    window._env_?.REACT_APP_KEYCLOAK_URL_REALM ??
    process.env.REACT_APP_KEYCLOAK_URL_REALM ??
    "5k8dbl4h";
export const KEYCLOAK_URL = window._env_?.REACT_APP_KEYCLOAK_URL ?? process.env.REACT_APP_KEYCLOAK_URL ?? "https://dev.oidc.gov.bc.ca";
export const KEYCLOAK_AUTH_URL = `${KEYCLOAK_URL}/auth`;
export const ANONYMOUS_USER = "anonymous";
export const SESSION_SECURITY_KEY = window._env_?.REACT_APP_SESSION_SECURITY_KEY ?? process.env.REACT_APP_SESSION_SECURITY_KEY;
export const SESSION_LIFETIME = 21600000;
export const PDFVIEWER_DISABLED_FEATURES= window._env_?.REACT_APP_PDFVIEWERDISABLED ??
process.env.REACT_APP_PDFVIEWERDISABLED ??
"linkButton,stickyToolButton,highlightToolButton,freeHandToolButton,freeHandHighlightToolButton,freeTextToolButton,markInsertTextToolButton,markReplaceTextToolButton,textSquigglyToolButton,textStrikeoutToolButton,textRedactToolButton,textUnderlineToolButton,textHighlightToolButton,markReplaceTextGroupButton,markInsertTextGroupButton,strikeoutToolGroupButton,squigglyToolGroupButton,underlineToolGroupButton,highlightToolGroupButton,toolbarGroup-Edit,toolbarGroup-Insert,toolbarGroup-Forms,toolbarGroup-FillAndSign,insertPage,modalRedactButton,annotationRedactButton,richTextFormats,annotationGroupButton,annotationUngroupButton,multiGroupButton,multiUngroupButton,redactionPanel,redactionPanelToggle";
export const ANNOTATION_PAGE_SIZE = window._env_?.REACT_APP_ANNOTATION_PAGE_SIZE ?? process.env.REACT_APP_ANNOTATION_PAGE_SIZE ?? 500;
export const PAGE_SELECT_LIMIT = window._env_?.REACT_APP_PAGE_SELECT_LIMIT ?? process.env.REACT_APP_PAGE_SELECT_LIMIT ?? 250;
export const REDACTION_SELECT_LIMIT = window._env_?.REACT_APP_REDACTION_SELECT_LIMIT ?? process.env.REACT_APP_REDACTION_SELECT_LIMIT ?? 250;
export const BIG_HTTP_GET_TIMEOUT = window._env_?.REACT_APP_BIG_HTTP_GET_TIMEOUT ?? process.env.REACT_APP_BIG_HTTP_GET_TIMEOUT ?? 300000;
export const REDLINE_OPACITY = window._env_?.REACT_APP_REDLINE_OPACITY ?? process.env.REACT_APP_REDLINE_OPACITY ?? 0.5;
export const REDACTION_SECTION_BUFFER = window._env_?.REACT_APP_REDACTION_SECTION_BUFFER ?? process.env.REACT_APP_REDACTION_SECTION_BUFFER ?? 3;
export const PII_CATEGORIES = window._env_?.REACT_APP_PII_CATEGORIES ?? process.env.REACT_APP_PII_CATEGORIES ?? 'Person,Email,Age,PassportNumber';
export const PII_BLACKLIST = window._env_?.REACT_APP_PII_BLACKLIST ?? process.env.REACT_APP_PII_BLACKLIST ?? '@gov.bc.ca';
export const PII_NUM_ROWS = window._env_?.REACT_APP_PII_NUM_ROWS ?? process.env.REACT_APP_PII_NUM_ROWS ?? 100;
