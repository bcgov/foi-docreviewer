import React, { useEffect } from 'react';
import Home from './Home/Home';
import UserService from '../../services/UserService';
import { setUserAuth } from '../../actions/userActions';
import { useAppSelector, useAppDispatch } from '../../hooks/hook';
import Header from "./Header/Header";
import Footer from "./Footer/Footer";
import Container from 'react-bootstrap/Container';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';

function PrivateRoute(props: any) {
  const dispatch = useAppDispatch();
  useEffect(() => {
    if (props.store) {
      UserService.initKeycloak(props.store, (_err: any, res: any) => {
        dispatch(setUserAuth(res.authenticated));
      });
    }
  }, [props.store, dispatch]);

  const isAuth = useAppSelector((state: any) => state.user.isAuthenticated);
  const userDetail = useAppSelector((state: any) => state.user.userDetail);
  return (
    <>
      {isAuth ?
        <><Header />
          <Container fluid="lg">
            <Row>
              <Col><Home /></Col>
            </Row>
          </Container>
          <Footer /></> : null}
    </>
  );
}

export default PrivateRoute;
