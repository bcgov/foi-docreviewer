import React, { useState, useEffect } from "react";
import Popover from "@mui/material/Popover";
import MenuList from "@mui/material/MenuList";
import MenuItem from "@mui/material/MenuItem";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCirclePlus, faAngleRight } from "@fortawesome/free-solid-svg-icons";
import { IconProp } from "@fortawesome/fontawesome-svg-core";
import { savePageFlag, editPersonalAttributes } from "../../../apiManager/services/docReviewerService";
import ConsultModal from "./ConsultModal";
import {
  getStitchedPageNoFromOriginal,
  createPageFlagPayload,
  getProgramAreas,
  updatePageFlagOnPage,
} from "./utils";
import { useAppSelector } from "../../../hooks/hook";
import MCFPersonal from "./MCFPersonal";
import { pageFlagTypes } from "../../../constants/enum";

const ContextMenu = ({
  openFOIPPAModal,
  requestId,
  pageFlagList,
  assignIcon,
  anchorPosition,
  openContextPopup,
  setOpenContextPopup,
  selectedPages,
  consultInfo,
  pageMappedDocs,
  pageFlags,
  syncPageFlagsOnAction,
  filesForDisplay,
  activeNode,
  requestInfo,
  currentEditRecord,
  setCurrentEditRecord
}: any) => {

  const [editTagModalOpen, setEditTagModalOpen] = useState(false);
  const [divisionModalTagValue, setDivisionModalTagValue] = useState(-1);
  const [curPersonalAttributes, setCurPersonalAttributes] = useState<any>({
    person: "",
    filetype: "",
    volume: "",
    trackingid: "",
    personaltag: "TBD"
  });
  const [newPersonalAttributes, setNewPersonalAttributes] = useState<any>();
  const [disablePageFlags, setDisablePageFlags] = useState(false);

  useEffect(() => {
    if(currentEditRecord?.attributes?.personalattributes)
      setCurPersonalAttributes(currentEditRecord.attributes.personalattributes);
  },[currentEditRecord])

  useEffect(() => {
    setDisablePageFlags(Object.keys(activeNode).length == 1);
  },[activeNode])
  
  const [openModal, setOpenModal] = useState(false);
  const [flagId, setFlagId] = React.useState(0);
  const currentLayer = useAppSelector(
    (state: any) => state.documents?.currentLayer
  );
  const validoipcreviewlayer = useAppSelector(
    (state: any) => state.documents?.requestinfo?.validoipcreviewlayer
  );

  const editTags = () => {
    setEditTagModalOpen(true);
  }

  const openConsultModal = (flagId: number) => {
    setOpenModal(true);
    setFlagId(flagId);
  };

  const savePageFlags = (flagId: number, data?: any) => {
    if (flagId === pageFlagTypes["Withheld in Full"]) {
      openFOIPPAModal(
        selectedPages.map((page: any) =>
          getStitchedPageNoFromOriginal(page.docid, page.page, pageMappedDocs)
        ),
        flagId
      );
    } else {
      let payload = createPageFlagPayload(
        selectedPages,
        currentLayer.redactionlayerid,
        flagId,
        data
      );
      let documentpageflags: any = payload.documentpageflags;
      savePageFlag(
        requestId,
        flagId,
        (data: any, flagid: number) => {
            if(data.status == true){
                const updatedPageFlags = updatePageFlagOnPage(
                    data.updatedpageflag,
                    pageFlags
                );
                if(updatedPageFlags?.length > 0)
                  syncPageFlagsOnAction(updatedPageFlags, [pageFlagTypes["Duplicate"], pageFlagTypes["Not Responsive"]].includes(flagid));
            }
        },
        (error: any) => console.log(error),
        payload
      );
    }
    setOpenContextPopup(false);
  };

  const getSelectedPhaseNo = (pageFlag: any) =>{
    let flag =pageFlags.find((d:any) => d.documentid === selectedPages[0]?.docid);
    let selected= flag?.pageflag.find((p:any) => (p.page === selectedPages[0]?.page && p.flagid===9 ));
    let phases= (!!selected && "phase" in selected) ? selected.phase : [0];
    return phases[0];
  }

  const showPageFlagList = () => {
    if (validoipcreviewlayer && currentLayer.name.toLowerCase() === "redline") {
      return (
        <MenuList key={"disabledpageflagsmenu"}>
          <MenuItem disabled={true}>
            <div>Disabled for OIPC review</div>
          </MenuItem>
        </MenuList>
      );
    }
    return pageFlagList?.map((pageFlag: any) => {
      const selectedPhase = selectedPages.length === 1 ? getSelectedPhaseNo(pageFlag): 0
      return pageFlag?.name === "Page Left Off" ? (
        <div
          className="pageLeftOff"
          style={
            selectedPages.length !== 1 || disablePageFlags
              ? { cursor: "not-allowed", color: "#cfcfcf" }
              : {}
          }
          onClick={() => {
            if (selectedPages.length === 1) {
              savePageFlags(pageFlag.pageflagid);
            }
          }}
        >
          {/* <hr className="hrStyle" /> */}
          <div>
            {pageFlag?.name}
            <span className="pageLeftOffIcon">
              <FontAwesomeIcon
                icon={assignIcon("Page Left Off") as IconProp}
                size="1x"
              />
            </span>
          </div>
        </div>
      ) : pageFlag?.name === "Phase" ? (
        <div>
          <hr className="hrStyle" />
          <div style={{marginLeft:"16px"}}>
            {pageFlag?.name}
          </div>
          <PhaseFlags pageFlag={pageFlag} selectedPhase={selectedPhase} />
          <hr className="hrStyle" />
        </div>
      ): 
      (
        <>
          <MenuList key={pageFlag?.pageflagid}>
            <MenuItem disabled={disablePageFlags}>
              {pageFlag?.name == "Consult" ? (
                <>
                  <div onClick={() => openConsultModal(pageFlag.pageflagid)}>
                    {/* <div onClick={popoverEnter}> */}
                    <FontAwesomeIcon
                      style={{ marginRight: "10px" }}
                      icon={assignIcon(pageFlag?.name) as IconProp}
                      size="1x"
                    />
                    {pageFlag?.name}
                    <span style={{ float: "right", marginLeft: "51px" }}>
                      <FontAwesomeIcon
                        icon={faAngleRight as IconProp}
                        size="1x"
                      />
                    </span>
                  </div>
                </>
              ) : (
                <div onClick={() => savePageFlags(pageFlag.pageflagid)}>
                  <FontAwesomeIcon
                    style={{ marginRight: "10px" }}
                    icon={assignIcon(pageFlag?.name) as IconProp}
                    size="1x"
                  />
                  {pageFlag?.name}
                </div>
              )}
            </MenuItem>
          </MenuList>
        </>
      );
    });
  };

  const comparePersonalAttributes = (a: any, b: any) => {
    return a?.person === b?.person && a?.volume === b?.volume
              && a?.filetype === b?.filetype
              && a?.personaltag === b?.personaltag
              && a?.trackingid === b?.trackingid;
  };

  const updatePersonalAttributes = (_all = false) => {
    setEditTagModalOpen(false);
    setOpenContextPopup(false);
    var documentMasterIDs = [];

    if(newPersonalAttributes) {
      if(_all) {
        for (let record of filesForDisplay) {
          if(record.attributes?.personalattributes?.person
             && record.attributes?.personalattributes?.person === currentEditRecord.attributes?.personalattributes?.person
            //  && record.attributes?.personalattributes?.filetype
            //  && record.attributes?.personalattributes?.filetype === currentEditRecord.attributes?.personalattributes?.filetype
          ) {
            documentMasterIDs.push(record.documentmasterid);
          }
        }
      } else {
        documentMasterIDs.push(currentEditRecord.documentmasterid);
      }
      
      if(currentEditRecord && !comparePersonalAttributes(newPersonalAttributes, curPersonalAttributes)) {
        editPersonalAttributes(
          requestId,
          (data: any) => {
              if(data.status == true){
                  console.log("Personal attributes updated")
              }
          },
          (error: any) => console.log(error),
          {
            documentmasterids: documentMasterIDs,
            personalattributes: newPersonalAttributes,
            ministryrequestid: requestId
          },
        );
  
        setCurrentEditRecord();
        setCurPersonalAttributes({
          person: "",
          filetype: "",
          volume: "",
          trackingid: "",
          personaltag: "TBD"
        });
        setNewPersonalAttributes({});
      }      
    }
  };

  const [showAll, setShowAll] = useState(false); // State to control visibility of all numbers
  const[selectedPhaseFlag, setSelectedPhaseFlag] = useState({});
  
  const addPhaseFlag = (pageFlagId:number, phaseNumber:number, selectedPhase:number)=>{
    let phase=[]
    if(selectedPhase != phaseNumber)
      phase.push(phaseNumber)
    else
      phase = []
    let phaseFlags = { flagid: pageFlagId, phase: phase }
    setSelectedPhaseFlag(phaseFlags)
    savePageFlags(pageFlagId,phaseFlags)
  }
  
  const handleToggle = () => {
    setShowAll(!showAll); // Toggle between showing all and showing the first 3
  };

  // const PhaseFlags = ({pageFlag, selectedPhase }: any) => {
  //   return (
  //     <div
  //       //className="phasesGrid"
  //       style={{
  //         display: "grid",
  //         gridTemplateColumns: "repeat(4, auto)",
  //         padding: "10px",
  //         margin: "10px",
  //       }}
  //     >
  //       {Array.from({ length: 9 }).map((_, index) => {
  //         // If not showing all numbers, only display the first 3 and the "+"
  //         if (!showAll && index > 2) {
  //           return index === 3 ? (
  //             <span
  //               key={index}
  //               style={{
  //                 fontSize: "1.5rem",
  //                 cursor: "pointer",
  //                 backgroundColor: (index+1) === selectedPhase ? "#d3e3fd" : "transparent",
  //               }}
  //               onClick={handleToggle}>+</span>
  //           ) : null;
  //         }
  //         return (
  //           <span
  //             key={index}
  //             style={{
  //               fontSize: "1.5rem",
  //               cursor: disablePageFlags ? "not-allowed" : "pointer",
  //             }}
  //             onClick={() => {
  //               if (!disablePageFlags) {
  //                 addPhaseFlag(pageFlag.pageflagid, (index+1))
  //               }
  //             }}
  //           >
  //             {index + 1}
  //           </span>
  //         );
  //       })}
  //     </div>
  //   );
  // };
    

  const PhaseFlags = ({ pageFlag, selectedPhase }: any) => {
    console.log("selectedPhase:",selectedPhase)
    // Dynamically determine the phases to display
    const phasesToShow = showAll
      ? Array.from({ length: 9 }, (_, i) => i + 1) // Show all 9 phases
      : selectedPhase > 3
      ? Array.from({ length: selectedPhase }, (_, i) => i + 1) // Show first 3 + selected phase if > 3
      : [1, 2, 3]; // Default first 3
  
    return (
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, auto)",
          gap:"5px",
          padding: "5px",
          margin: "5px",
        }}
      >
        {phasesToShow.map((phaseNumber) => (
          <span
            key={phaseNumber}
            style={{
              fontSize: "1.5rem",
              cursor: disablePageFlags ? "not-allowed" : "pointer",
              backgroundColor: phaseNumber === selectedPhase ? "#8080804f" : "transparent", // Highlight selected phase
              fontWeight: phaseNumber === selectedPhase ? "bold" : "normal",
              borderRadius: "4px",
              margin: "0 2px",
              padding: "2px 6px",
              display: "inline-block",
              lineHeight: "1",
              transition: "background-color 0.2s ease-in-out",
              textAlign: "center",
              alignContent: "center"
            }}
            onClick={() => {
              if (!disablePageFlags) {
                addPhaseFlag(pageFlag.pageflagid, phaseNumber, selectedPhase);
              }
            }}
          >
            {phaseNumber}
          </span>
        ))}
  
        {/* Show '+' only if not showing all numbers */}
        {!showAll && selectedPhase <= 9 && (
          <span
            style={{ 
              fontSize: "1.5rem", 
              textAlign: "center",
              cursor: "pointer",
              margin: "0px 2px",
              padding: "2px 6px", }}
            onClick={handleToggle}
          >
            +
          </span>
        )}
      </div>
    );
  };
  

  return (
    <>
      <Popover
        anchorReference="anchorPosition"
        anchorPosition={
          anchorPosition && {
            top: anchorPosition?.bottom,
            left: anchorPosition?.right,
          }
        }
        open={openContextPopup}
        anchorOrigin={{
          vertical: "center",
          horizontal: "center",
        }}
        transformOrigin={{
          vertical: "center",
          horizontal: "center",
        }}
        onClose={() => setOpenContextPopup(false)}
      >
        <div className="pageFlagModal">
          <div className="heading">
            <div>Export</div>
            <hr className="hrStyle" />
            {requestInfo?.bcgovcode === "MCF" && requestInfo?.requesttype === "personal" && (<>
            <div
              className={
                selectedPages.length > 1
                  ? "editPersonalTagsDisabled"
                  : "editPersonalTags"
              }
              onClick={() => {
                if(selectedPages.length <= 1) {
                  editTags()
                }
              }}
            >
              Edit Tags
            </div>
            <hr className="hrStyle" />
            </>)}
            <div>Page Flags</div>
          </div>
          {showPageFlagList()}
        </div>
      </Popover>

      {openModal && (
        <ConsultModal
          flagId={flagId}
          initialPageFlag={consultInfo}
          openModal={openModal}
          setOpenModal={setOpenModal}
          savePageFlags={savePageFlags}
          programAreaList={getProgramAreas(pageFlagList)}
        />
      )}
      {(editTagModalOpen && requestInfo.bcgovcode === "MCF" && requestInfo.requesttype === "personal") &&
        <MCFPersonal
          editTagModalOpen={editTagModalOpen}
          setEditTagModalOpen={setEditTagModalOpen}
          setOpenContextPopup={setOpenContextPopup}
          setNewDivision={setDivisionModalTagValue}
          comparePersonalAttributes={comparePersonalAttributes}
          curPersonalAttributes={curPersonalAttributes}
          setNewPersonalAttributes={setNewPersonalAttributes}
          updatePersonalAttributes={updatePersonalAttributes}
          setCurrentEditRecord={setCurrentEditRecord}
          setCurPersonalAttributes={setCurPersonalAttributes}
        />
      }
    </>
  );
};

export default ContextMenu;
