import React, { useEffect, useState, useRef } from 'react'
import Dialog from '@material-ui/core/Dialog';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';
import CloseIcon from '@material-ui/icons/Close';
import IconButton from "@mui/material/IconButton";

const PageLeftOffModal = ({
    openPageLeftOffModal,
    setOpenPageLeftOffModal,
    signout
}: any) => {

    // const signout = () => {
    //     setOpenPageLeftOffModal(false);
    //     localStorage.removeItem('authToken');
    //     UserService.userLogout();
    // }

    return (
        <div>
            <Dialog
                open={openPageLeftOffModal}
                onClose={() => setOpenPageLeftOffModal(false)}
                aria-labelledby="bookmark-dialog-title"
                aria-describedby="bookmark-dialog-description"
                maxWidth={'md'}
                //fullWidth={true}
            >
                <DialogTitle disableTypography id="state-change-dialog-title" className="consult-modal-margin">
                    <h2 className="state-change-header">Page Left Off Bookmark</h2>
                    <IconButton aria-label="close" onClick={() => setOpenPageLeftOffModal(false)}>
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent>
                    <DialogContentText id="consult-modal-description" component={'span'}>
                        <div className={`row other-pb-modal-message bookmark-text-align`}>
                            <div>Do you want to close the records package without
                            adding a </div> 
                            <div>'Page Left Off' bookmark?</div>
                        </div>
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    {/* <div className='consult-modal-margin'> */}
                    <button className={`btn-bottom btn-save btnenabled`}
                        onClick={() => signout()}>
                        Close Redaction App
                    </button>
                    <button className="btn-bottom btn-cancel" onClick={() => setOpenPageLeftOffModal(false)}>
                        Cancel
                    </button>
                    {/* </div> */}
                </DialogActions>
            </Dialog >
        </div >
    )
}

export default PageLeftOffModal;