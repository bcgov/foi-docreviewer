import { useEffect, useState } from "react";
import TextField from "@mui/material/TextField";
import MenuItem from '@mui/material/MenuItem';
import { useAppSelector } from '../../../hooks/hook';
import { setCurrentLayer } from "../../../actions/documentActions";
import { store } from "../../../services/StoreService";
import { faCirclePlus } from '@fortawesome/free-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import CloseIcon from '@mui/icons-material/Close';
import IconButton from "@mui/material/IconButton";

const LayerDropdown = ({
    ministryrequestid,
    validoipcreviewlayer,
}: any) => {

    const layers = useAppSelector((state: any) => state.documents?.redactionLayers);
    const currentLayer = useAppSelector((state: any) => state.documents?.currentLayer);
    const [layer, setLayer] = useState(1);
    const [openModal, setOpenModal] = useState(false);

    const handleSelect = (e: any) => {
        let selectedlayerid = e.target.value;
        setLayer(selectedlayerid);
        let layer = layers.find((l: any) => l.redactionlayerid === selectedlayerid)
        if (e.target.value > 2 && layer.count === 0) {
            setOpenModal(true);
        } else {
            store.dispatch(setCurrentLayer(layer));
        }
    }

    useEffect(() => {
        setLayer(currentLayer?.redactionlayerid)
    }, [currentLayer])

    const handleModalContinue = (e: any) => {
        setOpenModal(false);
        store.dispatch(setCurrentLayer(layers.find((l: any) => l.redactionlayerid === layer)));
    }

    const handleModalCancel = (e: any) => {
        setOpenModal(false);
        setLayer(currentLayer.redactionlayerid)
    }

    return (
        <>
            <TextField
                sx={{width: 188, "& .MuiInputBase-root": {height: 32}}}
                InputLabelProps={{ shrink: false }}                
                inputProps={{'aria-labelledby': 'layer-dropdown-label'}}
                select
                // size="small"
                value={layer}
                onChange={handleSelect}
                variant="outlined"
            >                
                {layers.map((option: any) => (
                    <MenuItem key={option.redactionlayerid} value={option.redactionlayerid} disabled={option.redactionlayerid === 3 && !validoipcreviewlayer} style={{color: "#808080"}}>
                    {
                    option.redactionlayerid > 2
                        && option.count === 0
                        && option.redactionlayerid !== layer &&
                        <FontAwesomeIcon icon={faCirclePlus} size='1x' style={{marginRight: 8}}/>
                    }
                    {option.description}
                    </MenuItem>
                ))}
            </TextField>

            <div className={`create-layer-dialog`}>
                <Dialog
                    open={openModal}
                    onClose={() => setOpenModal(false)}
                    aria-labelledby="state-change-dialog-title"
                    aria-describedby="state-change-dialog-description"
                    maxWidth={'md'}
                    fullWidth={true}
                >
                    <DialogTitle id="state-change-dialog-title" className="consult-modal-margin">
                        <h2 className="state-change-header">Create New Layer</h2>
                        <IconButton aria-label="close" onClick={() => setOpenModal(false)}>
                            <CloseIcon />
                        </IconButton>
                    </DialogTitle>
                    <DialogContent>
                        <DialogContentText id="consult-modal-description" component={'span'}>
                            <div>Are you sure you want to create a new layer? <br></br>All existing redlines will be carried over and all new redlines will only apply to the new layer.</div>
                        </DialogContentText>
                    </DialogContent>
                    <DialogActions>
                        <button className={`btn-bottom btn-save btnenabled`}
                        onClick={handleModalContinue}>
                            Continue
                        </button>
                        <button className="btn-bottom btn-cancel" onClick={handleModalCancel}>
                            Cancel
                        </button>
                    </DialogActions>
                </Dialog >
            </div >
        </>
    )
}

export default LayerDropdown;