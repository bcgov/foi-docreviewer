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
export const SESSION_SECURITY_KEY = "u7x!A%D*G-KaNdRgUkXp2s5v8y/B?E(H";
export const SESSION_LIFETIME = 21600000;
export const PDFVIEWER_DISABLED_FEATURES= window._env_?.REACT_APP_PDFVIEWERDISABLED ??
process.env.REACT_APP_PDFVIEWERDISABLED ??
"linkButton,stickyToolButton,highlightToolButton,freeHandToolButton,freeHandHighlightToolButton,freeTextToolButton,markInsertTextToolButton,markReplaceTextToolButton,textSquigglyToolButton,textStrikeoutToolButton,textRedactToolButton,textUnderlineToolButton,textHighlightToolButton,markReplaceTextGroupButton,markInsertTextGroupButton,strikeoutToolGroupButton,squigglyToolGroupButton,underlineToolGroupButton,highlightToolGroupButton,toolbarGroup-Edit,toolbarGroup-Insert,toolbarGroup-Forms,toolbarGroup-FillAndSign,insertPage,modalRedactButton,annotationRedactButton,richTextFormats,annotationGroupButton,annotationUngroupButton,multiGroupButton,multiUngroupButton,redactionPanel,redactionPanelToggle";
export const ANNOTATION_PAGE_SIZE = window._env_?.REACT_APP_ANNOTATION_PAGE_SIZE ?? process.env.REACT_APP_ANNOTATION_PAGE_SIZE ?? 500;
export const PAGE_SELECT_LIMIT = window._env_?.REACT_APP_PAGE_SELECT_LIMIT ?? process.env.REACT_APP_PAGE_SELECT_LIMIT ?? 250;
export const REDACTION_SELECT_LIMIT = window._env_?.REACT_APP_REDACTION_SELECT_LIMIT ?? process.env.REACT_APP_REDACTION_SELECT_LIMIT ?? 250;
