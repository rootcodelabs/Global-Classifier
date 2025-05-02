import { FC } from 'react';
import './unauthorized.scss';
import { useTranslation } from 'react-i18next';

const Unauthorized: FC = () => {
  const { t } = useTranslation();
  return (
    <div className="unauthorized-container">
      <div className="unauthorized-card">
        <h1 className="unauthorized-header">{t('global.unAuthorized')}</h1>
        <p className="unauthorized-message">{t('global.unAuthorizedDesc')}</p>
      </div>
    </div>
  );
};

export default Unauthorized;
