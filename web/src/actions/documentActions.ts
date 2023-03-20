import ACTION_CONSTANTS from "./actionConstants";


export const setRedactionInfo = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_REDACTION_INFO,
        payload:data
    })
}


export const setIsPageLeftOff = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_IS_PAGE_LEFT_OFF,
        payload:data
    })
}

    