import React, { useEffect, useState, useRef } from 'react'
import Chip from "@mui/material/Chip";
import TreeView from '@mui/lab/TreeView';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import TreeItem from '@mui/lab/TreeItem';
import SearchIcon from "@material-ui/icons/Search";
import InputAdornment from "@mui/material/InputAdornment";
import InputBase from "@mui/material/InputBase";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Grid from "@material-ui/core/Grid";
import Stack from "@mui/material/Stack";

import Tooltip, { TooltipProps, tooltipClasses } from '@mui/material/Tooltip';
import Popover from "@material-ui/core/Popover";
import MoreHorizIcon from "@material-ui/icons/MoreHoriz";
import MenuList from "@material-ui/core/MenuList";
import MenuItem from "@material-ui/core/MenuItem";
import { fetchPageFlagsMasterData, fetchPageFlag, savePageFlag } from '../../../apiManager/services/docReviewerService';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCircleHalfStroke, faCircle, faCircleQuestion,
    faCircleStop, faCircleXmark, faBookmark, faCirclePlus, faAngleRight
} from '@fortawesome/free-solid-svg-icons';
import { faCircle as filledCircle } from '@fortawesome/free-regular-svg-icons';
import { IconProp } from '@fortawesome/fontawesome-svg-core';
import "./DocumentSelector.scss";
import ConsultModal from "./ConsultModal";


const DocumentSelector = ({
    requestid,
    documents,
    currentPageInfo,
    setCurrentPageInfo
}: any) => {
    const [files, setFiles] = useState(documents);
    const [openContextPopup, setOpenContextPopup] = useState(false);
    const [openConsultPopup, setOpenConsultPopup] = useState(false)
    //const [popoverOpen, setPopoverOpen] = useState(false);
    const [anchorPosition, setAnchorPosition] = useState<any>(undefined);
    const [orgListAnchorPosition, setOrgListAnchorPosition] = useState<any>(undefined);
    const [organizeBy, setOrganizeBy] = useState("lastmodified")
    const [pageFlags, setPageFlags] = useState([]);
    const [openModal, setOpenModal] = useState(false);
    const [completionPercentage, setCompletionPercentage] = useState(0);
    const [flagId, setFlagId] = React.useState(0);
    const [docId, setDocumentId] = React.useState(0);
    const [docVersion, setDocumentVersion] = React.useState(0);

    useEffect(() => {
        // fetchPageFlag(
        //     requestid,
        //   (data: any) => setPageFlags(data),
        //   (error: any)=> console.log(error)
        // )
        let resp = [
            {
                "docid": 1,
                "pageflag": [{ "page": 1, "flagid": 0, "other": "test" }]
            },
            {
                "docid": 2,
                "pageflag": [{ "page": 2, "flagid": 0, "other2": "test2" }]
            }
        ];
        fetchPageFlagsMasterData(
            (data: any) => setPageFlags(data),
            (error: any) => console.log(error)
        );
    }, []);

    const assignIcon = (pageFlag: any) => {
        switch (pageFlag) {
            case 0:
            case "Partial Disclosure":
                return faCircleHalfStroke;
            case 1:
            case "Full Disclosure":
                return faCircle;
            case 2:
            case "Withheld in Full":
                return filledCircle;
            case 3:
            case "Consult":
                return faCircleQuestion;
            case 4:
            case "Duplicate":
                return faCircleStop;
            case 5:
            case "Not Responsive":
                return faCircleXmark;
            case 6:
            case "Page Left Off":
                return faBookmark;
            default:
                return faBookmark;
        }
    }

    const assignPageIcon = (docId: number, page: number) => {
        let resp = [
            {
                "docid": 14,
                "pageflag": [{ "page": 1, "flagid": 4, "other": "test" }, { "page": 2, "flagid": 3 }]
            },
            {
                "docid": 2,
                "pageflag": [{ "page": 2, "flagid": 0, "other2": "test2" }]
            }
        ];
        let docs: any = resp?.find((doc) => doc.docid === docId);
        let pageFlagObj = docs?.pageflag?.find((flag: any) => flag.page === page);
        return assignIcon(pageFlagObj?.flagid);
    }

    let arr: any[] = [];
    const divisions = [...new Map(files.reduce((acc: any[], file: any) => [...acc, ...new Map(file.divisions.map((division: any) => [division.divisionid, division]))], arr)).values()]

    const [filesForDisplay, setFilesForDisplay] = useState(files);

    const onFilterChange = (filterValue: string) => {
        setFilesForDisplay(files.filter((file: any) => file.filename.includes(filterValue)))
    }

    // const getDivisionFiles = (division) => {
    //     let filteredFiles = filesForDisplay.filter(file => file.divisions.map(d => d.divisionid = division.divisionid).includes(division.divisionid))
    //     console.log(division)
    //     return filteredFiles.map((file, index) => {
    //                 return <TreeItem nodeId={`${index}`} label={file.filename}/>
    //             })

    // }

    const getFilePages = (pagecount: Number, index: Number) => {
        let pages = []
        for (var p = 1; p <= pagecount; p++) {
            pages.push(<TreeItem nodeId={`file${index}page${p}`} label={`Page ${p}`} />)
        }
        return pages;
    }

    const selectTreeItem = (file: any, page: number) => {
        setCurrentPageInfo({ 'file': file, 'page': page });
        localStorage.setItem("currentDocumentInfo", JSON.stringify({ 'file': file, 'page': page }));
    };

    const openContextMenu = (e: any) => {
        e.preventDefault();
        setOpenContextPopup(true);
        setAnchorPosition(
            e.currentTarget.getBoundingClientRect()
        );
    }

    const ministryOrgCodes = (pageFlag: any, documentId: number, documentVersion: number) => pageFlag.programareas?.map((programarea: any, index: number) => {
        return (
            <div onClick={() => savePageFlags(pageFlag.pageflagid, documentId, documentVersion, "", programarea?.programareaid)}>
                <MenuList key={programarea?.programareaid}>
                    <MenuItem>
                        {programarea?.bcgovcode}
                    </MenuItem>
                </MenuList>
            </div>
        )
    })



    const popoverEnter = (e: any) => {
        setOrgListAnchorPosition(
            e.currentTarget.getBoundingClientRect()
        );
        setOpenConsultPopup(true)
    };

    const savePageFlags = (flagId: number, documentid: number, documentversion: number, other?: string, programareaid?: number) => {
        setOpenConsultPopup(false);
        setOpenContextPopup(false);
        savePageFlag(
            requestid,
            documentid,
            documentversion,
            1,
            flagId,
            (data: any) => console.log(data),
            (error: any) => console.log(error),
            other,
            programareaid
        );
    }

    const addOtherPublicBody = (flagId: number, documentId: number, documentVersion: number) => {
        setOpenModal(true);
        setFlagId(flagId);
        setDocumentId(documentId);
        setDocumentVersion(documentVersion);
        console.log("Open Modal:", openModal);
    }

    const closePopup = ()=>{
        setOpenConsultPopup(false);
    }

    const pageFlagList = (file: any) => pageFlags?.map((pageFlag: any, index) => {
        return (
            <>
                <MenuList key={pageFlag?.pageflagid}>
                    <MenuItem>
                        <span style={{ marginRight: '10px' }}>
                            <FontAwesomeIcon icon={assignIcon(pageFlag?.name) as IconProp} size='1x' />
                        </span>
                        {(pageFlag?.name == 'Consult' ?
                            <>
                                <div onClick={popoverEnter}>
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
                                    {ministryOrgCodes(pageFlag, file.documentid, file.version)}
                                    <div style={{ margin: ' 3px 16px' }} onClick={() => addOtherPublicBody(pageFlag.pageflagid, file.documentid, file.version)}>
                                        <span style={{ marginRight: '10px' }}>
                                            <FontAwesomeIcon icon={faCirclePlus as IconProp} size='1x' />
                                        </span>
                                        Add Other
                                    </div>
                                </div>
                                </Popover>
                            </>
                            :
                            <div onClick={() => savePageFlags(pageFlag.pageflagid, file.documentid, file.version)}>
                                {pageFlag?.name}
                            </div>
                        )}
                    </MenuItem>
                </MenuList>
            </>
        )
    })



    const ContextMenu = (file: any) => {
        return (
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
                        <hr />
                        <div>
                            Page Flags
                        </div>
                    </div>
                    {pageFlagList(file)}
                    <div style={{ marginLeft: '16px' }}>
                        <hr />
                        <div>
                            Page Left Off
                            <span className='leftOffFlag'>
                                <FontAwesomeIcon icon={assignIcon("Page Left Off") as IconProp} size='1x' />
                            </span>
                        </div>
                    </div>
                </div>
            </Popover>
        );
    };

    const completionCounter = () => {
        setCompletionPercentage(0);
    }

    return (
        <>
        <div className='leftPanel'>
            <Stack sx={{ maxHeight: "calc(100vh - 117px)" }}>
                <Paper
                    component={Grid}
                    sx={{
                        border: "1px solid #38598A",
                        color: "#38598A",
                        maxWidth: "100%",
                        backgroundColor: "rgba(56,89,138,0.1)"
                    }}
                    alignItems="center"
                    justifyContent="center"
                    direction="row"
                    container
                    item
                    xs={12}
                    elevation={0}
                >
                    <Grid
                        item
                        container
                        alignItems="center"
                        direction="row"
                        xs={true}
                        className="search-grid"
                    >
                        <label className="hideContent">Filter Records</label>
                        <InputBase
                            id="foicommentfilter"
                            placeholder="Filter Records ..."
                            defaultValue={""}
                            onChange={(e) => { onFilterChange(e.target.value.trim()) }}
                            // inputProps={{'aria-labelledby': 'foi-status-dropdown-label'}}
                            sx={{
                                color: "#38598A",
                            }}
                            startAdornment={
                                <InputAdornment position="start">
                                    <IconButton
                                        className="search-icon"
                                    >
                                        <span className="hideContent">Filter Records ...</span>
                                        <SearchIcon />
                                    </IconButton>
                                </InputAdornment>
                            }
                            fullWidth
                        />
                    </Grid>
                </Paper>
                <hr/>
                <div>Organize by: </div>
                <Stack direction="row" sx={{ /*overflowX: "scroll",*/ paddingBottom: "5px" }} spacing={1}>
                    <ClickableChip
                        label="Division"
                        color="primary"
                        size="small"
                        onClick={() => setOrganizeBy("division")}
                        clicked={organizeBy === "division"}
                    />
                    <ClickableChip
                        label="Modified Date"
                        color="primary"
                        size="small"
                        onClick={() => setOrganizeBy("lastmodified")}
                        clicked={organizeBy === "lastmodified"}
                    />
                </Stack>
                <hr/>
                <div className='row'>
                    <div className='col-lg-6'>
                        {`Complete:${completionPercentage}%`}
                    </div>
                    {/* <div className='col-lg-6 style-float'>
                        Total Pages: 4875
                    </div> */}
                </div>
                <hr/>
                <TreeView
                    aria-label="file system navigator"
                    defaultCollapseIcon={<ExpandMoreIcon />}
                    defaultExpandIcon={<ChevronRightIcon />}
                    sx={{ flexGrow: 1, maxWidth: 400, overflowY: 'auto' }}
                >
                    {organizeBy === "division" ?
                        divisions.map((division: any, index) =>
                            <TreeItem nodeId={`division${index}`} label={division.name}>
                                {filesForDisplay.filter((file: any) => file.divisions.map((d: any) => d.divisionid).includes(division.divisionid)).map((file: any, i: number) =>
                                    <Tooltip
                                        sx={{
                                            backgroundColor: 'white',
                                            color: 'rgba(0, 0, 0, 0.87)',
                                            fontSize: 11
                                        }}
                                        title={<>
                                            Last Modified Date: {new Date(file.lastmodified).toLocaleString('en-US', { timeZone: 'America/Vancouver' })}
                                        </>}
                                        placement="bottom-end"
                                        arrow
                                    >
                                        <TreeItem nodeId={`division${index}file${i}`} label={file.filename} onClick={() => selectTreeItem(file, 1)} >
                                            {[...Array(file.pagecount)].map((_x, p) =>
                                                <TreeItem nodeId={`file${index}page${p + 1}`} icon={<FontAwesomeIcon icon={assignPageIcon(file.documentid, 1) as IconProp} size='1x' />} label={`Page ${p + 1}`} onClick={() => selectTreeItem(file, p + 1)} />
                                            )
                                            }
                                            {ContextMenu(file)}
                                        </TreeItem>
                                    </Tooltip>
                                )}
                            </TreeItem>
                        )
                        :
                        filesForDisplay.sort((a: any, b: any) => Date.parse(a.lastmodified) - Date.parse(b.lastmodified)).map((file: any, index: number) =>
                            <Tooltip
                                sx={{
                                    backgroundColor: 'white',
                                    color: 'rgba(0, 0, 0, 0.87)',
                                    // boxShadow: theme.shadows[1],
                                    fontSize: 11
                                }}
                                title={<>
                                    Last Modified Date: {new Date(file.lastmodified).toLocaleString('en-US', { timeZone: 'America/Vancouver' })}
                                </>}
                                placement="bottom-end"
                                arrow
                            >
                                <TreeItem nodeId={`${index}`} label={file.filename} onClick={() => selectTreeItem(file, 1)} >
                                    {[...Array(file.pagecount)].map((_x, p) =>

                                        <TreeItem nodeId={`file${index}page${p + 1}`} icon={<FontAwesomeIcon icon={assignPageIcon(file.documentid, 1) as IconProp} size='1x' />} label={`Page ${p + 1}`}
                                            onClick={() => selectTreeItem(file, p + 1)} onContextMenu={openContextMenu} />
                                    )
                                        //getFilePages(file.pagecount, index)
                                    }
                                    {ContextMenu(file)}
                                </TreeItem>
                            </Tooltip>
                        )}
                </TreeView>
            </Stack>
            </div>
            {openModal &&
                <ConsultModal
                    flagId={flagId}
                    documentId={docId}
                    documentVersion={docVersion}
                    openModal={openModal}
                    setOpenModal={setOpenModal}
                    savePageFlags={savePageFlags} />
            }
        </>
    )
}

const ClickableChip = ({ clicked, ...rest }: any) => {
    return (
        <Chip
            sx={[
                {
                    ...(clicked
                        ? {
                            backgroundColor: "#38598A",
                            width: "100%",
                        }
                        : {
                            color: "#38598A",
                            border: "1px solid #38598A",
                            width: "100%",
                        }),
                },
                {
                    '&:focus': {
                        backgroundColor: "#38598A",
                    }
                }
            ]}
            variant={clicked ? "filled" : "outlined"}
            {...rest}
        />
    );
};

export default DocumentSelector