import {TreeView, TreeItem} from '@mui/x-tree-view';
import React, { useEffect, useState, useImperativeHandle, useRef, createRef, LegacyRef } from 'react'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import Tooltip from '@mui/material/Tooltip';

const ModifiedDateTreeView = React.forwardRef(({
    selected,
    expanded,
    handleToggle,
    handleSelect,
    filesForDisplay,
    filterBookmark,
    consulteeFilterView,
    noFilterView,
    disableHover,
    displayFilePages
}: any, ref) => {

    return (
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
                filesForDisplay?.map((file: any, index: number) => { 
                    return (
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
                                {displayFilePages(file)}
                            </TreeItem>
                        </Tooltip>
                    )
                })
            }
        </TreeView>
    );
})

export default ModifiedDateTreeView;