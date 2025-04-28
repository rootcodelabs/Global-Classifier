import { FC } from 'react';
import { Outlet } from 'react-router-dom';
import useStore from 'store';
import './Layout.scss';
import { useToast } from '../../hooks/useToast';
import Header from 'components/Header';
import MainNavigation from 'components/MainNavigation';

const Layout: FC = () => {
  return (
    <div className="layout">
      <MainNavigation />
      <div className="layout__wrapper">
        <Header toastContext={useToast()} user={useStore.getState().userInfo} />
        <main className="layout__main">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
