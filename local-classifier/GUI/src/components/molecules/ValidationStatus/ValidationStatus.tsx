import { ValidationStatus } from 'enums/datasetEnums';
import React from 'react';
import Label from 'components/Label';
import { LabelType } from 'enums/commonEnums';
import { useTranslation } from 'react-i18next';

const DatasetValidationStatus = ({
  status,
}: {
  status: string | undefined;
}) => {
  const { t } = useTranslation();

  if (status === ValidationStatus.SUCCESS) {
    return (
      <Label type={LabelType.SUCCESS}>
        {t('datasetGroups.datasetCard.validationSuccess')}
      </Label>
    );
  } else if (status === ValidationStatus.FAIL) {
    return (
      <Label type={LabelType.ERROR}>
        {t('datasetGroups.datasetCard.validationFail')}
      </Label>
    );
  } else if (status === ValidationStatus.UNVALIDATED) {
    return (
      <Label type={LabelType.INFO}>
        {t('datasetGroups.datasetCard.notValidated')}
      </Label>
    );
  } else if (status === ValidationStatus.IN_PROGRESS) {
    return (
      <Label type={LabelType.WARNING}>
        {t('datasetGroups.datasetCard.validationInprogress')}
      </Label>
    );
  } else {
    return null;
  }
};

export default DatasetValidationStatus;
