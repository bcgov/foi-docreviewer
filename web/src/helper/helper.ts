
import { SESSION_SECURITY_KEY, SESSION_LIFETIME } from "../constants/constants";
import { toast } from "react-toastify";
import { KCProcessingTeams, MINISTRYGROUPS } from "../constants/enum";



let CryptoJS = require("crypto-js");

const replaceUrl = (URL: any, key: any, value: any) => {
  return URL.replace(key, value);
};

const isMinistryCoordinator = (userdetail: any, ministryteam: any) => {
  if (
    userdetail === undefined ||
    userdetail === null ||
    userdetail === "" ||
    userdetail.groups === undefined ||
    userdetail.groups.length === 0 ||
    ministryteam === undefined ||
    ministryteam === ""
  ) {
    return false;
  }

  if (
    userdetail.groups.indexOf("/Intake Team") !== -1 ||
    userdetail.groups.indexOf("/Flex Team") !== -1 ||
    userdetail.groups.indexOf("/Processing Team") !== -1
  ) {
    return false;
  } else if (userdetail.groups.indexOf("/" + ministryteam) !== -1) {
    return true;
  } else {
    return false;
  }
};

const isMinistryLogin = (userGroups: any) => {
  return Object.values(MINISTRYGROUPS).some((group) =>
    userGroups?.includes(group)
  );
};
const isProcessingTeam = (userGroups: any) => {
  return userGroups?.some((userGroup: any) =>
    KCProcessingTeams.includes(userGroup.replace("/", ""))
  );
};

const isFlexTeam = (userGroups: any) => {
  return (
    userGroups?.map((userGroup: any) => userGroup.replace("/", "")).indexOf("Flex Team") !== -1
  );
};

const isIntakeTeam = (userGroups: any) => {
  return (
    userGroups?.map((userGroup: any) => userGroup.replace("/", "")).indexOf("Intake Team") !== -1
  );
};

const encrypt = (obj: any) => {
  return CryptoJS.AES.encrypt(
    JSON.stringify(obj),
    SESSION_SECURITY_KEY
  ).toString();
};

const decrypt = (encrypted: any) => {
  if (encrypted) {
    let bytes = CryptoJS.AES.decrypt(encrypted, SESSION_SECURITY_KEY);
    return JSON.parse(bytes.toString(CryptoJS.enc.Utf8));
  } else {
    return {};
  }
};

const saveSessionData = (key: any, data: any) => {
  let expiresInMilliseconds = Date.now() + SESSION_LIFETIME;
  let sessionObject = {
    expiresAt: new Date(expiresInMilliseconds),
    sessionData: data,
  };

  sessionStorage.setItem(key, encrypt(sessionObject));
};

const getSessionData = (key: any) => {
  let sessionObject = decrypt(sessionStorage.getItem(key));

  if (sessionObject && sessionObject.sessionData && sessionObject.expiresAt) {
    let currentDate: Date = new Date();
    let expirationDate = sessionObject.expiresAt;

    if (Date.parse(currentDate.toDateString()) < Date.parse(expirationDate)) {
      return sessionObject.sessionData;
    } else {
      sessionStorage.removeItem(key);
      //console.log(`${key} session expired`);
      return null;
    }
  } else {
    return null;
  }
};

const addToFullnameList = (userArray: any, foiteam: any) => {
  if (!foiteam) return;

  const _team = foiteam.toLowerCase();
  let currentMember;

  //fullname array (all teams) -> fullname value pairs
  let fullnameArray = getSessionData("fullnameList");
  if (!Array.isArray(fullnameArray)) {
    fullnameArray = [];
  }

  //teams saved in fullnameList
  let fullnameTeamArray = getSessionData("fullnameTeamList");
  if (!Array.isArray(fullnameTeamArray)) {
    fullnameTeamArray = [];
  }

  //extract fullname and append to the array
  if (Array.isArray(userArray)) {
    userArray?.forEach((team) => {
      if (Array.isArray(team?.members)) {
        team.members?.forEach((member: any) => {
          if (!fullnameArray.some((e: any) => e.username === member.username)) {
            currentMember = {
              username: member.username,
              fullname: `${member.lastname}, ${member.firstname}`,
            };
            fullnameArray.push(currentMember);
          }
        });
      }
    });

    //save team name
    if (!fullnameTeamArray.includes(_team)) {
      fullnameTeamArray.push(_team);
      saveSessionData(`fullnameTeamList`, fullnameTeamArray);

      //save for assignedto or ministryassignto dropdown
      saveSessionData(`${_team}AssignToList`, userArray);
    }
  }
  saveSessionData("fullnameList", fullnameArray);
};

const getFullnameList = () => {
  return getSessionData("fullnameList") || [];
};

const getAssignToList = (team: any) => {
  return getSessionData(`${team.toLowerCase()}AssignToList`);
};

const getFullnameTeamList = () => {
  return getSessionData("fullnameTeamList");
};


const errorToast = (errorMessage: any, options?: any) => {
  const defaultOptions = {
    position: "top-right",
    autoClose: 3000,
    hideProgressBar: true,
    closeOnClick: true,
    pauseOnHover: true,
    draggable: true,
    progress: undefined,
  }
  return toast.error(errorMessage, { ...defaultOptions, ...options });
};

export {
  replaceUrl,
  isMinistryCoordinator,
  isMinistryLogin,
  addToFullnameList,
  getFullnameList,
  getAssignToList,
  getFullnameTeamList,
  errorToast,
  isProcessingTeam,
  isFlexTeam,
  isIntakeTeam,
  encrypt,
  decrypt,
};