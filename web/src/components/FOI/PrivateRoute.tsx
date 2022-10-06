import React, {useEffect} from 'react';
import Home from './Home/Home';
import UserService from '../../services/userService';
import {setUserAuth} from '../../actions/userActions';
import { useAppSelector, useAppDispatch } from '../../hooks/hook'

function PrivateRoute(props: any) {
    const dispatch = useAppDispatch();     
    useEffect(()=>{
        console.log('authenticate')
        if(props.store){
        UserService.initKeycloak(props.store, (_err: any, res: any) => {
            console.log(`error = ${JSON.stringify(_err)}`)
            dispatch(setUserAuth(res.authenticated));
        });
        }
    },[props.store, dispatch]);

    const isAuth = useAppSelector((state: any) => state.user.isAuthenticated);
    const userDetail = useAppSelector((state: any) => state.user.userDetail);
    console.log(userDetail)
  return (
    <>
      {isAuth ? 
      <Home /> : null }
    </>
  );
}

export default PrivateRoute;
