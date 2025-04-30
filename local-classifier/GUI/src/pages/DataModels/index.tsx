import { FC, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, FormSelect } from 'components';
import Pagination from 'components/molecules/Pagination';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { formattedArray, parseVersionString } from 'utils/commonUtilts';
import { getDataModelsOverview, getFilterData } from 'services/data-models';
import DataModelCard from 'components/molecules/DataModelCard';
import ConfigureDataModel from './ConfigureDataModel';
import { customFormattedArray, extractedArray } from 'utils/dataModelsUtils';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import { ButtonAppearanceTypes } from 'enums/commonEnums';
import {
  DataModelResponse,
  DataModelsFilters,
  FilterData,
} from 'types/dataModels';
import { dataModelsQueryKeys } from 'utils/queryKeys';
import NoDataView from 'components/molecules/NoDataView';
import './DataModels.scss';

const DataModels: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [pageIndex, setPageIndex] = useState<number>(1);
  const [id, setId] = useState<number>(0);
  const [enableFetch, setEnableFetch] = useState<boolean>(true);
  const [enableProdModelsFetch, setEnableProdModelsFetch] =
    useState<boolean>(true);

  const [view, setView] = useState<'list' | 'individual'>('list');
  const [availableProdModels, setAvailableProdModels] = useState<string[]>([]);

  useEffect(() => {
    setEnableFetch(true);
  }, [view]);

  const [filters, setFilters] = useState<DataModelsFilters>({
    modelName: 'all',
    version: 'x.x.x',
    platform: 'all',
    datasetGroup: -1,
    trainingStatus: 'all',
    maturity: 'all',
    sort: 'created_timestamp desc',
  });

  const { data: dataModelsData, isLoading: isModelDataLoading } = useQuery(
    dataModelsQueryKeys.DATA_MODELS_OVERVIEW(
      pageIndex,
      filters.modelName,
      parseVersionString(filters.version)?.major,
      parseVersionString(filters.version)?.minor,
      filters.platform,
      filters.datasetGroup,
      filters.trainingStatus,
      filters.maturity,
      filters.sort,
      false
    ),
    () =>
      getDataModelsOverview(
        pageIndex,
        filters.modelName,
        parseVersionString(filters.version)?.major,
        parseVersionString(filters.version)?.minor,
        filters.platform,
        filters.datasetGroup,
        filters.trainingStatus,
        filters.maturity,
        filters.sort,
        false
      ),
    {
      keepPreviousData: true,
      enabled: enableFetch,
    }
  );

  const { data: prodDataModelsData, isLoading: isProdModelDataLoading } =
    useQuery(
      dataModelsQueryKeys.DATA_MODELS_OVERVIEW(
        0,
        'all',
        -1,
        -1,
        'all',
        -1,
        'all',
        'all',
        'created_timestamp desc',
        true
      ),
      () =>
        getDataModelsOverview(
          1,
          'all',
          -1,
          -1,
          'all',
          -1,
          'all',
          'all',
          'created_timestamp desc',
          true
        ),
      {
        onSuccess: (data) => {
          setAvailableProdModels(extractedArray(data?.data, 'deploymentEnv'));
          setEnableProdModelsFetch(false);
        },
        keepPreviousData: true,
        enabled: enableProdModelsFetch,
      }
    );

  const { data: filterData } = useQuery<FilterData>(
    dataModelsQueryKeys.DATA_MODEL_FILTERS(),
    () => getFilterData()
  );

  const pageCount = dataModelsData?.data[0]?.totalPages || 1;

  const handleFilterChange = (
    name: keyof DataModelsFilters,
    value: string | number | undefined | { name: string; id: string }
  ) => {
    setEnableFetch(false);
    setFilters((prevFilters) => ({
      ...prevFilters,
      [name]: value,
    }));
  };

  return (
    <div>
      {view === 'list' && (
        <div className="container">
          {!isModelDataLoading && !isProdModelDataLoading ? (
            <div>
              <div className="featured-content">
                <div className="title_container mt-30">
                  <div className="title">
                    {t('dataModels.productionModels')}
                  </div>{' '}
                </div>
                {prodDataModelsData?.data?.length > 0 ? (
                  <div className="grid-container m-30-0">
                    {prodDataModelsData?.data?.map(
                      (dataset: DataModelResponse) => {
                        return (
                          <DataModelCard
                            key={dataset?.id}
                            modelId={dataset?.id}
                            dataModelName={dataset?.modelName}
                            datasetGroupName={dataset?.connectedDgName}
                            version={`V${dataset?.majorVersion}.${dataset?.minorVersion}`}
                            isLatest={dataset.latest}
                            dgVersion={`V${dataset?.connectedDgMajorVersion}.${dataset?.connectedDgMinorVersion}.${dataset?.connectedDgPatchVersion}`}
                            lastTrained={dataset?.lastTrainedTimestamp}
                            trainingStatus={dataset.trainingStatus}
                            platform={dataset?.deploymentEnv}
                            maturity={dataset?.maturityLabel}
                            results={dataset?.trainingResults ?? null}
                            setId={setId}
                            setView={setView}
                          />
                        );
                      }
                    )}
                  </div>
                ) : (
                  <NoDataView text={t('dataModels.noProdModels') ?? ''} />
                )}
              </div>
              <div>
                <div className="title_container">
                  <div className="title">{t('dataModels.dataModels')}</div>
                  <Button
                    appearance="primary"
                    size="m"
                    onClick={() => navigate('/create-data-model')}
                  >
                    {t('dataModels.createModel')}
                  </Button>
                </div>
                <div className="search-panel flex">
                  <div
                    className='models-filter-div'
                  >
                    <FormSelect
                      label=""
                      name=""
                      placeholder={t('dataModels.filters.modelName') ?? ''}
                      options={formattedArray(filterData?.modelNames) ?? []}
                      onSelectionChange={(selection) =>
                        handleFilterChange('modelName', selection?.value ?? '')
                      }
                      defaultValue={filters?.modelName}
                      style={{ fontSize: '1rem', width: '200px' }}
                    />
                    <FormSelect
                      label=""
                      name=""
                      placeholder={t('dataModels.filters.version') ?? ''}
                      options={formattedArray(filterData?.modelVersions) ?? []}
                      onSelectionChange={(selection) =>
                        handleFilterChange('version', selection?.value ?? '')
                      }
                      defaultValue={filters?.version}
                      style={{ width: 'auto' }}
                    />
                    <FormSelect
                      label=""
                      name=""
                      placeholder={t('dataModels.filters.platform') ?? ''}
                      options={
                        formattedArray(filterData?.deploymentsEnvs) ?? []
                      }
                      onSelectionChange={(selection) =>
                        handleFilterChange('platform', selection?.value ?? '')
                      }
                      defaultValue={filters?.platform}
                      style={{ width: 'auto' }}
                    />
                    <FormSelect
                      label=""
                      name=""
                      placeholder={t('dataModels.filters.datasetGroup') ?? ''}
                      options={
                        customFormattedArray(
                          filterData?.datasetGroups,
                          'name'
                        ) ?? []
                      }
                      onSelectionChange={(selection) =>
                        handleFilterChange('datasetGroup', selection?.value)
                      }
                      defaultValue={filters?.datasetGroup}
                      style={{ width: '200px' }}
                    />
                    <FormSelect
                      label=""
                      name=""
                      placeholder={t('dataModels.filters.trainingStatus') ?? ''}
                      options={
                        formattedArray(filterData?.trainingStatuses) ?? []
                      }
                      onSelectionChange={(selection) =>
                        handleFilterChange('trainingStatus', selection?.value)
                      }
                      defaultValue={filters?.trainingStatus}
                      style={{ width: '150px' }}
                    />
                    <FormSelect
                      label=""
                      name=""
                      placeholder={t('dataModels.filters.maturity') ?? ''}
                      options={formattedArray(filterData?.maturityLabels) ?? []}
                      onSelectionChange={(selection) =>
                        handleFilterChange('maturity', selection?.value)
                      }
                      defaultValue={filters?.maturity}
                      style={{ width: '150px' }}
                    />
                    <FormSelect
                      label=""
                      name=""
                      placeholder={t('dataModels.filters.sort') ?? ''}
                      options={[
                        {
                          label: t('dataModels.sortOptions.dataModelAsc'),
                          value: 'name asc',
                        },
                        {
                          label: t('dataModels.sortOptions.dataModelDesc'),
                          value: 'name desc',
                        },
                        {
                          label: t('dataModels.sortOptions.createdDateDesc'),
                          value: 'created_timestamp desc',
                        },
                        {
                          label: t('dataModels.sortOptions.createdDateAsc'),
                          value: 'created_timestamp asc',
                        },
                      ]}
                      onSelectionChange={(selection) =>
                        handleFilterChange('sort', selection?.value)
                      }
                      defaultValue={filters?.sort}
                      style={{ width: 'auto' }}
                    />
                  </div>
                  <div
                   className='filter-buttons'
                  >
                    <Button onClick={() => setEnableFetch(true)}>
                      {t('global.search') ?? ''}
                    </Button>
                    <Button
                      onClick={() =>
                        setFilters({
                          modelName: 'all',
                          version: 'x.x.x',
                          platform: 'all',
                          datasetGroup: -1,
                          trainingStatus: 'all',
                          maturity: 'all',
                          sort: 'created_timestamp desc',
                        })
                      }
                      appearance={ButtonAppearanceTypes.SECONDARY}
                    >
                      {t('global.reset') ?? ''}
                    </Button>
                  </div>
                </div>

                {dataModelsData?.data?.length > 0 ? (
                  <div className="grid-container m-30-0">
                    {dataModelsData?.data?.map(
                      (dataset: DataModelResponse, index: number) => {
                        return (
                          <DataModelCard
                            key={dataset?.id}
                            modelId={dataset?.id}
                            dataModelName={dataset?.modelName}
                            datasetGroupName={dataset?.connectedDgName}
                            version={`V${dataset?.majorVersion}.${dataset?.minorVersion}`}
                            isLatest={dataset.latest}
                            dgVersion={`V${dataset?.connectedDgMajorVersion}.${dataset?.connectedDgMinorVersion}.${dataset?.connectedDgPatchVersion}`}
                            lastTrained={dataset?.lastTrainedTimestamp}
                            trainingStatus={dataset.trainingStatus}
                            platform={dataset?.deploymentEnv}
                            maturity={dataset?.maturityLabel}
                            results={dataset?.trainingResults ?? null}
                            setId={setId}
                            setView={setView}
                          />
                        );
                      }
                    )}
                  </div>
                ) : (
                  <NoDataView text={t('dataModels.noModels') ?? ''} />
                )}
              </div>
              <Pagination
                pageCount={pageCount}
                pageIndex={pageIndex}
                canPreviousPage={pageIndex > 1}
                canNextPage={pageIndex < 10}
                onPageChange={setPageIndex}
              />
            </div>
          ) : (
            <CircularSpinner />
          )}
        </div>
      )}
      {view === 'individual' && (
        <ConfigureDataModel id={id} availableProdModels={availableProdModels} />
      )}
    </div>
  );
};

export default DataModels;
