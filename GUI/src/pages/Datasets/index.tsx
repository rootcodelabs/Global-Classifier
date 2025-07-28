import { FC, useState } from 'react';
import './DatasetGroups.scss';
import { useTranslation } from 'react-i18next';
import { Button, FormSelect } from 'components';
import Pagination from 'components/molecules/Pagination';
import { useQuery } from '@tanstack/react-query';
import { datasetQueryKeys } from 'utils/queryKeys';
import { DatasetViewEnum } from 'enums/datasetEnums';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import NoDataView from 'components/molecules/NoDataView';
import SearchInput from 'components/FormElements/SearchInput';
import DatasetCard from 'components/molecules/DatasetCard';
import { getDatasetsOverview } from 'services/datasets';
import { Dataset } from 'types/datasets';

const Datasets: FC = () => {
  const { t } = useTranslation();

  const [pageIndex, setPageIndex] = useState(1);
  const view = (DatasetViewEnum.LIST);
  const [sortOption, setSortOption] = useState("created_at desc");
  const [searchTerm, setSearchTerm] = useState<string>('all');


  const { data: datasets, isLoading } = useQuery({
    queryKey: datasetQueryKeys.DATASET_OVERVIEW(pageIndex, sortOption),
    queryFn: () => getDatasetsOverview(pageIndex, sortOption),
  });

  const pageCount = datasets?.[0]?.totalPages ?? 1;


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
            <div className="title">{t('datasets.title')}</div>
          </div>
          <div>
            <div className="search-panel">
              <div style={{ flex: 4 }}>
                <SearchInput
                  onSearch={handleSearch}
                  placeholder="Search datasets..."
                  initialValue={searchTerm}
                />
              </div>
              <div style={{ flex: 2 }}>
                <FormSelect
                  label=""
                  name="sort"
                  placeholder={t('datasets.table.sortBy') ?? ''}
                  options={[
                    {
                      label: t(
                        'datasets.sortOptions.createdDateDesc'
                      ),
                      value: 'created_at desc',
                    },
                    {
                      label: t('datasets.sortOptions.createdDateAsc'),
                      value: 'created_at asc',
                    }
                  ]}
                  onSelectionChange={handleSortChange}
                  defaultValue={sortOption}
                />
              </div>
              <div style={{ flex: 1 }}>
                <Button
                  appearance="secondary"
                  onClick={() => { setPageIndex(1); setSortOption("created_at desc"); setSearchTerm('all'); }}
                >Reset
                </Button>
              </div>
            </div>

            {isLoading && (
              <div className="skeleton-container">
                <CircularSpinner />
              </div>
            )}
            {datasets?.length > 0 && (
              <div className="grid-container m-30-0">
                {datasets?.map(
                  (dataset: Dataset, index: number) => {
                    return (
                      <DatasetCard
                        key={index}
                        datasetId={dataset?.id ??""}
                        dataGenerationStatus={dataset?.generationStatus}
                        lastTrained={dataset.lastTrained}
                        lastModelTrained={dataset?.lastModelTrained ?? "N/A"}
                        majorVersion={dataset?.major}
                        minorVersion={dataset?.minor}
                      />
                    );
                  }
                )}
              </div>
            )}

            {!isLoading && datasets?.response?.data?.length === 0 && (
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

export default Datasets;
