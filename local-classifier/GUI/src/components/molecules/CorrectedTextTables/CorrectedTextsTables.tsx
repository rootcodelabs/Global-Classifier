import React, { useMemo } from 'react';
import SkeletonTable from '../TableSkeleton/TableSkeleton';
import DataTable from 'components/DataTable';
import {
  ColumnDef,
  createColumnHelper,
  PaginationState,
} from '@tanstack/react-table';
import { useTranslation } from 'react-i18next';
import { formatClassHierarchyArray, formatDateTime } from 'utils/commonUtilts';
import Card from 'components/Card';
import { InferencePayload } from 'types/correctedTextTypes';
import './CorrectedTextTable.scss';
import NoDataView from '../NoDataView';

const CorrectedTextsTable = ({
  correctedTextData,
  totalPages,
  isLoading,
  setPagination,
  pagination,
  setEnableFetch,
}: {
  correctedTextData: InferencePayload[];
  totalPages: number;
  isLoading: boolean;
  setPagination: React.Dispatch<React.SetStateAction<PaginationState>>;
  pagination: PaginationState;
  setEnableFetch: React.Dispatch<React.SetStateAction<boolean>>;
}) => {
  const columnHelper = createColumnHelper<InferencePayload>();
  const { t } = useTranslation();

  const dataColumns = useMemo(
    () => [
      columnHelper.accessor('inferenceTimeStamp', {
        header: () => (
          <div className="inferenceTimeLabel">
            {t('correctedTexts.inferenceTime') ?? ''}
          </div>
        ),
        cell: (props) => (
          <div className="inferenceTimeCell">
            <span>
              {
                formatDateTime(props?.row?.original?.inferenceTimeStamp)
                  .formattedDate
              }
            </span>
            <span>
              {
                formatDateTime(props?.row?.original?.inferenceTimeStamp)
                  .formattedTime
              }
            </span>
          </div>
        ),
      }),
      columnHelper.accessor('platform', {
        header: () => (
          <div className="probabilityLabels">
            {t('correctedTexts.platform') ?? ''}
          </div>
        ),
        cell: (props) => (
          <div className="probabilityLabels">
            {props?.row?.original?.platform}
          </div>
        )
      }),
      columnHelper.accessor('inferenceText', {
        header: () => (
          <div>
            <span
             className='w-750'
            >
              {t('correctedTexts.text') ?? ''}
            </span>
          </div>
        ),
        cell: (props) => (
          <div
           className='w-750-wrap'
          >
            {props?.row?.original?.inferenceText}
          </div>
        ),
      }),
      columnHelper.accessor('predictedLabels', {
        header: () => (
          <div className="correctedHierarchy">
            <span
             className='w-150'
            >
              {t('correctedTexts.predictedHierarchy') ?? ''}
            </span>
          </div>
        ),
        cell: (props) => (
          <div className="hierarchyLabels">
            {props?.row?.original?.predictedLabels &&
              formatClassHierarchyArray(props?.row?.original?.predictedLabels)}
          </div>
        ),
      }),
      columnHelper.accessor('averagePredictedClassesProbability', {
        header: () => (
          <div className="probabilityLabels">
            {t('correctedTexts.predictedConfidenceProbability') ?? ''}
          </div>
        ),
        cell: (props) => (
          <div className="probabilityLabels">
            {props?.row?.original?.averagePredictedClassesProbability}%
          </div>
        ),
        meta: {
          size: '90%',
        },
      }),
      columnHelper.accessor('correctedLabels', {
        header: () => (
          <div className="correctedHierarchy">
            <span
             className='w-150'
            >
              {t('correctedTexts.correctedHierarchy') ?? ''}
            </span>
          </div>
        ),
        cell: (props) => (
          <div className="hierarchyLabels">
            {props?.row?.original?.correctedLabels &&
              formatClassHierarchyArray(props?.row?.original?.correctedLabels)}
          </div>
        ),
      }),
      columnHelper.accessor('averageCorrectedClassesProbability', {
        header: () => (
          <div className="probabilityLabels">
            {t('correctedTexts.correctedConfidenceProbability') ?? ''}
          </div>
        ),
        cell: (props) => (
          <div className="probabilityLabels">
            {props?.row?.original?.averageCorrectedClassesProbability === -1 ? (
              <>{t('correctedTexts.labelNotFoundText') ?? ''}</>
            ) : (
              props?.row?.original?.averageCorrectedClassesProbability && (
                <>{props?.row?.original?.averageCorrectedClassesProbability}%</>
              )
            )}
          </div>
        ),
      }),
    ],
    [t]
  );

  return (
      <div className='container-div'>
        {isLoading && <SkeletonTable rowCount={5} />}
        {!isLoading && correctedTextData && correctedTextData.length === 0 && (
          <Card>
            <div
             className='card-div'
            >
              <NoDataView
                text={t('datasetGroups.detailedView.noCorrectedTexts') ?? ''}
              />
            </div>
          </Card>
        )}
        {!isLoading && correctedTextData && correctedTextData.length > 0 && (
          <DataTable
            data={correctedTextData ?? []}
            columns={dataColumns as ColumnDef<string, string>[]}
            pagination={pagination}
            setPagination={(state: PaginationState) => {
              if (
                state.pageIndex === pagination.pageIndex &&
                state.pageSize === pagination.pageSize
              )
                return;
              setPagination({
                pageIndex: state.pageIndex,
                pageSize: state.pageSize,
              });
              setEnableFetch(true);
            }}
            pagesCount={totalPages}
            isClientSide={false}
          />
        )}
      </div>
  );
};

export default CorrectedTextsTable;
