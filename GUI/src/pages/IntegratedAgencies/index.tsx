import { FC,  useState } from 'react';
import './DatasetGroups.scss';
import { useTranslation } from 'react-i18next';
import {  Button, FormSelect } from 'components';
import Pagination from 'components/molecules/Pagination';
import { useQuery } from '@tanstack/react-query';
import { integratedAgenciesQueryKeys } from 'utils/queryKeys';
import { DatasetViewEnum } from 'enums/datasetEnums';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import NoDataView from 'components/molecules/NoDataView';
import SearchInput from 'components/FormElements/SearchInput';
import { fetchAgencies } from 'services/agencies';
import IntegratedAgencyCard from 'components/molecules/IntegratedAgencyCard';
import { Agency } from 'types/agencies';

const IntegratedAgencies: FC = () => {
  const { t } = useTranslation();

  const [pageIndex, setPageIndex] = useState(1);
  const view = (DatasetViewEnum.LIST);
  const [sortOption, setSortOption] = useState("last_updated_timestamp desc");
  const [searchTerm, setSearchTerm] = useState<string>('all');


    const { data: agencies, isLoading } = useQuery({
      queryKey: integratedAgenciesQueryKeys.INTEGRATED_AGENCIES_LIST(pageIndex,sortOption,searchTerm),
      queryFn: () => fetchAgencies(pageIndex,sortOption,searchTerm),
    });

    const pageCount=agencies?.[0]?.totalPages??1;

    
    const handleSearch = (term: string) => {
      // Set the search term to 'all' if empty, otherwise use the provided term
      setSearchTerm(term.trim() === '' ? 'all' : term);
      // Reset to first page when searching to show most relevant results first
      setPageIndex(1);
    };

  const handleSortChange = (selection: any) => {
    setSortOption(selection?.value as string);
    setPageIndex(1); 
  };  

  return (
    <div>
      {view === DatasetViewEnum.LIST && (
        <div className="container">
          <div className="title_container">
            <div className="title">{t('integratedAgencies.title')}</div>
          </div>
          <div>
            <div className="search-panel">
              <div style={{ flex: 4 }}>
                <SearchInput
                  onSearch={handleSearch}
                  placeholder="Search clients..."
                  initialValue={searchTerm}
                />
              </div>
              <div style={{ flex: 2 }}>
                <FormSelect
                  label=""
                  name="sort"
                  placeholder={t('datasetGroups.table.sortBy') ?? ''}
                  options={[
                    {
                      label: t('integratedAgencies.sortOptions.agencyAsc'),
                      value: 'agency_name asc',
                    },
                    {
                      label: t('integratedAgencies.sortOptions.agencyDesc'),
                      value: 'agency_name desc',
                    },
                    {
                      label: t(
                        'integratedAgencies.sortOptions.createdDateDesc'
                      ),
                      value: 'created_at desc',
                    },
                    {
                      label: t('integratedAgencies.sortOptions.createdDateAsc'),
                      value: 'created_at asc',
                    },
                    {
                      label: t(
                        'integratedAgencies.sortOptions.lastUpdatedDateDesc'
                      ),
                      value: 'last_updated_timestamp desc',
                    },
                    {
                      label: t(
                        'integratedAgencies.sortOptions.lastUpdatedDateAsc'
                      ),
                      value: 'last_updated_timestamp asc',
                    },
                  ]}
                  onSelectionChange={handleSortChange}
                  defaultValue={sortOption}
                />
              </div>
              <div style={{ flex: 1 }}>
                <Button
                  appearance="secondary"
                  onClick={() => {setPageIndex(1); setSortOption("last_updated_timestamp desc"); setSearchTerm('all');}}
                >Reset
                </Button>
              </div>
            </div>
            
            {isLoading && (
              <div className="skeleton-container">
                <CircularSpinner />
              </div>
            )}
            {agencies?.length > 0 && (
              <div className="grid-container m-30-0">
                {agencies?.map(
                  (agenciesData : Agency, index: number) => {
                    return (
                      <IntegratedAgencyCard
                        key={agenciesData?.id}
                        enableAllowed={agenciesData?.enableAllowed}
                        agencyId={agenciesData?.agencyId}
                        isEnabled={agenciesData?.isEnabled}
                        agencyName={agenciesData?.agencyName}
                        syncStatus={agenciesData?.syncStatus}
                        isLatest={agenciesData.isLatest}
                        lastSynced={agenciesData?.lastUpdatedTimestamp}
                        lastUsed={agenciesData?.lastTrainedTimestamp}
                        lastTrained={agenciesData.lastTrainedTimestamp}
                        lastModelTrained={agenciesData?.lastModelTrained  ??"N/A"}
                      />
                    );
                  }
                )}
              </div>
            ) }

              {!isLoading && agencies?.response?.data?.length===0 && (
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
    </div>
  );
};

export default IntegratedAgencies;
