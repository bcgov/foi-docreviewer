// import {TreeView, TreeItem} from '@mui/x-tree-view';
import {TreeItem, TreeItem2} from '@mui/x-tree-view';
import { treeItemClasses } from "@mui/x-tree-view/TreeItem";
import { RichTreeView } from '@mui/x-tree-view/RichTreeView';
import React, { useEffect, useState, useImperativeHandle, useRef, createRef, LegacyRef } from 'react'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import Tooltip from '@mui/material/Tooltip';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
    faCircleHalfStroke, faCircle, faCircleQuestion, faSpinner,
    faCircleStop, faCircleXmark, faBookmark, faAngleDown, faCircleExclamation,
    faAnglesDown, faAnglesUp
} from '@fortawesome/free-solid-svg-icons';
import { faCircle as filledCircle } from '@fortawesome/free-regular-svg-icons';
import { useTreeViewApiRef } from '@mui/x-tree-view/hooks/useTreeViewApiRef';
import { SyntheticEvent } from 'react-toastify/dist/utils';
import SvgIcon, { SvgIconProps } from '@mui/material/SvgIcon';
import { IconProp } from '@fortawesome/fontawesome-svg-core';
import ContextMenu from "./ContextMenu";
import { PAGE_SELECT_LIMIT } from '../../../constants/constants'
import { styled } from "@mui/material/styles";
import PAGE_FLAGS from '../../../constants/PageFlags';
import _ from "lodash";

const CustomTreeView = React.memo(React.forwardRef(({
    items,
    filesForDisplay,
    pageMappedDocs,
    selectTreeItem,
    setWarningModalOpen,
    updatePageFlags,
    pageFlagList,
    openFOIPPAModal,
    requestid

}: any, ref) => {
    const StyledTreeItem = styled(TreeItem)((props: any) => ({
    // const StyledTreeItem = styled(TreeItem)(() => ({
        [`& .${treeItemClasses.label}`]: {
            fontSize: '14px'
        },
        [`& .${treeItemClasses.content}`]: {
            padding: props.children ? '0 8px' : '0 16px'
            // padding: '0 16px'
        }
    }));

    const apiRef = useTreeViewApiRef();

    const [expandedItems, setExpandedItems] = useState<string[]>([]);
    const [selectedPages, setSelectedPages] = useState<any>([]);
    const [selected, setSelected] = useState<any>([]);
    const [consultInfo, setConsultInfo] = useState({});
    const [openContextPopup, setOpenContextPopup] = useState(false);
    const [disableHover, setDisableHover] = useState(false);
    const [anchorPosition, setAnchorPosition] = useState<any>(undefined);


    useImperativeHandle(ref, () => ({
        async scrollToPage(event: any, newExpandedItems: string[], pageId: string) {
            setExpandedItems([...new Set(expandedItems.concat(newExpandedItems))]);
            await new Promise(resolve => setTimeout(resolve, 400)); // wait for expand animation to finish
            apiRef.current?.focusItem(event, pageId)
            setSelected([])
            setSelectedPages([])
        },
    }), [apiRef, expandedItems]);

    const getAllItemsWithChildrenItemIds = () => {
      const itemIds: any = [];
      const registerItemId = (item: any) => {
        if (item.children?.length) {
          itemIds.push(item.id);
        //   item.children.forEach(registerItemId);
        }
      };

      items.forEach(registerItemId);

      return itemIds;
    };

    const handleExpandClick = () => {
        setExpandedItems((oldExpanded: any) =>
            oldExpanded.length === 0 ? getAllItemsWithChildrenItemIds() : []
        );
        // setExpanded((oldExpanded:any) => {
        //         let result: any = [];
        //         if (oldExpanded.length === 0 ) {
        //             if (organizeBy == "lastmodified" ) {
        //                 result = expandall;
        //             }
        //             else {
        //                 result = expandallorganizebydivision;
        //             }
        //         }
        //         return result;
        //     }
        // );
    };

    const handleExpandedItemsChange = (event: any, itemIds: any) => {
        setExpandedItems(itemIds);
    };

    function CloseSquare(props: SvgIconProps) {
        return (
            // <>
            <FontAwesomeIcon
            // key={icon.flagid}
            className='leftPanelIcons'
            icon={faCircleHalfStroke as IconProp}
            size='1x'
            // title={PAGE_FLAGS[icon.flagid as keyof typeof PAGE_FLAGS]}
            />
            /* <FontAwesomeIcon
            // key={icon.flagid}
            className='leftPanelIcons'
            icon={faCircleHalfStroke as IconProp}
            size='1x'
            // title={PAGE_FLAGS[icon.flagid as keyof typeof PAGE_FLAGS]}
            />
            </> */
        );
      }

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
            selectTreeItem(selectedNodes[0].docid, selectedNodes[0].page || 1);
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

    const addIcons = (itemid: any) => {
        // console.log("iconfn")
        if (itemid.page) { //&& pageFlags) {
            let returnElem = (<>{itemid.flagid.map((id: any) => (
                <FontAwesomeIcon
                key={id}
                className='leftPanelIcons'
                icon={assignIcon(id) as IconProp}
                size='1x'
                title={PAGE_FLAGS[id as keyof typeof PAGE_FLAGS]}
                />
        ))}</>)
            return returnElem
        }
    }

    const CustomTreeItem = React.forwardRef((props: any, ref: any) => {
        let itemid = JSON.parse(props.itemId);
        return (
        <StyledTreeItem
          ref={ref}
          {...props}
          title={itemid.title}

        //   slots={{endIcon: (_props) => {return CloseSquare(props)}}}
          slots={{endIcon: (_props) => {return addIcons(itemid)}}}
        //   icon={faCircleHalfStroke}
          onContextMenu={(e) => openContextMenu(e, props)}
        //   slotProps={{
        //     label: {
        //       id: `${props.itemId}-label`,
        //     },
        //   }}
        />
      )
    });

    const openContextMenu = (e: any, props: any) => {
        if (props.children) return
        // console.log("contextmenu")
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
            let selectedFile: any = filesForDisplay.find((f: any) => f.documentid === selectedNodes[0].docid);
            setConsultInfo(selectedFile?.consult?.find((flag: any) => flag.page === selectedNodes[0].page) || {
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
        // console.log("contextfncomplete")
    }

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

    return (
        // <TreeView
        //     aria-label="file system navigator"
        //     defaultCollapseIcon={<ExpandMoreIcon />}
        //     defaultExpandIcon={<ChevronRightIcon />}
        //     expanded={expanded}
        //     multiSelect
        //     selected={selected}
        //     onNodeToggle={handleToggle}
        //     onNodeSelect={handleSelect}
        //     sx={{ flexGrow: 1, maxWidth: 400, overflowY: 'auto' }}
        // >
        //     {filesForDisplay.length <= 0 && filterBookmark ?
        //         <div style={{ textAlign: 'center' }}>No page has been book marked.</div>
        //         :
        //         filesForDisplay?.map((file: any, index: number) => {
        //             return (
        //                 // <Tooltip
        //                 //     sx={{
        //                 //         backgroundColor: 'white',
        //                 //         color: 'rgba(0, 0, 0, 0.87)',
        //                 //         // boxShadow: theme.shadows[1],
        //                 //         fontSize: 11
        //                 //     }}
        //                 //     title={<>
        //                 //         Last Modified Date: {new Date(file.attributes.lastmodified).toLocaleString('en-US', { timeZone: 'America/Vancouver' })}
        //                 //         {file.attachmentof && <><br></br> Attachment of: {file.attachmentof}</>}
        //                 //     </>}
        //                 //     placement="bottom-end"
        //                 //     arrow
        //                 //     key={file?.documentid}
        //                 //     disableHoverListener={disableHover}
        //                 // >
        //                     <TreeItem nodeId={`{"docid": ${file.documentid}}`} label={file.filename} key={file?.documentid}>
        //                         {displayFilePages(file)}
        //                     </TreeItem>
        //                 // </Tooltip>
        //             )
        //         })
        //     }
        // </TreeView>
        <>
        {openContextPopup === true &&
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
        <Box sx={{ mb: 1 }}>
                        <Tooltip
                            sx={{
                                backgroundColor: 'white',
                                color: 'rgba(0, 0, 0, 0.87)',
                                fontSize: 11
                            }}
                            title={expandedItems.length === 0 ? "Expand All" : "Collapse All"}
                            placement="right"
                            arrow
                            disableHoverListener={disableHover}
                        >
                            <Button onClick={handleExpandClick} sx={{minWidth:"35px"}}>
                            {expandedItems.length === 0 ? <FontAwesomeIcon icon={faAnglesDown} className='expandallicon' /> : <FontAwesomeIcon icon={faAnglesUp} className='expandallicon' />}
                            </Button>
                        </Tooltip>
                    </Box>
        {/* <Button onClick={handleExpandClick}>
          {expandedItems.length === 0 ? 'Expand all' : 'Collapse all'}
        </Button> */}
        <RichTreeView
          items={items}
          selectedItems={selected}
          expandedItems={expandedItems}
          onSelectedItemsChange={handleSelect}
          onExpandedItemsChange={handleExpandedItemsChange}
          multiSelect
          apiRef={apiRef}
          slots={{item: CustomTreeItem}}
        //   slotProps={{item: {ContentProps: {id: 'test'}}}}
          sx={{ flexGrow: 1, maxWidth: 400, overflowY: 'auto' }}
        /></>
    );
}))

export default CustomTreeView;