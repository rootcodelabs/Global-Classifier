import { integratedAgenciesEndPoints } from 'utils/endpoints';
import apiDev from './api-dev';

export const fetchAgencies = async (
    pageIndex: number,
    sortOption:string,
    agencyName: string = 'all'

  ) => {
    const [sortBy, sortType] = sortOption.split(' ');

    const { data } = await apiDev.get(integratedAgenciesEndPoints.GET_INTEGRATED_AGENCIES(), {
     params:{
      page: pageIndex,
      pageSize: 9,
      sortBy: sortBy,
      sortType: sortType,
      agencyName
     }
    });
    return data?.response ?? [];
  };

  export async function enableAgncy(agencyId: string) {
  const { data } = await apiDev.post('global-classifier/agencies/enable', {
    "agencyId": agencyId
  });
  return data;
}

 export async function disableAgncy(agencyId: string) {
  const { data } = await apiDev.post('global-classifier/agencies/disable', {
    "agencyId": agencyId
  });
  return data;
}

 export async function resync(agencyId: string) {
  const { data } = await apiDev.post('global-classifier/agencies/data/resync', {
    "agencyId": agencyId
  });
  return data;
}

export const fetchAllAgencies = async () => {
    const { data } = await apiDev.get(integratedAgenciesEndPoints.GET_ALL_AGENCIES());
    return data?.response ?? [];
  };