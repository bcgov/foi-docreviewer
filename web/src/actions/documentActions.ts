import ACTION_CONSTANTS from "./actionConstants";

type PublicBody = {
    bcgovcode: string,
    iaocode: string,
    name: string,
    isactive: boolean,
    type: string,
    programareaid: number
}

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

// export const setPageFlags = (data: any) => (dispatch:any) =>{
//     dispatch({
//         type:ACTION_CONSTANTS.SET_PAGE_FLAGS,
//         payload:data
//     })
// }

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

export const setDeletedPages = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_DELETED_PAGES,
        payload:data
    })
}

export const setPublicBodies = (data: PublicBody[]) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.SET_PUBLIC_BODIES,
        payload:data
    })
}

export const setFOIPersonalSections = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.FOI_PERSONAL_SECTIONS,
        payload:data      
    })
  }
  export const setFOIPersonalPeople = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.FOI_PERSONAL_PEOPLE,
        payload:data      
    })
  }
  export const setFOIPersonalFiletypes = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.FOI_PERSONAL_FILETYPES,
        payload:data      
    })
  }
  export const setFOIPersonalVolumes = (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.FOI_PERSONAL_VOLUMES,
        payload:data      
    })
  }

  export const setSOLRAuth =  (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.FOI_SOLR_AUTH,
        payload:data      
    })
  }

  export const setPIIJSONList =  (data: any) => (dispatch:any) =>{
    dispatch({
        type:ACTION_CONSTANTS.FOI_SOLR_PII_VALUES,
        payload:data      
    })
  }