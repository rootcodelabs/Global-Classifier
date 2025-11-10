import { dataModelsEndpoints, datasetsEndpoints } from 'utils/endpoints';
import apiDev from './api-dev';
import { DATASET_PAGE_SIZE, OVERVIEW_PAGE_SIZE } from 'utils/constants';

export async function getDatasetsOverview(
  pageNum: number,
  sort: string,
  searchTerm: string = 'all'
) {
  const { data } = await apiDev.get(datasetsEndpoints.GET_OVERVIEW(), {
    params: {
      page: pageNum,
      generationStatus: "all",
      sortBy: sort?.split(" ")?.[0],
      sortType: sort?.split(" ")?.[1],
      pageSize: OVERVIEW_PAGE_SIZE,
      datasetName: searchTerm,
    },
  });
  return data?.response ?? [];
}

export async function getDatasetMetadata(
  datasetId: number | string) {
  const { data } = await apiDev.get(datasetsEndpoints.GET_METADATA(), {
    params: {
      datasetId
    },
  });
  return data?.response?.response?.[0] ?? [];
}

export async function getDatasetData(
  datasetVersionId: number | string,
  pageNum?: number,
  clientId?: string,
  pageSize?: number

) {
  const { data } = await apiDev.get(datasetsEndpoints.GET_DATASETS_DATA(), {
    params: {
      datasetVersionId,
      pageNum: pageNum ?? 1,
      pageSize: pageSize ?? DATASET_PAGE_SIZE,
      clientId: clientId ?? "all",
    },
  });
  return data?.response ?? [];
}

export async function getAllDatasetVersions() {
  const { data } = await apiDev.get(datasetsEndpoints.GET_ALL_DATASET_VERSIONS());
  return data?.response ?? [];
}

export async function getDataGenerationProgress() {
  const { data } = await apiDev.get(datasetsEndpoints.GET_DATA_GENERATION_PROGRESS());
  return data?.response?.data;
}

export async function updateDataset(payload: {
  updatedDataItems: any[];
  deletedRows: (string | number)[];
  updatedRowsLength: number;
  deletedRowsLength: number;
}) {
  const { data } = await apiDev.post(datasetsEndpoints.UPDATE_DATASET(), payload);
  return data?.response ?? {};
}

export async function deleteDataset(datasetVersionId: number | string) {
  const { data } = await apiDev.post(datasetsEndpoints.DELETE_DATASET(), { datasetVersionId });
  return data?.response ?? {};
}