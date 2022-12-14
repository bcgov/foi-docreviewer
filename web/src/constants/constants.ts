//keycloak
export const Keycloak_Client =
    (window._env_ && window._env_.REACT_APP_KEYCLOAK_CLIENT) ||
    process.env.REACT_APP_KEYCLOAK_CLIENT ||
    "foi-document-redaction";
export const KEYCLOAK_REALM =
    (window._env_ && window._env_.REACT_APP_KEYCLOAK_URL_REALM) ||
    process.env.REACT_APP_KEYCLOAK_URL_REALM ||
    "5k8dbl4h";
export const KEYCLOAK_URL = (window._env_ && window._env_.REACT_APP_KEYCLOAK_URL) || process.env.REACT_APP_KEYCLOAK_URL || "https://dev.oidc.gov.bc.ca";
export const KEYCLOAK_AUTH_URL = `${KEYCLOAK_URL}/auth`;
export const ANONYMOUS_USER = "anonymous";
export const SESSION_SECURITY_KEY = "u7x!A%D*G-KaNdRgUkXp2s5v8y/B?E(H";
export const SESSION_LIFETIME = 21600000;


