import { correctedTextEndpoints, datasetsEndpoints } from 'utils/endpoints';
import apiDev from './api-dev';
import apiExternal from './api-external';
import { PaginationState } from '@tanstack/react-table';
import {
  DatasetDetails,
  DatasetGroup,
  MetaData,
  MinorPayLoad,
  Operation,
  PatchPayLoad,
} from 'types/datasetGroups';

export async function getDatasetsOverview(
  pageNum: number,
  name: string,
  majorVersion: number,
  minorVersion: number,
  patchVersion: number,
  validationStatus: string,
  sort: string
) {
  const { data } = await apiDev.get(datasetsEndpoints.GET_OVERVIEW(), {
    params: {
      page: pageNum,
      groupName: name,
      majorVersion,
      minorVersion,
      patchVersion,
      validationStatus,
      sortBy:sort?.split(" ")?.[0],
      sortType: sort?.split(" ")?.[1],
      pageSize: 12,
    },
  });
  return data;
}

export async function enableDataset(enableData: Operation) {
  const { data } = await apiDev.post(datasetsEndpoints.ENABLE_DATASET(), {
    dgId: enableData.dgId,
    operationType: enableData.operationType,
  });
  return data;
}

export async function getFilterData() {
  const { data } = await apiDev.get(datasetsEndpoints.GET_DATASET_FILTERS());
  return data;
}

export async function getDatasets(
  pagination: PaginationState,
  groupId: string | number | null
) {
  const { data } = await apiDev.get(datasetsEndpoints.GET_DATASETS(), {
    params: {
      pageNum: pagination.pageIndex + 1,
      groupId,
    },
  });

  return data?.response?.data[0] as DatasetDetails;
}

export async function getMetadata(groupId: string | number | null) {
  const { data } = await apiDev.get(datasetsEndpoints.GET_METADATA(), {
    params: {
      groupId,
    },
  });
  return data?.response?.data as MetaData[];
}

export async function createDatasetGroup(datasetGroup: DatasetGroup) {
  const { data } = await apiDev.post(datasetsEndpoints.CREATE_DATASET_GROUP(), {
    ...datasetGroup,
  });
  return data;
}

export async function importDataset(file: File, id: string | number) {
  const { data } = await apiExternal.post(datasetsEndpoints.IMPORT_DATASETS(), {
    dataFile: file,
    dgId: id,
  });
  return data;
}

export async function exportDataset(id: number, type: string) {
  const headers = {
    'Content-Type': 'application/json',
  };
  const { data } = await apiExternal.post(
    datasetsEndpoints.EXPORT_DATASETS(),
    {
      dgId: id,
      exportType: type,
    },
    { headers, responseType: 'blob' }
  );
  return data;
}

export async function patchUpdate(updatedData: PatchPayLoad) {
  const { data } = await apiDev.post(
    datasetsEndpoints.DATASET_GROUP_PATCH_UPDATE(),
    {
      ...updatedData,
    }
  );
  return data;
}

export async function minorUpdate(updatedData: MinorPayLoad) {
  const { data } = await apiDev.post(
    datasetsEndpoints.DATASET_GROUP_MINOR_UPDATE(),
    {
      ...updatedData,
    }
  );
  return data;
}

export async function majorUpdate(updatedData: DatasetGroup) {
  const { data } = await apiDev.post(
    datasetsEndpoints.DATASET_GROUP_MAJOR_UPDATE(),
    {
      ...updatedData,
    }
  );
  return data;
}

export async function deleteDatasetGroup(dgId: number) {
  const { data } = await apiDev.post(
    datasetsEndpoints.DELETE_DATASET_GROUP(),
    { dgId }
  );
  return data;
}

export async function getStopWords() {
  const { data } = await apiDev.get(datasetsEndpoints.GET_STOP_WORDS());
  return data?.response?.stopWords;
}

export async function addStopWord(stopWordData: { stopWords: string[] }) {
  const { data } = await apiDev.post(datasetsEndpoints.POST_STOP_WORDS(), {
    ...stopWordData,
  });
  return data;
}

export async function deleteStopWord(stopWordData: { stopWords: string[] }) {
  const { data } = await apiDev.post(datasetsEndpoints.DELETE_STOP_WORD(), {
    ...stopWordData,
  });
  return data;
}

export async function getDatasetGroupsProgress() {
  const { data } = await apiDev.get('classifier/datasetgroup/progress');
  return data?.response?.data;
}

export async function importStopWords(file: File) {
  const { data } = await apiExternal.post(
    datasetsEndpoints.IMPORT_STOP_WORDS(),
    {
      stopWordsFile: file,
    }
  );
  return data;
}

export async function deleteStopWords(file: File) {
  const { data } = await apiExternal.post(
    datasetsEndpoints.DELETE_STOP_WORDS(),
    {
      stopWordsFile: file,
    }
  );
  return data;
}

export async function exportCorrectedTexts(
  platform: string,
  exportType: string
) {
  const headers = {
    'Content-Type': 'application/json',
  };
  const { data } = await apiExternal.post(
    correctedTextEndpoints.EXPORT_CORRECTED_TEXTS(),
    {
      platform,
      exportType,
    },
    { headers, responseType: 'blob' }
  );
  return data;
}