import React, { useEffect, useState, useRef } from 'react';
import Container from 'react-bootstrap/Container';
import Navbar from 'react-bootstrap/Navbar';
import logo from "../../../assets/images/logo-banner.png";
import "./Header.scss";
import { useAppSelector } from '../../../hooks/hook';
import UserService from "../../../services/UserService";
import PageLeftOffModal from "../Home/PageLeftOffModal";

interface IHeaderProps {
}

const Header: React.FunctionComponent<IHeaderProps> = (props) => {
  const user = useAppSelector((state: any) => state.user?.userDetail);
  const redactionInfo = useAppSelector((state: any) => state.documents?.redactionInfo);
  const isPageLeftOff = useAppSelector((state: any) => state.documents?.isPageLeftOff);



  const [openPageLeftOffModal, setOpenPageLeftOffModal] = useState(false);

  const showModalAndSignOut = () => {
    console.log("redactionInfo:",redactionInfo);
    if(redactionInfo?.length > 0 && !isPageLeftOff)
      setOpenPageLeftOffModal(true);
    else{
      signout();
    }
    
  }

  const signout = () => {
    setOpenPageLeftOffModal(false);
    localStorage.removeItem('authToken');
    UserService.userLogout();
}

  return (
    <>
    <Navbar bg="#036" variant="dark" className='foiHeader'>
      <Container className="container">
        <Navbar.Brand href="#home">
          <img src={logo} alt="Go to the Government of British Columbia website" style={{ width: '70%' }} />
        </Navbar.Brand>
        <Navbar.Collapse className="justify-content-end">
          <span className="navbar-text foiNavItem">  {user?.name || user?.preferred_username || ""} </span>
          <Navbar.Text>
            <button type="button" className="btn btn-primary signout-btn" onClick={showModalAndSignOut}>Sign Out</button>
          </Navbar.Text>
        </Navbar.Collapse>
      </Container>
    </Navbar>

    <PageLeftOffModal
    openPageLeftOffModal={openPageLeftOffModal}
    setOpenPageLeftOffModal={setOpenPageLeftOffModal}
    signout={signout}
    />
    </>
  );
};

export default Header;
