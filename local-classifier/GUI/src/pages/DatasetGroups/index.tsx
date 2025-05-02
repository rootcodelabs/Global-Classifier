import { FC, useEffect, useState } from 'react';
import './DatasetGroups.scss';
import { useTranslation } from 'react-i18next';
import { Button, FormSelect } from 'components';
import DatasetGroupCard from 'components/molecules/DatasetGroupCard';
import Pagination from 'components/molecules/Pagination';
import { getDatasetsOverview, getFilterData } from 'services/datasets';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { formattedArray, parseVersionString } from 'utils/commonUtilts';
import { FilterData, SingleDatasetType } from 'types/datasetGroups';
import ViewDatasetGroup from './ViewDatasetGroup';
import { datasetQueryKeys } from 'utils/queryKeys';
import { DatasetViewEnum } from 'enums/datasetEnums';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import NoDataView from 'components/molecules/NoDataView';
import { ButtonAppearanceTypes } from 'enums/commonEnums';

const DatasetGroups: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [pageIndex, setPageIndex] = useState(1);
  const [id, setId] = useState(0);
  const [enableFetch, setEnableFetch] = useState(true);
  const [view, setView] = useState<DatasetViewEnum>(DatasetViewEnum.LIST);

  const [filters, setFilters] = useState<FilterData>({
    datasetGroupName: 'all',
    version: 'x.x.x',
    validationStatus: 'all',
    sort: 'last_updated_timestamp desc',
  });

  useEffect(() => {
    setEnableFetch(true);
  }, [view]);

  const { data: datasetGroupsData, isLoading } = useQuery(
    datasetQueryKeys.DATASET_OVERVIEW(
      pageIndex,
      filters.datasetGroupName,
      parseVersionString(filters?.version)?.major,
      parseVersionString(filters?.version)?.minor,
      parseVersionString(filters?.version)?.patch,
      filters.validationStatus,
      filters.sort
    ),
    () =>
      getDatasetsOverview(
        pageIndex,
        filters.datasetGroupName,
        parseVersionString(filters?.version)?.major,
        parseVersionString(filters?.version)?.minor,
        parseVersionString(filters?.version)?.patch,
        filters.validationStatus,
        filters.sort
      ),
    {
      keepPreviousData: true,
      enabled: enableFetch,
    }
  );

  const { data: filterData } = useQuery(
    datasetQueryKeys.DATASET_FILTERS(),
    () => getFilterData()
  );

  const pageCount = datasetGroupsData?.response?.data?.[0]?.totalPages || 1;

  const handleFilterChange = (name: string, value: string) => {
    setEnableFetch(false);
    setFilters((prevFilters) => ({
      ...prevFilters,
      [name]: value,
    }));
  };

  return (
    <div>
      {view === DatasetViewEnum.LIST && (
        <div className="container">
          <div className="title_container">
            <div className="title">{t('datasetGroups.title')}</div>
            <Button
              appearance="primary"
              size="m"
              onClick={() => navigate('/create-dataset-group')}
            >
              {t('datasetGroups.createDatasetGroupButton')}
            </Button>
          </div>
          <div>
            <div className="search-panel">
              <div>
                <FormSelect
                  label=""
                  name="datasetGroupName"
                  placeholder={t('datasetGroups.table.group') ?? ''}
                  options={formattedArray(filterData?.response?.dgNames) ?? []}
                  onSelectionChange={(selection) =>
                    handleFilterChange(
                      'datasetGroupName',
                      (selection?.value as string) ?? ''
                    )
                  }
                  defaultValue={filters.datasetGroupName}
                />
              </div>
              <div>
                <FormSelect
                  label=""
                  name="version"
                  placeholder={t('datasetGroups.table.version') ?? ''}
                  options={
                    formattedArray(filterData?.response?.dgVersions) ?? []
                  }
                  onSelectionChange={(selection) =>
                    handleFilterChange(
                      'version',
                      (selection?.value as string) ?? ''
                    )
                  }
                  defaultValue={filters.version}
                />
              </div>
              <div>
                <FormSelect
                  label=""
                  name="validationStatus"
                  placeholder={t('datasetGroups.table.validationStatus') ?? ''}
                  options={
                    formattedArray(
                      filterData?.response?.dgValidationStatuses
                    ) ?? []
                  }
                  onSelectionChange={(selection) =>
                    handleFilterChange(
                      'validationStatus',
                      (selection?.value as string) ?? ''
                    )
                  }
                  defaultValue={filters.validationStatus}
                />
              </div>
              <div>
                <FormSelect
                  label=""
                  name="sort"
                  placeholder={t('datasetGroups.table.sortBy') ?? ''}
                  options={[
                    {
                      label: t('datasetGroups.sortOptions.datasetAsc'),
                      value: 'name asc',
                    },
                    {
                      label: t('datasetGroups.sortOptions.datasetDesc'),
                      value: 'name desc',
                    },
                    {
                      label: t('datasetGroups.sortOptions.createdDateDesc'),
                      value: 'created_timestamp desc',
                    },
                    {
                      label: t('datasetGroups.sortOptions.createdDateAsc'),
                      value: 'created_timestamp asc',
                    },
                    {
                      label: t('datasetGroups.sortOptions.lastUpdatedDateDesc'),
                      value: 'last_updated_timestamp desc',
                    },
                    {
                      label: t('datasetGroups.sortOptions.lastUpdatedDateAsc'),
                      value: 'last_updated_timestamp asc',
                    },
                  ]}
                  onSelectionChange={(selection) =>
                    handleFilterChange(
                      'sort',
                      (selection?.value as string) ?? ''
                    )
                  }
                  defaultValue={filters.sort}
                />
              </div>
              <div style={{
                display: "flex",
                flexDirection: "row",
                gap: 5
              }}>
                <Button onClick={() => setEnableFetch(true)}>
                  {t('global.search')}
                </Button>
                <Button
                  onClick={() => {
                    setFilters({
                      datasetGroupName: 'all',
                      version: 'x.x.x',
                      validationStatus: 'all',
                      sort: 'last_updated_timestamp desc',
                    });
                  }}
                  appearance={ButtonAppearanceTypes.SECONDARY}
                >
                  {t('global.reset')}
                </Button>
              </div>
            </div>

            {isLoading && (
              <div className="skeleton-container">
                <CircularSpinner />
              </div>
            )}
            {datasetGroupsData?.response?.data?.length > 0 && (
              <div className="grid-container m-30-0">
                {datasetGroupsData?.response?.data?.map(
                  (dataset: SingleDatasetType, index: number) => {
                    return (
                      <DatasetGroupCard
                        key={dataset?.id}
                        datasetGroupId={dataset?.id}
                        isEnabled={dataset?.isEnabled}
                        datasetName={dataset?.groupName}
                        version={`V${dataset?.majorVersion}.${dataset?.minorVersion}.${dataset?.patchVersion}`}
                        isLatest={dataset.latest}
                        lastUpdated={dataset?.lastUpdatedTimestamp}
                        lastUsed={dataset?.lastTrainedTimestamp}
                        validationStatus={dataset.validationStatus}
                        lastModelTrained={dataset?.lastModelTrained}
                        setId={setId}
                        setView={setView}
                      />
                    );
                  }
                )}
              </div>
            ) }

              {!isLoading && datasetGroupsData?.response?.data?.length===0 && (
              <NoDataView text={t('datasetGroups.noDatasets') ?? ''} />
            )}

            <Pagination
              pageCount={pageCount}
              pageIndex={pageIndex}
              canPreviousPage={pageIndex > 1}
              canNextPage={pageIndex < pageCount}
              onPageChange={setPageIndex}
            />
          </div>
        </div>
      )}
      {view === DatasetViewEnum.INDIVIDUAL && (
        <ViewDatasetGroup dgId={id} setView={setView} />
      )}
    </div>
  );
};

export default DatasetGroups;
