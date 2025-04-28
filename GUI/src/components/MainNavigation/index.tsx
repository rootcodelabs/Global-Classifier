import { FC, MouseEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, useLocation } from 'react-router-dom';
import { MdKeyboardArrowDown } from 'react-icons/md';
import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import { Icon } from 'components';
import type { MenuItem } from 'types/mainNavigation';
import './MainNavigation.scss';
import apiDev from 'services/api-dev';
import { userManagementEndpoints } from 'utils/endpoints';
import { integrationQueryKeys } from 'utils/queryKeys';
import { ROLES } from 'enums/roles';
import UserIcon from 'assets/UserIcon';
import IntegrationIcon from 'assets/IntegrationIcon';
import DatabaseIcon from 'assets/DatabaseIcon';
import DataModelsIcon from 'assets/DataModelsIcon';
import IncomingTextsIcon from 'assets/IncomingTextsIcon';
import TestModelIcon from 'assets/TestModelIcon';

const MainNavigation: FC = () => {
  const { t } = useTranslation();
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);

  const items = [
    {
      id: 'userManagement',
      label: t('menu.userManagement'),
      path: '/user-management',
      icon: <UserIcon />,
    },
    {
      id: 'integration',
      label: t('menu.integration'),
      path: 'integration',
      icon: <IntegrationIcon />,
    },
    {
      id: 'datasets',
      label: t('menu.datasets'),
      path: '#',
      icon: <DatabaseIcon />,
      children: [
        {
          label: t('menu.datasetGroups'),
          path: 'dataset-groups',
        },
        {
          label: t('menu.validationSessions'),
          path: 'validation-sessions',
        },
        {
          label: t('menu.stopWords'),
          path: 'stop-words',
        },
      ],
    },
    {
      id: 'dataModels',
      label: t('menu.dataModels'),
      path: '#',
      icon: <DataModelsIcon />,
      children: [
        {
          label: t('menu.models'),
          path: '/data-models',
        },
        {
          label: t('menu.trainingSessions'),
          path: 'training-sessions',
        },
      ],
    },
    {
      id: 'correctedTexts',
      label: t('menu.correctedTexts'),
      path: '/corrected-texts',
      icon: <IncomingTextsIcon />,
    },
    {
      id: 'testModel',
      label: t('menu.testModel'),
      path: '/test-model',
      icon: <TestModelIcon />,
    },
  ];

  const filterItemsByRole = (role: string[], items: MenuItem[]) => {
    return items?.filter((item) => {
      if (role.includes(ROLES.ROLE_ADMINISTRATOR)) return item?.id;
      else if (role.includes(ROLES.ROLE_MODEL_TRAINER))
        return item?.id !== 'userManagement' && item?.id !== 'integration';
      else return false;
    });
  };

  useQuery(integrationQueryKeys.USER_ROLES(), {
    queryFn: async () => {
      const res = await apiDev.get(userManagementEndpoints.FETCH_USER_ROLES());
      return res?.data?.response;
    },
    onSuccess: (res) => {
      const roles = res;
      const filteredItems = filterItemsByRole(roles, items);
      setMenuItems(filteredItems);
    },
    onError: (error) => {
      console.error('Error fetching user roles:', error);
    },
  });
  const location = useLocation();
  const [navCollapsed, setNavCollapsed] = useState(false);

  const handleNavToggle = (event: MouseEvent) => {
    const isExpanded =
      event?.currentTarget?.getAttribute('aria-expanded') === 'true';
    event?.currentTarget?.setAttribute(
      'aria-expanded',
      isExpanded ? 'false' : 'true'
    );
  };

  const renderMenuTree = (menuItems: MenuItem[]) => {
    return menuItems?.map((menuItem) => (
      <li key={menuItem?.label}>
        {menuItem?.children ? (
          <div>
            <button
              className={clsx('nav__toggle', {
                'nav__toggle--icon': !!menuItem.id,
              })}
              aria-expanded={
                menuItem?.path && location?.pathname?.includes(menuItem?.path)
                  ? 'true'
                  : 'false'
              }
              onClick={handleNavToggle}
            >
              <Icon icon={menuItem?.icon} />
              <span
                style={{
                  marginLeft: '10px',
                }}
              >
                {menuItem?.label}
              </span>
              <Icon icon={<MdKeyboardArrowDown />} />
            </button>
            <ul className="nav__submenu">
              {renderMenuTree(menuItem?.children)}
            </ul>
          </div>
        ) : (
          <NavLink to={menuItem?.path ?? '#'}>
            {' '}
            <Icon
              icon={menuItem?.icon}
              style={{
                marginRight: '10px',
              }}
            />
            {menuItem?.label}
          </NavLink>
        )}
      </li>
    ));
  };

  if (!menuItems) return null;

  return (
    <nav className={clsx('nav', { 'nav--collapsed': navCollapsed })}>
      <ul className="nav__menu">{renderMenuTree(menuItems)}</ul>
    </nav>
  );
};

export default MainNavigation;