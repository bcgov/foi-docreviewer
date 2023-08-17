import React, { useEffect, useState } from 'react'
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
import { fetchPageFlagsMasterData, fetchPageFlag } from '../../../apiManager/services/docReviewerService';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCircleHalfStroke, faCircle, faCircleQuestion, faSpinner,
    faCircleStop, faCircleXmark, faBookmark, faMagnifyingGlass, faAngleDown
} from '@fortawesome/free-solid-svg-icons';
import { faCircle as filledCircle } from '@fortawesome/free-regular-svg-icons';
import { IconProp } from '@fortawesome/fontawesome-svg-core';
import "./DocumentSelector.scss";
import PAGE_FLAGS from '../../../constants/PageFlags';
import ContextMenu from "./ContextMenu";
import { styled } from "@mui/material/styles";
import { useAppSelector } from '../../../hooks/hook';
import { getStitchedPageNoFromOriginal, docSorting, getProgramAreas } from "./utils";
import { pageFlagTypes } from '../../../constants/enum';
import _, { forEach } from "lodash";
import Popover from "@material-ui/core/Popover";
import MenuList from "@material-ui/core/MenuList";
import MenuItem from "@material-ui/core/MenuItem";


const DocumentSelector = ({
    openFOIPPAModal,
    requestid,
    documents,
    totalPageCount,
    setCurrentPageInfo,
    setIndividualDoc,
    pageMappedDocs
}: any) => {

    const pageFlags = useAppSelector((state: any) => state.documents?.pageFlags);
    const [files, setFiles] = useState(documents);
    const [openContextPopup, setOpenContextPopup] = useState(false);
    const [anchorPosition, setAnchorPosition] = useState<any>(undefined);
    const [organizeBy, setOrganizeBy] = useState("lastmodified")
    const [pageFlagList, setPageFlagList] = useState([]);
    //const [pageFlags, setPageFlags] = useState([]);
    const [pageFlagChanged, setPageFlagChanged] = useState(false);
    const [filesForDisplay, setFilesForDisplay] = useState(files);
    const [consultMinistries, setConsultMinistries] = useState<any>([]);
    const [selectedPages, setSelectedPages] = useState([]);
    const [consultInfo, setConsultInfo] = useState({});
    const [filterFlags, setFilterFlags] = useState<any>([]);
    const [filteredFiles, setFilteredFiles] = useState(files);
    const [filterBookmark, setFilterBookmark] = useState(false);
    const [disableHover, setDisableHover] = useState(false);
    const [selected, setSelected] = useState<any>([]);
    const [openconsulteeModal, setOpenConsulteeModal] = useState(false);
    const [assignedConsulteeList, setAssignedConsulteeList] = useState<any>([]);
    const [consulteeFilter, setConsulteeFilter] = useState<any>([]);
    const [selectAllConsultee, setSelectAllConsultee] = useState(false);
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

    const StyledTreeItem = styled(TreeItem)(() => ({
        [`& .${treeItemClasses.label}`]: {
            fontSize: '14px'
        },
        [`& .${treeItemClasses.content}`]: {
            padding: '0 16px'
        }
    }));

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
            (error: any) => console.log(error)
        )
    }, [pageFlagChanged]);

    const ministryOrgCode = (pageNo: number, consults: Array<any>) => {
        let consultVal = consults?.find((consult: any) => consult.page == pageNo);
        if (consultVal?.programareaid?.length === 1 && consultVal?.other?.length === 0) {
            let ministry: any = consultMinistries?.find((ministry: any) => ministry.programareaid === consultVal.programareaid[0]);
            return ministry?.iaocode;
        } else if (consultVal?.other?.length === 1 && consultVal?.programareaid?.length === 0) {
            return consultVal?.other[0];
        } else {
            return consultVal?.programareaid?.length + consultVal?.other?.length;
        }
    }

    const setPageData = (data: any) => {
        setConsultMinistries(data.find((flag: any) => flag.name === 'Consult').programareas);
        setPageFlagList(data);
    }

    const updateCompletionCounter = () => {
        let totalPagesWithFlags = 0;
        pageFlags?.forEach((element: any) => {
            /**Page Flags to be avoided while 
             * calculating % on left panel-  
             * 'Consult'(flagid:4),'In Progress'(flagid:7),'Page Left Off'(flagid:8) */
            let documentSpecificCount = element?.pageflag?.filter((obj: any) => (!([4, 7, 8].includes(obj.flagid))))?.length;
            totalPagesWithFlags += documentSpecificCount;
        });
        return (totalPageCount > 0 && totalPagesWithFlags >= 0) ? Math.round((totalPagesWithFlags / totalPageCount) * 100) : 0;
    }


    const updatePageCount = () => {
        let totalFilteredPages = 0;
        pageFlags?.forEach((element: any) => {
            /**Page Flags to be avoided while 
             * calculating % on left panel-  
             * 'Consult'(flagid:4),'In Progress'(flagid:7),'Page Left Off'(flagid:8) */
            let documentSpecificCount = element?.pageflag?.filter((obj: any) => (filterFlags.includes(obj.flagid)))?.length;
            totalFilteredPages += documentSpecificCount;
        });
        return filterFlags.length > 0 ? totalFilteredPages : totalPageCount;
    }


    const setAdditionalData = () => {
        let filesForDisplayCopy = [...filesForDisplay];
        filesForDisplayCopy.forEach((file1: any) => {
            pageFlags?.forEach((pageFlag1: any) => {
                if (file1.documentid == pageFlag1?.documentid) {
                    file1.pageFlag = pageFlag1?.pageflag;
                    let consultDetails: any = pageFlag1?.pageflag?.filter((flag1: any) => (flag1.programareaid || flag1.other));
                    if (consultDetails?.length > 0) {
                        consultDetails.forEach((consult: any) => {
                            let ministryCode: any = consultMinistries?.find((ministry: any) => ministry.programareaid === consult.programareaid);
                            if (ministryCode)
                                consult['iaocode'] = ministryCode.iaocode;
                        })
                        file1.consult = consultDetails;
                    }
                    else {
                        delete file1.consult;
                    }
                }
            })
        });
        setFilesForDisplay(filesForDisplayCopy);
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
                return filledCircle;
            case 3:
            case "Withheld in Full":
                return faCircle;
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
            case "In Progress":
                return faSpinner;
            case 8:
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
        setFilteredFiles(files.filter((file: any) => file.filename.includes(filterValue)))

    }

    const getFilePages = (pagecount: number, index: number) => {
        let pages = []
        for (var p = 1; p <= pagecount; p++) {
            pages.push(<TreeItem nodeId={`file${index}page${p}`} label={`Page ${p}`} />)
        }
        return pages;
    }

    const selectTreeItem = (file: any, page: number) => {
        if (pageMappedDocs?.docIdLookup && Object.keys(pageMappedDocs?.docIdLookup).length > 0) {
            let pageNo: number = getStitchedPageNoFromOriginal(file.documentid, page, pageMappedDocs);
            setIndividualDoc({ 'file': file, 'page': pageNo })
            setCurrentPageInfo({ 'file': file, 'page': page });
            // setCurrentDocument({ 'file': file, 'page': page })
            if (page == 1)
                setDisableHover(false);
        }
    };

    const handleSelect = (event: any, nodeIds: any) => {
        setSelected(nodeIds);
        let selectedNodes = nodeIds.map((n: any) => JSON.parse(n));
        if (selectedNodes.length === 1 && !_.isEqual(Object.keys(selectedNodes[0]), ["division"])) {
            let selectedFile = filesForDisplay.find((f: any) => f.documentid === selectedNodes[0].docid);
            selectTreeItem(selectedFile, selectedNodes[0].page || 1);
        }
        setSelectedPages(selectedNodes.filter((n: any) => n.page));
    };

    const openContextMenu = (file: any, page: number, e: any) => {
        e.preventDefault();
        var nodeId: string = e.target.parentElement.parentElement.id;
        nodeId = nodeId.substring(nodeId.indexOf('{'));
        var selectedNodes: any;
        if (!selected.includes(nodeId)) {
            selectedNodes = [nodeId]
            handleSelect(e, selectedNodes)
        } else {
            selectedNodes = selected
        }
        selectedNodes = selectedNodes.map((n: any) => JSON.parse(n));
        if (selectedNodes.length === 1 && Object.keys(selectedNodes[0]).includes("page")) {
            let selectedFile = filesForDisplay.find((f: any) => f.documentid === selectedNodes[0].docid);
            setConsultInfo(selectedFile.consult?.find((flag: any) => flag.page === selectedNodes[0].page) || {
                flagid: 4, other: [], programareaid: []
            })
        } else {
            setConsultInfo({ flagid: 4, other: [], programareaid: [] });
        }
        setOpenContextPopup(true);
        setAnchorPosition(
            e.currentTarget.getBoundingClientRect()
        );
        setDisableHover(true);
    }

    const isConsult = (consults: Array<any>, pageNo: number) => {
        if (consults?.find((consult: any) => consult.page == pageNo))
            return true;
        return false;
    }

    const filterFiles = (filters: Array<number>, consulteeFilters: Array<number>) => {
        if (filters?.length > 0) {
            if (consulteeFilters.length > 0) {
                setFilesForDisplay(filteredFiles.filter((file: any) =>
                    file.pageFlag?.find((obj: any) => (
                        filters.includes(obj.flagid) &&
                        (
                            (obj.flagid != 4 && filters.includes(obj.flagid)) ||
                            (obj.programareaid && obj.programareaid.some((val: any) => consulteeFilters.includes(val))) ||
                            (obj.other && obj.other.some((val: any) => consulteeFilters.includes(val)))
                        )
                    ))
                ));

            }

            else
                setFilesForDisplay(filteredFiles.filter((file: any) =>
                    file.pageFlag?.find((obj: any) => (obj.flagid != 4 && filters.includes(obj.flagid)))));
        }
        else
            setFilesForDisplay(filteredFiles);
    }

    const applyFilter = (flagId: number, consultee: any, event: any, allSelectedconsulteeList: any[]) => {

        const flagFilterCopy = [...filterFlags];
        let consulteeIds = [...consulteeFilter];
        if (flagFilterCopy.includes(flagId)) {
            if (flagId == 4) {
                if (event.target.checked) {
                    if (allSelectedconsulteeList.length > 0) {
                        consulteeIds = allSelectedconsulteeList
                    }
                    else
                        consulteeIds.push(consultee)
                } else {
                    if (allSelectedconsulteeList.length > 0) {
                        consulteeIds = []
                    }
                    else
                        consulteeIds?.splice(consulteeIds.indexOf(consultee), 1);
                }
                if (consulteeIds.length <= 0)
                    flagFilterCopy.splice(flagFilterCopy.indexOf(flagId), 1);
            }
            else {
                flagFilterCopy.splice(flagFilterCopy.indexOf(flagId), 1);
            }
            event.currentTarget.classList.remove('selected');
            if (flagId === pageFlagTypes["Page Left Off"])
                setFilterBookmark(false);
            else if ((flagFilterCopy.length == 1 && flagFilterCopy.includes(pageFlagTypes["Page Left Off"])))
                setFilterBookmark(true);
        }
        else {
            if (flagId == 4) {
                if (event.target.checked) {
                    if (allSelectedconsulteeList.length > 0)
                        consulteeIds = allSelectedconsulteeList
                    else
                        consulteeIds.push(consultee)
                }
                else {
                    if (allSelectedconsulteeList.length > 0)
                        consulteeIds = []
                    else
                        consulteeIds?.splice(consulteeIds.indexOf(consultee), 1);
                }
            }
            flagFilterCopy.push(flagId);
            event.currentTarget.classList.add('selected');
            if (flagId === pageFlagTypes["Page Left Off"] || (flagFilterCopy.length == 1 && flagFilterCopy.includes(pageFlagTypes["Page Left Off"])))
                setFilterBookmark(true);
            else
                setFilterBookmark(false);
        }
        setFilterFlags(flagFilterCopy);
        setConsulteeFilter(consulteeIds);
        filterFiles(flagFilterCopy, consulteeIds);
    }


    const getFlagName = (file: any, pageNo: number) => {
        let flag: any = file?.pageFlag?.find((flg: any) => flg.page === pageNo);
        if (flag.flagid === 4 && file.consult?.length > 0) {
            let ministries = flag.programareaid.map((m: any) => (consultMinistries?.find((ministry: any) => ministry.programareaid === m) as any)?.iaocode);
            ministries.push(...flag.other);
            return `Consult - [` + ministries.join(`]\nConsult - [`) + ']';
        }
        return PAGE_FLAGS[flag.flagid as keyof typeof PAGE_FLAGS];
    }

    const assignConsulteeCode = (flag: any) => {
        let ministries = flag.programareaid.map((m: any) => (consultMinistries?.find((ministry: any) => ministry.programareaid === m) as any));
        ministries.push(...flag.other);
        return ministries;
    }

    const codeById: Record<number, string> = consultMinistries.reduce((acc: any, item: any) => {
        acc[item.programareaid] = item.iaocode;
        return acc;
    }, {});

    const openConsulteeList = (e: any) => {
        const consultFlagged = files.filter((file: any) => file.pageFlag?.find((obj: any) => (obj.flagid == 4)));
        if (consultFlagged?.length > 0) {
            const namedConsultValues: any[] = Array.from(new Set(
                consultFlagged.flatMap((item: any) => item.consult)
                    .flatMap((consultItem: any) => [...consultItem.programareaid, ...consultItem.other])
                    .map((value: any) => JSON.stringify({ id: value, code: codeById[value] || value }))
            )).map((strObject: any) => JSON.parse(strObject));
            
            console.log(namedConsultValues);
            setOpenConsulteeModal(true);
            setAssignedConsulteeList(namedConsultValues);
            setAnchorEl(e.currentTarget);
        }
    }



    const showConsultee = (assignedConsulteeList: any[]) => assignedConsulteeList?.map((consultee: any, index: number) => {
        return (
            <>
                <div key={index} className="consulteeItem">
                    <span style={{ marginRight: '10px' }}>
                        <input
                            type="checkbox"
                            id={`checkbox-${index}`}
                            checked={consulteeFilter.includes(consultee.id || consultee.code)}
                            onChange={(e) => { applyFilter(4, consultee.id || consultee.code, e, []) }}
                        />
                    </span>
                    <label htmlFor={`checkbox-${index}`}>
                        {consultee.code}
                    </label>
                </div>
            </>
        )
    })

    const selectAllConsultees = (assignedConsulteeList: any[], event: any) => {
        if (event.target.checked)
            setSelectAllConsultee(true);
        else
            setSelectAllConsultee(false);
        let consulteeIds = assignedConsulteeList.map((obj: any) => obj.id||obj.code);
        applyFilter(4, null, event, consulteeIds)
    }

    const consultFilterStyle = {
        color: consulteeFilter.length === 0 ? '#808080' : '#003366' // Change colors as needed
    };

    const handleClose = () => {
        setAnchorEl(null);
        setOpenConsulteeModal(false)
    };

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
                                id="documentfilter"
                                placeholder="Filter Records ..."
                                defaultValue={""}
                                onChange={(e) => { onFilterChange(e.target.value.trim()) }}
                                inputProps={{ 'aria-labelledby': 'document-filter' }}
                                sx={{
                                    color: "#38598A",
                                }}
                                startAdornment={
                                    <InputAdornment position="start" >
                                        <IconButton aria-hidden="true"
                                            className="search-icon"
                                            aria-label="search-icon"
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

                    <div className='row'>
                        <div className='col-lg-4' style={{ paddingRight: '0px' }}>
                            Organize by:
                        </div>
                        <div className='col-lg-8' style={{ paddingLeft: '0px' }}>
                            <Stack direction="row" sx={{ paddingBottom: "5px" }} spacing={1}>
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
                        </div>
                    </div>
                    <hr className='hrStyle' />
                    <div>
                        <span className='filterText'>
                            Filter:
                        </span>
                        <span>
                            {pageFlagList.map((item: any) =>
                                < >

                                    {(item.pageflagid == 'Consult' || item.pageflagid == 4) ?
                                        <span style={consultFilterStyle} onClick={(event) => openConsulteeList(event)}>
                                            <FontAwesomeIcon key={item.pageflagid} title={item.name} className={(item.pageflagid == 'Consult' || item.pageflagid == 4) ? 'filterConsultIcon' : 'filterIcons'}
                                                id={item.pageflagid} style={{ color: 'inherit' }}
                                                icon={assignIcon(item.pageflagid) as IconProp} size='1x' />
                                            <FontAwesomeIcon className={'filterDropDownIcon'} icon={faAngleDown as IconProp}
                                                style={{ color: 'inherit' }} />
                                        </span> :
                                        <FontAwesomeIcon key={item.pageflagid} title={item.name}
                                            className={(item.pageflagid == 'Consult' || item.pageflagid == 4) ? 'filterConsultIcon' : 'filterIcons'}
                                            onClick={(event) => applyFilter(item.pageflagid, null, event, [])} id={item.pageflagid}
                                            icon={assignIcon(item.pageflagid) as IconProp} size='1x' />
                                    }
                                </>
                            )}
                        </span>

                        <Popover
                            anchorEl={anchorEl}
                            open={openconsulteeModal}
                            anchorOrigin={{
                                vertical: "bottom",
                                horizontal: "center",
                            }}
                            transformOrigin={{
                                vertical: "top",
                                horizontal: "center",
                            }}
                            PaperProps={{
                                style: { marginTop: '10px', padding: '10px' }
                            }}
                            onClose={() => handleClose()}>
                            <div className='consultDropDown'>
                                <div className='heading'>
                                    <div className="consulteeItem">
                                        <span style={{ marginRight: '10px' }}>
                                            <input
                                                type="checkbox"
                                                id={`checkbox-all`}
                                                checked={selectAllConsultee}
                                                onChange={(e) => { selectAllConsultees(assignedConsulteeList, e) }}
                                            />
                                        </span>
                                        <label htmlFor={`checkbox-all`}>
                                            Select Consult
                                        </label>
                                    </div>
                                    <hr className='hrStyle' />
                                </div>
                                {showConsultee(assignedConsulteeList)}
                            </div>
                        </Popover>
                    </div>
                    <hr className='hrStyle' />
                    <div className='row counters'>
                        <div className='col-lg-6'>
                            {`Complete: ${updateCompletionCounter()}%`}
                        </div>
                        <div className='col-lg-6 style-float'>
                            {`Total Pages: ${updatePageCount()}/${totalPageCount}`}
                        </div>
                    </div>
                    <hr className='hrStyle' />
                    <TreeView
                        aria-label="file system navigator"
                        defaultCollapseIcon={<ExpandMoreIcon />}
                        defaultExpandIcon={<ChevronRightIcon />}
                        multiSelect
                        selected={selected}
                        onNodeSelect={handleSelect}
                        sx={{ flexGrow: 1, maxWidth: 400, overflowY: 'auto' }}
                    >
                        {filesForDisplay.length <= 0 && filterBookmark ?
                            <div style={{ textAlign: 'center' }}>No page has been book marked.</div>
                            :
                            (filesForDisplay.length > 0 &&
                                (organizeBy === "division" ?
                                    divisions.map((division: any, index) =>
                                        <TreeItem nodeId={`{"division": ${division.divisionid}}`} label={division.name} key={division.divisionid}>
                                            {filesForDisplay.filter((file: any) => file.divisions.map((d: any) => d.divisionid).includes(division.divisionid)).map((file: any, i: number) =>
                                                <Tooltip
                                                    sx={{
                                                        backgroundColor: 'white',
                                                        color: 'rgba(0, 0, 0, 0.87)',
                                                        fontSize: 11
                                                    }}
                                                    title={<>
                                                        Last Modified Date: {new Date(file.attributes.lastmodified).toLocaleString('en-US', { timeZone: 'America/Vancouver' })}
                                                        {file.attachmentof && <><br></br> Attachment of: {file.attachmentof}</>}
                                                    </>}
                                                    placement="bottom-end"
                                                    arrow
                                                    key={i}
                                                    disableHoverListener={disableHover}
                                                >

                                                    <TreeItem nodeId={`{"division": ${division.divisionid}, "docid": ${file.documentid}}`} label={file.filename} key={file.documentid} disabled={pageMappedDocs?.length <= 0}>
                                                        {[...Array(file.pagecount)].map((_x, p) =>
                                                        (filterFlags.length > 0 ?
                                                            (consulteeFilter.length > 0 ?
                                                                ((file.pageFlag && file.pageFlag?.find((obj: any) => obj.page === p + 1 &&
                                                                    (   (obj.flagid != 4 && filterFlags?.includes(obj.flagid))||
                                                                        (obj.programareaid && obj.programareaid.some((val: any) => consulteeFilter.includes(val))) ||
                                                                        (obj.other && obj.other.some((val: any) => consulteeFilter.includes(val))))))                                                                       
                                                                    &&
                                                                    <>
                                                                        <StyledTreeItem nodeId={`{"division": ${division.divisionid}, "docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} icon={<FontAwesomeIcon className='leftPanelIcons' icon={assignPageIcon(file.documentid, p + 1) as IconProp} size='1x' />}
                                                                            title={getFlagName(file, p + 1)} label={isConsult(file.consult, p + 1) ? `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1} (${ministryOrgCode(p + 1, file.consult)})` : `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1}`}
                                                                            onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
                                                                    </>
                                                                ) :
                                                                (
                                                                    (file.pageFlag && file.pageFlag?.find((obj: any) => obj.page === p + 1 && obj.flagid != 4 && filterFlags?.includes(obj.flagid))) &&
                                                                    <>
                                                                        <StyledTreeItem nodeId={`{"division": ${division.divisionid}, "docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} icon={<FontAwesomeIcon className='leftPanelIcons' icon={assignPageIcon(file.documentid, p + 1) as IconProp} size='1x' />}
                                                                            title={getFlagName(file, p + 1)} label={isConsult(file.consult, p + 1) ? `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1} (${ministryOrgCode(p + 1, file.consult)})` : `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1}`}
                                                                            onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
                                                                    </>
                                                                )
                                                            )
                                                            :
                                                            (file.pageFlag && file.pageFlag?.find((obj: any) => obj.page === p + 1) ?
                                                                <StyledTreeItem nodeId={`{"division": ${division.divisionid}, "docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} icon={<FontAwesomeIcon className='leftPanelIcons' icon={assignPageIcon(file.documentid, p + 1) as IconProp} size='1x' />}
                                                                    title={getFlagName(file, p + 1)} label={isConsult(file.consult, p + 1) ? `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1} (${ministryOrgCode(p + 1, file.consult)})` : `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1}`}
                                                                    onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
                                                                :
                                                                <StyledTreeItem nodeId={`{"division": ${division.divisionid}, "docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} label={`Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1}`}
                                                                    onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
                                                            )
                                                        )
                                                        )
                                                        }
                                                        {pageFlagList && pageFlagList?.length > 0 &&
                                                            <ContextMenu
                                                                openFOIPPAModal={openFOIPPAModal}
                                                                requestId={requestid}
                                                                pageFlagList={pageFlagList}
                                                                assignIcon={assignIcon}
                                                                anchorPosition={anchorPosition}
                                                                openContextPopup={openContextPopup}
                                                                setOpenContextPopup={setOpenContextPopup}
                                                                selectedPages={selectedPages}
                                                                consultInfo={consultInfo}
                                                                setPageFlagChanged={setPageFlagChanged}
                                                            />
                                                        }
                                                    </TreeItem>
                                                </Tooltip>
                                            )}
                                        </TreeItem>
                                    )
                                    :
                                    filesForDisplay.sort(docSorting).map((file: any, index: number) =>
                                        <Tooltip
                                            sx={{
                                                backgroundColor: 'white',
                                                color: 'rgba(0, 0, 0, 0.87)',
                                                // boxShadow: theme.shadows[1],
                                                fontSize: 11
                                            }}
                                            title={<>
                                                Last Modified Date: {new Date(file.attributes.lastmodified).toLocaleString('en-US', { timeZone: 'America/Vancouver' })}
                                                {file.attachmentof && <><br></br> Attachment of: {file.attachmentof}</>}
                                            </>}
                                            placement="bottom-end"
                                            arrow
                                            key={file?.documentid}
                                            disableHoverListener={disableHover}
                                        >
                                            <TreeItem nodeId={`{"docid": ${file.documentid}}`} label={file.filename} key={file?.documentid}>
                                                {[...Array(file.pagecount)].map((_x, p) =>
                                                (filterFlags.length > 0 ?
                                                    (consulteeFilter.length > 0 ?
                                                        ((file.pageFlag && file.pageFlag?.find((obj: any) => obj.page === p + 1 &&
                                                            ((obj.flagid != 4 && filterFlags?.includes(obj.flagid))||
                                                                (obj.programareaid && obj.programareaid.some((val: any) => consulteeFilter.includes(val))) ||
                                                                    (obj.other && obj.other.some((val: any) => consulteeFilter.includes(val))) )))
                                                            &&
                                                            <>
                                                                <StyledTreeItem nodeId={`{"docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} icon={<FontAwesomeIcon className='leftPanelIcons' icon={assignPageIcon(file.documentid, p + 1) as IconProp} size='1x' />}
                                                                    title={getFlagName(file, p + 1)} label={isConsult(file.consult, p + 1) ? `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1} (${ministryOrgCode(p + 1, file.consult)})` : `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1}`}
                                                                    onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
                                                            </>
                                                        ) :
                                                        (
                                                            (file.pageFlag && file.pageFlag?.find((obj: any) => obj.page === p + 1 && obj.flagid != 4 && filterFlags?.includes(obj.flagid))) &&
                                                            <>
                                                                <StyledTreeItem nodeId={`{"docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} icon={<FontAwesomeIcon className='leftPanelIcons' icon={assignPageIcon(file.documentid, p + 1) as IconProp} size='1x' />}
                                                                    title={getFlagName(file, p + 1)} label={isConsult(file.consult, p + 1) ? `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1} (${ministryOrgCode(p + 1, file.consult)})` : `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1}`}
                                                                    onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
                                                            </>
                                                        )
                                                    )
                                                    :
                                                    (file.pageFlag && file.pageFlag?.find((obj: any) => obj.page === p + 1) ?
                                                        <StyledTreeItem nodeId={`{"docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} icon={<FontAwesomeIcon className='leftPanelIcons' icon={assignPageIcon(file.documentid, p + 1) as IconProp} size='1x' />}
                                                            title={getFlagName(file, p + 1)} label={isConsult(file.consult, p + 1) ? `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1} (${ministryOrgCode(p + 1, file.consult)})` : `Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1}`}
                                                            onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
                                                        :
                                                        <StyledTreeItem nodeId={`{"docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} label={`Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1}`}
                                                            onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
                                                    )
                                                )
                                                )}
                                                {pageFlagList && pageFlagList?.length > 0 &&
                                                    <ContextMenu
                                                        openFOIPPAModal={openFOIPPAModal}
                                                        requestId={requestid}
                                                        pageFlagList={pageFlagList}
                                                        assignIcon={assignIcon}
                                                        anchorPosition={anchorPosition}
                                                        openContextPopup={openContextPopup}
                                                        setOpenContextPopup={setOpenContextPopup}
                                                        selectedPages={selectedPages}
                                                        consultInfo={consultInfo}
                                                        setPageFlagChanged={setPageFlagChanged}
                                                        pageMappedDocs={pageMappedDocs}
                                                    />
                                                }
                                            </TreeItem>
                                        </Tooltip>
                                    )
                                )
                            )
                        }
                    </TreeView>
                </Stack>

            </div>
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