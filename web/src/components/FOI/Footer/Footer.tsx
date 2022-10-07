import * as React from 'react';
import Container from 'react-bootstrap/Container';
import Navbar from 'react-bootstrap/Navbar';
import "./Footer.scss";

interface IFooterProps {
}

const Footer: React.FunctionComponent<IFooterProps> = (props) => {
  return (
    <Navbar fixed="bottom" bg="#036" variant="dark">
    <Container className="container">
      <Navbar.Brand>
      </Navbar.Brand>
    </Container>
  </Navbar>
  );
};

export default Footer;
