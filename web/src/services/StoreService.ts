import thunk from "redux-thunk";
import { createBrowserHistory } from "history";
import { createReduxHistoryContext } from "redux-first-history";
import { combineReducers } from "redux";
import { configureStore } from "@reduxjs/toolkit";
import user from "../modules/userDetailReducer";
import documents from "../modules/documentReducer";

const {
  createReduxHistory,
  routerMiddleware,
  routerReducer
} = createReduxHistoryContext({ history: createBrowserHistory() });

export const store = configureStore({
  reducer: combineReducers({
    user,
    documents,
    router: routerReducer
  }),
  middleware: [thunk, routerMiddleware]
});

export const history = createReduxHistory(store);

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>
// Inferred type: {posts: PostsState, comments: CommentsState, users: UsersState}
export type AppDispatch = typeof store.dispatch



