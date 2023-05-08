import React, { useState } from 'react'
import Popover from "@material-ui/core/Popover";
import MenuList from "@material-ui/core/MenuList";
import MenuItem from "@material-ui/core/MenuItem";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCirclePlus, faAngleRight } from '@fortawesome/free-solid-svg-icons';
import { IconProp } from '@fortawesome/fontawesome-svg-core';
import { savePageFlag } from '../../../apiManager/services/docReviewerService';
import ConsultModal from "./ConsultModal";

const ContextMenu = ({
    openFOIPPAModal,
    requestId,
    pageFlagList,
    assignIcon,
    openContextPopup,
    setOpenContextPopup,
    anchorPosition,
    selectedPage,
    selectedFile,
    setPageFlagChanged
}: any) => {

    const [openModal, setOpenModal] = useState(false);
    const [orgListAnchorPosition, setOrgListAnchorPosition] = useState<any>(undefined);
    const [openConsultPopup, setOpenConsultPopup] = useState(false)
    const [flagId, setFlagId] = React.useState(0);
    const [docId, setDocumentId] = React.useState(0);
    const [docVersion, setDocumentVersion] = React.useState(0);


    const popoverEnter = (e: any) => {
        setOrgListAnchorPosition(
            e.currentTarget.getBoundingClientRect()
        );
        setOpenConsultPopup(true)
    };


    const addOtherPublicBody = (flagId: number, documentId: number, documentVersion: number) => {
        setOpenModal(true);
        setFlagId(flagId);
        setDocumentId(documentId);
        setDocumentVersion(documentVersion);
    }

    const closePopup = () => {
        setOpenConsultPopup(false);
    }

    const savePageFlags = (flagId: number, pageNo: number, documentid: number, documentversion: number, data?: any) => {
        if(flagId === 3){
            console.log("Withheld in Full Selection");
            openFOIPPAModal(pageNo);
        } else {
            savePageFlag(
                requestId,
                documentid,
                documentversion,
                pageNo,
                flagId,
                (data: any) => setPageFlagChanged(true),
                (error: any) => console.log(error),
                data
            );
        }
        setOpenConsultPopup(false);
        setOpenContextPopup(false);
    }

    // const ministryOrgCodes = (pageFlag: any, documentId: number, documentVersion: number) => pageFlag.programareas?.map((programarea: any, index: number) => {
    //     return (
    //         <div key={programarea?.programareaid} onClick={() => savePageFlags(pageFlag.pageflagid, selectedPage, documentId, documentVersion, "", "", programarea?.programareaid)}>
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
    //         <div onClick={() => savePageFlags(pageFlag.pageflagid, selectedPage, documentId, documentVersion, "", other)} key={index}>
    //             <MenuList>
    //                 <MenuItem>
    //                     {other}
    //                 </MenuItem>
    //             </MenuList>
    //         </div>
    //     )
    // })

    const getProgramAreas = () => {
        let consult = pageFlagList.find((pageFlag: any) => pageFlag.name === 'Consult')
        return (({others , programareas }) => ({ others, programareas }))(consult);
    }

    const getSelectedPageFlag = () => {
        return selectedFile.consult?.find((flag: any) => flag.page === selectedPage) || {
            flagid: 4, other: [], programareaid: [], page: selectedPage
        }
    }

    const showPageFlagList = () => pageFlagList?.map((pageFlag: any, index: number) => {
        return (pageFlag?.name === 'Page Left Off' ?
            <div className='pageLeftOff' onClick={() => savePageFlags(pageFlag.pageflagid, selectedPage, selectedFile.documentid, selectedFile.version)}>
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
                                <div onClick={() => setOpenModal(true)}>
                                {/* <div onClick={popoverEnter}> */}
                                    <FontAwesomeIcon style={{ marginRight: '10px' }} icon={assignIcon(pageFlag?.name) as IconProp} size='1x' />
                                    {pageFlag?.name}
                                    <span style={{ float: 'right', marginLeft: '51px' }}>
                                        <FontAwesomeIcon icon={faAngleRight as IconProp} size='1x' />
                                    </span>
                                </div>
                                <Popover
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
                                        {/* {ministryOrgCodes(pageFlag, selectedFile.documentid, selectedFile.version)} */}
                                        {/* {otherMinistryOrgCodes(pageFlag, selectedFile.documentid, selectedFile.version)} */}
                                        <div className="otherOption" onClick={() => addOtherPublicBody(pageFlag.pageflagid, selectedFile.documentid, selectedFile.version)}>
                                            <span style={{ marginRight: '10px' }}>
                                                <FontAwesomeIcon icon={faCirclePlus as IconProp} size='1x' />
                                            </span>
                                            Add Other
                                        </div>
                                    </div>
                                </Popover>
                            </>
                            :
                            <div onClick={() => savePageFlags(pageFlag.pageflagid, selectedPage, selectedFile.documentid, selectedFile.version)}>
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
                    initialPageFlag={getSelectedPageFlag()}
                    documentId={selectedFile.documentid}
                    documentVersion={selectedFile.version}
                    openModal={openModal}
                    setOpenModal={setOpenModal}
                    savePageFlags={savePageFlags} 
                    programAreaList={getProgramAreas()}
                />
            }
        </>
    );
};

export default ContextMenu;
