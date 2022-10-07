import React from 'react';
import { Helmet } from 'react-helmet';
// import { BrowserRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { HistoryRouter as Router } from "redux-first-history/rr6";

//import './App.css';
import PrivateRoute from "./FOI/PrivateRoute";

function App(props: any) {
  const { store, history } = props;
  const KEYCLOAK_URL = "https://dev.oidc.gov.bc.ca"
  return (
    <div>
        <Helmet>
          {KEYCLOAK_URL?<link rel="preconnect" href={KEYCLOAK_URL} />:null}
        </Helmet>
        <Provider store={store}>
          <Router history={history}>
            
              <PrivateRoute  store={store}/>
               
          </Router>
        </Provider>
      </div>
  );
}

export default App;
