import { useTranslation } from 'react-i18next';
import ProgressBar from 'components/ProgressBar';
import { Card, Label } from 'components';
import { ValidationSessionsStatuses } from 'enums/datasetEnums';
import './ValidationSessionCard.scss';

type ValidationSessionCardProps = {
  dgName: string;
  version: string;
  isLatest: boolean;
  status?: string;
  validationMessage?: string;
  progress: number;
};

const ValidationSessionCard: React.FC<ValidationSessionCardProps> = ({
  dgName,
  version,
  isLatest,
  status,
  validationMessage,
  progress,
}) => {
  const { t } = useTranslation();

  return (
    <Card
      header={
        <div className="validationHeader">
          {dgName} <Label type="success">{version}</Label>
            {isLatest && <Label type="success">{t('global.latest')}</Label>}
            {status === ValidationSessionsStatuses.VALIDATION_FAILED_STATUS && (
              <Label type="error">{t('global.failed')}</Label>
            )}
        </div>
      }
    >
      <div>
        {(status === ValidationSessionsStatuses.VALIDATION_FAILED_STATUS ||
          status === ValidationSessionsStatuses.VALIDATION_SUCCESS_STATUS) &&
        progress === 100 ? (
          <div
            className={`text-center ${
              status === ValidationSessionsStatuses.VALIDATION_FAILED_STATUS
                ? 'error'
                : ''
            }`}
          >
            {validationMessage}
          </div>
        ) : (
          <div>
            <div className="text-center">{status}</div>
            <ProgressBar value={progress} max={100} label={`${progress}%`} />
            <div className="text-center">{validationMessage}</div>
          </div>
        )}
      </div>
    </Card>
  );
};

export default ValidationSessionCard;
