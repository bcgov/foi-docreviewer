import { useEffect, useState } from "react";
import TextField from "@mui/material/TextField";
import MenuItem from '@mui/material/MenuItem';
import { useAppSelector } from '../../../hooks/hook';
import { setCurrentLayer } from "../../../actions/documentActions";
import { store } from "../../../services/StoreService";
import { fetchRedactionLayerMasterData } from '../../../apiManager/services/docReviewerService';

const LayerDropdown = ({

}: any) => {

    const layers = useAppSelector((state: any) => state.documents?.redactionLayers);
    const currentLayer = useAppSelector((state: any) => state.documents?.currentLayer);
    const [layer, setLayer] = useState(1);

    useEffect(() => {
        fetchRedactionLayerMasterData(
            (data: any) => {
                store.dispatch(setCurrentLayer(data.find((l: any) => l.name === "Redline")))
            },
            (error: any) => console.log(error)
        );
    }, []);

    useEffect(() => {
        setLayer(currentLayer?.redactionlayerid)
    }, [currentLayer]);

    const handleSelect = (e: any) => {    
        store.dispatch(setCurrentLayer(layers.find((l: any) => l.redactionlayerid === e.target.value)));
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
                    <MenuItem key={option.redactionlayerid} value={option.redactionlayerid}>
                    {option.description}
                    </MenuItem>
                ))}
            </TextField>
        </>
    )
}

export default LayerDropdown;