import { pageFlagTypes } from "../../../../constants/enum";
import TextField from "@mui/material/TextField";
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';

import Dropdown from 'react-bootstrap/Dropdown';
import DropdownButton from 'react-bootstrap/DropdownButton';


import React, { useEffect, useState } from "react";
import ReactModal from "react-modal-resizable-draggable";
// import useSaveResponsePackage from "./useSaveResponsePackage";

export const createResponsePDFMenu = (document, docInstance, docViewer) => {
  // const {enableSavingRedline} = useSaveResponsePackage(docInstance, docViewer);
  const menu = document.createElement("div");
  menu.classList.add("Overlay");
  menu.classList.add("FlyoutMenu");
  menu.id = "saving_menu";
  menu.style.right = "auto";
  menu.style.top = "30px";
  menu.style.minWidth = "200px";
  menu.padding = "0px";
  menu.style.display = "none";

  // const redlineForSignOffBtn = createRedlineForSignOffSelection(document, enableSavingRedline);
  // const redlineForOipcBtn = createOIPCForReviewSelection(document, enableSavingOipcRedline);
  // const finalPackageBtn = createFinalPackageSelection(document, enableSavingFinal);
  // redlineForOipcBtn.onclick = () => {
  //   handleRedlineForOipcClick(setModalFor, setModalTitle, setModalMessage, setModalButtonLabel, setRedlineModalOpen);
  // };
  // redlineForSignOffBtn.onclick = () => {
  //   handleRedlineForSignOffClick(setModalFor, setModalTitle, setModalMessage, setModalButtonLabel, setRedlineModalOpen);
  // };
  // finalPackageBtn.onclick = () => {
  //   handleFinalPackageClick(setModalFor, setModalTitle, setModalMessage, setModalButtonLabel, setRedlineModalOpen);
  // };
  // menu.appendChild(redlineForOipcBtn);
  // menu.appendChild(redlineForSignOffBtn);
  // menu.appendChild(finalPackageBtn);

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
  setModalFor,
  setModalTitle,
  setModalMessage,
  setModalButtonLabel,
  setRedlineModalOpen
) => {
  console.log("redlinebtn");
  // Save to s3
  setModalFor("redline");
  setModalTitle("Redline for Sign Off");
  setModalMessage([
    "Are you sure want to create the redline PDF for ministry sign off?",
    <br key="lineBreak1" />,
    <br key="lineBreak2" />,
    <span key="modalDescription1">
      When you create the redline PDF, your web browser page will automatically
      refresh
    </span>,
  ]);
  setModalButtonLabel("Create Redline PDF");
  setRedlineModalOpen(true);
};

export const handleRedlineForOipcClick = (
  setModalFor,
  setModalTitle,
  setModalMessage,
  setModalButtonLabel,
  setRedlineModalOpen
) => {
  console.log("oipcbtn");
  // Save to s3
  setModalFor("oipcreview");
  setModalTitle("Redline for OIPC Review");
  setModalMessage([
    "Are you sure want to create the redline PDF for OIPC review?",
    <br key="lineBreak1" />,
    <br key="lineBreak2" />,
    <span key="modalDescription1">
      This redline will be created from the active layer with s.14 annotations
      redacted. When you create the redline PDF, your web browser page will
      automatically refresh
    </span>,
  ]);
  setModalButtonLabel("Create OIPC Redline PDF");
  setRedlineModalOpen(true);
};

export const handleFinalPackageClick = (
  setModalFor,
  setModalTitle,
  setModalMessage,
  setModalButtonLabel,
  setRedlineModalOpen
) => {
  console.log("finalbtn");
  // Download
  setModalFor("responsepackage");
  setModalTitle("Create Package for Applicant");
  setModalMessage([
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
      When you create the response package, your web browser page will
      automatically refresh
    </span>,
  ]);
  setModalButtonLabel("Create Applicant Package");
  setRedlineModalOpen(true);
};

export const isReadyForSignOff = (documentList, pageFlags) => {
  console.log("READYFORSIGNOFF");
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
  console.log("isvalidredlinedownload");
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
  
export class ResponseDropdown extends React.Component {
  constructor(props) {
    super(props);
    this.menuBtn = React.createRef()
    this.state = {
      modalOpen: false
    }
    const parent = props.instance.Core.documentViewer.getScrollViewElement().parentElement;
    const document = props.instance.UI.iframeWindow.document;
    const menu = createResponsePDFMenu(document);
    const redlineForSignOffBtn = createRedlineForSignOffSelection(document, true);
    const redlineForOipcBtn = createOIPCForReviewSelection(document, true);
    const finalPackageBtn = createFinalPackageSelection(document, true);
    redlineForOipcBtn.onclick = () => {
      this.setState({
        modalOpen: true
      });
    };
    // redlineForOipcBtn.onclick = () => {
    //   handleRedlineForOipcClick(setModalFor, setModalTitle, setModalMessage, setModalButtonLabel, setRedlineModalOpen);
    // };
    // redlineForSignOffBtn.onclick = () => {
    //   handleRedlineForSignOffClick(setModalFor, setModalTitle, setModalMessage, setModalButtonLabel, setRedlineModalOpen);
    // };
    // finalPackageBtn.onclick = () => {
    //   handleFinalPackageClick(setModalFor, setModalTitle, setModalMessage, setModalButtonLabel, setRedlineModalOpen);
    // };
    menu.appendChild(redlineForOipcBtn);
    menu.appendChild(redlineForSignOffBtn);
    menu.appendChild(finalPackageBtn);
    parent.appendChild(menu);
    this.options = [
      {
        "label": "Redline for OIPC Review",      
      },
      {
        "label": "Redline for Sign Off",      
      },
      {
        "label": "Final Package for Applicant",      
      },
    ]
    this.openMenu = () => {
      if (menu.style.display === "flex") {
        menu.style.display = "none";
      } else {
        menu.style.left = `${
          document.body.clientWidth - (this.menuBtn.current.clientWidth + 96)
        }px`;
        menu.style.display = "flex";
      }
    }
  }
  render() { return (
    <>
      <ReactModal
          initWidth={800}
          initHeight={300}
          minWidth={600}
          minHeight={250}
          className={"state-change-dialog"}
          // onRequestClose={}
          isOpen={this.state.modalOpen}
      ></ReactModal>
      <button ref={this.menuBtn} class="create_response_pdf" onClick={this.openMenu}>
        Create Response PDF
      </button>
    </>
  )}
}

// export const Slider = () => {
//   const [test, setTest] = useState(0)
//   return (
//     <input
//       value={test}
//       type="range"
//       onInput={(e) => { setTest(e.target.value)}}
//     >
//     </input>    
//   );
// }
