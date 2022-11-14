import React, { useEffect, useState } from 'react'
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

const DocumentSelector = ({
    documents,
    currentPageInfo,
    setCurrentPageInfo
  }: any) => {
    const [files, setFiles] = useState(documents)
    // console.log(documents);

    // const files = [
    //     {filename: "test1.pdf", lastmodified: "2022-07-09T20:18:55.022Z", divisions: [
    //         {"divisionid": 2, "name": "Deputy Minister's Office"},
    //         {"divisionid": 1, "name": "Minister's Office"},
    //         {"divisionid": 6, "name": "Governance & Analytics"}
    //     ], pagecount: 9},
    //     {filename: "test2.pdf", lastmodified: "2022-10-09T20:18:55.022Z", divisions: [
    //         {"divisionid": 2, "name": "Deputy Minister's Office"}
    //     ], pagecount: 9},
    //     {filename: "test3.pdf", lastmodified: "2022-08-09T20:18:55.022Z", divisions: [
    //         {"divisionid": 2, "name": "Deputy Minister's Office"}
    //     ], pagecount: 9},
    //     {filename: "test4.pdf", lastmodified: "2022-06-09T20:18:55.022Z", divisions: [
    //         {"divisionid": 2, "name": "Deputy Minister's Office"}
    //     ], pagecount: 9},
    //     {filename: "test5.pdf", lastmodified: "2022-10-03T20:18:55.022Z", divisions: [
    //         {"divisionid": 2, "name": "Deputy Minister's Office"}
    //     ], pagecount: 9},
    // ]

    let arr: any[] = [];
    const divisions = [...new Map(files.reduce((acc: any[], file: any) => [...acc, ...new Map(file.divisions.map((division: any) => [division.divisionid, division]))], arr)).values()]
    // console.log(divisions)

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
            pages.push(<TreeItem nodeId={`file${index}page${p}`} label={`Page ${p}`}/>)
        }
        return pages;
    }

    // const selectTreeItem = (event: React.SyntheticEvent, nodeIds: string) => {
    //     console.log(nodeIds);
    //     if (nodeIds.includes("page")) {
    //         let page = parseInt(nodeIds.split('page')[1])
    //         setCurrentPage(page)
    //     } else if (nodeIds.includes("file")) {
    //         let doc = parseInt(nodeIds.split('file')[1])
    //         console.log("hi");
    //     }
    // }

    const selectTreeItem = (file: any, page: number) => {
        console.log("onclick:");
        console.log(file);
        console.log(page);
        setCurrentPageInfo({'file': file, 'page': page});
        localStorage.setItem("currentDocumentInfo", JSON.stringify({'file': file, 'page': page}));
    };

    const [organizeBy, setOrganizeBy] = useState("lastmodified")
    return (
        <Stack sx={{maxHeight: "calc(100vh - 117px)"}}>
            <Paper
                component={Grid}
                sx={{
                  border: "1px solid #38598A",
                  color: "#38598A",
                  maxWidth:"100%",
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
                    onChange={(e)=>{onFilterChange(e.target.value.trim())}}
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
            <TreeView
                aria-label="file system navigator"
                defaultCollapseIcon={<ExpandMoreIcon />}
                defaultExpandIcon={<ChevronRightIcon />}
                sx={{flexGrow: 1, maxWidth: 400, overflowY: 'auto' }}
                // onNodeSelect={selectTreeItem}
            >
                {organizeBy === "division" ?
                // <TreeItem nodeId={`1`} label="Test Division 1">
                //         {getFiles()}
                // </TreeItem>
                divisions.map((division: any, index) =>
                    <TreeItem nodeId={`division${index}`} label={division.name}>
                        {/* {getDivisionFiles(division)} */}
                        {filesForDisplay.filter((file: any) => file.divisions.map((d: any) => d.divisionid).includes(division.divisionid)).map((file: any, i: number) =>
                            <Tooltip
                                sx={{backgroundColor: 'white',
                                color: 'rgba(0, 0, 0, 0.87)',
                                // boxShadow: theme.shadows[1],
                                fontSize: 11}}
                                title={<>
                                    Last Modified Date: {new Date(file.lastmodified).toLocaleString('en-US', { timeZone: 'America/Vancouver' })}
                                </>}
                                placement="bottom-end"
                                arrow
                            >
                                {/* <TreeItem nodeId={`division${index}file${i}`} label={file.filename}/> */}
                                <TreeItem nodeId={`division${index}file${i}`} label={file.filename} onClick={() => selectTreeItem(file, 1)} >
                                    {[...Array(file.pagecount)].map((_x, p) =>
                                        <TreeItem nodeId={`file${index}page${p + 1}`} label={`Page ${p + 1}`} onClick={() => selectTreeItem(file, p + 1)} />
                                    )
                                    //getFilePages(file.pagecount, index)
                                    }
                                </TreeItem>
                            </Tooltip>
                        )}
                    </TreeItem>
                )
                :
                filesForDisplay.sort((a: any, b: any) => Date.parse(a.lastmodified) - Date.parse(b.lastmodified)).map((file: any, index: number) =>
                    <Tooltip
                        sx={{backgroundColor: 'white',
                        color: 'rgba(0, 0, 0, 0.87)',
                        // boxShadow: theme.shadows[1],
                        fontSize: 11}}
                        title={<>
                            Last Modified Date: {new Date(file.lastmodified).toLocaleString('en-US', { timeZone: 'America/Vancouver' })}
                        </>}
                        placement="bottom-end"
                        arrow
                    >
                        <TreeItem nodeId={`${index}`} label={file.filename} onClick={() => selectTreeItem(file, 1)} >
                            {[...Array(file.pagecount)].map((_x, p) =>
                                <TreeItem nodeId={`file${index}page${p + 1}`} label={`Page ${p + 1}`} onClick={() => selectTreeItem(file, p + 1)} />
                            )
                            //getFilePages(file.pagecount, index)
                            }
                        </TreeItem>
                    </Tooltip>
                )}
            </TreeView>
        </Stack>
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