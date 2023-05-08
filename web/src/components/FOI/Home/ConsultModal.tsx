import React, { useState } from 'react'
import Dialog from '@material-ui/core/Dialog';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';
import CloseIcon from '@material-ui/icons/Close';
import IconButton from "@mui/material/IconButton";
import TextField from '@mui/material/TextField';
import _ from 'lodash';


const ConsultModal = ({
    flagId,
    initialPageFlag,
    documentId,
    documentVersion,
    openModal,
    setOpenModal,
    savePageFlags,
    programAreaList,
}: any) => {

    const[newConsultBody,setNewConsultBody]= useState("");
    const[errorMessage, setErrorMessage] = useState("");
    const[selectedPageFlag, setSelectedPageFlag] = useState(_.cloneDeep(initialPageFlag));

    const saveConsult = () => {
        if(newConsultBody?.length >100){
            setErrorMessage("Character limit exceeded.")
        }
        else{
            setOpenModal(false);
            if(_.isEqual(selectedPageFlag.others, initialPageFlag.others)) {
                selectedPageFlag.publicbodyaction = 'add';
            }
                savePageFlags(flagId,
                    selectedPageFlag.page,
                    documentId,
                    documentVersion,
                    selectedPageFlag
                    );
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

    const addNewConsultBody = () => {
        programAreaList.others.push(newConsultBody)
        selectedPageFlag.other.push(newConsultBody)
        setSelectedPageFlag(selectedPageFlag)
        setNewConsultBody("");
    }

    const handleSelectMinistry = (e: any) => {
        let pageFlag = {...selectedPageFlag}
        if (e.target.checked) {
            pageFlag.programareaid.push(Number(e.target.getAttribute('data-programareaid')))
        } else {
            let i = pageFlag.programareaid.findIndex((m: any) => m === Number(e.target.getAttribute('data-programareaid')));
            pageFlag.programareaid.splice(i, 1)
        }
        setSelectedPageFlag(pageFlag)
    }

    const handleSelectCustomMinistry = (e: any) => {
        let pageFlag = {...selectedPageFlag}
        if (e.target.checked) {
            pageFlag.other.push(e.target.getAttribute('data-iaocode'))
        } else {
            let i = pageFlag.other.findIndex((m: any) => m === e.target.getAttribute('data-iaocode'));
            pageFlag.other.splice(i, 1)
        }
        setSelectedPageFlag(pageFlag)
    }

    const isSaveDisabled = () => {
        return _.isEqual(selectedPageFlag, initialPageFlag);
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
                <h2 className="state-change-header">Consultations</h2>
                <IconButton aria-label="close" onClick={() => setOpenModal(false)}>
                    <CloseIcon />
                </IconButton>
            </DialogTitle>
            <DialogContent>
                <DialogContentText id="consult-modal-description" component={'span'}>
                    <div style={{textAlign: "left", marginLeft: 25}}>Select one or more Ministry you with the send the selected page(s) to for consult.</div>
                    <div className="consult-modal-ministries-list">
                        {programAreaList.programareas.map((programArea: any, index: number) => (
                            <label  id={"lbl"+programArea.iaocode}  key={index} className="check-item">
                            <input
                                type="checkbox"
                                className="checkmark"
                                id={"selectchk"+programArea.iaocode}
                                key={programArea.programareaid}
                                data-programareaid={programArea.programareaid}
                                data-iaocode={programArea.iaocode}
                                onChange={handleSelectMinistry}
                                required
                                defaultChecked={selectedPageFlag?.programareaid?.findIndex((e:any) => e === programArea.programareaid) > -1}
                            />
                            <span id={"selectspan"+programArea.iaocode} key={index + 1} className="checkmark"></span>
                            {programArea.iaocode}
                            </label>
                        ))}
                    </div>

                    <div className="consult-modal-ministries-list">
                        {programAreaList.others.map((programArea: any, index: number) => (
                            <label  id={"lbl"+programArea}  key={index} className="check-item other-ministry">
                            <input
                                type="checkbox"
                                className="checkmark"
                                id={"selectchk"+programArea}
                                key={programArea + index}
                                data-iaocode={programArea}
                                onChange={handleSelectCustomMinistry}
                                required
                                defaultChecked={selectedPageFlag?.other?.findIndex((e:any) => e === programArea) > -1}
                            />
                            <span id={"selectspan"+programArea} key={index + 1} className="checkmark"></span>
                            {programArea}
                            </label>
                        ))}
                    </div>

                    <div style={{textAlign: "left", marginLeft: 25}}>If you do not see the name of the Ministry you would like to send for consult above please type it below.</div>
                    <div className={`other-pb-modal-message`}>
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
                        <button disabled={newConsultBody.length === 0} className="add-consult-ministry" onClick={addNewConsultBody}>
                            <div>+</div>
                        </button>
                    </div>
                </DialogContentText>
            </DialogContent>
            <DialogActions>
                <button className={`btn-bottom btn-save btnenabled`} 
                disabled={isSaveDisabled()}
                onClick={saveConsult}>
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