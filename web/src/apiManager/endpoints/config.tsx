export const WEB_BASE_URL = (window._env_ && window._env_.REACT_APP_WEB_BASE_URL) || process.env.REACT_APP_WEB_BASE_URL;

export const DOCREVIEWER_BASE_API_URL = `${(window._env_ && window._env_.FOI_DOCREVIEWER_BASE_API_URL) || process.env.FOI_DOCREVIEWER_BASE_API_URL || "http://localhost:15500"}`;
export const SOLR_API_BASE_URL= `${(window._env_ && window._env_.SOLR_API_BASE_URL) || process.env.SOLR_API_BASE_URL || "https://solr-fc7a67-test.apps.gold.devops.gov.bc.ca/solr/foisearch_rook/select?"}`;
export const FOI_REQ_MANAGEMENT_API_URL = `${(window._env_ && window._env_.FOI_REQ_MANAGEMENT_API_URL) || process.env.FOI_REQ_MANAGEMENT_API_URL || "http://localhost:15000"}`;

// export const DOCREVIEWER_BASE_API_URL = 'http://localhost:15500'

// export const DOCREVIEWER_BASE_API_URL = 'https://dev-reviewer-api.apps.silver.devops.gov.bc.ca'