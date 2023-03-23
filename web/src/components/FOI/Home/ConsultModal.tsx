import React, { useState } from 'react'
import Dialog from '@material-ui/core/Dialog';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';
import CloseIcon from '@material-ui/icons/Close';
import IconButton from "@mui/material/IconButton";
import TextField from '@mui/material/TextField';


const ConsultModal = ({
    flagId,
    selectedPage,
    documentId,
    documentVersion,
    openModal,
    setOpenModal,
    savePageFlags
}: any) => {

    const[newConsultBody,setNewConsultBody]= useState("");
    const[errorMessage, setErrorMessage] = useState("");

    const saveNewCode = (newConsultBody: string) => {
        if(newConsultBody?.length >100){
            setErrorMessage("Character limit cannot exceeded.")
        }
        else{
            setOpenModal(false);
            setNewConsultBody(newConsultBody);
            if(newConsultBody){
                savePageFlags(flagId,
                    selectedPage,
                    documentId,
                    documentVersion,
                    "add",
                    newConsultBody
                    );
            }
        }
    }

    const updateConsultBody = (e:any) => {
        if(e.target.value?.length >100){
            setErrorMessage("Character limit exceeded.")
        }
        else{
            setNewConsultBody(e.target.value);
        }
    }

    return (
        <div className={`consult-modal-dialog`}>
            <Dialog
                open={openModal}
                onClose={() => setOpenModal(false)}
                aria-labelledby="state-change-dialog-title"
                aria-describedby="state-change-dialog-description"
                maxWidth={'md'}
                fullWidth={true}
            >
            <DialogTitle disableTypography id="state-change-dialog-title" className="consult-modal-margin">
                <h2 className="state-change-header">Add Other Public Body for Consult</h2>
                <IconButton aria-label="close" onClick={() => setOpenModal(false)}>
                    <CloseIcon />
                </IconButton>
            </DialogTitle>
            <DialogContent>
                <DialogContentText id="consult-modal-description" component={'span'}>
                    <div className={`row other-pb-modal-message`}>
                        <TextField
                            id="new-public-body"
                            label="Type Name of Other Public Body for Consult"
                            placeholder='Type Other Public Body Name'
                            inputProps={{ "aria-labelledby": "otherPublicBody-label" , maxLength: 100 }}
                            InputLabelProps={{ shrink: true}}
                            focused
                            value={newConsultBody || ''}
                            onChange={updateConsultBody}
                            error={newConsultBody?.length >100}
                            helperText={errorMessage}
                        />
                    </div>
                </DialogContentText>
            </DialogContent>
            <DialogActions>
                <button className={`btn-bottom btn-save btnenabled`} 
                disabled={newConsultBody?.length <=0}
                onClick={() => saveNewCode(newConsultBody)}>
                    Save
                </button>
                <button className="btn-bottom btn-cancel" onClick={() => setOpenModal(false)}>
                    Cancel
                </button>
            </DialogActions>
        </Dialog >
        </div >
    )
  }

export default ConsultModal;