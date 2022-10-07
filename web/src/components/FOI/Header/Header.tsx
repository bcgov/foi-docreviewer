import * as React from 'react';
import Container from 'react-bootstrap/Container';
import Navbar from 'react-bootstrap/Navbar';
import logo from "../../../assets/images/logo-banner.png";
import "./Header.scss";
import {useDispatch, useSelector} from "react-redux";
import { useAppSelector } from '../../../hooks/hook';
import Nav from 'react-bootstrap/Nav';
import UserService from "../../../services/UserService";

interface IHeaderProps {
}



const Header: React.FunctionComponent<IHeaderProps> = (props) => {



    const user = useAppSelector((state: any) => state.user.userDetail);

    const signout = () => {
        localStorage.removeItem('authToken');
        UserService.userLogout(); 
    }

  return (
    <Navbar bg="#036" variant="dark" className='foiHeader'>
    <Container className="container">
      <Navbar.Brand href="#home">
        <img src={logo} alt="Go to the Government of British Columbia website" style={{width:'70%'}}/>
      </Navbar.Brand>
      <Navbar.Collapse className="justify-content-end">
        <span className="navbar-text foiNavItem">  {user.name || user.preferred_username || ""} </span>
        <Navbar.Text>
            <button type="button" className="btn btn-primary signout-btn" onClick={signout}>Sign Out</button>
        </Navbar.Text>
      </Navbar.Collapse>
    </Container>
  </Navbar>
  );
};

export default Header;
