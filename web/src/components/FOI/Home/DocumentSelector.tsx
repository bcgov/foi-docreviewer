import React, { useEffect, useState, useRef } from 'react'
import Chip from "@mui/material/Chip";
import TreeView from '@mui/lab/TreeView';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import TreeItem, { treeItemClasses } from "@mui/lab/TreeItem";
import SearchIcon from "@material-ui/icons/Search";
import InputAdornment from "@mui/material/InputAdornment";
import InputBase from "@mui/material/InputBase";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Grid from "@material-ui/core/Grid";
import Stack from "@mui/material/Stack";
import Tooltip, { TooltipProps, tooltipClasses } from '@mui/material/Tooltip';
import Popover from "@material-ui/core/Popover";
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
import e from 'express';


const DocumentSelector = ({
    requestid,
    documents,
    currentPageInfo,
    setCurrentPageInfo
}: any) => {
    const [files, setFiles] = useState(documents);
    const [openContextPopup, setOpenContextPopup] = useState(false);
    const [openConsultPopup, setOpenConsultPopup] = useState(false)
    const [anchorPosition, setAnchorPosition] = useState<any>(undefined);
    const [orgListAnchorPosition, setOrgListAnchorPosition] = useState<any>(undefined);
    const [organizeBy, setOrganizeBy] = useState("lastmodified")
    const [pageFlagList, setPageFlagList] = useState([]);
    const [openModal, setOpenModal] = useState(false);
    const [completionPercentage, setCompletionPercentage] = useState(0);
    const [flagId, setFlagId] = React.useState(0);
    const [docId, setDocumentId] = React.useState(0);
    const [docVersion, setDocumentVersion] = React.useState(0);
    const [pageFlags, setPageFlags] = useState([]);
    const [pageFlagChanged, setPageFlagChanged] = useState(false);
    const [filesForDisplay, setFilesForDisplay] = useState(files);
    const [consultMinistries, setConsultMinistries] = useState([]);
    const [selectedPage, setSelectedPage] = useState(1);

    useEffect(() => {
        fetchPageFlagsMasterData(
            requestid,
            (data: any) => setPageData(data),
            (error: any) => console.log(error)
        );
    }, []);

    useEffect(() => {
        setPageFlagChanged(false);
        fetchPageFlagsMasterData(
            requestid,
            (data: any) => setPageData(data),
            (error: any) => console.log(error)
        );
        fetchPageFlag(
            requestid,
          (data: any) => updatePageFlag(data),
          (error: any)=> console.log(error)
        )
    }, [pageFlagChanged]);

    const ministryOrgCode = (pageNo:number, consults:Array<any>) => {
        let consultVal= consults?.find((consult: any) => consult.page == pageNo);
        if(consultVal?.programareaid){
            return consultVal?.iaocode;
        }
        else
            return consultVal?.other;
    }

    const setPageData = (data:any) => {
        setConsultMinistries(data.find((flag: any) => flag.name === 'Consult').programareas);
        setPageFlagList(data);
    }

    const updatePageFlag = (resp: any)=> {
        setPageFlags(resp);
        //setAdditionalData();
    }

    const setAdditionalData = ()=> {
        filesForDisplay.forEach((file1: any) => {
            pageFlags?.forEach((pageFlag1: any) => {
                if(file1.documentid == pageFlag1?.documentid){
                    console.log("pageFlag1?.pageflag",pageFlag1?.pageflag);
                    file1.pageFlag =  pageFlag1?.pageflag;
                    let consultDetails: any = pageFlag1?.pageflag?.filter((flag1: any) => (flag1.programareaid || flag1.other));
                    if(consultDetails?.length >0){
                        consultDetails.forEach((consult: any)=> {
                            let ministryCode: any= consultMinistries?.find((ministry: any) => ministry.programareaid === consult.programareaid);
                            if(ministryCode)
                                consult['iaocode']= ministryCode.iaocode;
                        })
                        file1.consult = consultDetails;
                    }
                    else{
                        delete file1.consult;
                    }
                }
            })
        });
        setFilesForDisplay(filesForDisplay);
    }

    useEffect(() => {
        setAdditionalData();
    }, [consultMinistries, pageFlags]);

    const assignIcon = (pageFlag: any) => {
        switch (pageFlag) {
            case 1:
            case "Partial Disclosure":
                return faCircleHalfStroke;
            case 2:
            case "Full Disclosure":
                return faCircle;
            case 3:
            case "Withheld in Full":
                return filledCircle;
            case 4:
            case "Consult":
                return faCircleQuestion;
            case 5:
            case "Duplicate":
                return faCircleStop;
            case 6:
            case "Not Responsive":
                return faCircleXmark;
            case 7:
            case "Page Left Off":
                return faBookmark;
            default:
                return null;
        }
    }

    //Revisit this method & assign icons when fetching itself!!
    const assignPageIcon = (docId: number, page: number) => {
        let docs: any = pageFlags?.find((doc: any) => doc?.documentid === docId);
        let pageFlagObj = docs?.pageflag?.find((flag: any) => flag.page === page);
        return assignIcon(pageFlagObj?.flagid);
    }

    let arr: any[] = [];
    const divisions = [...new Map(files.reduce((acc: any[], file: any) => [...acc, ...new Map(file.divisions.map((division: any) => [division.divisionid, division]))], arr)).values()]

    

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

    const openContextMenu = (file:any, page:number, e: any) => {
        setSelectedPage(page);
        e.preventDefault();
        setOpenContextPopup(true);
        setAnchorPosition(
            e.currentTarget.getBoundingClientRect()
        );
        //ContextMenu(file, page);
    }

    const ministryOrgCodes = (pageFlag: any, documentId: number, documentVersion: number) => pageFlag.programareas?.map((programarea: any, index: number) => {
        return (
            <div onClick={() => savePageFlags(pageFlag.pageflagid, selectedPage, documentId, documentVersion, "", "", programarea?.programareaid)}>
                <MenuList key={programarea?.programareaid}>
                    <MenuItem>
                        {programarea?.iaocode}
                    </MenuItem>
                </MenuList>
            </div>
        )
    })

    const otherMinistryOrgCodes = (pageFlag: any,  documentId: number, documentVersion: number) => pageFlag.others?.map((other: any, index: number) => {
        return (
            <div onClick={() => savePageFlags(pageFlag.pageflagid, selectedPage, documentId, documentVersion,"",other)}>
                <MenuList key={index}>
                    <MenuItem>
                        {other}
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

    const savePageFlags = (flagId: number, pageNo: number, documentid: number, documentversion: number, publicbodyaction? : string, other?: string, programareaid?: number) => {
        setOpenConsultPopup(false);
        setOpenContextPopup(false);
        savePageFlag(
            requestid,
            documentid,
            documentversion,
            pageNo,
            flagId,
            (data: any) => setPageFlagChanged(true),
            (error: any) => console.log(error),
            publicbodyaction,
            other,
            programareaid
        );
    }

    const addOtherPublicBody = (flagId: number, documentId: number, documentVersion: number) => {
        setOpenModal(true);
        setFlagId(flagId);
        setDocumentId(documentId);
        setDocumentVersion(documentVersion);
    }

    const closePopup = ()=>{
        setOpenConsultPopup(false);
    }

    const showPageFlagList = (file: any) => pageFlagList?.map((pageFlag: any, index) => {
        return (pageFlag?.name === 'Page Left Off' ?
            <div className='pageLeftOff' onClick={() => savePageFlags(pageFlag.pageflagid, selectedPage, file.documentid, file.version)}>
                <hr className='hrStyle'/>
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
                                    {otherMinistryOrgCodes(pageFlag, file.documentid, file.version)}
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
                            <div onClick={() => savePageFlags(pageFlag.pageflagid, selectedPage, file.documentid, file.version)}>
                                {pageFlag?.name}
                            </div>
                        )}
                    </MenuItem>
                </MenuList>
            </>
        )
    });
  

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
                        <hr className='hrStyle' />
                        <div>
                            Page Flags
                        </div>
                    </div>
                    {showPageFlagList(file)}
                </div>
            </Popover>
        );
    };

    const completionCounter = () => {
        setCompletionPercentage(0);
    }

    const isConsult= (consults: Array<any>, pageNo: number) => {
        if(consults?.find((consult: any) => consult.page == pageNo))
            return true;
        return false;
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
                <hr className='hrStyle' />
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
                <hr className='hrStyle'/>
                <div className='row'>
                    <div className='col-lg-6'>
                        {`Complete: ${completionPercentage}%`}
                    </div>
                    {/* <div className='col-lg-6 style-float'>
                        Total Pages: 4875
                    </div> */}
                </div>
                <hr className='hrStyle'/>
                <TreeView
                    aria-label="file system navigator"
                    defaultCollapseIcon={<ExpandMoreIcon />}
                    defaultExpandIcon={<ChevronRightIcon />}
                    sx={{ flexGrow: 1, maxWidth: 400, overflowY: 'auto' }}
                >
                    {organizeBy === "division" ?
                        divisions.map((division: any, index) =>
                            <TreeItem nodeId={`division${index}`} label={division.name} key={division.divisionid}>
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
                                        key={i}
                                    >
                                        {/* { file.consult?.length >0 ? */}
                                            <TreeItem nodeId={`division${index}file${i}`} label={file.filename} key={index} onClick={() => selectTreeItem(file, 0)} >
                                                {[...Array(file.pagecount)].map((_x, p) =>
                                                    (file.pageFlag && file.pageFlag.find((obj:any)=> obj.page === p+1)?
                                                    <TreeItem nodeId={`file${index}page${p + 1}`} key={p + 1} icon={<FontAwesomeIcon icon={assignPageIcon(file.documentid, p + 1) as IconProp} size='1x' />} 
                                                    label={isConsult(file.consult,p+1)?`Page ${p + 1} (${ministryOrgCode(p+1,file.consult)})`:`Page ${p + 1}`} onClick={() => selectTreeItem(file, p + 1)} />
                                                    :
                                                    <TreeItem nodeId={`file${index}page${p + 1}`} key={p + 1}
                                                    label={`Page ${p + 1}`} onClick={() => selectTreeItem(file, p + 1)} />
                                                    )
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
                            {/* { file.consult?.length >0 ? */}
                                <TreeItem nodeId={`${index}`} label={file.filename} key={index} onClick={() => selectTreeItem(file, 0)} >
                                    {[...Array(file.pagecount)].map((_x, p) =>
                                    (file.pageFlag && file.pageFlag.find((obj:any)=> obj.page === p+1)?
                                        <TreeItem nodeId={`file${index}page${p + 1}`} key={p + 1} icon={<FontAwesomeIcon icon={assignPageIcon(file.documentid, p+1) as IconProp} size='1x' />} 
                                            label={isConsult(file.consult,p+1)?`Page ${p + 1} (${ministryOrgCode(p+1,file.consult)})`:`Page ${p + 1}`} onClick={() => selectTreeItem(file, p + 1)} onContextMenu={(e) => openContextMenu(file,p+1,e)} /> :
                                        <TreeItem nodeId={`file${index}page${p + 1}`} key={p + 1} label={`Page ${p + 1}`}
                                         onClick={() => selectTreeItem(file, p + 1)} onContextMenu={(e) => openContextMenu(file,p+1,e)} />
                                    )
                                    )}
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
                    selectedPage ={selectedPage}
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