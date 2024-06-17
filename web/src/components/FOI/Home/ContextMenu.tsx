import React, { useState } from "react";
import Popover from "@mui/material/Popover";
import MenuList from "@mui/material/MenuList";
import MenuItem from "@mui/material/MenuItem";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCirclePlus, faAngleRight } from "@fortawesome/free-solid-svg-icons";
import { IconProp } from "@fortawesome/fontawesome-svg-core";
import { savePageFlag } from "../../../apiManager/services/docReviewerService";
import ConsultModal from "./ConsultModal";
import {
  getStitchedPageNoFromOriginal,
  createPageFlagPayload,
  getProgramAreas,
  updatePageFlagOnPage,
} from "./utils";
import { useAppSelector } from "../../../hooks/hook";
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
}: any) => {

  const [openModal, setOpenModal] = useState(false);
  const [flagId, setFlagId] = React.useState(0);
  const currentLayer = useAppSelector(
    (state: any) => state.documents?.currentLayer
  );
  const validoipcreviewlayer = useAppSelector(
    (state: any) => state.documents?.requestinfo?.validoipcreviewlayer
  );

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
                  syncPageFlagsOnAction(updatedPageFlags);
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
            selectedPages.length !== 1
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
            <MenuItem>
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
    </>
  );
};

export default ContextMenu;
