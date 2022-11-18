export const WEB_BASE_URL = (window._env_ && window._env_.REACT_APP_WEB_BASE_URL) || process.env.REACT_APP_WEB_BASE_URL;

export const FOI_BASE_API_URL = `${(window._env_ && window._env_.REACT_APP_FOI_BASE_API_URL) || process.env.REACT_APP_FOI_BASE_API_URL}`;

export const DOCREVIEWER_BASE_API_URL = `${(window._env_ && window._env_.FOI_DOCREVIEWER_BASE_API_URL) || process.env.FOI_DOCREVIEWER_BASE_API_URL || "http://localhost:15500"}`;

// export const DOCREVIEWER_BASE_API_URL = 'http://localhost:5000'