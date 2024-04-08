import { pageFlagTypes, RequestStates } from "../../../../constants/enum";

export const isReadyForSignOff = (documentList, pageFlags) => {
    console.log("READYFORSIGNOFF")
    let pageFlagArray = [];
    let stopLoop = false;
    if (
      documentList.length > 0 &&
      documentList.length === pageFlags?.length
    ) {
      documentList.every((docInfo) => {
        if (pageFlags?.length > 0) {
          pageFlags.every((pageFlagInfo) => {
            if (docInfo.documentid === pageFlagInfo?.documentid) {
              const exceptConsult = pageFlagInfo.pageflag?.filter(flag => flag.flagid !== pageFlagTypes["Consult"])
              if (docInfo.pagecount > exceptConsult?.length) {
                // not all page has flag set
                stopLoop = true;
                return false; //stop loop
              } else {
                // Partial Disclosure, Full Disclosure, Withheld in Full, Duplicate, Not Responsive
                pageFlagArray = pageFlagInfo.pageflag?.filter((flag) =>
                  [
                    pageFlagTypes["Partial Disclosure"],
                    pageFlagTypes["Full Disclosure"],
                    pageFlagTypes["Withheld in Full"],
                    pageFlagTypes["Duplicate"],
                    pageFlagTypes["Not Responsive"],
                  ].includes(flag.flagid)
                );
                if (pageFlagArray.length != exceptConsult?.length) {
                  stopLoop = true;
                  return false; //stop loop
                }
              }
            }
            return true; //continue loop
          });
        } else {
          stopLoop = true;
        }

        return !stopLoop; //stop / continue loop
      });
    } else {
      return false;
    }

    return !stopLoop;
  };

export const isValidRedlineDownload = (pageFlags) => {
    console.log("isvalidredlinedownload")
    let isvalid = false;
    let pageFlagArray = [];
    if (pageFlags?.length > 0) {
      for (let pageFlagInfo of pageFlags) {
        pageFlagArray = pageFlagInfo.pageflag?.filter((flag) =>
          [
            pageFlagTypes["Partial Disclosure"],
            pageFlagTypes["Full Disclosure"],
            pageFlagTypes["Withheld in Full"],
          ].includes(flag.flagid)
        );
        if (pageFlagArray.length > 0) {
          if (isvalid === false) {
            isvalid = true;
          }
        }
      }
    }
    return isvalid;
  };

//TEST
export const isValidRedlineDivisionDownload = (divisionid, divisionDocuments, includeDuplicatePages, includeNRPages) => {
    console.log("isValidRedlineDivisionDownload")
    let isvalid = false;
    for (let divObj of divisionDocuments) {    
      if (divObj.divisionid == divisionid)  {
        // enable the Redline for Sign off if a division has only Incompatable files
        if (divObj?.incompatableList?.length > 0) {
          if(isvalid == false) {
            isvalid = true; 
          } 
        }
        else {
          for (let doc of divObj.documentlist) {
            for (const flagInfo of doc.pageFlag) {
              // Added condition to handle Duplicate/NR clicked for Redline for Sign off Modal
              if (
                  (flagInfo.flagid != pageFlagTypes["Duplicate"] && flagInfo.flagid != pageFlagTypes["Not Responsive"]) ||
                  (
                    (includeDuplicatePages && flagInfo.flagid === pageFlagTypes["Duplicate"]) ||
                    (includeNRPages && flagInfo.flagid === pageFlagTypes["Not Responsive"])
                  )
                ) {
                  if(isvalid === false) {
                    isvalid = true; 
                  } 
              }
            }
          }
        }
      }
    }
    return isvalid;
  };

export const checkSavingRedline = (enableSavingRedline, requestStatus, instance, setEnableSavingRedline) => {
  const validRedlineStatus = [
    RequestStates["Records Review"],
    RequestStates["Ministry Sign Off"],
    RequestStates["Peer Review"],
  ].includes(requestStatus);
  setEnableSavingRedline(enableSavingRedline && validRedlineStatus);
  if (instance) {
    const document = instance.UI.iframeWindow.document;
    document.getElementById("redline_for_sign_off").disabled = !enableSavingRedline || !validRedlineStatus;
  }
}

export const checkSavingOIPCRedline = (enableSavingOipcRedline, requestStatus, instance, readyForSignOff, setEnableSavingOipcRedline) => {
  const validOIPCRedlineStatus = [
    RequestStates["Records Review"],
    RequestStates["Ministry Sign Off"]
  ].includes(requestStatus);
  setEnableSavingOipcRedline(enableSavingOipcRedline && validOIPCRedlineStatus);
  if (instance) {
    const document = instance.UI.iframeWindow.document;
    document.getElementById("redline_for_oipc").disabled = !enableSavingOipcRedline || !validOIPCRedlineStatus || !readyForSignOff;
  }
}

export const checkSavingFinalPackage = (enableSavingRedline, requestStatus, instance, setEnableSavingFinal) => {
  const validFinalPackageStatus = requestStatus === RequestStates["Response"];
  setEnableSavingFinal(enableSavingRedline && validFinalPackageStatus);
  if (instance) {
    const document = instance.UI.iframeWindow.document;
    document.getElementById("final_package").disabled = !enableSavingRedline || !(validFinalPackageStatus);
  }
}