import ReactModal from "react-modal-resizable-draggable";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import CloseIcon from "@mui/icons-material/Close";
import IconButton from "@mui/material/IconButton";

export const NRWarningModal= ({
    cancelRedaction,
    messageModalOpen,
    modalData
}) => {


return (
    <ReactModal
    initWidth={800}
    initHeight={300}
    minWidth={600}
    minHeight={250}
    className={"state-change-dialog"}
    onRequestClose={cancelRedaction}
    isOpen={messageModalOpen}
  >
    <DialogTitle disableTypography id="state-change-dialog-title">
      <h2 className="state-change-header">{modalData.modalTitle}</h2>
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
        <span className="confirmation-message">
          {modalData.modalMessage} <br></br>
        </span>
      </DialogContentText>
    </DialogContent>
    <DialogActions className="foippa-modal-actions">
      <button
        className="btn-bottom btn-cancel"
        onClick={cancelRedaction}
      >
        Cancel
      </button>
    </DialogActions>
  </ReactModal>
)

}