import { CreateDataModelPayload, UpdatedDataModelPayload } from 'types/dataModels';
import apiDev from './api-dev';
import { dataModelsEndpoints } from 'utils/endpoints';

export async function getDataModelsOverview(
  pageNum: number,
  modelName: string,
  majorVersion: number,
  minorVersion: number,
  platform: string,
  datasetGroup: number,
  trainingStatus: string,
  deploymentMaturity: string,
  sort: string,
  isProductionModel: boolean
) {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_OVERVIEW(), {
    params: {
      page: pageNum,
      modelName,
      majorVersion,
      minorVersion,
      platform,
      datasetGroup,
      trainingStatus,
      deploymentMaturity,
      sortBy:sort?.split(" ")?.[0],
      sortType: sort?.split(" ")?.[1],
      pageSize: 12,
      isProductionModel
    },
  });
  return data?.response;
}

export async function getFilterData() {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_DATAMODELS_FILTERS());
  return data?.response;
}

export async function getCreateOptions() {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_CREATE_OPTIONS());
  return data?.response;
}

export async function getMetadata(modelId: string | number | null) {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_METADATA(), {
    params: {
      modelId,
    },
  });
  return data?.response?.data[0];
}

export async function createDataModel(dataModel:CreateDataModelPayload) {
  const { data } = await apiDev.post(dataModelsEndpoints.CREATE_DATA_MODEL(), {
    ...dataModel,
  });
  return data;
}

export async function updateDataModel(dataModel:UpdatedDataModelPayload) {
  const { data } = await apiDev.post(dataModelsEndpoints.UPDATE_DATA_MODEL(), {
    ...dataModel,
  });
  return data;
}

export async function deleteDataModel(modelId : number) {
  const { data } = await apiDev.post(dataModelsEndpoints.DELETE_DATA_MODEL(), {
    modelId
  });
  return data;
}

export async function retrainDataModel(modelId : number) {
  const { data } = await apiDev.post(dataModelsEndpoints.RETRAIN_DATA_MODEL(), {
    modelId
  });
  return data;
}

export async function getDataModelsProgress() {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_DATA_MODEL_PROGRESS());
  return data?.response?.data;
}