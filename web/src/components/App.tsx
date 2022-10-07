
import { Helmet } from 'react-helmet';
import { Provider } from 'react-redux';
import { HistoryRouter as Router } from "redux-first-history/rr6";
import PrivateRoute from "./FOI/PrivateRoute";
import { KEYCLOAK_URL } from '../constants/constants'

function App(props: any) {
  const { store, history } = props;
  return (
    <div>
      <Helmet>
        {KEYCLOAK_URL ? <link rel="preconnect" href={KEYCLOAK_URL} /> : null}
      </Helmet>
      <Provider store={store}>
        <Router history={history}>

          <PrivateRoute store={store} />

        </Router>
      </Provider>
    </div>
  );
}

export default App;
