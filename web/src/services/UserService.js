import { ANONYMOUS_USER } from "../constants/constants";
import {
  setUserRole,
  setUserToken,
  setUserDetails,
  setUserAuthorization,
} from "../actions/userActions";

import { _kc } from "../constants/keycloakConstant";
import {
  isMinistryLogin,
  isProcessingTeam,
  isIntakeTeam,
  isFlexTeam,
  isOITeam,
} from "../helper/helper";

const tokenRefreshInterval = 180000; // how often we should check for token expiry --> 180000 = 3 mins
const tokenUpdateThreshold = 600; // if token expires in less than 10 minutes (600 seconds), refresh token

/**
 * Initializes Keycloak instance and calls the provided callback function if successfully authenticated.
 *
 * @param onAuthenticatedCallback
 */

const KeycloakData = _kc;

const doLogin = KeycloakData.login;
const doLogout = KeycloakData.logout;
const getToken = () => KeycloakData.token;

const initKeycloak = (store, ...rest) => {
  const done = rest.length ? rest[0] : () => {};
  KeycloakData.init({
    // onLoad: "check-sso",
    onLoad: "login-required",
    // silentCheckSsoRedirectUri: window.location.origin + "/silent-check-sso.html",
    pkceMethod: "S256",
    checkLoginIframe: false,
  })
    .then((authenticated) => {
      if (authenticated) {
        store.dispatch(setUserToken(KeycloakData.token));
        KeycloakData.loadUserInfo().then((res) => {
          store.dispatch(setUserDetails(res));
          const userGroups = res.groups.map((group) => group.slice(1));
          const authorized =
            isIntakeTeam(userGroups) ||
            isFlexTeam(userGroups) ||
            isProcessingTeam(userGroups) ||
            isOITeam(userGroups) ||
            isMinistryLogin(userGroups);
          store.dispatch(setUserAuthorization(authorized));
        });
        done(null, KeycloakData);
        refreshToken(store);
      } else {
        console.warn("not authenticated!");
        doLogin();
      }
    })
    .catch((error) => {
      console.log(error);
    });
};
let refreshInterval;
const refreshToken = (store) => {
  refreshInterval = setInterval(() => {
    KeycloakData &&
      KeycloakData.updateToken(tokenUpdateThreshold)
        .then((refreshed) => {
          if (refreshed) {
            store.dispatch(setUserToken(KeycloakData.token));
          }
        })
        .catch((error) => {
          console.log(error);
          userLogout();
        });
  }, tokenRefreshInterval);
};

/**
 * Logout function
 */
const userLogout = () => {
  localStorage.clear();
  sessionStorage.clear();
  clearInterval(refreshInterval);
  doLogout();
};

const authenticateAnonymousUser = (store) => {
  const user = ANONYMOUS_USER;
  store.dispatch(setUserRole([user]));
};

const UserService = {
  initKeycloak,
  userLogout,
  getToken,
  authenticateAnonymousUser,
};

export default UserService;
