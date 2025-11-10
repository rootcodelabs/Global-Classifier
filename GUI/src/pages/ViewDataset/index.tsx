import BackArrowButton from 'assets/BackArrowButton';
import { Button, Card, DataTable, Dialog, Icon, Label, Switch } from 'components';
import { ButtonAppearanceTypes, LabelType } from 'enums/commonEnums';
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { MdOutlineDeleteOutline, MdOutlineEdit } from 'react-icons/md';
import { CellContext, ColumnDef, createColumnHelper, PaginationState, RowSelectionState } from '@tanstack/react-table';
import {
  SelectedRowPayload,
} from 'types/datasets';
import SkeletonTable from '../../components/molecules/TableSkeleton/TableSkeleton';
import DynamicForm from 'components/FormElements/DynamicForm';
import { datasetQueryKeys, integratedAgenciesQueryKeys } from 'utils/queryKeys';
import { deleteDataset, getDatasetData, getDatasetMetadata, updateDataset } from 'services/datasets';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useDialog } from 'hooks/useDialog';
import { fetchAllAgencies } from 'services/agencies';
import NoDataView from 'components/molecules/NoDataView';
import { DATASET_PAGE_SIZE } from 'utils/constants';

const ViewDataset = () => {
  const { t } = useTranslation();
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: DATASET_PAGE_SIZE,
  });
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState<boolean>(false);
  const { open, close } = useDialog();
  const [deletedRowIds, setDeletedRowIds] = useState<(string | number)[]>([]);
  const [searchParams] = useSearchParams();
  const datasetVersionId = searchParams.get('datasetId');
  const [selectedRow, setSelectedRow] = useState<SelectedRowPayload>();
  const [editedRows, setEditedRows] = useState<SelectedRowPayload[]>([]);
  const [selectedAgencyId, setSelectedAgencyId] = useState<string | number>("all");
  const [originalDataset, setOriginalDataset] = useState<any[]>([]);
  const [updatePayload, setUpdatePayload] = useState<{
    updatedDataItems: SelectedRowPayload[];
    deletedRows: (string | number)[];
    updatedRowsLength: number;
    deletedRowsLength: number;
  } | null>(null);
  const navigate = useNavigate();
  const { data: metadata, isLoading: isMetadataLoading, refetch: refetchMetadata } = useQuery({
    queryKey: datasetQueryKeys.GET_META_DATA(datasetVersionId ?? 0),
    queryFn: () => getDatasetMetadata(datasetVersionId ?? 0),
  });

  const { data: dataset, isLoading: datasetIsLoading, refetch: refetchDataset } = useQuery({
    queryKey: datasetQueryKeys.GET_DATA_SETS(
      datasetVersionId ?? 0,
      selectedAgencyId,
      pagination.pageIndex + 1
    ),
    queryFn: () => getDatasetData(
      datasetVersionId ?? 0,
      pagination.pageIndex + 1,
      selectedAgencyId === "all" ? "all" : selectedAgencyId.toString(),
      pagination.pageSize
    ),
  });
  const [updatedDataset, setUpdatedDataset] = useState(dataset);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [isProgressModalOpen, setIsProgressModalOpen] = useState<boolean>(false);

  const selectedRowsData = useMemo(() => {
    if (!updatedDataset) return [];
    return Object.keys(rowSelection)
      .filter(key => rowSelection[key])
      .map(key => updatedDataset[parseInt(key)])
      .filter(Boolean);
  }, [rowSelection, updatedDataset]);
  const selectedRowsCount = selectedRowsData.length;

   useEffect(() => {
    setRowSelection({});
  }, [pagination.pageIndex, pagination.pageSize,selectedAgencyId]);

   const handleBulkDelete = () => {
    if (selectedRowsCount === 0) return;
    
    open({
      title: t('datasets.detailedView.bulkDeleteTitle') || 'Delete Selected Items',
      content: (
        <div>
          <p>{t('datasets.detailedView.bulkDeleteDesc1') || 'Are you sure you want to delete the selected items?'}</p>
          <p><strong>{t('datasets.detailedView.bulkDeleteDesc2') || 'Note : This deletion will not be affected in the original dataset until you click on Save Changes.'}</strong> </p>
        </div>
      ),
      footer: (
        <div className="button-wrapper">
          <Button
            appearance={ButtonAppearanceTypes.SECONDARY}
            onClick={() => close()}
          >
            {t('global.cancel')}
          </Button>
          <Button
            appearance={ButtonAppearanceTypes.ERROR}
            onClick={() => {
              // Add selected items to deleted rows
              const selectedIds = selectedRowsData.map(row => row.itemId);
              setDeletedRowIds(prev => [...prev, ...selectedIds]);
              
              // Remove selected items from updated dataset
                setUpdatedDataset((prev: SelectedRowPayload[] | undefined) => 
                prev?.filter((row: SelectedRowPayload) => !selectedIds.includes(row.itemId))
                );
              // Clear selection
              setRowSelection({});
              close();
            }}
          >
            {t('global.delete')}
          </Button>
        </div>
      ),
    });
  };

  useEffect(() => {
    if (dataset) {
      setOriginalDataset(prev => {
        const newOriginal = [...prev];
        dataset.forEach((row: any) => {
          if (!newOriginal.find(orig => orig.itemId === row.itemId)) {
            newOriginal.push(row);
          }
        });
        return newOriginal;
      });

      const mergedDataset = dataset?.map((row: any) => {
        const editedRow = editedRows.find((edited) => edited.itemId === row.itemId);
        return editedRow ? editedRow : row;
      });

      setUpdatedDataset(mergedDataset);
    }
  }, [dataset, editedRows]);

  useEffect(() => {
   refetchDataset();
  }, [pagination]);

  const { data: agencies } = useQuery({
    queryKey: integratedAgenciesQueryKeys.ALL_AGENCIES_LIST(),
    queryFn: () => fetchAllAgencies(),
  });

  const handleClearFilters = () => {
    setSelectedAgencyId("all");
    setPagination({
      pageIndex: 0,
      pageSize: DATASET_PAGE_SIZE,
    });
    setUpdatedDataset([]);
  };

  const hasActiveFilters = selectedAgencyId !== "all";

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
          content: <div><p>{t('datasets.detailedView.deleteDataRowDesc')}</p>
          <strong>{t('datasets.detailedView.bulkDeleteDesc2')}</strong></div>,
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

       // Selection checkbox column
    const selectColumn = columnHelper.display({
      id: 'select',
      header: ({ table }) => (
        <input
          type="checkbox"
          checked={table.getIsAllPageRowsSelected()}
          onChange={table.getToggleAllPageRowsSelectedHandler()}
          aria-label={t('global.selectAll') || 'Select all'}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
          aria-label={`${t('global.select') || 'Select'} ${row.original.dataItem}`}
        />
      ),
      meta: { size: 40 },
    });

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

    return [selectColumn, incrementalIdColumn, questionColumn, agencyColumn, editColumn, deleteColumn];
  }, [editView, deleteView, pagination.pageIndex, pagination.pageSize, t]);

  const editDataRecord = (dataRow: SelectedRowPayload) => {
    const originalRow = originalDataset.find((row: any) => row.itemId === dataRow.itemId);

    const hasChanges = originalRow && (
      originalRow.dataItem !== dataRow.dataItem ||
      originalRow.agencyId !== dataRow.agencyId
    );

    if (hasChanges) {
      setEditedRows((prev) => {
        const exists = prev.find((row) => row.itemId === dataRow.itemId);
        const newEditedRows = exists
          ? prev.map((row) => (row.itemId === dataRow.itemId ? dataRow : row))
          : [...prev, dataRow];

        return newEditedRows;
      });
    }

    setIsUpdateModalOpen(false);
  };

  const deleteDataRecord = (dataRow: SelectedRowPayload) => {
    if (!dataRow) return;
    setUpdatedDataset((prev: { itemId: number; dataItem: string; agencyName: string; agencyId: string }[] | undefined) => prev?.filter((row: { itemId: number }) => row.itemId !== dataRow.itemId));
    setDeletedRowIds((prev) => [...prev, dataRow.itemId]);
    close();
  };

  const deleteMutation = useMutation({
    mutationFn: deleteDataset,
    onSuccess: () => {
      navigate('/datasets');

    },
    onError: () => {
      open({
        title: t('datasets.detailedView.datasetUpdateUnsuccessfulTitle'),
        content: t('datasets.detailedView.datasetUpdateUnsuccessfulDesc'),
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: updateDataset,
    onSuccess: async () => {
      setTimeout(() => {
        setIsUpdating(false);
        setIsProgressModalOpen(false);
        setEditedRows([]);
        setDeletedRowIds([]);
      }, 3000);
      await Promise.all([
        refetchMetadata(),
        refetchDataset()
      ]);
    },
    onError: () => {
      setIsUpdating(false);
      setIsProgressModalOpen(false);
      setEditedRows([]);
      setDeletedRowIds([]);
      open({
        title: t('datasets.detailedView.datasetUpdateUnsuccessfulTitle'),
        content: t('datasets.detailedView.datasetUpdateUnsuccessfulDesc'),
      });
    },
  });


  const minorUpdate = () => {
    setIsProgressModalOpen(true);

    // Create payload inside the function
    const updatedDataItems: SelectedRowPayload[] = editedRows.filter((row) => {
      return !deletedRowIds.includes(row.itemId);
    });

    const updatePayload = {
      updatedDataItems,
      deletedRows: deletedRowIds,
      updatedRowsLength: updatedDataItems.length,
      deletedRowsLength: deletedRowIds.length,
    };

    // Store payload in a ref or state if you need to access it in the dialog
    setUpdatePayload(updatePayload);
  };

  const handleDeleteDataset = () => {
    open({
      title: t('datasets.detailedView.confirmDeleteDatasetTitle'),
      content: t('datasets.detailedView.confirmDeleteDatasetDesc'),
      footer: (
        <div className="button-wrapper">
          <Button
            appearance={ButtonAppearanceTypes.SECONDARY}
            onClick={() => close()}
          >
            {t('global.cancel')}
          </Button>
          <Button
            appearance={ButtonAppearanceTypes.ERROR}
            onClick={() => {
              deleteMutation.mutate(datasetVersionId ?? 0);
              close();
            }}
          >
            {t('global.delete')}
          </Button>
        </div>
      ),
    });
  };

  return (
    <div className="container">
      {isMetadataLoading && <SkeletonTable rowCount={2} />}
      {metadata && !isMetadataLoading && (
        <div>
          <div className="title_container">
            <div className="flex-grid m-30-0">
              <Link to={'/datasets'}>
                <BackArrowButton />
              </Link>
              <div className="title">{t('datasets.detailedView.dataset')} {`V${metadata?.major}.${metadata?.minor}`}</div>
            </div>
          </div>
          <Card
            isHeaderLight={false}
          >
            <div className="flex-between">
              <div style={{ minWidth: 'fit-content' }}>
                <p>
                  <b>{t('datasets.detailedView.version') ?? ''} :</b>  {`V${metadata?.major}.${metadata?.minor}`}
                </p>
                <p><b>{t('datasets.detailedView.connectedModels') ?? ''} : </b>
                {metadata?.connectedModels.length>0 ? metadata?.connectedModels?.join(', ') : 'N/A'}</p>
                <p>
                  <b>{t('datasets.detailedView.noOfItems') ?? ''} :</b> {metadata?.totalDataCount ?? "-"}
                </p>
              </div>
              <Button
                appearance={ButtonAppearanceTypes.PRIMARY}
              >
                {t('datasets.detailedView.export') ?? ''}
              </Button>

            </div>
          </Card>
        </div>
      )}
      <div className="mb-20">
        <div className="dataset-controls">
          <div className="filter-controls">
            {hasActiveFilters && (
              <Button
                appearance={ButtonAppearanceTypes.SECONDARY}
                onClick={handleClearFilters}
                size="s"
              >
                {t('global.clearFilters') || 'Clear Filters'}
              </Button>
            )}
          </div>
          {/* Bulk actions */}
          {selectedRowsCount > 0 && (
            <div className="bulk-actions">
              <span className="selected-count">
                {selectedRowsCount} {t('datasets.detailedView.itemsSelected') || 'items selected'}
              </span>
              <Button
                appearance={ButtonAppearanceTypes.ERROR}
                onClick={handleBulkDelete}
                size="s"
              >
                <Icon icon={<MdOutlineDeleteOutline />} />
                {t('global.deleteSelected') || 'Delete Selected'}
              </Button>
            </div>
          )}
        </div>
        {datasetIsLoading && <SkeletonTable rowCount={10} />}
        {!datasetIsLoading && (
          <DataTable
            data={updatedDataset ?? []}
            columns={dataColumns as ColumnDef<string, string>[]}
            pagination={pagination}
            rowSelection={rowSelection}
            setRowSelection={setRowSelection}
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
            showPageSizeSelector={true}
            onSelect={(value) => {
              setSelectedAgencyId(value);
              setPagination({
                pageIndex: 0,
                pageSize: pagination.pageSize,
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
            pagesCount={dataset?.[0]?.totalPages ?? 0}
            isClientSide={false}
          />
        )}

        <div className="button-container-bottom">
          <Button
            appearance={ButtonAppearanceTypes.ERROR}
            onClick={handleDeleteDataset}
          >
            {t('datasets.detailedView.delete') ?? ''}
          </Button>
          <Button
            onClick={minorUpdate}
            disabled={editedRows.length === 0 && deletedRowIds.length === 0}
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
      {isProgressModalOpen && (
        <Dialog
          title={t('datasets.detailedView.confirmUpdateDatasetTitle')}
          onClose={() => setIsProgressModalOpen(false)}
          isOpen={isProgressModalOpen}
          footer={
            <div className="button-wrapper">
              <Button
                appearance={ButtonAppearanceTypes.SECONDARY}
                onClick={() => setIsProgressModalOpen(false)}
                disabled={isUpdating}
              >
                {t('global.cancel')}
              </Button>
              <Button
                appearance={ButtonAppearanceTypes.PRIMARY}
                onClick={() => {
                  if (updatePayload) {
                    updateMutation.mutate(updatePayload);
                    setIsUpdating(true);
                  }
                }}
                disabled={isUpdating || !updatePayload}
              >
                {t('global.confirm')}
              </Button>
            </div>
          }
        >
          {isUpdating ? (
            <div style={{ justifyContent: 'center', alignItems: 'center' }} className='flex'>
              <p>{t('datasets.detailedView.dataBeingUpdated')}</p>
              <div style={{ justifyContent: 'center', alignItems: 'center' }} className='flex'>
                <div
                  className="spinner"
                  style={{ width: 30, height: 30, borderWidth: 5 }}
                />
              </div>
            </div>
          ) : (
            <div>
              <p>{t('datasets.detailedView.confirmUpdateDatasetDesc')}</p>
              {updatePayload && (
                <div>
                  <p>Items to update: {updatePayload.updatedRowsLength}</p>
                  <p>Items to delete: {updatePayload.deletedRowsLength}</p>
                </div>
              )}
            </div>
          )}
        </Dialog>
      )}
    </div>
  );
};

export default ViewDataset;