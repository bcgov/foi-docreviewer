import React, {useEffect} from 'react';
import Home from './Home/Home';
import UserService from '../../services/UserService';
import {setUserAuth} from '../../actions/UserActions';
import { useAppSelector, useAppDispatch } from '../../hooks/hook'

function PrivateRoute(props: any) {
    const dispatch = useAppDispatch();
    const isAuth = useAppSelector((state: any) => state.user.isAuthenticated); 
    useEffect(()=>{
        console.log('authenticate')
        if(props.store){
        UserService.initKeycloak(props.store, (_err: any, res: any) => {
            console.log(`error = ${JSON.stringify(_err)}`)
            dispatch(setUserAuth(res.authenticated));
        });
        }
    },[props.store, dispatch]);

    const userDetail = useAppSelector((state: any) => state.user.userDetail);
    console.log(userDetail)
  return (
    <Home />
  );
}

export default PrivateRoute;
