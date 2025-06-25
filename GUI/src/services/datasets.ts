import { datasetsEndpoints } from 'utils/endpoints';
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
  return data?.response?.[0] ?? [];
}

export async function getDatasetData(
  datasetId: number |string,
  agencyId?: number |string,
  pageNum?: number,
) {
  const { data } = await apiDev.get(datasetsEndpoints.GET_DATASETS_DATA(), {
    params: {
      datasetId,
      agencyId,
      pageNum : pageNum ?? 1,
    },
  });
  return data?.response ?? [];
}