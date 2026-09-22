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
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Box from '@mui/material/Box';

const FOIPPAShortCodeModal = ({
    cancelRedaction, 
    saveDisabled, 
    AntSwitch, 
    sections,
    compareValues,
    defaultSections,
    clearDefaultSections,
    saveDefaultSections,
    sectionIsDisabled,
    handleSelectCodes,
    handleSectionSelected,
    selectedSections,
    tabValue,
    handleTabChange,
    changeSortOrder,
    modalSortNumbered,
    modalSortAsc,
    changeModalSort
    } : any) => {
    // NEEDS ITS OWN SAVEDISABLED??, SELCTED SECTIONS, HANDLE SELECTED SECTIONS, OWN SORTING. SAVE AS DEFAULT CAN BE CROSS FUNCTIONAL? // REUSE REDACTION LOGIC THOUGH
    return (
        <>
            <DialogTitle disabletypography="true" id="FOIPPA-modal-dialog-title">
            <h2 className="state-change-header">FOIPPA Short Codes</h2>
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
                <Stack direction="row" spacing={1} alignItems="center">
                    <Tabs
                        value={tabValue}
                        onChange={handleTabChange}
                        TabIndicatorProps={{
                            sx: { backgroundColor: '#036' }
                        }}
                        sx={{
                            '& .MuiTab-root': {
                                color: '#7F8C8D',
                            },
                            '& .MuiTab-root.Mui-selected': {
                                color: '#036',
                            },
                        }}
                    >
                    <Tab value="originalCodes" label="FOIPPA Codes" />
                    <Tab value="shortCodes" label="Short Codes" />
                    </Tabs>
                    <Typography>Most Used</Typography>
                    <AntSwitch
                        onChange={changeModalSort}
                        checked={modalSortNumbered}
                        inputProps={{ "aria-label": "ant design" }}
                    />
                    <Typography>Numbered Order</Typography>
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
                </Stack>
                <div style={{ overflowY: "scroll" }}>
                <List className="section-list">
                    {sections?.sort(compareValues).map((section : any, index : number) => {
                        if (section.shortcode) {
                            return (<ListItem key={"list-item" + section.id}>
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
                                    {section.shortcode + " - " + section.section + " - " + section.description}
                                </label>
                            </ListItem>)
                        }
                    })}
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
        </>
    );
}

export default FOIPPAShortCodeModal;