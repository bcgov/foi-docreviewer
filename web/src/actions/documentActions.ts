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

export const setSections = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_SECTIONS,
        payload:data
    })
}

export const setPageFlags = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_PAGE_FLAGS,
        payload:data
    })
}

export const setDocumentList = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_DOCUMENT_LIST,
        payload:data
    })
}

export const setKeywords = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_KEYWORDS,
        payload:data
    })
}

export const setRequestInfo = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_REQUEST_INFO,
        payload:data
    })
}

export const setRequestStatus = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_REQUEST_STATUS,
        payload:data
    })
}

export const setRequestNumber = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_REQUEST_NUMBER,
        payload:data
    })
}

export const setRedactionLayers = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_REDACTION_LAYERS,
        payload:data
    })
}

export const setCurrentLayer = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_CURRENT_LAYER,
        payload:data
    })
}

export const incrementLayerCount = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.INC_REDACTION_LAYER,
        payload:data
    })
}