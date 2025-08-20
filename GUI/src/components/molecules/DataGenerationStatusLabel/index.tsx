import { DataGenerationStatus } from 'enums/datasetEnums';
import Label from 'components/Label';
import { LabelType } from 'enums/commonEnums';
import { useTranslation } from 'react-i18next';

const DataGenerationStatusLabel = ({
  status,
}: {
  status: string | undefined;
}) => {
  const { t } = useTranslation();

  if (status === DataGenerationStatus.SUCCESS) {
    return (
      <Label type={LabelType.SUCCESS}>
        {t('datasets.datasetCard.success')}
      </Label>
    );
  } else if (status === DataGenerationStatus.FAILED) {
    return (
      <Label type={LabelType.ERROR}>
        {t('datasets.datasetCard.failed')}
      </Label>
    );
  } else if (status === DataGenerationStatus.IN_PROGRESS) {
    return (
      <Label type={LabelType.INFO}>
        {t('datasets.datasetCard.inProgress')}
      </Label>
    );
  } else {
    return null;
  }
};

export default DataGenerationStatusLabel;
