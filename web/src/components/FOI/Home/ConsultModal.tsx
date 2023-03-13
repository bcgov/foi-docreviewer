import React, { useEffect, useState, useRef } from 'react'
import Dialog from '@material-ui/core/Dialog';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';
import CloseIcon from '@material-ui/icons/Close';
import TextField from '@material-ui/core/TextField';
import IconButton from "@mui/material/IconButton";
import { makeStyles } from '@material-ui/core/styles';


const ConsultModal = ({
    flagId,
    documentId,
    documentVersion,
    openModal,
    setOpenModal,
    savePageFlags
}: any) => {


    const useStyles = makeStyles((theme) => ({
        root: {
          "& .MuiTextField-root": {
            margin: theme.spacing(1, "0px"),
          },
        },
      }));

    const classes = useStyles();

    const[newConsultBody,setNewConsultBody]= useState("");
    const[errorMessage, setErrorMessage] = useState("");

    const saveNewCode = (newConsultBody: string) => {
        if(newConsultBody?.length >100){
            setErrorMessage("Character limit cannot exceeded.")
        }
        else{
            setNewConsultBody(newConsultBody);
            if(newConsultBody){
                savePageFlags(flagId,
                    documentId,
                    documentVersion,
                    newConsultBody
                    );
            }
        }
    }

    const updateConsultBody = (e:any) => {
        console.log("newConsultBody:",e.target.value);
        if(e.target.value?.length >100 || e.target.value?.length <=0 ){
            setErrorMessage("Character limit should be between 0-100.")
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
                            id="outlined-required"
                            label="Type Name of Other Public Body for Consult"
                            placeholder='Type Other Public Body Name'
                            inputProps={{ "aria-labelledby": "otherPublicBody-label" }}
                            InputLabelProps={{ shrink: true}}
                            variant="outlined"
                            fullWidth
                            value={newConsultBody || ''}
                            onChange={updateConsultBody}
                            error={newConsultBody?.length >100}
                            helperText={errorMessage}
                        />
                    </div>
                </DialogContentText>
            </DialogContent>
            <DialogActions>
                {/* <div className='consult-modal-margin'> */}
                    <button className={`btn-bottom btn-save btnenabled`} onClick={() => saveNewCode(newConsultBody)}>
                        Save
                    </button>
                    <button className="btn-bottom btn-cancel" onClick={() => setOpenModal(false)}>
                        Cancel
                    </button>
                {/* </div> */}
            </DialogActions>
        </Dialog >
        </div >



    )
  }

export default ConsultModal;