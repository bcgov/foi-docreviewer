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
import Grid from '@mui/material/Grid';
//import type { ReactModalProps } from './types';


export const ConfirmationModal= ({
    cancelRedaction,
    redlineModalOpen,
    cancelSaveRedlineDoc,
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
    handleApplyRedlines
}) => {

    return (
      <ReactModal
      initWidth={800}
      initHeight={300}
      minWidth={600}
      minHeight={250}
      className={"state-change-dialog" + (modalData?.modalFor === "redline" ? " redline-modal" : modalData?.modalFor === "consult" ? " consult-modal" : "")}
      onRequestClose={cancelRedaction}
      isOpen={redlineModalOpen}
    >
      <DialogTitle disabletypography="true" id="state-change-dialog-title">
        <h2 className="state-change-header">{modalData?.modalTitle}</h2>
        <IconButton className="title-col3" onClick={cancelSaveRedlineDoc}>
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
            {modalData?.modalMessage} <br/><br/>
            {modalData?.modalFor == "redline" && <>
            <input
              type="checkbox"
              style={{ marginRight: 10 }}
              className="redline-checkmark"
              id="nr-checkbox"
              checked={includeNRPages}
              onChange={handleIncludeNRPages}
              disabled={isDisableNRDuplicate}
            />
            <label for="nr-checkbox">Include NR pages</label>
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
            <label for="duplicate-checkbox">Include Duplicate pages</label>
            </>}
            {modalData?.modalFor === "consult" &&
              <>
                <Grid container spacing={0.5}>
                  {documentPublicBodies?.map((publicBody) => {
                    return (<>
                    <Grid item sm={1.5} md={1.5}>
                      <input
                        key={publicBody.programareaid ? publicBody.programareaid : publicBody.name}
                        type="checkbox"
                        style={{ marginRight: 10 }}
                        className="redline-checkmark"
                        id={`${publicBody.iaocode}-checkbox`}
                        value={publicBody.programareaid ? publicBody.programareaid : publicBody.name}
                        checked={publicBody.programareaid ? selectedPublicBodyIDs.includes(publicBody.programareaid) : selectedPublicBodyIDs.includes(publicBody.name)}
                        onClick={handleSelectedPublicBodies}
                      />
                      <label for={`${publicBody.iaocode}-checkbox`}>{publicBody.iaocode}</label>
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
                <label for="nr-checkbox">Include NR pages</label>
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
                <label for="duplicate-checkbox">Include Duplicate pages</label>
                <br/>
                <input
                    type="checkbox"
                    style={{ marginRight: 10 }}
                    className="redline-checkmark"
                    id="applyredline-checkbox"
                    checked={consultApplyRedlines}
                    onChange={handleApplyRedlines}
                  />
                  <label for="applyredline-checkbox">Include Transparent Redactions (Redlines)</label>
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
                <label for="redaction-checkbox">Apply Redactions (NR code only)</label>
              </>}
          </span>
        </DialogContentText>
      </DialogContent>
      <DialogActions className="foippa-modal-actions">
        <button className="btn-bottom btn-save btn" onClick={saveDoc} disabled={selectedPublicBodyIDs.length < 1}>
          {modalData?.modalButtonLabel}
        </button>
        <button
          className="btn-bottom btn-cancel"
          onClick={cancelSaveRedlineDoc}
        >
          Cancel
        </button>
      </DialogActions>
    </ReactModal>
    );

};
