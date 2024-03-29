import React, { useEffect, useState, useImperativeHandle, useRef, createRef, LegacyRef } from 'react'
import Chip from "@mui/material/Chip";
import {TreeView, TreeItem} from '@mui/x-tree-view';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { treeItemClasses } from "@mui/x-tree-view/TreeItem";
import SearchIcon from "@mui/icons-material/Search";
import InputAdornment from "@mui/material/InputAdornment";
import InputBase from "@mui/material/InputBase";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Grid from "@mui/material/Grid";
import Stack from "@mui/material/Stack";
import Tooltip from '@mui/material/Tooltip';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import { fetchPageFlagsMasterData, fetchPageFlag } from '../../../apiManager/services/docReviewerService';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCircleHalfStroke, faCircle, faCircleQuestion, faSpinner,
    faCircleStop, faCircleXmark, faBookmark, faAngleDown, faCircleExclamation,
    faAnglesDown, faAnglesUp
} from '@fortawesome/free-solid-svg-icons';
import { faCircle as filledCircle } from '@fortawesome/free-regular-svg-icons';
import { IconProp } from '@fortawesome/fontawesome-svg-core';
import "./DocumentSelector.scss";
import PAGE_FLAGS from '../../../constants/PageFlags';
import ContextMenu from "./ContextMenu";
import LayerDropdown from "./LayerDropdown"
import { styled } from "@mui/material/styles";
import { useAppSelector } from '../../../hooks/hook';
import { getStitchedPageNoFromOriginal, docSorting} from "./utils";
import { pageFlagTypes } from '../../../constants/enum';
import _ from "lodash";
import Popover from "@mui/material/Popover";
import { PAGE_SELECT_LIMIT } from '../../../constants/constants'


const DocumentSelector = React.forwardRef(({
    openFOIPPAModal,
    requestid,
    documents,
    totalPageCount,
    setCurrentPageInfo,
    setIndividualDoc,
    pageMappedDocs,
    setWarningModalOpen
}: any, ref) => {

    const requestInfo = useAppSelector((state: any) => state.documents?.requestinfo);
    const pageFlags = useAppSelector((state: any) => state.documents?.pageFlags);
    const currentLayer = useAppSelector((state: any) => state.documents?.currentLayer);
    const [files] = useState(documents);
    const [openContextPopup, setOpenContextPopup] = useState(false);
    const [anchorPosition, setAnchorPosition] = useState<any>(undefined);
    const [organizeBy, setOrganizeBy] = useState("lastmodified")
    const [pageFlagList, setPageFlagList] = useState([]);
    const [filesForDisplay, setFilesForDisplay] = useState(files);
    const [consultMinistries, setConsultMinistries] = useState<any>([]);
    const [selectedPages, setSelectedPages] = useState<any>([]);
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
    const [expanded, setExpanded] = useState<string[]>([]);
    const pageRefs = useRef([]);

    const StyledTreeItem = styled(TreeItem)(() => ({
        [`& .${treeItemClasses.label}`]: {
            fontSize: '14px'
        },
        [`& .${treeItemClasses.content}`]: {
            padding: '0 16px'
        }
    }));

    useImperativeHandle(ref, () => ({
        async scrollToPage(pageNumber: number) {
            setExpanded([...new Set([...expanded, "{\"docid\": " + pageMappedDocs.stitchedPageLookup[pageNumber].docid + "}"])]);
            await new Promise(resolve => setTimeout(resolve, 400)); // wait for expand animation to finish
            let pageRef = (pageRefs.current[pageNumber - 1] as any).current;
            if (pageRef) {
                pageRef.scrollIntoView();
                let nodeId = pageRef.children[0].id;
                nodeId = nodeId.substring(nodeId.indexOf('{'));
                setSelected([nodeId])
                setSelectedPages([JSON.parse(nodeId)])
            }
        },
    }), [pageRefs, expanded, pageMappedDocs]);


    useEffect(() => {
        let refLength = documents.reduce((acc: any, file: any) => acc + file.pagecount, 0);
        pageRefs.current = Array(refLength).fill(0).map((_, i) => pageRefs.current[i] || createRef());
    }, [documents])

    useEffect(() => {
        fetchPageFlagsMasterData(
            requestid,
            currentLayer.name.toLowerCase(),
            (data: any) => setPageData(data),
            (error: any) => console.log(error)
        );
    }, [currentLayer]);

    useEffect(() => {
        if(requestInfo.requesttype == "personal" && ["MSD", "MCF"].includes(requestInfo.bcgovcode)) {
            setOrganizeBy("division");
        }
    }, [requestInfo]);

    const updatePageFlags = () => {
        fetchPageFlagsMasterData(
            requestid,
            currentLayer.name.toLowerCase(),
            (data: any) => setPageData(data),
            (error: any) => console.log(error)
        );
        fetchPageFlag(
            requestid,
            currentLayer.name.toLowerCase(),
            documents.map((d: any) => d.documentid),            
            (error: any) => console.log(error)
        )
    }

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
            let documentSpecificCount = element?.pageflag?.filter((obj: any) => (!([pageFlagTypes["Consult"], pageFlagTypes["In Progress"], pageFlagTypes["Page Left Off"]].includes(obj.flagid))))?.length;
            totalPagesWithFlags += documentSpecificCount;
        });
        /* We need to Math.floor the result because the result can be a float value and we want to take the lower value
           as it may show 100% even if the result is 99.9% */ 
        return (totalPageCount > 0 && totalPagesWithFlags >= 0) ? Math.floor((totalPagesWithFlags / totalPageCount) * 100) : 0;
    }


    function intersection(setA: any, setB: any) {
        const _intersection = new Set();
        for (const elem of setB) {
            if (setA.has(elem)) {
            _intersection.add(elem);
            }
        }
        return _intersection;
    }

    const updatePageCount = () => {
        let totalFilteredPages = 0;
        pageFlags?.forEach((element: any) => {
            /**Page Flags to be avoided while 
             * calculating % on left panel-  
             * 'Consult'(flagid:4),'In Progress'(flagid:7),'Page Left Off'(flagid:8) */
            let documentSpecificCount = element?.pageflag?.filter((obj: any) => {
                if (obj.flagid  === pageFlagTypes["Consult"]) {
                    const consultFilter = new Set(consulteeFilter);
                    const selectedMinistries = new Set([...obj.programareaid, ...obj.other]);
                    const consultOverlap = intersection(consultFilter, selectedMinistries);
                    return filterFlags.includes(obj.flagid) && consultOverlap.size > 0;
                }
                return filterFlags.includes(obj.flagid);
            })?.length;
            totalFilteredPages += documentSpecificCount;
        });
        let unflagged = 0;
        if (filterFlags.length > 0 && filterFlags.includes(0)) {
            filesForDisplay?.forEach((file: any) => {
                let flagedpages = file.pageFlag ? file.pageFlag.length : 0;
                unflagged += file.pagecount - flagedpages;
            });

        }
        return filterFlags.length > 0 ? totalFilteredPages + unflagged : totalPageCount;
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
        let pageFlagObjs = docs?.pageflag?.filter((flag: any) => flag.page === page).sort((a: any, b: any) => (Number(b.flagid === pageFlagTypes["Consult"] || false)) - (Number(a.flagid === pageFlagTypes["Consult"] || false)));
        let assignIconValue: any = [];
        for (const pageFlag of pageFlagObjs) {
            if (pageFlag.flagid !== undefined) {              
                assignIconValue.push({icon: assignIcon(pageFlag.flagid), flagid: pageFlag.flagid});
            }
          }
        return assignIconValue;
        
    }

    let arr: any[] = [];
    const divisions = [...new Map(files.reduce((acc: any[], file: any) => [...acc, ...new Map(file.divisions.map((division: any) => [division.divisionid, division]))], arr)).values()]

    let expandall: any[] = [];
    let expandallorganizebydivision: any[] = [];
    divisions.forEach((division:any) => {
        expandallorganizebydivision.push(`{"division": ${division.divisionid}}`);
        files.filter((file: any) => file.divisions.map((d: any) => d.divisionid).includes(division.divisionid)).map((file: any, i: number) => {
            expandallorganizebydivision.push(`{"division": ${division.divisionid}, "docid": ${file.documentid}}`);
            expandall.push(`{"docid": ${file.documentid}}`);
        })
    });

    const onFilterChange = (filterValue: string) => {
        setFilesForDisplay(files.filter((file: any) => file.filename.includes(filterValue)))
        setFilteredFiles(files.filter((file: any) => file.filename.includes(filterValue)))

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

        let selectedpages:any[] = [];
        let selectedothers:any[] = [];
        let selectedNodes:any[] = [];
        for (let n of nodeIds) {
            let _n = JSON.parse(n);
            selectedNodes.push(_n);
            if(_n.page) {
                selectedpages.push(n);
            } else {
                selectedothers.push(n);
            }
        }

        if (selectedNodes.length === 1 && !_.isEqual(Object.keys(selectedNodes[0]), ["division"])) {
            let selectedFile = filesForDisplay.find((f: any) => f.documentid === selectedNodes[0].docid);
            selectTreeItem(selectedFile, selectedNodes[0].page || 1);
        }

        // if new select includes divisions and filenames:
        // 1. remove divisions and filenames from new select
        // 2. join old select and new select
        // else only keep new select
        if(selectedothers.length > 0) {
            selectedpages = [...new Set([...selected, ...selectedpages])];
        }

        if(selectedpages.length > PAGE_SELECT_LIMIT) {
            setWarningModalOpen(true);
        } else {
            setSelected(selectedpages);
            let _selectedpages:any[] = selectedpages.map((n: any) => JSON.parse(n));
            setSelectedPages(_selectedpages);
        }
    };

    const openContextMenu = (file: any, page: number, e: any) => {
        e.preventDefault();
        let nodeId: string = e.target.parentElement.parentElement.id;
        if (nodeId === "") {
            nodeId = e.currentTarget.id;
        }
        nodeId = nodeId.substring(nodeId.indexOf('{'));
        let selectedNodes: any;
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
            e?.currentTarget?.getBoundingClientRect()
        );
        setDisableHover(true);
    }

    const isConsult = (consults: Array<any>, pageNo: number) => {
        if (consults?.find((consult: any) => consult.page == pageNo))
            return true;
        return false;
    }

    const isUnflagged = (pageflags: Array<any>, pageNo: number) => {
        const isFound = pageflags?.some(pageflag => pageflag.page == pageNo)
        return !isFound;
        }

    const filterFiles = (filters: Array<number>, consulteeFilters: Array<number>) => {
        if (filters?.length > 0) {
            if (consulteeFilters.length > 0) {
                setFilesForDisplay(filteredFiles.filter((file: any) =>
                    file.pageFlag?.find((obj: any) => (
                        filters.includes(obj.flagid) &&
                        (
                            (obj.flagid != 4 && filters.includes(obj.flagid)) ||
                            (obj.programareaid?.some((val: any) => consulteeFilters.includes(val))) ||
                            (obj.other?.some((val: any) => consulteeFilters.includes(val)))
                        )
                    ))
                ));

            }
            else
                 setFilesForDisplay(filteredFiles.filter((file: any) =>  ((filters.includes(0) && (typeof file.pageFlag === "undefined" || file.pageFlag?.length == 0 || file.pagecount != file.pageFlag?.length))
                              || (file.pageFlag?.find((obj: any) => ((obj.flagid != 4 && filters.includes(obj.flagid))))))
                    ));
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
                } else if (allSelectedconsulteeList.length > 0) {
                        consulteeIds = []
                    }
                    else
                        consulteeIds?.splice(consulteeIds.indexOf(consultee), 1);
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
                else if (allSelectedconsulteeList.length > 0)
                        consulteeIds = []
                    else
                        consulteeIds?.splice(consulteeIds.indexOf(consultee), 1);
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
        let consultFlag: any = file?.pageFlag?.find((flg: any) => flg.page === pageNo && flg.flagid === pageFlagTypes["Consult"]);
        if (consultFlag && file.consult?.length > 0) {
            let ministries = consultFlag.programareaid.map((m: any) => consultMinistries?.find((ministry: any) => ministry.programareaid === m)?.iaocode);
            ministries.push(...consultFlag.other);
            return `Consult - [` + ministries.join(`]\nConsult - [`) + ']';
        }
        return PAGE_FLAGS[flag.flagid as keyof typeof PAGE_FLAGS];
    }

   const codeById: Record<number, String> = {};
   if (consultMinistries && consultMinistries?.length > 0) {
        consultMinistries?.map((item: any) => {
            codeById[item.programareaid] = item.iaocode;
        });
    }
    


    const openConsulteeList = (e: any) => {
        const consultFlagged = files.filter((file: any) => file.pageFlag?.find((obj: any) => (obj.flagid == 4)));
        if (consultFlagged?.length > 0 && codeById) {
            const namedConsultValues: any[] = Array.from(new Set(
                consultFlagged.flatMap((item: any) => item.consult)
                    .flatMap((consultItem: any) => [...consultItem.programareaid, ...consultItem.other])
                    .map((value: any) => JSON.stringify({ id: value, code: codeById[value] || value }))
            )).map((strObject: any) => JSON.parse(strObject));
            
            setOpenConsulteeModal(true);
            setAssignedConsulteeList(namedConsultValues);
            setAnchorEl(e.currentTarget);
        }
    }



    const showConsultee = (assignedConsulteeList: any[]) => assignedConsulteeList?.map((consultee: any, index: number) => {
        return (            
                <div key={consultee.id} className="consulteeItem">
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
    
    const addIcons = (file: any, p: any) => {
        return assignPageIcon(file.documentid, p + 1).map((icon: any, index: any) => (
                <FontAwesomeIcon
                key={icon.flagid}
                className='leftPanelIcons'
                icon={icon.icon as IconProp}
                size='1x'
                title={PAGE_FLAGS[icon.flagid as keyof typeof PAGE_FLAGS]}
                />
        ))
    }

    const consulteeFilterView = (file: any, p: number, division?: any) => {
        return (
        (consulteeFilter.length > 0 ?
            ((file.pageFlag?.find((obj: any) => obj.page === p + 1 &&
                (   (obj.flagid != 4 && filterFlags?.includes(obj.flagid))||
                    (obj.programareaid?.some((val: any) => consulteeFilter.includes(val))) ||
                    (obj.other?.some((val: any) => consulteeFilter.includes(val))))))                                                                       
                &&
                <div ref={pageRefs.current[displayStitchedPageNo(file, pageMappedDocs, p + 1) - 1]}>                    
                    <StyledTreeItem nodeId={division ? `{"division": ${division?.divisionid}, "docid": ${file.documentid}, "page": ${p + 1}}` : `{"docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} icon= {addIcons(file, p)}
                        title={getFlagName(file, p + 1)} label={isConsult(file.consult, p + 1) ? `Page ${displayStitchedPageNo(file, pageMappedDocs, p + 1)} (${ministryOrgCode(p + 1, file.consult)})` : `Page ${displayStitchedPageNo(file, pageMappedDocs, p + 1)}`}
                        onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
                </div>
            ) :
            viewWithoutConsulteeFilter(file, p)
        )
        );
    }

    const noFilterView = (file: any, p: number, division?: any) => {
        return (
            (file.pageFlag?.find((obj: any) => obj.page === p + 1) ?
            <div ref={pageRefs.current[displayStitchedPageNo(file, pageMappedDocs, p + 1) - 1]}>                
                <StyledTreeItem nodeId={division ? `{"division": ${division.divisionid}, "docid": ${file.documentid}, "page": ${p + 1}}` : `{"docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} icon= {addIcons(file, p)}
                    title={getFlagName(file, p + 1)} label={isConsult(file.consult, p + 1) ? `Page ${displayStitchedPageNo(file, pageMappedDocs, p + 1)} (${ministryOrgCode(p + 1, file.consult)})` : `Page ${displayStitchedPageNo(file, pageMappedDocs, p + 1)}`}
                    onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
            </div>
                :
                <div ref={pageRefs.current[displayStitchedPageNo(file, pageMappedDocs, p + 1) - 1]}>
                <StyledTreeItem nodeId={division ? `{"division": ${division.divisionid}, "docid": ${file.documentid}, "page": ${p + 1}}` : `{"docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} label={`Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1}`}
                    onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
                </div>
            )
        )
    }

    const displayStitchedPageNo = (file: any, pageMappedDocs: any, p : number) => {
        return file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p, pageMappedDocs) : p;
    }

    const viewWithoutConsulteeFilter = (file: any, p:number) => {
        return (file.pageFlag?.find((obj: any) => obj.page === p + 1 && obj.flagid != 4 && filterFlags?.includes(obj.flagid))) ?
        (
        <div ref={pageRefs.current[displayStitchedPageNo(file, pageMappedDocs, p + 1) - 1]}>
            <StyledTreeItem nodeId={`{"docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} icon= {addIcons(file, p)}
                title={getFlagName(file, p + 1)} label={isConsult(file.consult, p + 1) ? `Page ${displayStitchedPageNo(file, pageMappedDocs, p + 1)} (${ministryOrgCode(p + 1, file.consult)})` : `Page ${displayStitchedPageNo(file, pageMappedDocs, p + 1)}`}
                onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
        </div>
        )
        :
        (filterFlags?.includes(0) && isUnflagged(file.pageFlag, p+1)) &&
        (
        <div ref={pageRefs.current[displayStitchedPageNo(file, pageMappedDocs, p + 1) - 1]}>
        <StyledTreeItem nodeId={`{"docid": ${file.documentid}, "page": ${p + 1}}`} key={p + 1} label={`Page ${file && !Array.isArray(pageMappedDocs) ? getStitchedPageNoFromOriginal(file?.documentid, p + 1, pageMappedDocs) : p + 1}`}
                onContextMenu={(e) => openContextMenu(file, p + 1, e)} />
        </div>
        )
    }

    const sortByModifiedDateView = filesForDisplay?.map((file: any, index: number) => { 
        return (
            organizeBy === "lastmodified" ? (
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
                    {
                        expanded?.length > 0 ?
                        (
                                [...Array(file.pagecount)].map((_x, p) =>
                                (filterFlags.length > 0 ?
                                    consulteeFilterView(file,p)
                                    :
                                    noFilterView(file,p)                                               
                                )
                                )
                        ) : (<></>)
                    }
                    {pageFlagList && pageFlagList?.length > 0 && openContextPopup === true &&
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
                            updatePageFlags={updatePageFlags}
                            pageMappedDocs={pageMappedDocs}
                        />
                    }
                </TreeItem>
            </Tooltip>) : <></>
        )
    })

    const sortByDivisionFilterView = divisions.map((division: any, index) => {
        return(
            organizeBy === "division" ? (
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
                        key={file.documentid}
                        disableHoverListener={disableHover}
                    >

                        <TreeItem nodeId={`{"division": ${division.divisionid}, "docid": ${file.documentid}}`} label={file.filename} key={file.documentid} disabled={pageMappedDocs?.length <= 0}>
                            {[...Array(file.pagecount)].map((_x, p) =>
                            (filterFlags.length > 0 ?
                                consulteeFilterView(file,p,division)
                                :
                                noFilterView(file,p,division)
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
                                    updatePageFlags={updatePageFlags}
                                    pageMappedDocs={pageMappedDocs}
                                />
                            }
                        </TreeItem>
                    </Tooltip>
                )}
            </TreeItem>) : (<></>)
        )
    })
    
    const displayFiles = () => {
       
        return (
                filesForDisplay?.length > 0 ?
                (
                organizeBy === "lastmodified" ? sortByModifiedDateView  : sortByDivisionFilterView
                )
                :
                    <></>                
            )         
    }

    const handleExpandClick = () => {
        setExpanded((oldExpanded:any) => {
                let result: any = [];
                if (oldExpanded.length === 0 ) {
                    if (organizeBy == "lastmodified" ) {
                        result = expandall;
                    }
                    else {
                        result = expandallorganizebydivision;
                    }
                }
                return result;
            }            
        );
    };

    const handleToggle = (event: React.SyntheticEvent, nodeIds: string[]) => {
        setExpanded(nodeIds);
    };

    return (
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
                        <div className='col-lg-5' style={{paddingRight: '0px', display: "flex", alignItems: "center"}}>
                            Redaction Layer:
                        </div>
                        <div className='col-lg-7' style={{paddingLeft: '0px', display: "flex", justifyContent: "flex-end"}}>
                            <LayerDropdown ministryrequestid={requestid} validoipcreviewlayer={requestInfo.validoipcreviewlayer}/>
                        </div>
                    </div>
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
                                    onClick={() => {setOrganizeBy("division");setExpanded([])}}
                                    clicked={organizeBy === "division"}
                                />
                                <ClickableChip
                                    label="Modified Date"
                                    color="primary"
                                    size="small"
                                    onClick={() => {setOrganizeBy("lastmodified");setExpanded([])}}
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

                            
                            <FontAwesomeIcon key='0' title='No Flag'
                                            className='filterIcons'
                                            onClick={(event) => applyFilter(0, null, event, [])} id='0'
                                            icon={faCircleExclamation as IconProp} size='1x' />
                          
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
                            slotProps={{
                                paper: {style: { marginTop: '10px', padding: '10px' }}
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
                    <Box sx={{ mb: 1 }}>
                        <Tooltip
                            sx={{
                                backgroundColor: 'white',
                                color: 'rgba(0, 0, 0, 0.87)',
                                fontSize: 11
                            }}
                            title={expanded.length === 0 ? "Expand All" : "Collapse All"}
                            placement="right"
                            arrow
                            disableHoverListener={disableHover}
                        >
                            <Button onClick={handleExpandClick} sx={{minWidth:"35px"}}>
                            {expanded.length === 0 ? <FontAwesomeIcon icon={faAnglesDown} className='expandallicon' /> : <FontAwesomeIcon icon={faAnglesUp} className='expandallicon' />}
                            </Button>
                        </Tooltip>
                    </Box>
                    <TreeView
                        aria-label="file system navigator"
                        defaultCollapseIcon={<ExpandMoreIcon />}
                        defaultExpandIcon={<ChevronRightIcon />}
                        expanded={expanded}
                        multiSelect
                        selected={selected}
                        onNodeToggle={handleToggle}
                        onNodeSelect={handleSelect}
                        sx={{ flexGrow: 1, maxWidth: 400, overflowY: 'auto' }}
                    >
                        {filesForDisplay.length <= 0 && filterBookmark ?
                            <div style={{ textAlign: 'center' }}>No page has been book marked.</div>
                            :
                            displayFiles()
                        }
                    </TreeView>
                </Stack>

            </div>
    )
}
)

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
