import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import CloseIcon from '@mui/icons-material/Close';
import IconButton from "@mui/material/IconButton";

const PageLeftOffModal = ({
    openPageLeftOffModal,
    setOpenPageLeftOffModal,
    signout
}: any) => {

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
                <DialogTitle id="state-change-dialog-title" className="consult-modal-margin">
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