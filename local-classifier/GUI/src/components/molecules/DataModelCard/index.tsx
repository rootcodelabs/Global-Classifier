import { FC, PropsWithChildren } from 'react';
import Button from 'components/Button';
import Label from 'components/Label';
import { useDialog } from 'hooks/useDialog';
import './DataModel.scss';
import { Maturity, TrainingStatus } from 'enums/dataModelsEnums';
import Card from 'components/Card';
import { useTranslation } from 'react-i18next';
import { TrainingResults } from 'types/dataModels';
import { formatDate } from 'utils/commonUtilts';

type DataModelCardProps = {
  modelId: number;
  dataModelName?: string;
  datasetGroupName?: string;
  version?: string;
  isLatest?: boolean;
  dgVersion?: string;
  lastTrained?: string;
  trainingStatus?: string;
  platform?: string;
  maturity?: string;
  setId: React.Dispatch<React.SetStateAction<number>>;
  setView: React.Dispatch<React.SetStateAction<'individual' | 'list'>>;
  results: string | null;
};

const DataModelCard: FC<PropsWithChildren<DataModelCardProps>> = ({
  modelId,
  dataModelName,
  datasetGroupName,
  version,
  isLatest,
  dgVersion,
  lastTrained,
  trainingStatus,
  platform,
  maturity,
  results,
  setId,
  setView,
}) => {
  const { open, close } = useDialog();
  const { t } = useTranslation();
  const resultsJsonData: TrainingResults = JSON.parse(results ?? '{}');

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
    } else if (status === TrainingStatus.TRAINING_INPROGRESS) {
      return (
        <Label type="info">
          {t('dataModels.trainingStatus.trainingInProgress') ?? ''}
        </Label>
      );
    } else if (status === TrainingStatus.UNTRAINABLE) {
      return (
        <Label type="error">
          {t('dataModels.trainingStatus.untrainable') ?? ''}
        </Label>
      );
    } else if (status === TrainingStatus.NOT_TRAINED) {
      return <Label>{t('dataModels.trainingStatus.notTrained') ?? ''}</Label>;
    }
  };

  const renderMaturityLabel = (status: string | undefined) => {
    if (status === Maturity.DEVELOPMENT) {
      return (
        <Label type="warning">
          {t('dataModels.maturity.development') ?? ''}
        </Label>
      );
    } else if (status === Maturity.PRODUCTION) {
      return (
        <Label type="success">
          {t('dataModels.maturity.production') ?? ''}
        </Label>
      );
    } else if (status === Maturity.STAGING) {
      return (
        <Label type="info">{t('dataModels.maturity.staging') ?? ''}</Label>
      );
    } else if (status === Maturity.TESTING) {
      return (
        <Label type="error">{t('dataModels.maturity.testing') ?? ''}</Label>
      );
    }
  };

  return (
    <div>
      <div className="dataset-group-card">
        <p>{dataModelName}</p>
        <div className="flex">
          <Label>{version}</Label>
          {isLatest ? (
            <Label type="success">
              {t('datasetGroups.datasetCard.latest') ?? ''}
            </Label>
          ) : null}
        </div>

        <div className="py-3">
          <div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {t('dataModels.dataModelCard.datasetGroup') ?? ''}:
              {datasetGroupName ??<div style={{marginLeft:'5px'}}> <Label type="error">Deleted </Label></div>}
            </div>
            <p>
              {t('dataModels.dataModelCard.dgVersion') ?? ''}:{dgVersion}
            </p>
          </div>

          <p>
            {t('dataModels.dataModelCard.lastTrained') ?? ''}:{' '}
            {lastTrained && formatDate(new Date(lastTrained), 'D.M.yy-H:m')}
          </p>
        </div>
        <div className="flex">
          {renderTrainingStatus(trainingStatus)}
          <Label type="info">{platform}</Label>
          {renderMaturityLabel(maturity)}
        </div>

        <div className="label-row flex-grid">
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
                  <div>
                    <div className="flex m-20-0">
                      {t('dataModels.trainingResults.bestPerformingModel') ??
                        ''}
                      -
                    </div>
                    <Card
                      isHeaderLight={true}
                      header={
                        <div className="training-results-grid-container">
                          <div>
                            {' '}
                            {t('dataModels.trainingResults.classes') ?? ''}
                          </div>
                          <div>
                            {t('dataModels.trainingResults.accuracy') ?? ''}
                          </div>
                          <div>
                            {t('dataModels.trainingResults.f1Score') ?? ''}
                          </div>
                        </div>
                      }
                    >
                      {results ? (
                        <div className="training-results-grid-container">
                          <div>
                            {resultsJsonData?.trainingResults?.classes?.map(
                              (c: string, index: number) => {
                                return <div key={index}>{c}</div>;
                              }
                            )}
                          </div>
                          <div>
                            {resultsJsonData?.trainingResults?.accuracy?.map(
                              (c: string, index: number) => {
                                return (
                                  <div key={index}>
                                    {parseFloat(c)?.toFixed(2)}
                                  </div>
                                );
                              }
                            )}
                          </div>
                          <div>
                            {resultsJsonData?.trainingResults?.f1_score?.map(
                              (c: string, index: number) => {
                                return (
                                  <div key={index}>
                                    {parseFloat(c)?.toFixed(2)}
                                  </div>
                                );
                              }
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="text-center">
                          {t('dataModels.trainingResults.noResults') ?? ''}
                        </div>
                      )}
                    </Card>
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
            onClick={() => {
              setId(modelId);
              setView('individual');
            }}
          >
            {t('datasetGroups.datasetCard.settings') ?? ''}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DataModelCard;
