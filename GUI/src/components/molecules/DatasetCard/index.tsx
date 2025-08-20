import { FC, PropsWithChildren } from 'react';
import './DatasetGroupCard.scss';
import { Switch } from 'components/FormElements';
import Button from 'components/Button';
import Label from 'components/Label';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useDialog } from 'hooks/useDialog';
import { datasetQueryKeys } from 'utils/queryKeys';
import { ButtonAppearanceTypes, LabelType } from 'enums/commonEnums';
import { useTranslation } from 'react-i18next';
import { formatDate } from 'utils/commonUtilts';
import SyncStatusLabel from '../SyncStatusLabel';
import DataGenerationStatusLabel from '../DataGenerationStatusLabel';
import { useNavigate } from 'react-router-dom';

type DatasetCardProps = {
  datasetId: number | string;
  lastTrained?: Date | null | string;
  isLatest?: boolean;
  dataGenerationStatus?: string;
  lastModelTrained?: string;
  majorVersion?: string | number;
  minorVersion?: string | number;
};

const DatasetCard: FC<PropsWithChildren<DatasetCardProps>> = ({
  datasetId,
  lastTrained,
  dataGenerationStatus,
  lastModelTrained,
  majorVersion,
  minorVersion
}) => {

  const { t } = useTranslation();
const navigate = useNavigate();

const viewDataset = () => {
  navigate(`/view-dataset?datasetId=${datasetId}`);

};
  return (
    <div>
      <div className="dataset-group-card">
        <div className="row switch-row">
          <div className="text" style={{ fontWeight: 600 }}>{`V${majorVersion}.${minorVersion}`}</div>
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
        </div>

        <div className="flex">
          <DataGenerationStatusLabel status={dataGenerationStatus} />
          {/* {isLatest ? (
            <Label type={LabelType.SUCCESS}>
              {t('integratedAgencies.agencyCard.latest')}
            </Label>
          ) : null} */}
        </div>

        <div className="label-row">
          <Button
            appearance={ButtonAppearanceTypes.SECONDARY}
            size="s"
            onClick={viewDataset}
          >
            {t('datasets.datasetCard.settings')}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DatasetCard;
