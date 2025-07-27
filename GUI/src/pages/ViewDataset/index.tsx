import BackArrowButton from 'assets/BackArrowButton';
import { Button, Card, DataTable, Dialog, Icon, Label, Switch } from 'components';
import { ButtonAppearanceTypes, LabelType } from 'enums/commonEnums';
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { generateDynamicColumns } from 'utils/dataTableUtils';
import { MdOutlineDeleteOutline, MdOutlineEdit } from 'react-icons/md';
import { CellContext, ColumnDef, createColumnHelper, PaginationState } from '@tanstack/react-table';
import {
  SelectedRowPayload,
} from 'types/datasets';
import SkeletonTable from '../../components/molecules/TableSkeleton/TableSkeleton';
import { sampleDatasetRows } from 'data/sampleDataset';
import DynamicForm from 'components/FormElements/DynamicForm';
import { datasetQueryKeys, integratedAgenciesQueryKeys } from 'utils/queryKeys';
import { getDatasetData, getDatasetMetadata } from 'services/datasets';
import { useQuery } from '@tanstack/react-query';
import { useDialog } from 'hooks/useDialog';
import { fetchAllAgencies } from 'services/agencies';
import NoDataView from 'components/molecules/NoDataView';

const ViewDataset = () => {
  const { t } = useTranslation();
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 5,
  });
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState<boolean>(false);
  const { open, close } = useDialog();
  const isMetadataLoading = false;
  // Sample data for demonstration purposes
  const datasets = sampleDatasetRows;
  const [deletedRowIds, setDeletedRowIds] = useState<(string | number)[]>([]);
  const [searchParams] = useSearchParams();
  const datasetId = searchParams.get('datasetId');
  const [selectedRow, setSelectedRow] = useState<SelectedRowPayload>();
  const [editedRows, setEditedRows] = useState<SelectedRowPayload[]>([]);
  const [selectedAgencyId, setSelectedAgencyId] = useState<string | number>("all");


  const { data: metadata, isLoading } = useQuery({
    queryKey: datasetQueryKeys.GET_META_DATA(datasetId ?? 0),
    queryFn: () => getDatasetMetadata(datasetId ?? 0),
  });

  const { data: dataset, isLoading: datasetIsLoading } = useQuery({
    queryKey: datasetQueryKeys.GET_DATA_SETS(datasetId ?? 0, selectedAgencyId, pagination.pageIndex + 1),
    queryFn: () => getDatasetData(datasetId ?? 0, pagination.pageIndex + 1),
  });
  const [updatedDataset, setUpdatedDataset] = useState(dataset);

  useEffect(() => {
    if (dataset) {
      setUpdatedDataset(dataset);
    }
  }, [dataset]);  

  const { data: agencies } = useQuery({
    queryKey: integratedAgenciesQueryKeys.ALL_AGENCIES_LIST(),
    queryFn: () => fetchAllAgencies(),
  });

  const editView = (props: CellContext<any, unknown>) => {
    return (
      <Button
        appearance={ButtonAppearanceTypes.TEXT}
        onClick={() => {
          setSelectedRow(props.row.original);
          setIsUpdateModalOpen(true);
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
        open({
          title: t('datasets.detailedView.deleteDataRowTitle') ?? '',
          content: <p>{t('datasets.detailedView.deleteDataRowDesc')}</p>,
          footer: (
            <div className="button-wrapper">
              <Button
                appearance={ButtonAppearanceTypes.SECONDARY}
                onClick={() => {
                  close();
                }}
              >
                {t('global.cancel')}
              </Button>
              <Button
                appearance={ButtonAppearanceTypes.ERROR}
                onClick={() => deleteDataRecord(props.row.original)}
              >
                {t('global.confirm')}
              </Button>
            </div>
          ),
        });
      }}
    >
      <Icon icon={<MdOutlineDeleteOutline />} />
      {t('global.delete')}
    </Button>
  );

const dataColumns = useMemo(() => {
  const columnHelper = createColumnHelper<any>();
  
  // Incremental ID column
  const incrementalIdColumn = columnHelper.display({
    id: 'rowNumber',
    header: t('datasets.detailedView.table.id') || 'Item ID',
    cell: ({ row }) => {
      const rowNumber = (pagination.pageIndex * pagination.pageSize) + row.index + 1;
      return <span>{rowNumber}</span>;
    },
    meta: { size: 60 },
  });

  const questionColumn = columnHelper.accessor('dataItem', {
    header: t('datasets.detailedView.table.data') || 'Data',
    id: 'dataItem',
  });

  const agencyColumn = columnHelper.accessor('agencyName', {
    header: t('datasets.detailedView.table.client') || 'Client Name',
    id: 'agencyName',
  });

  // Action columns
  const editColumn = columnHelper.display({
    id: 'edit',
    cell: editView,
    meta: { size: '1%' },
  });

  const deleteColumn = columnHelper.display({
    id: 'delete', 
    cell: deleteView,
    meta: { size: '1%' },
  });

  return [incrementalIdColumn, questionColumn, agencyColumn, editColumn, deleteColumn];
}, [editView, deleteView, pagination.pageIndex, pagination.pageSize, t]);

  const editDataRecord = (dataRow: SelectedRowPayload) => {
    const originalRow = dataset?.find(
      (row: any) => row.itemId === dataRow.itemId
    );

    if (
      originalRow &&
      (originalRow.dataItem !== dataRow.dataItem || originalRow.agencyId !== dataRow.agencyId)
    ) {
      setEditedRows((prev) => {
        const exists = prev.find((row) => row.itemId === dataRow.itemId);
        const newEditedRows = exists
          ? prev.map((row) => (row.itemId === dataRow.itemId ? dataRow : row))
          : [...prev, dataRow];
        setIsUpdateModalOpen(false);

        return newEditedRows;
      });
    }

    // Update the table view
    const payload = updatedDataset?.map((row: any) =>
      row.itemId === selectedRow?.itemId
        ? {
          itemId: dataRow.itemId,
          dataItem: (dataRow as any).dataItem,
          agencyId: (dataRow as any).agencyId,
          agencyName: (dataRow as any).agencyName,

        }
        : row
    );
    setUpdatedDataset(payload as { itemId: number; dataItem: string; agencyId: string; agencyName: string; }[]);
  };

  const deleteDataRecord = (dataRow: SelectedRowPayload) => {
    if (!dataRow) return;
    setUpdatedDataset((prev: { itemId: number; dataItem: string; agencyName: string; agencyId: string }[] | undefined) => prev?.filter((row: { itemId: number }) => row.itemId !== dataRow.itemId));
    setDeletedRowIds((prev) => [...prev, dataRow.itemId]);
    close();
  };

const minorUpdate = () => {
  const updatedDataItems: SelectedRowPayload[] = [];

  editedRows.forEach((row) => {
    // Skip if this row was deleted
    if (deletedRowIds.includes(row.itemId)) {
      return;
    }

    const original = dataset?.find((r: any) => r.itemId === row.itemId);
    if (!original) return;
    
    // Check if anything changed
    if (original.dataItem !== row.dataItem || original.agencyId !== row.agencyId) {
      updatedDataItems.push(row);
    }
  });

  const payload = {
    updatedDataItems,
    deletedRows: deletedRowIds,
  };
  console.log(payload, 'minorUpdatePayload');
};
  
  return (
    <div className="container">
      <div className="title_container">
        <div className="flex-between">
          <Link to={'/datasets'}>
            <BackArrowButton />
          </Link>
          <div className="title">{t('datasets.detailedView.dataset')} {`V${metadata?.major}.${metadata?.minor}`}</div>
        </div>
      </div>
      {isMetadataLoading && <SkeletonTable rowCount={2} />}
      {metadata && !isMetadataLoading && (
        <div>
          <Card
            isHeaderLight={false}
          >
            <div className="flex-between">
              <div>
                <p>
                  {t('datasets.detailedView.version') ?? ''} : {`V${metadata?.major}.${metadata?.minor}`}
                </p>
                <p>
                  {t('datasets.detailedView.connectedModels') ?? ''} : {metadata?.connectedModels?.join(', ') ?? ''}
                </p>
                <p>
                  {t('datasets.detailedView.noOfItems') ?? ''} : {20}
                </p>
              </div>
              <div>
                <Button appearance='secondary' size='s'>
                  Export Dataset
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
      <div className="mb-20">
        {isLoading && <SkeletonTable rowCount={5} />}
        {!isLoading && updatedDataset && updatedDataset?.length > 0 && (
          <DataTable
            data={updatedDataset}
            columns={dataColumns as ColumnDef<string, string>[]}
            pagination={pagination}
            dropdownFilters={[
              {
                columnId: 'agencyName',
                options: agencies?.map((a: { agencyName: string; agencyId: number }) => ({
                  label: a.agencyName,
                  value: a.agencyId,
                  agencyId: a.agencyId,
                })) ?? [],
              },
            ]}
            onSelect={(value) => {
              setSelectedAgencyId(value);
              setPagination({
                pageIndex: 0,
                pageSize: 5,
              });
              setUpdatedDataset([]);
            }}
            setPagination={(state: PaginationState) => {
              if (
                state.pageIndex === pagination.pageIndex &&
                state.pageSize === pagination.pageSize
              )
                return;
              setPagination(state);
            }}
            pagesCount={4}
            isClientSide={false}
          />
        )}
        {
          updatedDataset?.length === 0 && (
           <NoDataView text='No data available'/>
          )
        }
        <div className="button-container">
          <Button
            appearance={ButtonAppearanceTypes.ERROR}
            onClick={() => { }
            }
          >
            {t('datasets.detailedView.delete') ?? ''}
          </Button>
          <Button
            onClick={minorUpdate}
          >
            {t('global.save') ?? ''}
          </Button>
        </div>
      </div>
      {isUpdateModalOpen && (
        <Dialog
          title={t('datasets.detailedView.editDataRowTitle')}
          onClose={() => setIsUpdateModalOpen(false)}
          isOpen={
            isUpdateModalOpen}
        >
          <p>{t('datasets.detailedView.editDataRowDesc')}</p>

          <DynamicForm
            formData={
              (selectedRow as SelectedRowPayload | undefined) ?? { dataItem: '', agencyName: '', itemId: 0, agencyId: 0 }
            }
            clientOptions={agencies?.map((a: { agencyName: string; agencyId: number }) => ({
              label: a.agencyName,
              value: a.agencyId,
              agencyId: a.agencyId,
            })) ?? []}
            onSubmit={editDataRecord as (data: SelectedRowPayload) => void}
            setPatchUpdateModalOpen={setIsUpdateModalOpen as React.Dispatch<React.SetStateAction<boolean>>}
          />
        </Dialog>
      )}
    </div>
  );
};

export default ViewDataset;