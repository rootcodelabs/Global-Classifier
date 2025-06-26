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