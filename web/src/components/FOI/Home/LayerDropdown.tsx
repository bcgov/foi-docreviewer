import { useEffect, useState } from "react";
import TextField from "@mui/material/TextField";
import MenuItem from '@mui/material/MenuItem';
import { useAppSelector } from '../../../hooks/hook';
import { setCurrentLayer, incrementLayerCount } from "../../../actions/documentActions";
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
import { createOipcLayer, savePageFlag } from "../../../apiManager/services/docReviewerService";
import {createPageFlagPayload} from "./utils";

const LayerDropdown = ({
    ministryrequestid,
    validoipcreviewlayer,
    requestInfo
}: any) => {

    const layers = useAppSelector((state: any) => state.documents?.redactionLayers);
    const currentLayer = useAppSelector((state: any) => state.documents?.currentLayer);
    const [layer, setLayer] = useState(1);
    const [openModal, setOpenModal] = useState(false);

    const handleSelect = (e: any) => {
        let selectedlayerid = e.target.value;
        setLayer(selectedlayerid);
        let layer = layers.find((l: any) => l.redactionlayerid === selectedlayerid)
        // console.log("Selected layer:",layer)
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
        const successCallback = () => {
            store.dispatch(setCurrentLayer(layers.find((l: any) => l.redactionlayerid === layer)));
        }
        if (layers.find((l: any) => l.redactionlayerid === layer).name === 'OIPC') {
            createOipcLayer(ministryrequestid, successCallback);
        }
        else if( layers.find((l: any) => l.redactionlayerid === layer).name === 'Open Info' ){
            store.dispatch(incrementLayerCount(layer) as any);
            /**saving pageflag value- {flagid: 0, page: 0, deleted: false} will 
             * get saved as {} in B.E. This is to make the OI layer persist  & increment the layer count value
             * as layer count is calculated based on the pageflag row count for request in db.
             */
            let payload = {
                documentpageflags: [] as Array<{
                  documentid: number;
                  version: number;
                  pageflags: object;
                  redactionlayerid: number;
                }>,
              };
              payload.documentpageflags.push({
                documentid: 1,
                version: 1,
                pageflags: [{flagid: 0, page: 0, deleted: false}],
                redactionlayerid: layer,
              });
            savePageFlag(
                ministryrequestid,
                0,
                (data: any) => {
                    if(data.status != true){
                        console.log("success")
                    }
                },
                (error: any) => console.log(error),
                payload
              );
            successCallback();
        }
    }

    const handleModalCancel = (e: any) => {
        setOpenModal(false);
        setLayer(currentLayer.redactionlayerid)
    }

    const isLayerDisabled = (option: any) => {

        if (option.name === 'OIPC' && !validoipcreviewlayer)
            return true;
        /**To Do : After Aman's work get the proper state field and value 
         * and update the condition for OI
         */
        // else if(option.name === 'Open Info' && !['Publication Review'].includes(requestInfo.requeststate))
        //     return true;
        return false;

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
                    <MenuItem key={option.redactionlayerid} value={option.redactionlayerid} disabled={isLayerDisabled(option)} 
                        style={{color: "#000000"}}>
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