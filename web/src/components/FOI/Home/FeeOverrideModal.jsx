import ReactModal from "react-modal-resizable-draggable";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import CloseIcon from "@mui/icons-material/Close";
import IconButton from "@mui/material/IconButton";

const FeeOverrideModal = ({
  modalData,
  cancelRedaction,
  outstandingBalanceModal,
  cancelSaveRedlineDoc,
  isOverride,
  feeOverrideReason,
  handleOverrideReasonChange,
  saveDoc,
  overrideOutstandingBalance,
}) => {
  return (
    <ReactModal
      initWidth={800}
      initHeight={300}
      minWidth={600}
      minHeight={250}
      className={
        "state-change-dialog" +
        (modalData?.modalFor == "redline" ? " redline-modal" : "")
      }
      onRequestClose={cancelRedaction}
      isOpen={outstandingBalanceModal}
    >
      <DialogTitle disableTypography id="state-change-dialog-title">
        <h2 className="state-change-header">{modalData?.modalTitle}</h2>
        <IconButton className="title-col3" onClick={cancelSaveRedlineDoc}>
          <i className="dialog-close-button">Close</i>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent className={"modal-content"}>
        <DialogContentText
          id="state-change-dialog-description"
          component={"span"}
        >
          <span>
            {modalData?.modalMessage}
            {isOverride && (
              <>
                <br />
                <br />
                <label for="override-reason">Reason for the override : </label>
                <input
                  type="text"
                  size={50}
                  style={{ marginLeft: 10 }}
                  id="override-reason"
                  value={feeOverrideReason}
                  onChange={handleOverrideReasonChange}
                />
              </>
            )}
          </span>
        </DialogContentText>
      </DialogContent>
      <DialogActions className="foippa-modal-actions">
        {!isOverride && (
          <button
            className="btn-bottom btn-save btn"
            onClick={overrideOutstandingBalance}
          >
            {modalData?.modalButtonLabel}
          </button>
        )}
        {isOverride && (
          <button className="btn-bottom btn-save btn" onClick={saveDoc} disabled={feeOverrideReason.length == 0 ? true : false}>
            Continue
          </button>
        )}
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

export default FeeOverrideModal;
