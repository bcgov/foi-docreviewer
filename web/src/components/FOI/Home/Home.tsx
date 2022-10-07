import React from 'react';
import {useDispatch, useSelector} from "react-redux";
import UserService from "../../../services/userService";
import { useAppSelector, useAppDispatch } from '../../../hooks/hook';
import "../../FOI/App.scss";

function Home() {

  // const isAuthenticated = useSelector((state) => state.user.isAuthenticated);
  // const user = useSelector((state) => state.user.userDetail);
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
