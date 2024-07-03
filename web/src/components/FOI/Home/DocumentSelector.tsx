import React, {
  useEffect,
  useState, useMemo,
  useImperativeHandle,
  useRef,
  createRef,
} from "react";
import Chip from "@mui/material/Chip";
import SearchIcon from "@mui/icons-material/Search";
import InputAdornment from "@mui/material/InputAdornment";
import InputBase from "@mui/material/InputBase";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Grid from "@mui/material/Grid";
import Stack from "@mui/material/Stack";
import { fetchPageFlagsMasterData } from "../../../apiManager/services/docReviewerService";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faAngleDown,
  faCircleExclamation,
} from "@fortawesome/free-solid-svg-icons";
import { IconProp } from "@fortawesome/fontawesome-svg-core";
import "./DocumentSelector.scss";
import { PAGE_FLAGS, pageFlagIcons } from "../../../constants/PageFlags";
import LayerDropdown from "./LayerDropdown";
import { useAppSelector } from "../../../hooks/hook";
import { getStitchedPageNoFromOriginal } from "./utils";
import { pageFlagTypes } from "../../../constants/enum";
import Popover from "@mui/material/Popover";
import CustomTreeView from "./CustomTreeView";


const DocumentSelector = React.memo(
  React.forwardRef(
    (
      {
        openFOIPPAModal,
        requestid,
        documents,
        totalPageCount,
        setCurrentPageInfo,
        setIndividualDoc,
        pageMappedDocs,
        setWarningModalOpen,
        divisions,
        pageFlags,
        syncPageFlagsOnAction,
      }: any,
      ref
    ) => {
      const requestInfo = useAppSelector(
        (state: any) => state.documents?.requestinfo
      );
      const currentLayer = useAppSelector(
        (state: any) => state.documents?.currentLayer
      );
      const files = useMemo(() => documents, [documents]);
      const [organizeBy, setOrganizeBy] = useState("lastmodified");
      const [pageFlagList, setPageFlagList] = useState([]);
      const [filesForDisplay, setFilesForDisplay] = useState([]);
      const [consultMinistries, setConsultMinistries] = useState<any>([]);
      const [filterFlags, setFilterFlags] = useState<any>([]);
      const [filteredFiles, setFilteredFiles] = useState(files);
      const [filterBookmark, setFilterBookmark] = useState(false);
      const [openConsulteeModal, setOpenConsulteeModal] = useState(false);
      const [assignedConsulteeList, setAssignedConsulteeList] = useState<any>(
        []
      );
      const [consulteeFilter, setConsulteeFilter] = useState<any>([]);
      const [selectAllConsultee, setSelectAllConsultee] = useState(false);
      const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
      const pageRefs = useRef([]);
      const treeRef: any = useRef();

      useImperativeHandle(
        ref,
        () => ({
          async scrollToPage(event: any, pageNumber: number) {
            let lookup = pageMappedDocs.stitchedPageLookup[pageNumber];
            let file: any = filesForDisplay.find(
              (f: any) => f.documentid === lookup.docid
            );
            let pageId, newExpandedItems;
            if (organizeBy === "lastmodified") {
              pageId = `{"docid": ${file.documentid}, "page": ${
                lookup.page
              }, "flagid": [${getPageFlagIds(
                file.pageFlag,
                lookup.page
              )}], "title": "${getFlagName(file, lookup.page)}"}`;
              newExpandedItems = ['{"docid": ' + lookup.docid + "}"];
            } else {
              pageId = `{"division": ${
                file.divisions[0].divisionid
              }, "docid": ${file.documentid}, "page": ${
                lookup.page
              }, "flagid": [${getPageFlagIds(
                file.pageFlag,
                lookup.page
              )}], "title": "${getFlagName(file, lookup.page)}"}`;
              newExpandedItems = [
                '{"division": ' + file.divisions[0].divisionid + "}",
                '{"division": ' +
                  file.divisions[0].divisionid +
                  ', "docid": ' +
                  lookup.docid +
                  "}",
              ];
            }
            
            treeRef?.current?.scrollToPage(event, newExpandedItems, pageId);
            
          },
          scrollLeftPanelPosition(event: any)
          {                            
              treeRef?.current?.scrollLeftPanelPosition(event)
          }
        }),
        [treeRef, pageMappedDocs, filesForDisplay, organizeBy]
      );

      useEffect(() => {
        let refLength = documents.reduce(
          (acc: any, file: any) => acc + file.originalpagecount,
          0
        );
        pageRefs.current = Array(refLength)
          .fill(0)
          .map((_, i) => pageRefs.current[i] || createRef());
      }, [documents]);

      useEffect(() => {
        fetchPageFlagsMasterData(
          requestid,
          currentLayer.name.toLowerCase(),
          (data: any) => setPageData(data),
          (error: any) => console.log(error)
        );
      }, [currentLayer]);

      useEffect(() => {
        if (
          requestInfo.requesttype == "personal" &&
          ["MSD", "MCF"].includes(requestInfo.bcgovcode)
        ) {
          setOrganizeBy("division");
        }
      }, [requestInfo]);

      const ministryOrgCode = (pageNo: number, consults: Array<any>) => {
        let consultVal = consults?.find(
          (consult: any) => consult.page == pageNo
        );
        if (
          consultVal?.programareaid?.length === 1 &&
          consultVal?.other?.length === 0
        ) {
          let ministry: any = consultMinistries?.find(
            (ministry: any) =>
              ministry.programareaid === consultVal.programareaid[0]
          );
          return ministry?.iaocode;
        } else if (
          consultVal?.other?.length === 1 &&
          consultVal?.programareaid?.length === 0
        ) {
          return consultVal?.other[0];
        } else {
          return consultVal?.programareaid?.length + consultVal?.other?.length;
        }
      };

      const setPageData = (data: any) => {
        setConsultMinistries(
          data.find((flag: any) => flag.name === "Consult").programareas
        );
        setPageFlagList(data);
      };

      const updateCompletionCounter = () => {
        let totalPagesWithFlags = 0;
        pageFlags?.forEach((element: any) => {
          /**Page Flags to be avoided while
           * calculating % on left panel-
           * 'Consult'(flagid:4),'In Progress'(flagid:7),'Page Left Off'(flagid:8) */
          let documentSpecificCount = element?.pageflag?.filter(
            (obj: any) =>
              ![
                pageFlagTypes["Consult"],
                pageFlagTypes["In Progress"],
                pageFlagTypes["Page Left Off"],
              ].includes(obj.flagid)
          )?.length;
          totalPagesWithFlags += documentSpecificCount;
        });
        /** We need to Math.floor the result because the result can be a float value and we want to take the lower value 
         * as it may show 100% even if the result is 99.9% */
        return totalPageCount > 0 && totalPagesWithFlags >= 0
          ? Math.floor((totalPagesWithFlags / totalPageCount) * 100)
          : 0;
        // setCompletionCounter(totalPageCount > 0 && totalPagesWithFlags >= 0
        //   ? Math.floor((totalPagesWithFlags / totalPageCount) * 100)
        //   : 0);
      };

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
            if (obj.flagid === pageFlagTypes["Consult"]) {
              const consultFilter = new Set(consulteeFilter);
              const selectedMinistries = new Set([
                ...obj.programareaid,
                ...obj.other,
              ]);
              const consultOverlap = intersection(
                consultFilter,
                selectedMinistries
              );
              return (
                filterFlags.includes(obj.flagid) && consultOverlap.size > 0
              );
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
        return filterFlags.length > 0
          ? totalFilteredPages + unflagged
          : totalPageCount;
        // setTotalDisplayedPages(filterFlags.length > 0
        //       ? totalFilteredPages + unflagged
        //       : totalPageCount);
      };

      const setAdditionalData = () => {
        let filesForDisplayCopy: any =
          filesForDisplay.length === 0 ? [...documents] : [...filesForDisplay];
        filesForDisplayCopy.forEach((file1: any) => {
          pageFlags?.forEach((pageFlag1: any) => {
            if (file1.documentid == pageFlag1?.documentid) {
              file1.pageFlag = pageFlag1?.pageflag;
              let consultDetails: any = pageFlag1?.pageflag?.filter(
                (flag1: any) => flag1.programareaid || flag1.other
              );
              if (consultDetails?.length > 0) {
                consultDetails.forEach((consult: any) => {
                  let ministryCode: any = consultMinistries?.find(
                    (ministry: any) =>
                      ministry.programareaid === consult.programareaid
                  );
                  if (ministryCode) consult["iaocode"] = ministryCode.iaocode;
                });
                file1.consult = consultDetails;
              } else {
                delete file1.consult;
              }
            }
          });
        });
        setFilesForDisplay(filesForDisplayCopy);
      };

      useEffect(() => {
        if (pageFlags) {
          setAdditionalData();
          //updateCompletionCounter();
          //updatePageCount();
        }
      }, [consultMinistries, pageFlags]);

      const assignIcon = (pageFlag: any) => {
        return pageFlagIcons[pageFlag];
      };

      const getPageFlagIds = (pageFlags: any, page: number) => {
        if (!pageFlags || pageFlags?.length == 0) return [];
        const pageFlagObjs = pageFlags
          .filter((flag: any) => flag.page === page)
          .sort((a: any, b: any) => {
            return (
              Number(b.flagid === pageFlagTypes["Consult"] || false) -
              Number(a.flagid === pageFlagTypes["Consult"] || false)
            );
          });
        /** Extract flagids from sorted pageFlagObjs */ 
        const flagids = pageFlagObjs
          .map((pageFlag: any) => pageFlag.flagid)
          .filter((flagid: any) => flagid !== undefined);
        return flagids;
      };


      const onFilterChange = (filterValue: string) => {
        setFilesForDisplay(
          files.filter((file: any) => file.filename.includes(filterValue))
        );
        setFilteredFiles(
          files.filter((file: any) => file.filename.includes(filterValue))
        );
      };

    const selectTreeItem = (docid: any, page: number) => {
        const file:any = filesForDisplay.find((f: any) => f.documentid === docid);
        if (!file || !file.pages.includes(page)) return;
        const pageNo: number = getStitchedPageNoFromOriginal(docid, page, pageMappedDocs);
        if (pageNo !== 0) {
            setIndividualDoc({ file, page: pageNo });
            setCurrentPageInfo({ file, page });
        }
    };

    const isConsult = (consults: Array<any>, pageNo: number) => {
        if (consults?.find((consult: any) => consult.page == pageNo))
          return true;
        return false;
      };

      const isUnflagged = (pageflags: Array<any>, pageNo: number) => {
        const isFound = pageflags?.some((pageflag) => pageflag.page == pageNo);
        return !isFound;
      };

      const filterFiles = (
        filters: Array<number>,
        consulteeFilters: Array<number>
      ) => {
        if (filters?.length > 0) {
          if (consulteeFilters.length > 0) {
            setFilesForDisplay(
              filteredFiles.filter((file: any) =>
                file.pageFlag?.find(
                  (obj: any) =>
                    filters.includes(obj.flagid) &&
                    ((obj.flagid != 4 && filters.includes(obj.flagid)) ||
                      obj.programareaid?.some((val: any) =>
                        consulteeFilters.includes(val)
                      ) ||
                      obj.other?.some((val: any) =>
                        consulteeFilters.includes(val)
                      ))
                )
              )
            );
          } else
            setFilesForDisplay(
              filteredFiles.filter(
                (file: any) =>
                  (filters.includes(0) &&
                    (typeof file.pageFlag === "undefined" ||
                      file.pageFlag?.length == 0 ||
                      file.pagecount !=
                        getUpdatedPageFlagCount(file.pageFlag))) ||
                  file.pageFlag?.find(
                    (obj: any) =>
                      obj.flagid != 4 && filters.includes(obj.flagid)
                  )
              )
            );
        } else setFilesForDisplay(filteredFiles);
      };

      /** pageflags.length won't give the exact value if multiple pages flags (consult and any other page flag) added to a page 
       * Below method will return the count(distinct pages with pageflag)*/ 
      const getUpdatedPageFlagCount = (pageFlags: any) => {
        const distinctPages = new Set();
        for (const item of pageFlags) {
          distinctPages.add(item.page);
        }
        return distinctPages.size;
      };

      const applyFilter = (
        flagId: number,
        consultee: any,
        event: any,
        allSelectedconsulteeList: any[]
      ) => {
        const flagFilterCopy = [...filterFlags];
        let consulteeIds = [...consulteeFilter];
        if (flagFilterCopy.includes(flagId)) {
          if (flagId == pageFlagTypes['Consult']) {
            if (event.target.checked) {
              if (allSelectedconsulteeList.length > 0) {
                consulteeIds = allSelectedconsulteeList;
              } else consulteeIds.push(consultee);
            } else if (allSelectedconsulteeList.length > 0) {
              consulteeIds = [];
            } else consulteeIds?.splice(consulteeIds.indexOf(consultee), 1);
            if (consulteeIds.length <= 0)
              flagFilterCopy.splice(flagFilterCopy.indexOf(flagId), 1);
          } else {
            flagFilterCopy.splice(flagFilterCopy.indexOf(flagId), 1);
          }
          event.currentTarget.classList.remove("selected");
          if (flagId === pageFlagTypes["Page Left Off"])
            setFilterBookmark(false);
          else if (
            flagFilterCopy.length == 1 &&
            flagFilterCopy.includes(pageFlagTypes["Page Left Off"])
          )
            setFilterBookmark(true);
        } else {
          if (flagId == pageFlagTypes['Consult']) {
            if (event.target.checked) {
              if (allSelectedconsulteeList.length > 0)
                consulteeIds = allSelectedconsulteeList;
              else consulteeIds.push(consultee);
            } else if (allSelectedconsulteeList.length > 0) consulteeIds = [];
            else consulteeIds?.splice(consulteeIds.indexOf(consultee), 1);
          }
          flagFilterCopy.push(flagId);
          event.currentTarget.classList.add("selected");
          if (
            flagId === pageFlagTypes["Page Left Off"] ||
            (flagFilterCopy.length == 1 &&
              flagFilterCopy.includes(pageFlagTypes["Page Left Off"]))
          )
            setFilterBookmark(true);
          else setFilterBookmark(false);
        }
        setFilterFlags(flagFilterCopy);
        setConsulteeFilter(consulteeIds);
        filterFiles(flagFilterCopy, consulteeIds);
      };

      const getFlagName = (file: any, pageNo: number) => {
        let flag: any = file?.pageFlag?.find((flg: any) => flg.page === pageNo);
        if (flag) {
          let consultFlag: any = file?.consult?.find(
            (flg: any) =>
              flg.page === pageNo && flg.flagid === pageFlagTypes["Consult"]
          );
          if (!!file.consult && file.consult.length > 0 && !!consultFlag) {
            let ministries = consultFlag?.programareaid.map(
              (m: any) =>
                consultMinistries?.find(
                  (ministry: any) => ministry.programareaid === m
                )?.iaocode
            );
            if (ministries) {
              ministries.push(...consultFlag.other);
              return `Consult - [` + ministries.join(`]\\nConsult - [`) + "]";
            }
          }
          return PAGE_FLAGS[flag.flagid as keyof typeof PAGE_FLAGS];
        }
        return "";
      };

      let codeById: Record<number, string> = {};
      const mapConsultMinistries = () => {
        if (consultMinistries && consultMinistries.length > 0) {
          codeById = {};
          consultMinistries.forEach((item: any) => {
            codeById[item.programareaid] = item.iaocode;
          });
        }
      };

      const openConsulteeList = (e: any) => {
        mapConsultMinistries();
        const consultFlagged = files.filter((file: any) =>
          file.pageFlag?.some((obj: any) => obj.flagid === pageFlagTypes['Consult'])
        );
        if (consultFlagged.length > 0 && Object.keys(codeById).length > 0) {
          const namedConsultValues: any[] = Array.from(
            new Set(
              consultFlagged
                .flatMap((item: any) => item.consult)
                .flatMap((consultItem: any) => [
                  ...consultItem.programareaid,
                  ...consultItem.other,
                ])
                .map((value: any) =>
                  JSON.stringify({ id: value, code: codeById[value] || value })
                )
            )
          ).map((strObject: any) => JSON.parse(strObject));
          setOpenConsulteeModal(true);
          setAssignedConsulteeList(namedConsultValues);
          setAnchorEl(e.currentTarget);
        }
      };

      const showConsultee = (assignedConsulteeList: any[]) =>
        assignedConsulteeList?.map((consultee: any, index: number) => {
          return (
            <div key={consultee.id} className="consulteeItem">
              <span style={{ marginRight: "10px" }}>
                <input
                  type="checkbox"
                  id={`checkbox-${index}`}
                  checked={consulteeFilter.includes(
                    consultee.id || consultee.code
                  )}
                  onChange={(e) => {
                    applyFilter(4, consultee.id || consultee.code, e, []);
                  }}
                />
              </span>
              <label htmlFor={`checkbox-${index}`}>{consultee.code}</label>
            </div>
          );
        });

      const selectAllConsultees = (
        assignedConsulteeList: any[],
        event: any
      ) => {
        if (event.target.checked) setSelectAllConsultee(true);
        else setSelectAllConsultee(false);
        let consulteeIds = assignedConsulteeList.map(
          (obj: any) => obj.id || obj.code
        );
        applyFilter(4, null, event, consulteeIds);
      };

      const consultFilterStyle = {
        color: consulteeFilter.length === 0 ? "#808080" : "#003366", // Change colors as needed
      };

      const handleClose = () => {
        setAnchorEl(null);
        setOpenConsulteeModal(false);
      };  

      const getPageLabel = (file: any, p: number) => {
        if (isConsult(file.consult, p)) {
          return `Page ${getStitchedPageNoFromOriginal(
            file.documentid,
            p,
            pageMappedDocs
          )} (${ministryOrgCode(p, file.consult)})`;
        } else {
          return `Page ${getStitchedPageNoFromOriginal(
            file.documentid,
            p,
            pageMappedDocs
          )}`;
        }
      };

      const getFilePages = (file: any, division?: any) => {
        if (filterFlags.length > 0) {
          let filteredpages = file.pages.filter((p: any) => {
            if (filterFlags?.includes(0) && isUnflagged(file.pageFlag, p)) {
              return true;
            } else {
              return file.pageFlag?.find((obj: any) => {
                if (obj.page === p) {
                  if (obj.flagid != 4 && filterFlags?.includes(obj.flagid)) {
                    return true;
                  } else if (consulteeFilter.length > 0) {
                    if (
                        obj.programareaid?.some((val: any) =>
                        consulteeFilter.includes(val)
                        ) ||
                        obj.other?.some((val: any) => consulteeFilter.includes(val))
                    ) {
                        return true;
                    }
                  }                    
                } else {
                  return false;
                }
              });
            }
          });
          if (organizeBy === "lastmodified") {
            return filteredpages.map((p: any) => {
              return {
                id: `{"docid": ${
                  file.documentid
                }, "page": ${p}, "flagid": [${getPageFlagIds(
                  file.pageFlag,
                  p
                )}], "title": "${getFlagName(file, p)}"}`,
                label: getPageLabel(file, p),
              };
            });
          } else {
            return filteredpages.map((p: any) => {
              return {
                id: `{"division": ${division?.divisionid}, "docid": ${
                  file.documentid
                }, "page": ${p}, "flagid": [${getPageFlagIds(
                  file.pageFlag,
                  p
                )}], "title": "${getFlagName(file, p)}"}`,
                label: getPageLabel(file, p),
              };
            });
          }
          // if (consulteeFilter.length > 0) {
          //     if (file.pageFlag?.find((obj: any) => obj.page === p + 1 &&
          //         ((obj.flagid != 4 && filterFlags?.includes(obj.flagid))||
          //         (obj.programareaid?.some((val: any) => consulteeFilter.includes(val))) ||
          //         (obj.other?.some((val: any) => consulteeFilter.includes(val)))))) {
          //     }
          // } else {
          //     if (file.pageFlag?.find((obj: any) => obj.page === p + 1 && obj.flagid != 4 && filterFlags?.includes(obj.flagid))) {
          //     } else if (filterFlags?.includes(0) && isUnflagged(file.pageFlag, p+1)) {
          //     }
          // }
        } else {
          if (organizeBy === "lastmodified") {
            return file.pages.map((p: any) => {
              return {
                id: `{"docid": ${
                  file.documentid
                }, "page": ${p}, "flagid": [${getPageFlagIds(
                  file.pageFlag,
                  p
                )}], "title": "${getFlagName(file, p)}"}`,
                label: getPageLabel(file, p),
              };
            });
          } else {
            return file.pages.map((p: any) => {
              return {
                id: `{"division": ${division?.divisionid}, "docid": ${
                  file.documentid
                }, "page": ${p}, "flagid": [${getPageFlagIds(
                  file.pageFlag,
                  p
                )}], "title": "${getFlagName(file, p)}"}`,
                label: getPageLabel(file, p),
              };
            });
          }
        }
      };

      const getTreeItems = () => {
        if (pageFlags) {
          if (organizeBy === "lastmodified") {
            return filesForDisplay.map((file: any, index: number) => {
              return {
                id: `{"docid": ${file.documentid}}`,
                label: file.filename,
                children: getFilePages(file), 
              };
            });
          } else {
            if (filesForDisplay.length > 0) {
              return divisions.map((division: any) => {
                return {
                  id:`{"division": ${division.divisionid}}`,
                  label: division.name,
                  children: filesForDisplay
                    .filter((file: any) =>
                      file.divisions
                        .map((d: any) => d.divisionid)
                        .includes(division.divisionid)
                    )
                    .map((file: any, index: number) => {
                      return {
                        id: `{"division": ${division.divisionid}, "docid": ${file.documentid}}`,
                        label: file.filename,
                        children: getFilePages(file, division),
                      };
                    }),
                };
              });
            } else {
              return [];
            }
          }
        } else {
          return [];
        }
      };

      return (
        <div className="leftPanel">
          <Stack sx={{ maxHeight: "calc(100vh - 117px)" }}>
            <Paper
              component={Grid}
              sx={{
                border: "1px solid #38598A",
                color: "#38598A",
                maxWidth: "100%",
                backgroundColor: "rgba(56,89,138,0.1)",
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
                  onChange={(e) => {
                    onFilterChange(e.target.value.trim());
                  }}
                  inputProps={{ "aria-labelledby": "document-filter" }}
                  sx={{
                    color: "#38598A",
                  }}
                  startAdornment={
                    <InputAdornment position="start">
                      <IconButton
                        aria-hidden="true"
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
            <hr className="hrStyle" />
            <div className="row">
              <div
                className="col-lg-5"
                style={{
                  paddingRight: "0px",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                Redaction Layer:
              </div>
              <div
                className="col-lg-7"
                style={{
                  paddingLeft: "0px",
                  display: "flex",
                  justifyContent: "flex-end",
                }}
              >
                <LayerDropdown
                  ministryrequestid={requestid}
                  validoipcreviewlayer={requestInfo.validoipcreviewlayer}
                />
              </div>
            </div>
            <hr className="hrStyle" />
            <div className="row">
              <div className="col-lg-4" style={{ paddingRight: "0px" }}>
                Organize by:
              </div>
              <div className="col-lg-8" style={{ paddingLeft: "0px" }}>
                <Stack
                  direction="row"
                  sx={{ paddingBottom: "5px" }}
                  spacing={1}
                >
                  <ClickableChip
                    label="Division"
                    color="primary"
                    size="small"
                    onClick={() => {
                      setOrganizeBy("division");
                      //setExpandedItems([]);
                    }}
                    clicked={organizeBy === "division"}
                  />
                  <ClickableChip
                    label="Modified Date"
                    color="primary"
                    size="small"
                    onClick={() => {
                      setOrganizeBy("lastmodified");
                      //setExpandedItems([]);
                    }}
                    clicked={organizeBy === "lastmodified"}
                  />
                </Stack>
              </div>
            </div>
            <hr className="hrStyle" />
            <div>
              <span className="filterText">Filter:</span>
              <span>
                {pageFlagList.map((item: any) => (
                  <>
                    {item.pageflagid == "Consult" || item.pageflagid == pageFlagTypes['Consult'] ? (
                      <span
                        style={consultFilterStyle}
                        onClick={(event) => openConsulteeList(event)}
                      >
                        <FontAwesomeIcon
                          key={item.pageflagid}
                          title={item.name}
                          className={
                            item.pageflagid == "Consult" || item.pageflagid == pageFlagTypes['Consult']
                              ? "filterConsultIcon"
                              : "filterIcons"
                          }
                          id={item.pageflagid}
                          style={{ color: "inherit" }}
                          icon={assignIcon(item.pageflagid) as IconProp}
                          size="1x"
                        />
                        <FontAwesomeIcon
                          className={"filterDropDownIcon"}
                          icon={faAngleDown as IconProp}
                          style={{ color: "inherit" }}
                        />
                      </span>
                    ) : (
                      <FontAwesomeIcon
                        key={item.pageflagid}
                        title={item.name}
                        className={
                          item.pageflagid == "Consult" || item.pageflagid == pageFlagTypes['Consult']
                            ? "filterConsultIcon"
                            : "filterIcons"
                        }
                        onClick={(event) =>
                          applyFilter(item.pageflagid, null, event, [])
                        }
                        id={item.pageflagid}
                        icon={assignIcon(item.pageflagid) as IconProp}
                        size="1x"
                      />
                    )}
                  </>
                ))}
                <FontAwesomeIcon
                  key="0"
                  title="No Flag"
                  className="filterIcons"
                  onClick={(event) => applyFilter(0, null, event, [])}
                  id="0"
                  icon={faCircleExclamation as IconProp}
                  size="1x"
                />
              </span>

              <Popover
                anchorEl={anchorEl}
                open={openConsulteeModal}
                anchorOrigin={{
                  vertical: "bottom",
                  horizontal: "center",
                }}
                transformOrigin={{
                  vertical: "top",
                  horizontal: "center",
                }}
                slotProps={{
                  paper: { style: { marginTop: "10px", padding: "10px" } },
                }}
                onClose={() => handleClose()}
              >
                <div className="consultDropDown">
                  <div className="heading">
                    <div className="consulteeItem">
                      <span style={{ marginRight: "10px" }}>
                        <input
                          type="checkbox"
                          id={`checkbox-all`}
                          checked={selectAllConsultee}
                          onChange={(e) => {
                            selectAllConsultees(assignedConsulteeList, e);
                          }}
                        />
                      </span>
                      <label htmlFor={`checkbox-all`}>Select Consult</label>
                    </div>
                    <hr className="hrStyle" />
                  </div>
                  {showConsultee(assignedConsulteeList)}
                </div>
              </Popover>
            </div>
            <hr className="hrStyle" />
            <div className="row counters">
              <div className="col-lg-6">
                {`Complete: ${updateCompletionCounter()}%`}
              </div>
              <div className="col-lg-6 style-float">
                {`Total Pages: ${updatePageCount()}/${totalPageCount}`}
              </div>
            </div>
            <hr className="hrStyle" />
            {
              filesForDisplay.length <= 0 && filterBookmark ? (
                <div style={{ textAlign: "center" }}>
                  No page has been book marked.
                </div>
              ) : (
                <CustomTreeView
                  ref={treeRef}
                  items={getTreeItems()}
                  filesForDisplay={filesForDisplay}
                  pageMappedDocs={pageMappedDocs}
                  selectTreeItem={selectTreeItem}
                  setWarningModalOpen={setWarningModalOpen}
                  pageFlagList={pageFlagList}
                  openFOIPPAModal={openFOIPPAModal}
                  requestid={requestid}
                  assignIcon={assignIcon}
                  pageFlags={pageFlags}
                  syncPageFlagsOnAction={syncPageFlagsOnAction}
                />
              )
            }
          </Stack>
        </div>
      );
    }
  )
);

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
          "&:focus": {
            backgroundColor: "#38598A",
          },
        },
      ]}
      variant={clicked ? "filled" : "outlined"}
      {...rest}
    />
  );
};

export default React.memo(DocumentSelector);
