import { FC, PropsWithChildren } from 'react';
import './DatasetGroupCard.scss';
import { Switch } from 'components/FormElements';
import Button from 'components/Button';
import Label from 'components/Label';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useDialog } from 'hooks/useDialog';
import { Operation } from 'types/datasets';
import { datasetQueryKeys, integratedAgenciesQueryKeys } from 'utils/queryKeys';
import { ButtonAppearanceTypes, LabelType, ToastTypes } from 'enums/commonEnums';
import { useTranslation } from 'react-i18next';
import { formatDate } from 'utils/commonUtilts';
import SyncStatusLabel from '../SyncStatusLabel';
import { SyncStatus } from 'enums/datasetEnums';
import { disableAgncy, enableAgncy, resync } from 'services/agencies';
import { AxiosError } from 'axios';
import { useToast } from 'hooks/useToast';

type IntegratedAgencyCardProps = {
  agencyId: string;
  agencyName?: string;
  lastTrained?: Date | null | string;
  isLatest?: boolean;
  isEnabled?: boolean;
  lastUpdated?: Date | null;
  lastUsed?: Date | null;
  validationStatus?: string;
  syncStatus?: string;
  lastModelTrained?: string;
  lastSynced?: Date | null;
  enableAllowed?: boolean;
};

const IntegratedAgencyCard: FC<PropsWithChildren<IntegratedAgencyCardProps>> = ({
  agencyId,
  agencyName,
  isLatest,
  isEnabled,
  lastUpdated,
  lastTrained,
  syncStatus,
  lastModelTrained,
  lastSynced,
  enableAllowed
}) => {

  const { t } = useTranslation();

  const queryClient = useQueryClient();
  const toast = useToast();


  const enableAgencyMutation = useMutation({
    mutationFn: ({
      id }: {
        id: string | number
      }) => enableAgncy(id as string),
    onSuccess: async () => {
      await queryClient.invalidateQueries(
        integratedAgenciesQueryKeys.INTEGRATED_AGENCIES_LIST()
      );
    },
    onError: (error: AxiosError) => {
      toast.open({
        type: ToastTypes.ERROR,
        title: t('global.notificationError'),
        message: error?.message ?? '',
      });
    },
  });

  const disableAgencyMutation = useMutation({
    mutationFn: ({
      id,
    }: {
      id: string | number;
    }) => disableAgncy(id as string),
    onSuccess: async () => {
      await queryClient.invalidateQueries(
        integratedAgenciesQueryKeys.INTEGRATED_AGENCIES_LIST()
      );
    },
    onError: (error: AxiosError) => {
      toast.open({
        type: ToastTypes.ERROR,
        title: t('global.notificationError'),
        message: error?.message ?? '',
      });
    },
  });

  const resyncAgencyMutation = useMutation({
    mutationFn: ({
      id }: {
        id: string | number
      }) => resync(id as string),
    onSuccess: async () => {
      await queryClient.invalidateQueries(
        integratedAgenciesQueryKeys.INTEGRATED_AGENCIES_LIST()
      );
    }
    // onError: (error: AxiosError) => {
    //   toast.open({
    //     type: ToastTypes.ERROR,
    //     title: t('global.notificationError'),
    //     message: error?.message ?? '',
    //   });
    // },
  });

  const handleCheckedChange = (checked: boolean) => {
    if (checked) {
      enableAgencyMutation.mutate({ id: agencyId });
    } else {
      disableAgencyMutation.mutate({ id: agencyId });
    }
  };

  return (
    <div>
      <div className="dataset-group-card">
        <div className="row switch-row">
          <div className="text">{agencyName}</div>
          <Switch
            label=""
            checked={isEnabled}
            onCheckedChange={handleCheckedChange}
          />
        </div>
        <div className="py-3">
          <p>
            {t('integratedAgencies.agencyCard.lastModelTrained')}:{' '}
            {lastModelTrained === "" ? "N/A" : lastModelTrained}
          </p>
          <p>
            {t('integratedAgencies.agencyCard.lastUsedForTraining')}:{' '}
            {lastTrained === "1970-01-01T00:00:00.000+00:00" ? "N/A" : formatDate(lastTrained as Date, 'D.M.yy-H:m')}
          </p>
          <p>
            {t('integratedAgencies.agencyCard.lastSynced')}:{' '}
            {lastSynced && formatDate(lastSynced, 'DD.MM.yy-HH:mm')}
          </p>
        </div>


        <div className="flex">
          <SyncStatusLabel status={syncStatus} />
        </div>

        <div className="label-row">
          <Button
            appearance={ButtonAppearanceTypes.SECONDARY}
            size="s"
            onClick={() => resyncAgencyMutation.mutate({ id: agencyId })}
            disabled={syncStatus !== SyncStatus.RESYNC_NEEDED}
          >
            {t('integratedAgencies.agencyCard.resync')}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default IntegratedAgencyCard;
