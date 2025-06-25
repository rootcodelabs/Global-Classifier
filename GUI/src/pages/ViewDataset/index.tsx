import BackArrowButton from 'assets/BackArrowButton';
import { Button, Card, DataTable, Dialog, Icon, Label, Switch } from 'components';
import { ButtonAppearanceTypes, LabelType } from 'enums/commonEnums';
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { generateDynamicColumns } from 'utils/dataTableUtils';
import { MdOutlineDeleteOutline, MdOutlineEdit } from 'react-icons/md';
import { CellContext, ColumnDef, PaginationState } from '@tanstack/react-table';
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
    queryFn: () => getDatasetData(datasetId ?? 0, selectedAgencyId, pagination.pageIndex + 1),
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

  const dataColumns = generateDynamicColumns(["id", "question", "clientName"], editView, deleteView);

  const editDataRecord = (dataRow: SelectedRowPayload) => {
    const originalRow = dataset?.find(
      (row: any) => row.id === dataRow.id
    );

    // Only proceed if question or clientId has changed
    if (
      originalRow &&
      (originalRow.question !== dataRow.question || originalRow.clientId !== dataRow.clientId)
    ) {
      // Compute the new editedRows array
      setEditedRows((prev) => {
        const exists = prev.find((row) => row.id === dataRow.id);
        const newEditedRows = exists
          ? prev.map((row) => (row.id === dataRow.id ? dataRow : row))
          : [...prev, dataRow];

        console.log('Updated editedRows:', newEditedRows);
        setIsUpdateModalOpen(false);

        return newEditedRows;
      });
    }
    // Update the table view as before
    const payload = updatedDataset?.map((row: any) =>
      row.id === selectedRow?.id
        ? {
          id: dataRow.id,
          question: (dataRow as any).question,
          clientId: (dataRow as any).clientId,
          clientName: (dataRow as any).clientName,

        }
        : row
    );
    setUpdatedDataset(payload as { id: number; question: string; clientId: string; clientName: string; }[]);
  };

  const deleteDataRecord = (dataRow: SelectedRowPayload) => {
    if (!dataRow) return;
    setUpdatedDataset((prev: { id: number; question: string; clientName: string; clientId: string }[] | undefined) => prev?.filter((row: { id: number }) => row.id !== dataRow.id));
    setDeletedRowIds((prev) => [...prev, dataRow.id]);
    close();
  };

  const minorUpdate = () => {
    const questionUpdated: SelectedRowPayload[] = [];
    const clientUpdated: SelectedRowPayload[] = [];

    editedRows.forEach((row) => {
      const original = dataset?.find((r: any) => r.id === row.id);
      if (!original) return;
      const isQuestionChanged = original.question !== row.question;
      const isClientChanged = original.clientId !== row.clientId;

      if (isQuestionChanged && !isClientChanged) {
        questionUpdated.push(row);
      }
      if (isClientChanged) {
        clientUpdated.push(row);
      }
    });

    const payload = {
      questionUpdated,
      clientUpdated,
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
                  {t('datasets.detailedView.connectedModels') ?? ''} : N/A
                </p>
                <p>
                  {t('datasets.detailedView.noOfItems') ?? ''} : {dataset?.length ?? 0}
                </p>
              </div>
              <div>
                {/* <Switch label=''></Switch>
                <br /> */}
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
        {!isLoading && updatedDataset && updatedDataset.length > 0 && (
          <DataTable
            data={updatedDataset}
            columns={dataColumns as ColumnDef<string, string>[]}
            pagination={pagination}
            filterable
            dropdownFilters={[
              {
                columnId: 'clientName',
                options: agencies?.map((a: { agencyName: string; agencyId: number }) => ({
                  label: a.agencyName,
                  value: a.agencyId,
                  clientId: a.agencyId,
                })) ?? [],
              },
            ]}
            onSelect={(value) => {
              console.log('Selected option:', value);
              setSelectedAgencyId(value);
              setPagination({
                pageIndex: 0,
                pageSize: 5,
              })
            }}
            setPagination={(state: PaginationState) => {
              if (
                state.pageIndex === pagination.pageIndex &&
                state.pageSize === pagination.pageSize
              )
                return;
              setPagination(state);
            }}
            pagesCount={10}
            isClientSide={false}
          />
        )}
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
              (selectedRow as SelectedRowPayload | undefined) ?? { question: '', clientName: '', id: 0, clientId: 0 }
            }
            clientOptions={agencies?.map((a: { agencyName: string; agencyId: number }) => ({
              label: a.agencyName,
              value: a.agencyId,
              clientId: a.agencyId,
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
