import { dataModelsEndpoints } from 'utils/endpoints';
import apiDev from './api-dev';

export async function getDataModelsOverview(
  pageNum: number,
  modelStatus: string,
  trainingStatus: string,
  deploymentEnvironment: string,
  sort: string,
) {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_OVERVIEW(), {
    params: {
      page: pageNum,
      modelStatus,
      trainingStatus,
      deploymentEnvironment,
      sortBy:sort?.split(" ")?.[0],
      sortType: sort?.split(" ")?.[1],
      pageSize: 12,
    },
  });
  return data?.response?? [];
}

export async function getDeploymentEnvironments() {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_DEPLOYMENT_ENVIRONMENTS());
  return data?.response?? [];
}

export async function getProductionDataModel() {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_PRODUCTION_DATA_MODEL());
  return data?.response?.[0] ?? null;
}

export async function getDataModelMetadata(
  modelId: number | string,
) {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_MODEL_METADATA(), {
    params: {
      modelId
    },
  });
  return data?.response?.[0]?? [];
}

export async function createDataModel(payload: {
  modelName: string;
  deploymentEnv: string;
  baseModels: string[];
  connectedDsId: string | number;
  connectedDsMajorVersion: string | number;
  connectedDsMinorVersion: string | number;
}) {
  const { data } = await apiDev.post(dataModelsEndpoints.CREATE_MODEL(), payload);
  return data?.response ?? {};
}

export async function configureDataModel(payload: {
  modelGroupKey: string;
  modelName: string;
  deploymentEnv: string;
  baseModels: string[];
  connectedDsId: string | number;
  connectedDsMajorVersion: string | number;
  connectedDsMinorVersion: string | number;
  updateType: string;
}, ) {
  let endpoint ="";
  if (payload.updateType === 'major') {
    endpoint = dataModelsEndpoints.CREATE_MAJOR_VERSION();
  } else if (payload.updateType === 'minor') {
    endpoint = dataModelsEndpoints.CREATE_MINOR_VERSION();
  } 
  const { data } = await apiDev.post(endpoint, payload);
  return data?.response ?? {};
}