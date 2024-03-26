import {TreeView, TreeItem} from '@mui/x-tree-view';
import React, { useEffect, useState, useImperativeHandle, useRef, createRef, LegacyRef } from 'react'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import Tooltip from '@mui/material/Tooltip';

const DivisionTreeView = React.forwardRef(({
    selected,
    expanded,
    handleToggle,
    handleSelect,
    filesForDisplay,
    divisions,
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
            {divisions?.map((division: any) => {
                return <TreeItem nodeId={`{"division": ${division.divisionid}}`} label={division.name} key={division.divisionid}>
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

                        <TreeItem nodeId={`{"division": ${division.divisionid}, "docid": ${file.documentid}}`} label={file.filename} key={file.documentid}>
                            {displayFilePages(file, division)}
                        </TreeItem>
                    </Tooltip>
                )}
            </TreeItem>
            })}
        </TreeView>
    );
})

export default DivisionTreeView;