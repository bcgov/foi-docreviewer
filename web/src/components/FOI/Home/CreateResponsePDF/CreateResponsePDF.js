import { pageFlagTypes } from "../../../../constants/enum";

export const createResponsePDFMenu = (document) => {
  const menu = document.createElement("div");
  menu.classList.add("Overlay");
  menu.classList.add("FlyoutMenu");
  menu.id = "saving_menu";
  menu.style.right = "auto";
  menu.style.top = "30px";
  menu.style.minWidth = "200px";
  menu.padding = "0px";
  menu.style.display = "none";

  return menu;
};

export const createRedlineForSignOffSelection = (document, enableSave) => {
  const redlineForSignOffBtn = document.createElement("button");
  redlineForSignOffBtn.textContent = "Redline for Sign Off";
  redlineForSignOffBtn.id = "redline_for_sign_off";
  redlineForSignOffBtn.className = "redline_for_sign_off";
  redlineForSignOffBtn.style.backgroundColor = "transparent";
  redlineForSignOffBtn.style.border = "none";
  redlineForSignOffBtn.style.padding = "8px 8px 8px 10px";
  redlineForSignOffBtn.style.cursor = "pointer";
  redlineForSignOffBtn.style.alignItems = "left";
  redlineForSignOffBtn.disabled = !enableSave;

  return redlineForSignOffBtn;
};

export const createOIPCForReviewSelection = (document, enableSave) => {
  const redlineForOipcBtn = document.createElement("button");
  redlineForOipcBtn.textContent = "Redline for OIPC Review";
  redlineForOipcBtn.id = "redline_for_oipc";
  redlineForOipcBtn.className = "redline_for_oipc";
  redlineForOipcBtn.style.backgroundColor = "transparent";
  redlineForOipcBtn.style.border = "none";
  redlineForOipcBtn.style.padding = "8px 8px 8px 10px";
  redlineForOipcBtn.style.cursor = "pointer";
  redlineForOipcBtn.style.alignItems = "left";
  redlineForOipcBtn.disabled = !enableSave;

  return redlineForOipcBtn;
};

export const createFinalPackageSelection = (document, enableSave) => {
  const finalPackageBtn = document.createElement("button");
  finalPackageBtn.textContent = "Final Package for Applicant";
  finalPackageBtn.id = "final_package";
  finalPackageBtn.className = "final_package";
  finalPackageBtn.style.backgroundColor = "transparent";
  finalPackageBtn.style.border = "none";
  finalPackageBtn.style.padding = "8px 8px 8px 10px";
  finalPackageBtn.style.cursor = "pointer";
  finalPackageBtn.style.alignItems = "left";
  finalPackageBtn.disabled = !enableSave;

  return finalPackageBtn;
};

export const renderCustomButton = (document, menu) => {
  const menuBtn = document.createElement("button");
  menuBtn.textContent = "Create Response PDF";
  menuBtn.id = "create_response_pdf";
  menuBtn.onclick = async () => {
    if (menu.style.display === "flex") {
      menu.style.display = "none";
    } else {
      menu.style.left = `${
        document.body.clientWidth - (menuBtn.clientWidth + 96)
      }px`;
      menu.style.display = "flex";
    }
  };

  return menuBtn;
};

export const handleRedlineForSignOffClick = (
  updateModalData,
  setRedlineModalOpen
) => {
  // Save to s3
  updateModalData({
    modalFor: "redline",
    modalTitle: "Redline for Sign Off",
    modalMessage: [
      "Are you sure want to create the redline PDF for ministry sign off?",
      <br key="lineBreak1" />,
      <br key="lineBreak2" />,
      <span key="modalDescription1">
        When you create the redline PDF, your web browser page will
        automatically refresh
      </span>,
    ],
    modalButtonLabel: "Create Redline PDF"
  });
  setRedlineModalOpen(true);
};

export const handleRedlineForOipcClick = (
  updateModalData,
  setRedlineModalOpen
) => {
  // Save to s3
  updateModalData({
    modalFor: "oipcreview",
    modalTitle: "Redline for OIPC Review",
    modalMessage: [
      "Are you sure want to create the redline PDF for OIPC review?",
      <br key="lineBreak1" />,
      <br key="lineBreak2" />,
      <span key="modalDescription1">
        This redline will be created from the active layer with s.14 annotations redacted. 
        When you create the redline PDF, your web browser page will
        automatically refresh
      </span>,
    ],
    modalButtonLabel: "Create OIPC Redline PDF"
  });
  setRedlineModalOpen(true);
};

export const handleFinalPackageClick = (
  updateModalData,
  setRedlineModalOpen
) => {
  updateModalData({
    modalFor: "responsepackage",
    modalTitle: "Create Package for Applicant",
    modalMessage: [
    "This should only be done when all redactions are finalized and ready to ",
    <b key="bold1">
      <i>be</i>
    </b>,
    " sent to the ",
    <b key="bold2">
      <i>Applicant</i>
    </b>,
    ". This will ",
    <b key="bold3">
      <i>permanently</i>
    </b>,
    " apply the redactions and automatically create page stamps.",
    <br key="break1" />,
    <br key="break2" />,
    <span key="modalDescription2">
      When you create the response package, your web browser page
      will automatically refresh
    </span>,
  ],
    modalButtonLabel: "Create Applicant Package"
  });
  setRedlineModalOpen(true);
};

export const isReadyForSignOff = (documentList, pageFlags) => {
  let pageFlagArray = [];
  let stopLoop = false;
  if (documentList.length > 0 && documentList.length === pageFlags?.length) {
    documentList.every((docInfo) => {
      if (pageFlags?.length > 0) {
        pageFlags.every((pageFlagInfo) => {
          if (docInfo.documentid === pageFlagInfo?.documentid) {
            const exceptConsult = pageFlagInfo.pageflag?.filter(
              (flag) => flag.flagid !== pageFlagTypes["Consult"]
            );
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
  let isvalid = false;
  let pageFlagArray = [];
  if (pageFlags?.length > 0) {
    for (let pageFlagInfo of pageFlags) {
      pageFlagArray = pageFlagInfo.pageflag?.filter((flag) =>
        [
          pageFlagTypes["Partial Disclosure"],
          pageFlagTypes["Full Disclosure"],
          pageFlagTypes["Withheld in Full"],
          pageFlagTypes["Duplicate"],
          pageFlagTypes["Not Responsive"],
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