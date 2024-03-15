import axios from "axios";
import UserService from "../../services/UserService";
import { params } from "./types";

export const httpGETRequest = (url: string, data: any, token: any, isBearer = true) => {
  return axios.get(url, {
    params: data,
    timeout: 60000,
    headers: {
      'Access-Control-Allow-Origin' : '*',
      Authorization: isBearer
        ? `Bearer ${token || UserService.getToken()}`
        : token,
    },
  });
};

export const httpGETRequest1 = ({url, data}:params) => {
  return axios.get(url, {
    params: data
  });
};

export const httpOpenGETRequest = ({url}:params) => {
  return axios.get(url);
};

export const httpOpenPOSTRequest = ({url, data}:params) => {
  const axiosConfig = {
    headers: {
        'Content-Type': 'application/json'       
    }
  };
  return axios.post(url, data, axiosConfig);
};

export const httpPOSTRequest = ({url, data, token, isBearer = true}:params) => {
  return axios.post(url, data, {
    headers: {
      Authorization: isBearer
        ? `Bearer ${token || UserService.getToken()}`
        : token,
    },
  });
};

export const httpPUTRequest = ({url, data, token, isBearer = true}:params) => {
  return axios.put(url, data, {
    headers: {
      Authorization: isBearer
        ? `Bearer ${token || UserService.getToken()}`
        : token,
    },
  });
};

export const httpDELETERequest = ({url, token, isBearer = true}:params) => {
  return axios.delete(url, {
    headers: {
      Authorization: isBearer
        ? `Bearer ${token || UserService.getToken()}`
        : token,
    },
  });
};

export const httpOSSPUTRequest = (url: string, data: any, requestOptions: any) => {  
  return axios.put(url, data, requestOptions);
};