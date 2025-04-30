import BackArrowButton from 'assets/BackArrowButton';
import { Button, Card, DataTable, Icon, Label, Switch } from 'components';
import { ButtonAppearanceTypes, LabelType } from 'enums/commonEnums';
import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import DatasetValidationStatus from '../ValidationStatus/ValidationStatus';
import { ViewDatasetGroupModalContexts } from 'enums/datasetEnums';
import { generateDynamicColumns } from 'utils/dataTableUtils';
import { MdOutlineDeleteOutline, MdOutlineEdit } from 'react-icons/md';
import { CellContext, ColumnDef, PaginationState } from '@tanstack/react-table';
import { getDatasets } from 'services/datasets';
import {
  DatasetDetails,
  MetaData,
  SelectedRowPayload,
} from 'types/datasetGroups';
import SkeletonTable from '../TableSkeleton/TableSkeleton';

const DatasetDetailedViewTable = ({
  metadata,
  handleOpenModals,
  bannerMessage,
  datasets,
  isLoading,
  updatedDataset,
  setSelectedRow,
  pagination,
  setPagination,
  dgId,
  isMetadataLoading,
}: {
  metadata: MetaData[];
  handleOpenModals: (context: ViewDatasetGroupModalContexts) => void;
  bannerMessage: string;
  datasets: DatasetDetails | undefined;
  isLoading: boolean;
  updatedDataset: any;
  setSelectedRow: React.Dispatch<
    React.SetStateAction<SelectedRowPayload | undefined>
  >;
  pagination: PaginationState;
  setPagination: React.Dispatch<React.SetStateAction<PaginationState>>;
  dgId: number;
  isMetadataLoading: boolean;
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const editView = (props: CellContext<any, unknown>) => {
    return (
      <Button
        appearance={ButtonAppearanceTypes.TEXT}
        onClick={() => {
          setSelectedRow(props.row.original);
          handleOpenModals(ViewDatasetGroupModalContexts.PATCH_UPDATE_MODAL);
        }}
      >
        <Icon icon={<MdOutlineEdit />} />
        {t('global.edit')}
      </Button>
    );
  };

  const deleteView = (props: CellContext<any, unknown>) => (
    <Button
      appearance={ButtonAppearanceTypes.TEXT}
      onClick={() => {
        setSelectedRow(props.row.original);
        handleOpenModals(ViewDatasetGroupModalContexts.DELETE_ROW_MODAL);
      }}
    >
      <Icon icon={<MdOutlineDeleteOutline />} />
      {t('global.delete')}
    </Button>
  );

  const dataColumns = useMemo(
    () => generateDynamicColumns(datasets?.fields ?? [], editView, deleteView),
    [datasets?.fields]
  );

  return (
    <div>
      {isMetadataLoading && <SkeletonTable rowCount={2} />}
      {metadata && !isMetadataLoading && (
        <div>
          <Card
            isHeaderLight={false}
            header={
              <div className="flex-between">
                <div className="flex-grid align-center">
                  <Link to={''} onClick={() => navigate(0)}>
                    <BackArrowButton />
                  </Link>
                  <div className="title">{metadata?.[0]?.name}</div>
                  {metadata && (
                    <Label
                      type={LabelType.SUCCESS}
                    >{`V${metadata?.[0]?.majorVersion}.${metadata?.[0]?.minorVersion}.${metadata?.[0]?.patchVersion}`}</Label>
                  )}
                  {metadata?.[0]?.latest ? (
                    <Label type={LabelType.SUCCESS}>
                      {t('datasetGroups.datasetCard.latest') ?? ''}
                    </Label>
                  ) : null}
                  <DatasetValidationStatus
                    status={metadata?.[0]?.validationStatus}
                  />
                </div>
                <Switch label="" checked={metadata?.[0]?.isEnabled} />
              </div>
            }
          >
            <div className="flex-between">
              <div>
                <p>
                  {t('datasetGroups.detailedView.connectedModels') ?? ''} :
                  {metadata?.[0]?.linkedModels?.map((model, index: number) => {
                    return index === metadata?.[0]?.linkedModels?.length - 1
                      ? ` ${model?.modelName}`
                      : ` ${model?.modelName}, `;
                  })}
                </p>
                <p>
                  {t('datasetGroups.detailedView.noOfItems') ?? ''} :
                  {` ${metadata?.[0]?.numSamples}`}
                </p>
              </div>
              <div className="flex-grid">
                <Button
                  appearance={ButtonAppearanceTypes.SECONDARY}
                  onClick={() =>
                    handleOpenModals(ViewDatasetGroupModalContexts.EXPORT_MODAL)
                  }
                  disabled={datasets?.numPages === 0}
                >
                  {t('datasetGroups.detailedView.export') ?? ''}
                </Button>
                <Button
                  appearance={ButtonAppearanceTypes.SECONDARY}
                  onClick={() =>
                    handleOpenModals(ViewDatasetGroupModalContexts.IMPORT_MODAL)
                  }
                >
                  {t('datasetGroups.detailedView.importNewData') ?? ''}
                </Button>
              </div>
            </div>
          </Card>
          {bannerMessage && <div className="banner">{bannerMessage}</div>}
          {(!datasets || (datasets && datasets?.numPages < 2)) &&
            !isLoading && (
              <Card>
                <div className="dataset-table-card">
                  {(!datasets || datasets?.numPages === 0) && (
                    <div>
                      <div className="dataset-no-data-view">
                        {t('datasetGroups.detailedView.noData') ?? ''}
                      </div>
                      <p>{t('datasetGroups.detailedView.noDataDesc') ?? ''}</p>
                      <Button
                        onClick={() =>
                          handleOpenModals(
                            ViewDatasetGroupModalContexts.IMPORT_MODAL
                          )
                        }
                      >
                        {t('datasetGroups.detailedView.importNewData') ?? ''}
                      </Button>
                    </div>
                  )}
                  {datasets &&
                    datasets?.numPages !== 0 &&
                    datasets?.numPages <= 2 && (
                      <div>
                        <p>
                          {t(
                            'datasetGroups.detailedView.insufficientExamplesDesc'
                          ) ?? ''}
                        </p>
                        <Button
                          onClick={() =>
                            handleOpenModals(
                              ViewDatasetGroupModalContexts.IMPORT_MODAL
                            )
                          }
                        >
                          {t('datasetGroups.detailedView.importNewData') ?? ''}
                        </Button>
                      </div>
                    )}
                </div>
              </Card>
            )}
        </div>
      )}
      <div className="mb-20">
        {isLoading && <SkeletonTable rowCount={5} />}
        {!isLoading && updatedDataset && updatedDataset.length > 0 && (
          <DataTable
            data={updatedDataset}
            columns={dataColumns as ColumnDef<string, string>[]}
            pagination={pagination}
            setPagination={(state: PaginationState) => {
              if (
                state.pageIndex === pagination.pageIndex &&
                state.pageSize === pagination.pageSize
              )
                return;
              setPagination(state);
              getDatasets(state, dgId);
            }}
            pagesCount={datasets?.numPages}
            isClientSide={false}
          />
        )}
      </div>
    </div>
  );
};

export default DatasetDetailedViewTable;
