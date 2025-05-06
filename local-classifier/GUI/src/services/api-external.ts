import axios, { AxiosError } from 'axios';

const instance = axios.create({
  baseURL: import.meta.env.REACT_APP_EXTERNAL_API_URL,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'multipart/form-data',
  },
  withCredentials: true,
});

instance.interceptors.response.use(
  (axiosResponse) => {
    return axiosResponse;
  },
  (error: AxiosError) => {
    return Promise.reject(new Error(error.message));
  }
);

instance.interceptors.request.use(
  (axiosRequest) => {
    return axiosRequest;
  },
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // To be added: handle unauthorized requests
    }
    if (error.response?.status === 403) {
      // To be added: handle unauthorized requests
    }
    return Promise.reject(new Error(error.message));
  }
);

export default instance;
