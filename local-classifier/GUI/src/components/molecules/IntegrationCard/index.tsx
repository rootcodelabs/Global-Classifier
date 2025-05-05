import {
  FC,
  PropsWithChildren,
  ReactNode,
  useState,
} from 'react';
import './IntegrationCard.scss';
import { useTranslation } from 'react-i18next';
import { Card, Switch } from 'components';
import {
  INTEGRATION_MODALS
} from 'enums/integrationEnums';
import IntegrationModals from '../IntegrationModals/IntegrationModals';

type IntegrationCardProps = {
  logo?: ReactNode;
  channel?: string;
  channelDescription?: string;
  isActive?: boolean;
};

const IntegrationCard: FC<PropsWithChildren<IntegrationCardProps>> = ({
  logo,
  channel,
  channelDescription,
  isActive,
}) => {
  const { t } = useTranslation();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalType, setModalType] = useState<INTEGRATION_MODALS>(
    INTEGRATION_MODALS.NULL
  );

  const renderStatusIndicators = () => {
    return (
      <span className="status">
        <span className={`dot ${isActive ? 'green' : 'grey'}`}></span>
        <div>
          {isActive
            ? t('integration.connected')
            : t('integration.disconnected')}
        </div>
      </span>
    );
  };

  const onSelect = () => {
    if (isActive) {
      setModalType(INTEGRATION_MODALS.DISCONNECT_CONFIRMATION);
    } else {
      setModalType(INTEGRATION_MODALS.CONNECT_CONFIRMATION);
    }
    setIsModalOpen(true);
  };

  return (
    <div>
      <Card isFullWidth={true}>
        <div className="card_header">
          <div className="logo">{logo}</div>
          <div className="title">
            <h2>{channel}</h2>
            <p>{channelDescription}</p>
          </div>
          <div className="toggle-switch">
            <div className="switch-wrapper">
              <Switch label="" checked={isActive} onCheckedChange={onSelect} />
            </div>
            <div className="footer-container-wrapper">
              <div className="footer_container">
                <div className="status-indicators">
                  {renderStatusIndicators()}
                </div>
              </div>
            </div>{' '}
          </div>
        </div>
      </Card>

      <IntegrationModals
        modalType={modalType}
        isModalOpen={isModalOpen}
        setIsModalOpen={setIsModalOpen}
        setModalType={setModalType}
        channel={channel}
      />
    </div>
  );
};

export default IntegrationCard;
