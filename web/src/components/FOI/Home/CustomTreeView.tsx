// import {TreeView, TreeItem} from '@mui/x-tree-view';
import {TreeItem} from '@mui/x-tree-view';
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
import {PAGE_FLAGS} from '../../../constants/PageFlags';
import _ from "lodash";
import { useAppSelector } from '../../../hooks/hook';

const CustomTreeView = React.memo(React.forwardRef(({
    items,
    filesForDisplay,
    pageMappedDocs,
    selectTreeItem,
    setWarningModalOpen,
    pageFlagList,
    openFOIPPAModal,
    requestid,
    assignIcon,
    pageFlags,
    syncPageFlagsOnAction,
    requestInfo,
    pageFlagTypes
}: any, ref) => {
    const StyledTreeItem = styled(TreeItem)((props: any) => ({
        [`& .${treeItemClasses.label}`]: {
            fontSize: '14px'
        },
        [`& .${treeItemClasses.content}`]: {
            padding: props.children ? '0 8px' : '0 16px'
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
    const [activeNode, setActiveNode] = useState<any>();
    const [currentEditRecord, setCurrentEditRecord] = useState();
    
    const currentLayer = useAppSelector((state: any) => state.documents?.currentLayer);

    useImperativeHandle(ref, () => ({
        async scrollToPage(event: any, newExpandedItems: string[], pageId: string) {
            setExpandedItems([...new Set(expandedItems.concat(newExpandedItems))]);
            await new Promise(resolve => setTimeout(resolve, 400)); // wait for expand animation to finish
            apiRef.current?.focusItem(event, pageId)            
            setSelected([])
            setSelectedPages([])
        },
        scrollLeftPanelPosition(event: any)
        {           
            let _lastselected = localStorage.getItem("lastselected")
            if(_lastselected)
           {                 
                let _docid = JSON.parse(_lastselected)?.docid   
                let docidstring = ''
                if(_lastselected.indexOf('division')>-1)
                {
                        let _divisionid = JSON.parse(_lastselected)?.division
                        docidstring = `{"division": ${_divisionid}, "docid": ${_docid}}`
                }
                else
                {                            
                        docidstring = `{"docid": ${_docid}}`                        
                }
                                
                //TODO: Future research ABIN: apiRef.current?.focusItem(event, '{"docid": 192, "page": 1, "flagid": [1], "title": "Partial Disclosure"}')
                apiRef.current?.focusItem(event, docidstring)
                localStorage.removeItem("lastselected")
            }
        }
    }), [apiRef, expandedItems]);

  

    const getAllItemsWithChildrenItemIds = () => {
        const itemIds: any[] = [];
        const registerItemId = (item: any) => {
          if (item.children?.length) {
            itemIds.push(item.id);
            item.children.forEach(registerItemId);
          }
        };
        items.forEach(registerItemId);
        return itemIds;
    };
      
    const handleExpandClick = () => {
        setExpandedItems((oldExpanded: any) =>
            oldExpanded.length === 0 ? getAllItemsWithChildrenItemIds() : []
        );

    };

    const handleExpandedItemsChange = (event: any,itemIds: any) => {
        setExpandedItems(itemIds);
    };
       
    const handleSelect = (event: any,nodeIds: any) => {
        let selectedPages = [];
        let selectedOthers = [];
        let selectedNodes = [];
        for (let nodeId of nodeIds) {
            nodeId = nodeId.replace(/undefined/g, "null");
            let node = JSON.parse(nodeId);
            selectedNodes.push(node);
            if (node.page) {
                selectedPages.push(nodeId);
            } else {
                selectedOthers.push(nodeId);
            }
        }
        if (selectedNodes.length === 1 && Object.keys(selectedNodes[0]).includes("docid")) {
            const { docid, page } = selectedNodes[0];
            selectTreeItem(docid, page || 1);
        }
        /**if new select includes divisions and filenames:
         * 1. remove divisions and filenames from new select
         * 2. join old select and new select
         * else only keep new select */
        if (selectedOthers.length > 0) {
            selectedPages = [...new Set([...selected, ...selectedPages])];
        }
        if (selectedPages.length > PAGE_SELECT_LIMIT) {
            setWarningModalOpen(true);
        } else {
                      
            localStorage.setItem("lastselected",nodeIds[nodeIds.length-1])
            setSelected(selectedPages);
            const selectedPagesInfo = selectedPages.map(nodeId => {
                const { docid, page } = JSON.parse(nodeId);
                return { docid, page };
            });
            setSelectedPages(selectedPagesInfo);
        }
    };

    
    const addIcons = (itemid: any) => {
        if (itemid.page) {
            let sortedFlags = [...itemid.flagid].sort((a: any, b: any) => {
                const order = (id: number) => {
                    if (id === pageFlagTypes['Consult']) return 0; // Leftmost icon
                    if (id === pageFlagTypes['Phase']) return 1; // Middle icon
                    return 2; // All others (1-8) → Rightmost icon
                };
                return order(a) - order(b);
            });
            return (
                <>
                    {sortedFlags.map((id: any) => (
                        <FontAwesomeIcon
                            key={id}
                            className="leftPanelIcons"
                            icon={assignIcon(id) as IconProp}
                            size="1x"
                            title={PAGE_FLAGS[id as keyof typeof PAGE_FLAGS]}
                        />
                    ))}
                </>
            );
        //     let returnElem = (<>{itemid.flagid.map((id: any) => (
        //         <FontAwesomeIcon
        //         key={id}
        //         className='leftPanelIcons'
        //         icon={assignIcon(id) as IconProp}
        //         size='1x'
        //         title={PAGE_FLAGS[id as keyof typeof PAGE_FLAGS]}
        //         />
        // ))}</>)
        //     return returnElem
        }
    }

    const CustomTreeItem = React.forwardRef((props: any, ref: any) => {
        
        // props.itemId = props?.itemId?.replaceAll("undefined", "\"\"");
        // let itemid = JSON.parse(props?.itemId);
        //console.log("CustomTreeItem-",props)
        const derivedItemId = props.itemId?.replaceAll("undefined", "\"\"") ?? "";
        // Parse the derived itemId
        let itemid:any;
        try {
          itemid = JSON.parse(derivedItemId);
        } catch (error) {
          console.error("Invalid JSON in itemId:", error);
          itemid = derivedItemId; // Fallback to the derived itemId if JSON parsing fails
        }

        return (
        <StyledTreeItem
          ref={ref}
          {...props}
          title={itemid.title || props.label}

        //   slots={{endIcon: (_props) => {return CloseSquare(props)}}}
          slots={{endIcon: (_props: any) => {return addIcons(itemid)}}}
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
        if (currentLayer.name === "Response Package") return
        if (props.children && requestInfo.bcgovcode !== "MCF" && requestInfo.requesttype !== "personal") return
        e.preventDefault();
        let nodeId: string = e.target.parentElement.parentElement.id;
        if (nodeId === "") {
            nodeId = e.currentTarget.id;
        }
        nodeId = nodeId.substring(nodeId.indexOf('{'));
        nodeId = nodeId.replace(/undefined/g, "null");
        
        //mcf personal
        let nodeIdJson = JSON.parse(nodeId);
        if(nodeIdJson.docid) { //popup menu only if docid exist (level 2 tree and children)
            let currentFiles: any = filesForDisplay.filter((f: any) => {
                return f.documentid === nodeIdJson.docid;
            });
            setCurrentEditRecord(currentFiles[0]);

            setActiveNode(nodeIdJson);
        } else { //mcf personal level 1 tree item
            return;
        }

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
    }

  

    return (        
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
                pageMappedDocs={pageMappedDocs}
                pageFlags={pageFlags}
                syncPageFlagsOnAction={syncPageFlagsOnAction}
                filesForDisplay={filesForDisplay}
                activeNode={activeNode}
                requestInfo={requestInfo}
                currentEditRecord={currentEditRecord}
                setCurrentEditRecord={setCurrentEditRecord}
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
