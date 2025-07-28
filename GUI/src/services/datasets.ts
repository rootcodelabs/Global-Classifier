import { dataModelsEndpoints, datasetsEndpoints } from 'utils/endpoints';
import apiDev from './api-dev';

export async function getDatasetsOverview(
  pageNum: number,
  sort: string
) {
  const { data } = await apiDev.get(datasetsEndpoints.GET_OVERVIEW(), {
    params: {
      page: pageNum,
      generationStatus: "all",
      sortBy:sort?.split(" ")?.[0],
      sortType: sort?.split(" ")?.[1],
      pageSize: 12,
    },
  });
  return data?.response ?? [];
}

export async function getDatasetMetadata(
  datasetId: number |string) {
  const { data } = await apiDev.get(datasetsEndpoints.GET_METADATA(), {
    params: {
      datasetId
    },
  });
  return data?.response?.response?.[0] ?? [];
}

export async function getDatasetData(
  datasetVersionId: number |string,
  pageNum?: number,
) {
  const { data } = await apiDev.get(datasetsEndpoints.GET_DATASETS_DATA(), {
    params: {
      datasetVersionId,
      pageNum : pageNum ?? 1,
      pageSize:5
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