import { dataModelsEndpoints, testModelsEndpoints } from 'utils/endpoints';
import apiDev from './api-dev';
import apiPublic from './api-public';
import { ClassifyTestModalPayloadType, ClassifyTestModalResponseType } from 'types/testModelTypes';
import { OVERVIEW_PAGE_SIZE } from 'utils/constants';

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
      sortBy: sort?.split(" ")?.[0],
      sortType: sort?.split(" ")?.[1],
      pageSize: OVERVIEW_PAGE_SIZE,
    },
  });
  return data?.response ?? [];
}

export async function getDeploymentEnvironments() {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_DEPLOYMENT_ENVIRONMENTS());
  return data?.response ?? [];
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
  return data?.response?.[0] ?? [];
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
},) {
  let endpoint = "";
  if (payload.updateType === 'major') {
    endpoint = dataModelsEndpoints.CREATE_MAJOR_VERSION();
  } else if (payload.updateType === 'minor') {
    endpoint = dataModelsEndpoints.CREATE_MINOR_VERSION();
  }
  const { data } = await apiDev.post(endpoint, payload);
  return data?.response ?? {};
}


export async function deployDataModel(payload: {
  modelId: string | number;
  currentEnv: string;
  targetEnv: string;
},) {
  const { data } = await apiPublic.post(dataModelsEndpoints.DEPLOY_MODEL(), payload);
  return data?.response ?? {};
}

export async function deleteDataModel(modelId: number | string | null) {
  const { data } = await apiDev.post(dataModelsEndpoints.DELETE_MODEL(), {
    modelId,
  });
  return data?.response ?? {};
}

export async function getAllModelVersions() {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_ALL_DATAMODELS_VERSIONS());
  return data?.response ?? [];
}

export async function loadModel(modelId: number | string | null) {
  const { data } = await apiPublic.post(dataModelsEndpoints.LOAD_MODEL(), {
    modelId,
  });
  return data?.response ?? [];
}

export async function classify(data: ClassifyTestModalPayloadType) {
  const response = await apiDev.post(
    testModelsEndpoints.CLASSIFY_TEST_MODELS(),
    { modelId: data.modelId, text: data.text },
  );
  return response?.data?.response?.data as ClassifyTestModalResponseType ?? [];
}
export async function getDataModelsProgress() {
  const { data } = await apiDev.get(dataModelsEndpoints.GET_DATA_MODEL_PROGRESS());
  return data?.response?.data;
}