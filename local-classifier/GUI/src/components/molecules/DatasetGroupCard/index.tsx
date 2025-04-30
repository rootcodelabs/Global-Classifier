import { FC, PropsWithChildren } from 'react';
import './DatasetGroupCard.scss';
import { Switch } from 'components/FormElements';
import Button from 'components/Button';
import Label from 'components/Label';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { enableDataset } from 'services/datasets';
import { useDialog } from 'hooks/useDialog';
import { Operation } from 'types/datasetGroups';
import { datasetQueryKeys } from 'utils/queryKeys';
import { DatasetViewEnum } from 'enums/datasetEnums';
import { ButtonAppearanceTypes, LabelType } from 'enums/commonEnums';
import { useTranslation } from 'react-i18next';
import { formatDate } from 'utils/commonUtilts';
import DatasetValidationStatus from '../ValidationStatus/ValidationStatus';

type DatasetGroupCardProps = {
  datasetGroupId: number;
  datasetName?: string;
  version?: string;
  isLatest?: boolean;
  isEnabled?: boolean;
  lastUpdated?: Date | null;
  lastUsed?: Date | null;
  validationStatus?: string;
  lastModelTrained?: Date | null;
  setId?: React.Dispatch<React.SetStateAction<number>>;
  setView?: React.Dispatch<React.SetStateAction<DatasetViewEnum>>;
};

const DatasetGroupCard: FC<PropsWithChildren<DatasetGroupCardProps>> = ({
  datasetGroupId,
  datasetName,
  version,
  isLatest,
  isEnabled,
  lastUpdated,
  lastUsed,
  validationStatus,
  lastModelTrained,
  setId,
  setView,
}) => {
  const queryClient = useQueryClient();
  const { open } = useDialog();
  const { t } = useTranslation();

  const datasetEnableMutation = useMutation({
    mutationFn: (data: Operation) => enableDataset(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries(datasetQueryKeys.DATASET_OVERVIEW(1));
    },
    onError: () => {
      open({
        title: t('datasetGroups.modals.enableDatasetTitle'),
        content: <p>{t('datasetGroups.modals.enableDatasetDesc')}</p>,
      });
    },
  });

  const datasetDisableMutation = useMutation({
    mutationFn: (data: Operation) => enableDataset(data),
    onSuccess: async (response) => {
      await queryClient.invalidateQueries(datasetQueryKeys.DATASET_OVERVIEW(1));
      if (response?.operationSuccessful)
        open({
          title: t('datasetGroups.modals.enableDatasetTitle'),
          content: <p>{t('datasetGroups.modals.enableDatasetDesc')}</p>,
        });
    },
    onError: () => {
      open({
        title: t('datasetGroups.modals.errorTitle'),
        content: <p>{t('datasetGroups.modals.errorDesc')}</p>,
      });
    },
  });

  const handleCheck = () => {
    if (isEnabled)
      datasetDisableMutation.mutate({
        dgId: datasetGroupId,
        operationType: 'disable',
      });
    else
      datasetEnableMutation.mutate({
        dgId: datasetGroupId,
        operationType: 'enable',
      });
  };

  return (
    <div>
      <div className="dataset-group-card">
        <div className="row switch-row">
          <div className="text">{datasetName}</div>
          <Switch
            label=""
            checked={isEnabled}
            onCheckedChange={() => handleCheck()}
          />
        </div>
        <DatasetValidationStatus status={validationStatus} />
        <div className="py-3">
          <p>
            {t('datasetGroups.datasetCard.lastModelTrained')}:{' '}
            {lastModelTrained && formatDate(lastModelTrained, 'D.M.yy-H:m')}
          </p>
          <p>
            {t('datasetGroups.datasetCard.lastUsedForTraining')}:{' '}
            {lastUsed && formatDate(lastUsed, 'D.M.yy-H:m')}
          </p>
          <p>
            {t('datasetGroups.datasetCard.lastUpdate')}:{' '}
            {lastUpdated && formatDate(lastUpdated, 'DD.MM.yy-HH:mm')}
          </p>
        </div>
        <div className="flex">
          <Label type={LabelType.SUCCESS}>{version}</Label>
          {isLatest ? (
            <Label type={LabelType.SUCCESS}>
              {t('datasetGroups.datasetCard.latest')}
            </Label>
          ) : null}
        </div>

        <div className="label-row">
          <Button
            appearance={ButtonAppearanceTypes.PRIMARY}
            size="s"
            onClick={() => {
              setId?.(datasetGroupId);
              setView?.(DatasetViewEnum.INDIVIDUAL);
            }}
          >
            {t('datasetGroups.datasetCard.settings')}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DatasetGroupCard;
