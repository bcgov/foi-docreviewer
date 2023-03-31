import ACTION_CONSTANTS from "../actions/actionConstants";
const initialState = {
  redactionInfo: []
}

const documents = (state = initialState, action:any)=> {
  switch (action.type) {
    case ACTION_CONSTANTS.SET_REDACTION_INFO:
      return {...state, redactionInfo: action.payload};
    case ACTION_CONSTANTS.SET_IS_PAGE_LEFT_OFF:
        return {...state, isPageLeftOff: action.payload};
    case ACTION_CONSTANTS.SET_SECTIONS:
      return {...state, sections: action.payload};
    case ACTION_CONSTANTS.SET_PAGE_FLAGS:
      return {...state, pageFlags: action.payload};
    default:
      return state;
  }
}
export default documents ;
