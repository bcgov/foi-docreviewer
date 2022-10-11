import { useAppSelector } from '../../../hooks/hook';
import "../../../styles.scss";

function Home() {

  const user = useAppSelector((state: any) => state.user.userDetail);

  return (
    <div className="App">
      <header className="app-header">
        <span className="navbar-text" style={{}}> Hi {user.name || user.preferred_username || ""} </span>
      </header>
    </div>
  );
}

export default Home;
