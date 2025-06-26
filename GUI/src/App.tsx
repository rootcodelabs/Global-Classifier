import { FC, useEffect, useState } from 'react';
import { Route, Routes, useNavigate, useLocation } from 'react-router-dom';
import { Layout } from 'components';
import useStore from 'store';
import UserManagement from 'pages/UserManagement';
import { useQuery } from '@tanstack/react-query';
import { UserInfo } from 'types/userInfo';
import { authQueryKeys } from 'utils/queryKeys';
import { ROLES } from 'enums/roles';
import LoadingScreen from 'pages/LoadingScreen/LoadingScreen';
import Unauthorized from 'pages/Unauthorized/unauthorized';
import IntegratedAgencies from 'pages/IntegratedAgencies';
import Datasets from 'pages/Datasets';
import ViewDataset from 'pages/ViewDataset';
import DataModels from 'pages/DataModels';

const App: FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [hasRedirected, setHasRedirected] = useState(false);
  const { isLoading, data } = useQuery({
    queryKey: authQueryKeys.USER_DETAILS(),

    onSuccess: (res: { response: UserInfo }) => {
      localStorage.setItem('exp', res.response.JWTExpirationTimestamp);
      useStore.getState().setUserInfo(res.response);
    },
  });

  useEffect(() => {
    if (!isLoading && data && !hasRedirected && location.pathname === '/') {
      const isAdmin = (data as { response: UserInfo }).response.authorities.some(
        (item) => item === ROLES.ROLE_ADMINISTRATOR
      );
      if (isAdmin) {
        navigate('/user-management');
      } else {
        navigate('/dataset-groups');
      }
      setHasRedirected(true);
    }
  }, [isLoading, data, navigate, hasRedirected, location.pathname]);

  return (
    <>
      {isLoading ? (
        <LoadingScreen />
      ) : (
        <Routes>
          <Route element={<Layout />}>
            {(data as { response: UserInfo })?.response.authorities.some(
              (item) => item === ROLES.ROLE_ADMINISTRATOR
            ) ? (
              <>
                <Route path="/user-management" element={<UserManagement />} />
                <Route path="/integrated-agencies" element={<IntegratedAgencies />} />

              </>
            ) : (
              <>
                <Route path="/user-management" element={<Unauthorized />} />
              </>
            )}
            <Route path="/datasets" element={<Datasets />} />
            <Route path="/view-dataset" element={<ViewDataset />} />
            <Route path="/data-models" element={<DataModels />} />

          </Route>
        </Routes>
      )}
    </>
  );
};

export default App;
