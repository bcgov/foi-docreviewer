const ConfirmationModal= ({

}: any) => {



    // return (
    //     <ReactModal
    //     initWidth={800}
    //     initHeight={300}
    //     minWidth={600}
    //     minHeight={250}
    //     className={"state-change-dialog" + (modalFor == "redline"?" redline-modal":"")}
    //     onRequestClose={cancelRedaction}
    //     isOpen={redlineModalOpen}
    //   >
    //     <DialogTitle disableTypography id="state-change-dialog-title">
    //       <h2 className="state-change-header">{modalTitle}</h2>
    //       <IconButton className="title-col3" onClick={cancelSaveRedlineDoc}>
    //         <i className="dialog-close-button">Close</i>
    //         <CloseIcon />
    //       </IconButton>
    //     </DialogTitle>
    //     <DialogContent className={"dialog-content-nomargin"}>
    //       <DialogContentText
    //         id="state-change-dialog-description"
    //         component={"span"}
    //       >
    //         <span>
    //           {modalMessage} <br/><br/>
    //           {modalFor == "redline" && <>
    //           <input
    //             type="checkbox"
    //             style={{ marginRight: 10 }}
    //             className="redline-checkmark"
    //             id="nr-checkbox"
    //             checked={includeNRPages}
    //             onChange={handleIncludeNRPages}
    //           />
    //           <label for="nr-checkbox">Include NR pages</label>
    //           <br/>
    //           <input
    //             type="checkbox"
    //             style={{ marginRight: 10 }}
    //             className="redline-checkmark"
    //             id="duplicate-checkbox"
    //             checked={includeDuplicatePages}
    //             onChange={handleIncludeDuplicantePages}
    //           />
    //           <label for="duplicate-checkbox">Include Duplicate pages</label>
    //           </>}
    //         </span>
    //       </DialogContentText>
    //     </DialogContent>
    //     <DialogActions className="foippa-modal-actions">
    //       <button className="btn-bottom btn-save btn" onClick={saveDoc}>
    //         {modalButtonLabel}
    //       </button>
    //       <button
    //         className="btn-bottom btn-cancel"
    //         onClick={cancelSaveRedlineDoc}
    //       >
    //         Cancel
    //       </button>
    //     </DialogActions>
    //   </ReactModal>
    // );

};

export default ConfirmationModal;
