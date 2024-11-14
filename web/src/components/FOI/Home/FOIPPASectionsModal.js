import React, {
    useEffect,
    useState,
  } from "react";
import ReactModal from "react-modal-resizable-draggable";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import CloseIcon from "@mui/icons-material/Close";
import IconButton from "@mui/material/IconButton";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { faArrowUp, faArrowDown } from "@fortawesome/free-solid-svg-icons";
import Switch from "@mui/material/Switch";
import { styled } from "@mui/material/styles";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";


export const FOIPPASectionsModal= ({
    cancelRedaction,
    modalOpen,
    sections,
    sectionIsDisabled,
    selectedSections,
    handleSectionSelected,
    editRedacts ,
    saveRedactions,
    saveDisabled,
    saveRedaction,
    defaultSections,
    saveDefaultSections,
    clearDefaultSections,
    pageSelectionsContainNRDup,
    setMessageModalOpen,
    currentLayer
}) => {

    const [modalSortNumbered, setModalSortNumbered] = useState(false);
    const [modalSortAsc, setModalSortAsc] = useState(true);

    const isOILayerSelected = () => {
      if(currentLayer.name.toLowerCase() === "open info")
        return true;
      return false;
    }

    const AntSwitch = styled(Switch)(({ theme }) => ({
        width: 28,
        height: 16,
        padding: 0,
        display: "flex",
        "&:active": {
          "& .MuiSwitch-thumb": {
            width: 15,
          },
          "& .MuiSwitch-switchBase.Mui-checked": {
            transform: "translateX(9px)",
          },
        },
        "& .MuiSwitch-switchBase": {
          padding: 2,
          "&.Mui-checked": {
            transform: "translateX(12px)",
            color: "#fff",
            "& + .MuiSwitch-track": {
              opacity: 1,
              backgroundColor:
                theme.palette.mode === "dark" ? "#177ddc" : "#38598a",
            },
          },
        },
        "& .MuiSwitch-thumb": {
          boxShadow: "0 2px 4px 0 rgb(0 35 11 / 20%)",
          width: 12,
          height: 12,
          borderRadius: 6,
          transition: theme.transitions.create(["width"], {
            duration: 200,
          }),
        },
        "& .MuiSwitch-track": {
          borderRadius: 16 / 2,
          opacity: 1,
          backgroundColor: theme.palette.mode === "dark" ? "#177ddc" : "#38598a",
          boxSizing: "border-box",
        },
      }));

      const changeModalSort = (e) => {
        setModalSortNumbered(e.target.checked);
      };

      const changeSortOrder = (e) => {
        if (modalSortNumbered) {
          setModalSortAsc(!modalSortAsc);
        }
      };

      const compareValues = (a, b) => {
        if (modalSortNumbered) {
          if (modalSortAsc) {
            return a.id - b.id;
          } else {
            return b.id - a.id;
          }
        } else {
          return b.count - a.count;
        }
      };

      const handleSelectCodes = () => {
        if (editRedacts) {
          saveRedactions();
        } else {
          saveRedaction();
        }
        pageSelectionsContainNRDup ? setMessageModalOpen(true) : setMessageModalOpen(false);
      }
      

    return(
        !isOILayerSelected() ? (
          <ReactModal
          initWidth={650}
          initHeight={700}
          minWidth={400}
          minHeight={200}
          className={"state-change-dialog"}
          onRequestClose={cancelRedaction}
          isOpen={modalOpen}
        >
          <DialogTitle disabletypography="true" id="state-change-dialog-title">
            <h2 className="state-change-header">FOIPPA Sections</h2>
            <IconButton className="title-col3" onClick={cancelRedaction}>
              <i className="dialog-close-button">Close</i>
              <CloseIcon />
            </IconButton>
          </DialogTitle>
          <DialogContent className={"dialog-content-nomargin"}>
            <DialogContentText
              id="state-change-dialog-description"
              component={"span"}
            >
              <Stack direction="row-reverse" spacing={1} alignItems="center">
                <button
                  onClick={changeSortOrder}
                  style={{
                    border: "none",
                    backgroundColor: "white",
                    padding: 0,
                  }}
                  disabled={!modalSortNumbered}
                >
                  {modalSortAsc ? (
                    <FontAwesomeIcon
                      icon={faArrowUp}
                      size="1x"
                      color="#666666"
                    />
                  ) : (
                    <FontAwesomeIcon
                      icon={faArrowDown}
                      size="1x"
                      color="#666666"
                    />
                  )}
                </button>
                <Typography>Numbered Order</Typography>
                <AntSwitch
                  onChange={changeModalSort}
                  checked={modalSortNumbered}
                  inputProps={{ "aria-label": "ant design" }}
                />
                <Typography>Most Used</Typography>
              </Stack>
              <div style={{ overflowY: "scroll" }}>
                <List className="section-list">
                  {sections?.sort(compareValues).map((section, index) => (
                    <ListItem key={"list-item" + section.id}>
                      <input
                        type="checkbox"
                        className="section-checkbox"
                        key={"section-checkbox" + section.id}
                        id={"section" + section.id}
                        data-sectionid={section.id}
                        onChange={handleSectionSelected}
                        disabled={sectionIsDisabled(section.id)}
                        defaultChecked={selectedSections.includes(section.id)}
                      />
                      <label
                        key={"list-label" + section.id}
                        className="check-item"
                      >
                        {section.section + " - " + section.description}
                      </label>
                    </ListItem>
                  ))}
                </List>
              </div>
            </DialogContentText>
          </DialogContent>
          <DialogActions className="foippa-modal-actions">
            <button
              className={`btn-bottom btn-save btn`}
              onClick={handleSelectCodes}
              disabled={saveDisabled}
            >
              Select Code(s)
            </button>
            {defaultSections.length > 0 ? (
              <button
                className="btn-bottom btn-cancel"
                onClick={clearDefaultSections}
              >
                Clear Defaults
              </button>
            ) : (
              <button
                className={`btn-bottom btn-cancel ${
                  saveDisabled && "btn-disabled"
                }`}
                onClick={saveDefaultSections}
                disabled={saveDisabled}
              >
                Save as Default
              </button>
            )}
            <button className="btn-bottom btn-cancel" onClick={cancelRedaction}>
              Cancel
            </button>
          </DialogActions>
          </ReactModal> 
        ): (
          <ReactModal
          initWidth={650}
          initHeight={700}
          minWidth={400}
          minHeight={200}
          top={15}
          className={"state-change-dialog"}
          onRequestClose={cancelRedaction}
          isOpen={modalOpen}
        >
          <DialogTitle disabletypography="true" id="oi-redaction-code-modal-title">
            <h2 className="state-change-header">OI Redaction codes</h2>
            <IconButton className="title-col3" onClick={cancelRedaction}>
              <i className="dialog-close-button">Close</i>
              <CloseIcon />
            </IconButton>
          </DialogTitle>
          <DialogContent className={"dialog-content-nomargin"}>
            <DialogContentText
              id="state-change-dialog-description"
              component={"span"}
            >
            <div style={{ overflowY: "scroll" }}>
              <List className="section-list">
                {sections?.sort(compareValues).map((section, index) => (
                  <ListItem key={"list-item" + section.id}>
                    <input
                      type="checkbox"
                      className="section-checkbox"
                      key={"section-checkbox" + section.id}
                      id={"section" + section.id}
                      data-sectionid={section.id}
                      onChange={handleSectionSelected}
                      disabled={sectionIsDisabled(section.id)}
                      defaultChecked={selectedSections.includes(section.id)}
                    />
                    <label
                      key={"list-label" + section.id}
                      className="check-item"
                    >
                      {section.section}
                    </label>
                  </ListItem>
                ))}
              </List>
            </div>
            </DialogContentText>
          </DialogContent>
          <DialogActions className="foippa-modal-actions">
            <button
              className={`btn-bottom btn-save btn`}
              onClick={editRedacts ? saveRedactions : saveRedaction}
              disabled={saveDisabled}
            >
              Select Code(s)
            </button>
            <button className="btn-bottom btn-cancel" onClick={cancelRedaction}>
              Cancel
            </button>
          </DialogActions>
          </ReactModal> 
      )
    );


}


