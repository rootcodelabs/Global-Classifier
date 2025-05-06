import { FC, useEffect, useState } from 'react';
import { Route, Routes, useNavigate, useLocation } from 'react-router-dom';
import { Layout } from 'components';
import useStore from 'store';
import './locale/et_EE';
import UserManagement from 'pages/UserManagement';
import Integrations from 'pages/Integrations';
import DatasetGroups from 'pages/DatasetGroups';
import { useQuery } from '@tanstack/react-query';
import { UserInfo } from 'types/userInfo';
import CreateDatasetGroup from 'pages/DatasetGroups/CreateDatasetGroup';
import StopWords from 'pages/StopWords';
import ValidationSessions from 'pages/ValidationSessions';
import { authQueryKeys } from 'utils/queryKeys';
import { ROLES } from 'enums/roles';
import DataModels from 'pages/DataModels';
import CreateDataModel from 'pages/DataModels/CreateDataModel';
import TrainingSessions from 'pages/TrainingSessions';
import LoadingScreen from 'pages/LoadingScreen/LoadingScreen';
import Unauthorized from 'pages/Unauthorized/unauthorized';
import CorrectedTexts from 'pages/CorrectedTexts';
import TestModel from 'pages/TestModel';

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
      const isAdmin = data.response.authorities.some(
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
            {data?.response.authorities.some(
              (item) => item === ROLES.ROLE_ADMINISTRATOR
            ) ? (
              <>
                <Route path="/user-management" element={<UserManagement />} />
                <Route path="/integration" element={<Integrations />} />
              </>
            ) : (
              <>
                <Route path="/user-management" element={<Unauthorized />} />
                <Route path="/integration" element={<Unauthorized />} />
              </>
            )}
            <Route path="/dataset-groups" element={<DatasetGroups />} />
            <Route
              path="/create-dataset-group"
              element={<CreateDatasetGroup />}
            />
            <Route path="/stop-words" element={<StopWords />} />
            <Route
              path="/validation-sessions"
              element={<ValidationSessions />}
            />{' '}
            <Route path="/data-models" element={<DataModels />} />
            <Route path="/create-data-model" element={<CreateDataModel />} />
            <Route path="/training-sessions" element={<TrainingSessions />} />
            <Route path="/corrected-texts" element={<CorrectedTexts />} />
            <Route path="/test-model" element={<TestModel />} />
          </Route>
        </Routes>
      )}
    </>
  );
};

export default App;
