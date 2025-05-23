import ReactModal from "react-modal-resizable-draggable";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import CloseIcon from "@mui/icons-material/Close";
import IconButton from "@mui/material/IconButton";
import Grid from '@mui/material/Grid';
import { Tooltip } from '@mui/material';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';

export const ConfirmationModal= ({
    cancelRedaction,
    redlineModalOpen,
    cancelSaveRedlineDoc,
    includeComments,
    handleIncludeComments,
    includeNRPages,
    handleIncludeNRPages,
    includeDuplicatePages,
    handleIncludeDuplicantePages,
    isDisableNRDuplicate,
    saveDoc,
    modalData,
    documentPublicBodies,
    handleSelectedPublicBodies,
    selectedPublicBodyIDs,
    consultApplyRedactions,
    handleApplyRedactions,
    consultApplyRedlines,
    handleApplyRedlines,
    setRedlinePhase,
    redlinePhase,
    assignedPhases,
    validoipcreviewlayer
}) => {
    const disableConsultSaveButton = modalData?.modalFor === "consult" && selectedPublicBodyIDs.length < 1;
    const disablePhasePackageCreation = ["redline","responsepackage"].includes(modalData?.modalFor) && assignedPhases && !redlinePhase;
    const modalClass = (["redline", "responsepackage"].includes(modalData?.modalFor) && assignedPhases ? " redlinephase-modal" : modalData?.modalFor === "redline" ? " redline-modal" : modalData?.modalFor === "consult" ? " consult-modal" : "");
    let phaseSelectionList;
    if(assignedPhases?.length >0){
      phaseSelectionList = [<MenuItem disabled key={0} value={0}>Select Phase</MenuItem>];
      for (let phase of assignedPhases?.sort((a,b) => a.activePhase - b.activePhase)) {
        const phaseNum = phase.activePhase;
        phaseSelectionList.push(<MenuItem disabled={!phase.valid} key={phaseNum} value={phaseNum}>{phaseNum}</MenuItem>);
      }
    }
    const handlePhaseSelect = (value) => {
      setRedlinePhase(value);
    }
    const handleCancel = () => {
      setRedlinePhase(null);
      cancelSaveRedlineDoc();
    }

    return (
      <ReactModal
      initWidth={800}
      initHeight={420}
      minWidth={600}
      minHeight={250}
      className={"state-change-dialog" + modalClass}
      onRequestClose={cancelRedaction}
      isOpen={redlineModalOpen}
    >
      <DialogTitle disabletypography="true" id="state-change-dialog-title">
        <h2 className="state-change-header">{modalData?.modalTitle}</h2>
        <IconButton className="title-col3" onClick={handleCancel}>
          <i className="dialog-close-button">Close</i>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent className={"dialog-content-nomargin"}>
        <DialogContentText
          id="state-change-dialog-description"
          component={"span"}
        >
          <span>
            {modalData?.modalMessage}
            <br/><br/>
            {assignedPhases && phaseSelectionList && ["redline","responsepackage"].includes(modalData?.modalFor) && !validoipcreviewlayer &&
              <div>
                <TextField
                    InputLabelProps={{ shrink: true }}
                    select
                    size="small"
                    variant="outlined"
                    style={{width: "30%"}}
                    value={redlinePhase ? redlinePhase : 0}
                    label="Phase"
                    onChange = {(event) => handlePhaseSelect(event.target.value)}
                    error={!redlinePhase}
                    required
                >
                  {phaseSelectionList}
                </TextField>
              </div>
            }
            <br/>
            {modalData?.modalFor == "redline" && 
              <>
                <input
                  type="checkbox"
                  style={{ marginRight: 10 }}
                  className="redline-checkmark"
                  id="comment-checkbox"
                  checked={includeComments}
                  onChange={handleIncludeComments}
                />
                <label htmlFor="comment-checkbox">Include Comments</label>
                <br/>
                <input
                  type="checkbox"
                  style={{ marginRight: 10 }}
                  className="redline-checkmark"
                  id="nr-checkbox"
                  checked={includeNRPages}
                  onChange={handleIncludeNRPages}
                  disabled={isDisableNRDuplicate}
                />
                <label htmlFor="nr-checkbox">Include NR pages</label>
                <br/>
                <input
                  type="checkbox"
                  style={{ marginRight: 10 }}
                  className="redline-checkmark"
                  id="duplicate-checkbox"
                  checked={includeDuplicatePages}
                  onChange={handleIncludeDuplicantePages}
                  disabled={isDisableNRDuplicate}
                />
                <label htmlFor="duplicate-checkbox">Include Duplicate pages</label>
              </>}
            {modalData?.modalFor === "consult" &&
              <>
                <Grid container spacing={0.5}>
                  {documentPublicBodies?.map((publicBody) => {
                    return (<>
                    <Grid item sm={1.5} md={1.5} style={{overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis"}}>
                      <input
                        key={publicBody.programareaid ? publicBody.programareaid : publicBody.name}
                        type="checkbox"
                        style={{ marginRight: 10, fontSize: "small"}}
                        className="redline-checkmark"
                        id={`${publicBody.iaocode}-checkbox`}
                        value={publicBody.programareaid ? publicBody.programareaid : publicBody.name}
                        checked={publicBody.programareaid ? selectedPublicBodyIDs.includes(publicBody.programareaid) : selectedPublicBodyIDs.includes(publicBody.name)}
                        onClick={handleSelectedPublicBodies}
                      />
                      <Tooltip title={publicBody.iaocode} enterDelay={1000}>
                        <label style={{display: "inline", fontSize: "small" }} htmlFor={`${publicBody.iaocode}-checkbox`}>{publicBody.iaocode}</label>
                      </Tooltip>
                    </Grid>
                    </>)
                  })}
                </Grid>
                <br/>
                <p>More Options:</p>
                <input
                  type="checkbox"
                  style={{ marginRight: 10 }}
                  className="redline-checkmark"
                  id="nr-checkbox"
                  checked={includeNRPages}
                  onChange={handleIncludeNRPages}
                  disabled={isDisableNRDuplicate}
                />
                <label htmlFor="nr-checkbox">Include NR pages</label>
                <br/>
                <input
                  type="checkbox"
                  style={{ marginRight: 10 }}
                  className="redline-checkmark"
                  id="duplicate-checkbox"
                  checked={includeDuplicatePages}
                  onChange={handleIncludeDuplicantePages}
                  disabled={isDisableNRDuplicate}
                />
                <label htmlFor="duplicate-checkbox">Include Duplicate pages</label>
                <br/>
                <input
                    type="checkbox"
                    style={{ marginRight: 10 }}
                    className="redline-checkmark"
                    id="applyredline-checkbox"
                    checked={consultApplyRedlines}
                    onChange={handleApplyRedlines}
                  />
                  <label htmlFor="applyredline-checkbox">Include Transparent Redactions (Redlines)</label>
                  <br/>
                <input
                  type="checkbox"
                  style={{ marginRight: 10 }}
                  className="redline-checkmark"
                  id="redaction-checkbox"
                  checked={consultApplyRedactions}
                  onChange={handleApplyRedactions}
                  disabled={!consultApplyRedlines}
                />
                <label htmlFor="redaction-checkbox">Apply Redactions (NR code only)</label>
              </>}
          </span>
        </DialogContentText>
      </DialogContent>
      <DialogActions className="foippa-modal-actions">
        <button className="btn-bottom btn-save btn" onClick={saveDoc} disabled={disableConsultSaveButton || disablePhasePackageCreation}>
          {modalData?.modalButtonLabel}
        </button>
        <button
          className="btn-bottom btn-cancel"
          onClick={handleCancel}
        >
          Cancel
        </button>
      </DialogActions>
    </ReactModal>
    );

};
