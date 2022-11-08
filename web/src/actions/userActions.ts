import ACTION_CONSTANTS from './actionConstants'

export const setCurrentPage = (data: any) => (dispatch: any) => {
  dispatch({
    type: ACTION_CONSTANTS.SET_CURRENT_PAGE,
    payload: data
  })
}

export const setUserAuth = (data: any) => (dispatch: any) => {
  dispatch({
    type: ACTION_CONSTANTS.SET_USER_AUTHENTICATION,
    payload: data
  })
}

export const setUserToken = (data: any) => (dispatch: any) => {
  dispatch({
    type: ACTION_CONSTANTS.SET_USER_TOKEN,
    payload: data
  })
}

export const setUserRole = (data: any) => (dispatch: any) => {
  dispatch({
    type: ACTION_CONSTANTS.SET_USER_ROLES,
    payload: data
  })
}
export const setUserDetails = (data: any) => (dispatch: any) => {
  dispatch({
    type: ACTION_CONSTANTS.SET_USER_DETAILS,
    payload: data
  })
}

export const serviceActionError = (data: any) => (dispatch: any) => {
  dispatch({
    type: ACTION_CONSTANTS.ERROR,
    payload: 'Error Handling Message'
  })
}

export const setUserAuthorization = (data: any) => (dispatch: any) => {
  dispatch({
    type: ACTION_CONSTANTS.SET_USER_AUTHORIZATION,
    payload: data
  })
}
