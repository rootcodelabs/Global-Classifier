import { useTranslation } from 'react-i18next';
import ProgressBar from 'components/ProgressBar';
import { Card, Label } from 'components';
import { TrainingSessionsStatuses } from 'enums/dataModelsEnums';

type TrainingSessionCardProps = {
  modelName: string;
  isLatest: boolean;
  version: string;
  status?: string;
  trainingMessage?: string;
  progress: number;
  platform?: string;
  maturity?: string;
};

const TrainingSessionCard: React.FC<TrainingSessionCardProps> = ({
  modelName,
  version,
  isLatest,
  status,
  trainingMessage,
  progress,
  maturity,
  platform,
}) => {
  const { t } = useTranslation();

  return (
    <Card
      header={
        <div>
          <div className="flex-grid">
          <div> {modelName} </div>
            {isLatest && <Label type="success">{t('global.latest')}</Label>}
            <Label type="success">{version}</Label>
            {platform && <Label type="success">{platform}</Label>}{' '}
            {maturity && <Label type="success">{maturity}</Label>}
            {status === TrainingSessionsStatuses.TRAINING_FAILED_STATUS && <Label type="error">{t('global.failed')}</Label>}
          </div>
        </div>
      }
    >
      <div>
      {(status===TrainingSessionsStatuses.TRAINING_FAILED_STATUS || status===TrainingSessionsStatuses.TRAINING_SUCCESS_STATUS) && progress===100 ? (
        <div className={`text-center ${status===TrainingSessionsStatuses.TRAINING_FAILED_STATUS?'error':''}`}>
         {trainingMessage}
        </div>
      ) : (
        <div>
          <div className="text-center">{status}</div>
          <ProgressBar
            value={progress}
            max={100}
            label={`${progress}%`}
          />
           <div className='text-center'>
         {trainingMessage}
        </div>
        </div>
      )}
      </div>
    </Card>
  );
};

export default TrainingSessionCard;
