import ACTION_CONSTANTS from "../actions/actionConstants";
const initialState = {
  redactionInfo: [],
  redactionLayers: [],
  currentLayer: {
    "redactionlayerid": 1,
    "name": "Redline",
    "description": "Redline",
    // "sortorder": 1,
    // "count": 0
  },
  allPublicBodies: [],
}

const documents = (state = initialState, action:any)=> {
  switch (action.type) {
    case ACTION_CONSTANTS.SET_REDACTION_INFO:
      return {...state, redactionInfo: action.payload};
    case ACTION_CONSTANTS.SET_IS_PAGE_LEFT_OFF:
        return {...state, isPageLeftOff: action.payload};
    case ACTION_CONSTANTS.SET_SECTIONS:
      return {...state, sections: action.payload};
    case ACTION_CONSTANTS.SET_REQUEST_NUMBER:
        return {...state, requestnumber: action.payload};  
    // case ACTION_CONSTANTS.SET_PAGE_FLAGS:
    //   return {...state, pageFlags: action.payload};
    case ACTION_CONSTANTS.SET_DOCUMENT_LIST:
      return {...state, documentList: action.payload};
    case ACTION_CONSTANTS.SET_KEYWORDS:
        return {...state, keywords: action.payload};
    case ACTION_CONSTANTS.SET_REQUEST_INFO:
        return {...state, requestinfo: action.payload};
    case ACTION_CONSTANTS.SET_REQUEST_STATUS:
        return {...state, requeststatus: action.payload};
    case ACTION_CONSTANTS.SET_REDACTION_LAYERS:
        return {...state, redactionLayers: action.payload};
    case ACTION_CONSTANTS.SET_CURRENT_LAYER:
        return {...state, currentLayer: action.payload};
    case ACTION_CONSTANTS.INC_REDACTION_LAYER:
        let layer: any = state.redactionLayers.find((l: any) => l.redactionlayerid === action.payload);
        layer.count++;
        return {...state, redactionLayers: state.redactionLayers };
    case ACTION_CONSTANTS.SET_DELETED_PAGES:
        return {...state, deletedDocPages: action.payload};
    case ACTION_CONSTANTS.SET_PUBLIC_BODIES:
      return {...state, allPublicBodies: action.payload};
    case ACTION_CONSTANTS.FOI_PERSONAL_SECTIONS:
      return { ...state, foiPersonalSections: action.payload };
    case ACTION_CONSTANTS.FOI_PERSONAL_PEOPLE:
      return { ...state, foiPersonalPeople: action.payload };
    case ACTION_CONSTANTS.FOI_PERSONAL_FILETYPES:
      return { ...state, foiPersonalFiletypes: action.payload };
    case ACTION_CONSTANTS.FOI_PERSONAL_VOLUMES:
      return { ...state, foiPersonalVolumes: action.payload };
    case ACTION_CONSTANTS.FOI_SOLR_PII_VALUES:
        return { ...state, foiPIIValues: action.payload };
    case ACTION_CONSTANTS.FOI_SOLR_AUTH:
          return { ...state, foisolrauth: action.payload };      
    default:
      return state;
  }
}
export default documents ;
