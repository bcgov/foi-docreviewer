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
        (data: any) => {
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
    return pageFlagList?.map((pageFlag: any, index: number) => {
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
          <hr className="hrStyle" />
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
      ) : (
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
