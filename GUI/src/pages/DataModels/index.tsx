import { FC, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, FormSelect } from 'components';
import Pagination from 'components/molecules/Pagination';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { formattedArray, parseVersionString } from 'utils/commonUtilts';
import DataModelCard from 'components/molecules/DataModelCard';
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
import { getDataModelsOverview, getDeploymentEnvironments } from 'services/datamodels';
import { fi } from 'date-fns/locale';
import { modelStatuses, trainingStatuses } from 'config/dataModelsConfig';

const DataModels: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [pageIndex, setPageIndex] = useState<number>(1);

  const [view, setView] = useState<'list' | 'individual'>('list');

  const [filters, setFilters] = useState<DataModelsFilters>({
    modelName: 'all',
    modelStatus: 'all',
    trainingStatus: 'all',
    deploymentEnvironment: 'all',
    sort: 'createdAt desc',
  });

  const { data: dataModelsData, isLoading: isModelDataLoading } = useQuery({
    queryKey: dataModelsQueryKeys.DATA_MODELS_OVERVIEW(pageIndex, filters.modelStatus, filters.trainingStatus, filters.deploymentEnvironment, filters.sort),
    queryFn: () => getDataModelsOverview(pageIndex, filters.modelStatus, filters.trainingStatus, filters.deploymentEnvironment, filters.sort),
  });

   const { data: deploymentEnvironmentsData } = useQuery({
    queryKey: dataModelsQueryKeys.DATA_MODEL_DEPLOYMENT_ENVIRONMENTS(),
    queryFn: () => getDeploymentEnvironments(),
  });

  const pageCount = dataModelsData?.[0]?.totalPages || 0;
console.log(deploymentEnvironmentsData);

  const handleFilterChange = (
    name: keyof DataModelsFilters,
    value: string | number | undefined | { name: string; id: string }
  ) => {
    setFilters((prevFilters) => ({
      ...prevFilters,
      [name]: value,
    }));
  };

  return (
    <div>
        <div className="container">
          {!isModelDataLoading ? (
            <div>
              {/* <div className="featured-content">
                <div className="title_container mt-30">
                  <div className="title">
                    {t('dataModels.productionModels')}
                  </div>{' '}
                </div>

              </div> */}
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
                      placeholder={t('dataModels.filters.modelStatus') ?? ''}
                      options={
                        modelStatuses
                      }
                      onSelectionChange={(selection) =>
                        handleFilterChange('modelStatus', selection?.value ?? '')
                      }
                      defaultValue={filters?.modelStatus}
                      style={{ width: '15%' }}
                    />

                    <FormSelect
                      label=""
                      name=""
                      placeholder={t('dataModels.filters.trainingStatus') ?? ''}
                      options={
                       trainingStatuses
                      }
                      onSelectionChange={(selection) =>
                        handleFilterChange('trainingStatus', selection?.value)
                      }
                      defaultValue={filters?.trainingStatus}
                      style={{ width: '15%' }}
                    />
                    <FormSelect
                      label=""
                      name=""
                      placeholder={t('dataModels.filters.maturity') ?? ''}
                      options={formattedArray(deploymentEnvironmentsData[0]?.deploymentEnvironments)??[]}
                      onSelectionChange={(selection) =>
                        handleFilterChange('deploymentEnvironment', selection?.value)
                      }
                      defaultValue={filters?.deploymentEnvironment}
                      style={{ width: '25%' }}
                    />
                    <FormSelect
                      label=""
                      name=""
                      placeholder={t('dataModels.filters.sort') ?? ''}
                      options={[
                        {
                          label: t('dataModels.sortOptions.dataModelAsc'),
                          value: 'modelName asc',
                        },
                        {
                          label: t('dataModels.sortOptions.dataModelDesc'),
                          value: 'modelName desc',
                        },
                        {
                          label: t('dataModels.sortOptions.createdDateDesc'),
                          value: 'createdAt desc',
                        },
                        {
                          label: t('dataModels.sortOptions.createdDateAsc'),
                          value: 'createdAt asc',
                        },
                      ]}
                      onSelectionChange={(selection) =>
                        handleFilterChange('sort', selection?.value)
                      }
                      defaultValue={filters?.sort}
                      style={{ width: '25%' }}
                    />
                    <Button
                      onClick={() =>
                        setFilters({
                          modelName: 'all',
                          modelStatus: 'all',
                          trainingStatus: 'all',
                          deploymentEnvironment: 'all',
                          sort: 'createdAt desc',
                        })
                      }
                      appearance={ButtonAppearanceTypes.SECONDARY}
                    >
                      {t('global.reset') ?? ''}
                    </Button>
                  </div>
                  {/* <div
                    className='filter-buttons'
                  > */}
                
                    
                  {/* </div> */}
                </div>

                {dataModelsData?.length > 0 ? (
                  <div className="grid-container m-30-0">
                    {dataModelsData?.map(
                      (model: DataModelResponse, index: number) => {
                        return (
                          <DataModelCard
                            key={model?.modelId}
                            modelId={model?.modelId}
                            dataModelName={model?.modelName}
                            version={`V${model?.major}.${model?.minor}`}
                            // isLatest={model.latest}
                            datasetVersion={model?.datasetVersion}
                            lastTrained={model?.lastTrained}
                            trainingStatus={model.trainingStatus}
                            modelStatus={model?.modelStatus}
                            maturity={model?.deploymentEnvironment}
                            // results={model?.trainingResults ?? null}
                        
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
    </div>
  );
};

export default DataModels;
