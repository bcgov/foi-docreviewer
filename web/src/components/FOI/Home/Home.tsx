import { useAppSelector } from '../../../hooks/hook';
import "../../FOI/App.scss";

function Home() {

  const isAuthenticated = useAppSelector((state: any) => state.user.isAuthenticated);
  const user = useAppSelector((state: any) => state.user.userDetail);

  return (
    <div className="App">
      <header className="App-header">
        <span className="navbar-text" style={{}}> Hi {user.name || user.preferred_username || ""} </span>
      </header>
    </div>
  );
}

export default Home;
