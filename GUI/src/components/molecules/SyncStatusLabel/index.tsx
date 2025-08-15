import { SyncStatus } from 'enums/datasetEnums';
import React from 'react';
import Label from 'components/Label';
import { LabelType } from 'enums/commonEnums';
import { useTranslation } from 'react-i18next';

const SyncStatusLabel = ({
  status,
}: {
  status: string | undefined;
}) => {
  const { t } = useTranslation();

  if (status === SyncStatus.SYNCED) {
    return (
      <Label type={LabelType.SUCCESS}>
        {t('integratedAgencies.agencyCard.syncStatus.synced')}
      </Label>
    );
  } else if (status === SyncStatus.UNAVAILABLE ) {
    return (
      <Label type={LabelType.ERROR}>
        {t('integratedAgencies.agencyCard.syncStatus.unavailable')}
      </Label>
    );
  }else if (status === SyncStatus.FAILED ) {
    return (
      <Label type={LabelType.ERROR}>
        {t('integratedAgencies.agencyCard.syncStatus.failed')}
      </Label>
    );
  }
   else if (status === SyncStatus.RESYNC_NEEDED) {
    return (
      <Label type={LabelType.WARNING}>
        {t('integratedAgencies.agencyCard.syncStatus.resync')}
      </Label>
    );
  }else if (status === SyncStatus.IN_PROGRESS) {
    return (
      <Label type={LabelType.INFO}>
        {t('integratedAgencies.agencyCard.syncStatus.inProgress')}
      </Label>
    );
  }else if (status === SyncStatus.RESYNC_IN_PROGRESS) {
    return (
      <Label type={LabelType.INFO}>
        {t('integratedAgencies.agencyCard.syncStatus.resyncInProgress')}
      </Label>
    );
  } else {
    return null;
  }
};

export default SyncStatusLabel;
