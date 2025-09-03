import { FC, PropsWithChildren } from 'react';
import Button from 'components/Button';
import Label from 'components/Label';
import { useDialog } from 'hooks/useDialog';
import './DataModel.scss';
import { Maturity, TrainingStatus } from 'enums/dataModelsEnums';
import { useTranslation } from 'react-i18next';
import { TrainingResultsResponse } from 'types/dataModels';
import { formatDate } from 'utils/commonUtilts';
import { useNavigate } from 'react-router-dom';
import ModelResults from '../TrainingResults';

type DataModelCardProps = {
  modelId: number | string;
  dataModelName?: string;
  datasetVersion?: string;
  version?: string;
  isLatest?: boolean;
  lastTrained?: string;
  trainingStatus?: string;
  modelStatus?: string;
  deploymentEnv?: string;
  results?: TrainingResultsResponse | null;
};

const DataModelCard: FC<PropsWithChildren<DataModelCardProps>> = ({
  modelId,
  dataModelName,
  datasetVersion,
  version,
  isLatest,
  lastTrained,
  trainingStatus,
  modelStatus,
  deploymentEnv,
  results,

}) => {
  const { open, close } = useDialog();
  const { t } = useTranslation();
  const navigate = useNavigate();

  let trainingResults = null;
  if (results?.value) {
    try {
      trainingResults = JSON.parse(results.value);
    } catch (error) {
      console.error("Failed to parse training results:", error);
    }
  }

  const configureDataModel = () => {
    navigate(`/configure-datamodel?datamodelId=${modelId}`);
  }

  const renderTrainingStatus = (status: string | undefined) => {
    if (status === TrainingStatus.RETRAINING_NEEDED) {
      return (
        <Label type="warning">
          {t('dataModels.trainingStatus.retrainingNeeded') ?? ''}
        </Label>
      );
    } else if (status === TrainingStatus.TRAINED) {
      return (
        <Label type="success">
          {t('dataModels.trainingStatus.trained') ?? ''}
        </Label>
      );
    } else if (status === TrainingStatus.TRAINING_INPROGRESS || status === TrainingStatus.INITIATING_TRAINING) {
      return (
        <Label type="info">
          {t('dataModels.trainingStatus.initiatingTraining') ?? ''}
        </Label>
      );
    } else if (status === TrainingStatus.FAILED) {
      return (
        <Label type="error">
          {t('dataModels.trainingStatus.trainingFailed') ?? ''}
        </Label>
      );
    } else if (status === TrainingStatus.NOT_TRAINED) {
      return <Label>{t('dataModels.trainingStatus.notTrained') ?? ''}</Label>;
    }
  };

  const renderMaturityLabel = (status: string | undefined) => {
    if (status === Maturity.UNDEPLOYED) {
      return (
        <Label type="warning">
          {t('dataModels.maturity.undeployed') ?? ''}
        </Label>
      );
    } else if (status === Maturity.PRODUCTION) {
      return (
        <Label type="success">
          {t('dataModels.maturity.production') ?? ''}
        </Label>
      );
    } else if (status === Maturity.TESTING) {
      return (
        <Label type="info">{t('dataModels.maturity.testing') ?? ''}</Label>
      );
    }
  };

  return (
    <div>
      <div className="dataset-group-card">
        <div className="flex space-between">
          <p>{dataModelName}</p>
          <Label>{version}</Label>
        </div>

        <div className="py-3">
          <div
            className='flex'
          >
            <div> {`${t('dataModels.dataModelCard.datasetVersion') ?? ''} `}</div>
            <div> {`: ${datasetVersion}`}</div>
          </div>
          <p>
            {t('dataModels.dataModelCard.lastTrained') ?? ''}:{' '}
            {lastTrained ? formatDate(new Date(lastTrained), 'D.M.yy-H:m'):"N/A"}
          </p>
        </div>
        <div className="flex" style={{ flexWrap: 'wrap', gap: '5px' }}>
          {renderTrainingStatus(trainingStatus)}
          <Label type="info">{modelStatus}</Label>
          {isLatest && <Label type="success">
            {t('global.latest') ?? ''}
          </Label>}
          {renderMaturityLabel(deploymentEnv)}
        </div>

        <div className="label-row flex-grid mt-3">
          <Button
            appearance="secondary"
            size="s"
            onClick={() => {
              open({
                title: t('dataModels.trainingResults.title') ?? '',
                footer: (
                  <Button onClick={close}>{t('global.close') ?? ''}</Button>
                ),
                size: 'large',
                content: (
                  <div className='training-results-container'>
                    {results ? (
                      <ModelResults models={trainingResults} />
                    ) : (
                      <div className="text-center">
                        {t('dataModels.trainingResults.noResults') ?? ''}
                      </div>
                    )}
                  </div>
                ),
              });
            }}
          >
            {t('dataModels.trainingResults.viewResults') ?? ''}
          </Button>
          <Button
            appearance="primary"
            size="s"
            onClick={configureDataModel}
          >
            {t('datasets.datasetCard.settings') ?? ''}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DataModelCard;