import React, { useState, useEffect } from "react";
import { useSelector } from "react-redux";
// import "../FileUpload/FileUpload.scss";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import CloseIcon from "@mui/icons-material/Close";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import SearchIcon from "@mui/icons-material/Search";
import InputAdornment from "@mui/material/InputAdornment";
import InputBase from "@mui/material/InputBase";
import IconButton from "@mui/material/IconButton";
import TextField from '@mui/material/TextField';
import AddCircleIcon from '@mui/icons-material/AddCircle';
import _ from 'lodash';
import { MCFPopularSections } from "../../../constants/enum";
// import "./DocumentSelector.scss";
// import "./FileUpload.scss";

const MCFPersonal = ({
    editTagModalOpen,
    setEditTagModalOpen,
    setOpenContextPopup,
    setNewDivision,
    // tagValue,
    curPersonalAttributes,
    setNewPersonalAttributes,
    updatePersonalAttributes,
    setCurPersonalAttributes,
    setCurrentEditRecord
}) => {
    const [personalAttributes, setPersonalAttributes] = useState({
      person: "",
      filetype: "",
      volume: "",
      trackingid: "",
      personaltag: "TBD"
    });

    const [searchValue, setSearchValue] = useState("");
    const [showAdditionalTags, setShowAdditionalTags] = useState(false);
    const [additionalTagList, setAdditionalTagList] = useState([]);

    const MCFSections = useSelector((state) => state.documents.foiPersonalSections);
    const [tagList, setTagList] = useState([]);
    const [otherTagList, setOtherTagList] = useState([]);
  
    const MCFPeople = useSelector(
      (state) => state.documents.foiPersonalPeople
    );
    const MCFFiletypes = useSelector(
      (state) => state.documents.foiPersonalFiletypes
    );
    const MCFVolumes = useSelector(
      (state) => state.documents.foiPersonalVolumes
    );

    const [people, setPeople] = useState([]);
    const [volumes, setVolumes] = useState([]);
    const [fileTypes, setFileTypes] = useState([]);
    const [otherFileTypes, setOtherFileTypes] = useState([]);

    const [showAllPeople, setShowAllPeople] = useState(false);
    const [showAllVolumes, setShowAllVolumes] = useState(false);
    const [fileTypeSearchValue, setFileTypeSearchValue] = useState("");
    const [additionalFileTypes, setAdditionalFileTypes] = useState([]);
    const [showAdditionalFileTypes, setShowAdditionalFileTypes] = useState(false);

    useEffect(() => {
      setPersonalAttributes(curPersonalAttributes);
    },[curPersonalAttributes])

    useEffect(() => {
      if(MCFSections?.sections) {
        if(MCFSections.sections.length > MCFPopularSections-1) {
          setTagList(MCFSections.sections.slice(0, MCFPopularSections-1));
          setOtherTagList(MCFSections.sections.slice(MCFPopularSections));
        } else {
          setTagList(MCFSections.sections);
          setOtherTagList([]);
        }
      }
    },[MCFSections])

    useEffect(() => {
      if(MCFPeople?.people) {
        if(MCFPeople.people.length > 5) {
          setPeople(MCFPeople.people.slice(0, 5));
        } else {
          setPeople(MCFPeople.people);
        }
      }
    },[MCFPeople])

    useEffect(() => {
      if(MCFVolumes?.volumes) {
        if(MCFFiletypes.filetypes.length > 5) {
          setVolumes(MCFVolumes.volumes.slice(0, 5));
        } else {
          setVolumes(MCFVolumes.volumes);
        }
      }
    },[MCFVolumes])

    useEffect(() => {
      if(MCFFiletypes?.filetypes) {
        if(MCFFiletypes.filetypes.length > 6) {
          setFileTypes(MCFFiletypes.filetypes.slice(0, 6));
          setOtherFileTypes(MCFFiletypes.filetypes.slice(6, MCFFiletypes.filetypes.length))
        } else {
          setFileTypes(MCFFiletypes.filetypes);
          setOtherFileTypes([])
        }
      }
    },[MCFFiletypes])

    const searchFileTypes = (_fileTypeArray, _keyword, _selectedFileType) => {
      let newFileTypeArray = [];
      if(_keyword || _selectedFileType) {
        _fileTypeArray.map((section) => {
          if(_keyword && section.name.toLowerCase().includes(_keyword.toLowerCase())) {
            newFileTypeArray.push(section);
          } else if(section.name === _selectedFileType) {
            newFileTypeArray.unshift(section);
          }
        });
      }

      if(newFileTypeArray.length > 0) {
        setShowAdditionalFileTypes(true);
      } else {
        setShowAdditionalFileTypes(false);
      }

      return newFileTypeArray;
    }

    React.useEffect(() => {
      if(showAllPeople) {
        setPeople(MCFPeople.people)
      } else {
        setPeople(MCFPeople.people.slice(0, 5))
      }
      if(showAllVolumes) {
        setVolumes(MCFVolumes.volumes)
      } else {
        setVolumes(MCFVolumes.volumes.slice(0, 5))
      }
    },[showAllPeople, showAllVolumes])

    React.useEffect(() => {
      setAdditionalFileTypes(searchFileTypes(otherFileTypes, fileTypeSearchValue, personalAttributes?.filetype));
    },[fileTypeSearchValue, otherFileTypes, personalAttributes])

    useEffect(() => {
      setAdditionalTagList(searchSections(otherTagList, searchValue, personalAttributes?.personaltag));
    },[searchValue, otherTagList, personalAttributes])

    const searchSections = (_sectionArray, _keyword, _selectedSectionValue) => {
      let newSectionArray = [];
      if(_keyword || _selectedSectionValue) {
        _sectionArray.map((section) => {
          if(_keyword && section.name.toLowerCase().includes(_keyword.toLowerCase())) {
            newSectionArray.push(section);
          } else if(section.divisionid === _selectedSectionValue) {
            newSectionArray.unshift(section);
          }
        });
      }

      if(newSectionArray.length > 0) {
        setShowAdditionalTags(true);
      } else {
        setShowAdditionalTags(false);
      }
      return newSectionArray;
    }

    const handlePersonalAttributesChange = (_attribute, _type) => {
      let _newPersonalAttributes = {
        person: personalAttributes.person,
        filetype: personalAttributes.filetype,
        volume: personalAttributes.volume,
        trackingid: personalAttributes.trackingid,
        personaltag: personalAttributes.personaltag
      };

      switch(_type) {
        case "person":
          _newPersonalAttributes.person = _attribute.name;
          setPersonalAttributes(_newPersonalAttributes);
          setNewPersonalAttributes(_newPersonalAttributes);
          return;
        case "filetype":
          _newPersonalAttributes.filetype = _attribute.name;
          setPersonalAttributes(_newPersonalAttributes);
          setNewPersonalAttributes(_newPersonalAttributes);
          return;
        case "volume":
          _newPersonalAttributes.volume = _attribute.name;
          setPersonalAttributes(_newPersonalAttributes);
          setNewPersonalAttributes(_newPersonalAttributes);
          return;
        case "trackingid":
          _newPersonalAttributes.trackingid = _attribute;
          setPersonalAttributes(_newPersonalAttributes);
          setNewPersonalAttributes(_newPersonalAttributes);
          return;
        case "personaltag":
          _newPersonalAttributes.personaltag = _attribute.name;
          setPersonalAttributes(_newPersonalAttributes);
          setNewPersonalAttributes(_newPersonalAttributes);
          return;
        default:
          return;
      }
    };

    const handleClose = () => {
      setCurrentEditRecord();
      setCurPersonalAttributes({
        person: "",
        filetype: "",
        volume: "",
        trackingid: "",
        personaltag: "TBD"
      });
      setNewPersonalAttributes();
      setEditTagModalOpen(false);
      setOpenContextPopup(false);
    };

    const handleFileTypeSearchKeywordChange = (keyword) => {
      setFileTypeSearchValue(keyword);
    } 

    const handleTagSearchKeywordChange = (keyword) => {
      setSearchValue(keyword);
    } 

    return (

      <div className="state-change-dialog">
        <Dialog
          open={editTagModalOpen}
          onClose={() => handleClose()}
          aria-labelledby="state-change-dialog-title"
          aria-describedby="state-change-dialog-description"
          maxWidth={"md"}
          fullWidth={true}
          disableEnforceFocus
          // id="state-change-dialog"
        >
          <DialogTitle disableTypography id="state-change-dialog-title">
            <h2 className="state-change-header">Edit Tags</h2>
            <IconButton
              className="title-col3"
              onClick={() => handleClose()}
            >
              <i className="dialog-close-button">Close</i>
              <CloseIcon />
            </IconButton>
          </DialogTitle>
          <DialogContent className={"dialog-content-nomargin"}>
            <DialogContentText
              id="state-change-dialog-description"
              component={"span"}
            >
              <div className="tagtitle">
                <span>
                  Update the tag you want to associate with the selected record. 
                  If this record is from the applicant's file, please select 
                  applicant otherwise you can associate it to a different person. 
                  If you choose to update all by ID, this edit will apply to all 
                  records associated with the tracking ID and file type associated 
                  to that person.
                </span>
              </div>

              <div className="tagtitle">
                <span>Select Person: *</span>
              </div>        
              <div className="taglist-cfdpersonal">
                {people.map(p =>
                  <ClickableChip
                    id={`${p.name}Tag`}
                    key={`${p.name}-tag`}
                    label={p.name.toUpperCase()}
                    sx={{width: "fit-content", marginRight: "8px", marginBottom: "8px"}}
                    color="primary"
                    size="small"
                    onClick={()=>{handlePersonalAttributesChange(p, "person")}}
                    clicked={personalAttributes?.person === p.name}
                  />
                )}
                {!showAllPeople && (<AddCircleIcon
                  id={`showallpeopleTag`}
                  key={`showallpeople-tag`}
                  color="primary"
                  size="small"
                  className="pluscircle"
                  onClick={()=>{setShowAllPeople(true)}}
                />)}
              </div>

              <div className="tagtitle">
                <span>Select Volume:</span>
              </div>  
              <div className="taglist-cfdpersonal">
                {volumes.map(v =>
                  <ClickableChip
                    id={`${v.name}Tag`}
                    key={`${v.name}-tag`}
                    label={v.name.toUpperCase()}
                    sx={{width: "fit-content", marginRight: "8px", marginBottom: "8px"}}
                    color="primary"
                    size="small"
                    onClick={()=>{handlePersonalAttributesChange(v, "volume")}}
                    clicked={personalAttributes?.volume === v.name}
                  />
                )}
                {!showAllVolumes && (<AddCircleIcon
                  id={`showallvolumeTag`}
                  key={`showallvolume-tag`}
                  color="primary"
                  size="small"
                  className="pluscircle"
                  onClick={()=>{setShowAllVolumes(true)}}
                />)}
              </div>

              <div className="tagtitle">
                <span>Select File Type: *</span>
              </div>  
              <div className="taglist-cfdpersonal">
                {fileTypes.map(f =>
                  <ClickableChip
                    id={`${f.name}Tag`}
                    key={`${f.name}-tag`}
                    label={f.name.toUpperCase()}
                    sx={{width: "fit-content", marginRight: "8px", marginBottom: "8px"}}
                    color="primary"
                    size="small"
                    onClick={()=>{handlePersonalAttributesChange(f, "filetype")}}
                    clicked={personalAttributes?.filetype === f.name}
                  />
                )}
              </div>
              <div className="taglist-cfdpersonal">
                <Grid
                  container
                  item
                  direction="row"
                  justify="flex-start"
                  alignItems="flex-start"
                  xs={12}
                  sx={{
                    marginTop: "1em",
                  }}
                >
                  <Paper
                    component={Grid}
                    sx={{
                      border: "1px solid #38598A",
                      color: "#38598A",
                      maxWidth:"100%",
                      backgroundColor: "rgba(56,89,138,0.1)",
                      borderBottomLeftRadius: 0,
                      borderBottomRightRadius: 0
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
                      <label className="hideContent">Search any additional filetypes here</label>
                      <InputBase
                        id="foirecordsfilter"
                        placeholder="Search any additional filetypes here"
                        defaultValue={""}
                        onChange={(e)=>{handleFileTypeSearchKeywordChange(e.target.value.trim())}}
                        sx={{
                          color: "#38598A",
                        }}
                        startAdornment={
                          <InputAdornment position="start">
                            <IconButton
                              aria-label="Search Icon"
                              className="search-icon"
                            >
                              <span className="hideContent">Search any additional filetypes here</span>
                              <SearchIcon />
                            </IconButton>
                          </InputAdornment>
                        }
                        fullWidth
                      />
                    </Grid>
                  </Paper>
                  {showAdditionalFileTypes === true && (<Paper
                    component={Grid}
                    sx={{
                      border: "1px solid #38598A",
                      color: "#38598A",
                      maxWidth:"100%",
                      padding: "8px 15px 0 15px",
                      borderTopLeftRadius: 0,
                      borderTopRightRadius: 0,
                      borderTop: "none",
                      maxHeight:"120px",
                      overflowY:"auto"
                    }}
                    alignItems="center"
                    justifyContent="flex-start"
                    direction="row"
                    container
                    item
                    xs={12}
                    elevation={0}
                  >
                    {additionalFileTypes.map(f =>
                      <ClickableChip
                        id={`${f.name}Tag`}
                        key={`${f.name}-tag`}
                        label={f.name.toUpperCase()}
                        sx={{width: "fit-content", marginRight: "8px", marginBottom: "8px"}}
                        color="primary"
                        size="small"
                        onClick={()=>{handlePersonalAttributesChange(f, "filetype")}}
                        clicked={personalAttributes?.filetype === f.name}
                      />
                    )}
                  </Paper>)}
                </Grid>
              </div>

              <div className="taglist-cfdpersonal">
                <TextField
                  id="trackingid"
                  label="Tracking ID #"
                  inputProps={{ "aria-labelledby": "trackingID-label"}}
                  InputLabelProps={{ shrink: true }}
                  variant="outlined"
                  value={personalAttributes?.trackingid}
                  fullWidth
                  onChange={(e)=>{handlePersonalAttributesChange(e.target.value.trim(), "trackingid")}}
                  required={true}
                />
              </div>

              <div className="tagtitle">
                <span>Select Section Name:</span>
              </div>
              <div className="taglist-cfdpersonal">
                {tagList.map(tag =>
                  <ClickableChip
                    id={`${tag.name}Tag`}
                    key={`${tag.name}-tag`}
                    label={tag.name.toUpperCase()}
                    sx={{width: "fit-content", marginRight: "8px", marginBottom: "8px"}}
                    color="primary"
                    size="small"
                    onClick={()=>{handlePersonalAttributesChange(tag, "personaltag");setNewDivision(tag.divisionid);}}
                    clicked={personalAttributes?.personaltag === tag.name}
                  />
                )}
              </div>
              <div className="taglist-cfdpersonal">
                <Grid
                  container
                  item
                  direction="row"
                  justify="flex-start"
                  alignItems="flex-start"
                  xs={12}
                  sx={{
                    marginTop: "1em",
                  }}
                >
                  <Paper
                    component={Grid}
                    sx={{
                      border: "1px solid #38598A",
                      color: "#38598A",
                      maxWidth:"100%",
                      backgroundColor: "rgba(56,89,138,0.1)",
                      borderBottomLeftRadius: 0,
                      borderBottomRightRadius: 0
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
                      <label className="hideContent">Search any additional sections here</label>
                      <InputBase
                        id="foirecordsfilter"
                        placeholder="Search any additional sections here"
                        defaultValue={""}
                        onChange={(e)=>{handleTagSearchKeywordChange(e.target.value.trim())}}
                        sx={{
                          color: "#38598A",
                        }}
                        startAdornment={
                          <InputAdornment position="start">
                            <IconButton
                              aria-label="Search Icon"
                              className="search-icon"
                            >
                              <span className="hideContent">Search any additional sections here</span>
                              <SearchIcon />
                            </IconButton>
                          </InputAdornment>
                        }
                        fullWidth
                      />
                    </Grid>
                  </Paper>
                  {showAdditionalTags === true && (<Paper
                    component={Grid}
                    sx={{
                      border: "1px solid #38598A",
                      color: "#38598A",
                      maxWidth:"100%",
                      padding: "8px 15px 0 15px",
                      borderTopLeftRadius: 0,
                      borderTopRightRadius: 0,
                      borderTop: "none",
                      maxHeight:"120px",
                      overflowY:"auto"
                    }}
                    alignItems="center"
                    justifyContent="flex-start"
                    direction="row"
                    container
                    item
                    xs={12}
                    elevation={0}
                  >
                    {additionalTagList.map(tag =>
                      <ClickableChip
                        id={`${tag.name}Tag`}
                        key={`${tag.name}-tag`}
                        label={tag.name.toUpperCase()}
                        sx={{width: "fit-content", marginRight: "8px", marginBottom: "8px"}}
                        color="primary"
                        size="small"
                        onClick={()=>{handlePersonalAttributesChange(tag, "personaltag");setNewDivision(tag.divisionid);}}
                        clicked={personalAttributes?.personaltag === tag.name}
                      />
                    )}
                  </Paper>)}
                </Grid>
              </div>
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <button
              className={`btn-bottom btn-save btn`}
              onClick={() => updatePersonalAttributes()}
            >
              Update for Individual
            </button>
            <button
              className={`btn-bottom btn-save btn`}
              onClick={() => updatePersonalAttributes(true)}
            >
              Update for All
            </button>
            <button
              className="btn-bottom btn-cancel"
              onClick={() => handleClose()}
            >
              Cancel
            </button>
          </DialogActions>
        </Dialog>
      </div>
    );
};

const ClickableChip = ({ clicked, sx={}, color, ...rest }) => {
  return (
    <Chip
      sx={[
        {
        ...(clicked
          ? {
              backgroundColor: (color === 'primary' ? "#38598A" : color),
              color: "white",
              width: "100%",
            }
          : {
              color: (color === 'primary' ? "#38598A" : color),
              border: ("1px solid " + (color === 'primary' ? "#38598A" : color)),
              width: "100%",
            }),
          ...sx
        },
        {
          '&:focus': {
            backgroundColor: (color === 'primary' ? "#38598A" : color),
            color: "white",
          }
        },
      ]}
      variant={clicked ? "filled" : "outlined"}
      {...rest}
    />
  );
};

export default MCFPersonal;