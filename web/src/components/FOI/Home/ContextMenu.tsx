import React, { useState } from 'react'
import Popover from "@mui/material/Popover";
import MenuList from "@mui/material/MenuList";
import MenuItem from "@mui/material/MenuItem";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCirclePlus, faAngleRight } from '@fortawesome/free-solid-svg-icons';
import { IconProp } from '@fortawesome/fontawesome-svg-core';
import { savePageFlag } from '../../../apiManager/services/docReviewerService';
import ConsultModal from "./ConsultModal";
import {getStitchedPageNoFromOriginal, createPageFlagPayload, getProgramAreas} from "./utils";
import { useAppSelector } from '../../../hooks/hook';

const ContextMenu = ({
    openFOIPPAModal,
    requestId,
    pageFlagList,
    assignIcon,
    openContextPopup,
    setOpenContextPopup,
    anchorPosition,
    selectedPages,
    consultInfo,
    updatePageFlags,
    pageMappedDocs
}: any) => {

    const [openModal, setOpenModal] = useState(false);
    const [orgListAnchorPosition, setOrgListAnchorPosition] = useState<any>(undefined);
    const [openConsultPopup, setOpenConsultPopup] = useState(false)
    const [flagId, setFlagId] = React.useState(0);
    const currentLayer = useAppSelector((state: any) => state.documents?.currentLayer);


    const popoverEnter = (e: any) => {
        setOrgListAnchorPosition(
            e?.currentTarget?.getBoundingClientRect()
        );
        setOpenConsultPopup(true)
    };


    const openConsultModal = (flagId: number) => {
        setOpenModal(true);
        setFlagId(flagId);
    }

    const closePopup = () => {
        setOpenConsultPopup(false);
    }

    const savePageFlags = (flagId: number, data?: any) => {
        if(flagId === 3){
            openFOIPPAModal(selectedPages.map((page: any) => getStitchedPageNoFromOriginal(page.docid, page.page, pageMappedDocs)));
        } else {
            savePageFlag(
                requestId,
                flagId,
                (data: any) => {
                    updatePageFlags()
                },
                (error: any) => console.log(error),
                createPageFlagPayload(selectedPages, currentLayer.redactionlayerid, flagId, data)
            );
        }
        setOpenConsultPopup(false);
        setOpenContextPopup(false);
    }

    // const ministryOrgCodes = (pageFlag: any, documentId: number, documentVersion: number) => pageFlag.programareas?.map((programarea: any, index: number) => {
    //     return (
    //         <div key={programarea?.programareaid} onClick={() => savePageFlags(pageFlag.pageflagid, selectedPages, documentId, documentVersion, "", "", programarea?.programareaid)}>
    //             <MenuList>
    //                 <MenuItem>
    //                     {programarea?.iaocode}
    //                 </MenuItem>
    //             </MenuList>
    //         </div>
    //     )
    // })

    // const otherMinistryOrgCodes = (pageFlag: any, documentId: number, documentVersion: number) => pageFlag.others?.map((other: any, index: number) => {
    //     return (
    //         <div onClick={() => savePageFlags(pageFlag.pageflagid, selectedPages, documentId, documentVersion, "", other)} key={index}>
    //             <MenuList>
    //                 <MenuItem>
    //                     {other}
    //                 </MenuItem>
    //             </MenuList>
    //         </div>
    //     )
    // })

    // const getProgramAreas = () => {
    //     let consult = pageFlagList.find((pageFlag: any) => pageFlag.name === 'Consult')
    //     return (({others , programareas }) => (others ? { others, programareas } : {others: [], programareas}))(consult);
    // }

    const showPageFlagList = () => pageFlagList?.map((pageFlag: any, index: number) => {
        return (pageFlag?.name === 'Page Left Off' ?
            <div className='pageLeftOff' style={selectedPages.length !== 1 ? {cursor: "not-allowed", color: "#cfcfcf"} : {}} onClick={() => {
                    if (selectedPages.length === 1) {
                        savePageFlags(pageFlag.pageflagid)
                    }
                }}>
                <hr className='hrStyle' />
                <div>
                    {pageFlag?.name}
                    <span className='pageLeftOffIcon'>
                        <FontAwesomeIcon icon={assignIcon("Page Left Off") as IconProp} size='1x' />
                    </span>
                </div>
            </div> :
            <>
                <MenuList key={pageFlag?.pageflagid}>
                    <MenuItem>
                        {(pageFlag?.name == 'Consult' ?
                            <>
                                <div onClick={() => openConsultModal(pageFlag.pageflagid)}>
                                {/* <div onClick={popoverEnter}> */}
                                    <FontAwesomeIcon style={{ marginRight: '10px' }} icon={assignIcon(pageFlag?.name) as IconProp} size='1x' />
                                    {pageFlag?.name}
                                    <span style={{ float: 'right', marginLeft: '51px' }}>
                                        <FontAwesomeIcon icon={faAngleRight as IconProp} size='1x' />
                                    </span>
                                </div>
                                {/* <Popover
                                    className='ministryCodePopUp'
                                    id="mouse-over-popover"
                                    anchorReference="anchorPosition"
                                    anchorPosition={
                                        orgListAnchorPosition && {
                                            top: orgListAnchorPosition?.bottom,
                                            left: orgListAnchorPosition?.right + 95,
                                        }
                                    }
                                    open={openConsultPopup}
                                    anchorOrigin={{
                                        vertical: "center",
                                        horizontal: "center",
                                    }}
                                    transformOrigin={{
                                        vertical: "center",
                                        horizontal: "center",
                                    }}
                                    onClose={() => closePopup()}
                                    disableRestoreFocus
                                >
                                    <div className='ministryCodeModal' >
                                        {ministryOrgCodes(pageFlag, selectedFile.documentid, selectedFile.version)}
                                        {otherMinistryOrgCodes(pageFlag, selectedFile.documentid, selectedFile.version)}
                                        <div className="otherOption" onClick={() => addOtherPublicBody(pageFlag.pageflagid)}>
                                            <span style={{ marginRight: '10px' }}>
                                                <FontAwesomeIcon icon={faCirclePlus as IconProp} size='1x' />
                                            </span>
                                            Add Other
                                        </div>
                                    </div>
                                </Popover> */}
                            </>
                            :
                            <div onClick={() => savePageFlags(pageFlag.pageflagid)}>
                                <FontAwesomeIcon style={{ marginRight: '10px' }} icon={assignIcon(pageFlag?.name) as IconProp} size='1x' />
                                {pageFlag?.name}
                            </div>
                        )}
                    </MenuItem>
                </MenuList>
            </>
        )
    });

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
                onClose={() => setOpenContextPopup(false)}>
                <div className='pageFlagModal'>
                    <div className='heading'>
                        <div>
                            Export
                        </div>
                        <hr className='hrStyle' />
                        <div>
                            Page Flags
                        </div>
                    </div>
                    {showPageFlagList()}
                </div>
            </Popover>

            {openModal &&
                <ConsultModal
                    flagId={flagId}
                    initialPageFlag={consultInfo}
                    openModal={openModal}
                    setOpenModal={setOpenModal}
                    savePageFlags={savePageFlags} 
                    programAreaList={getProgramAreas(pageFlagList)}
                />
            }
        </>
    );
};

export default ContextMenu;
