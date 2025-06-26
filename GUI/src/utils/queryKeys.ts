import { PaginationState, SortingState } from '@tanstack/react-table';

export const userManagementQueryKeys = {
  getAllEmployees: function (
    pagination?: PaginationState,
    sorting?: SortingState
  ) {
    return ['accounts/users', pagination, sorting].filter(
      (val) => val !== undefined
    );
  },
};

export const integratedAgenciesQueryKeys = {
  INTEGRATED_AGENCIES_LIST: function (pageIndex?: number,sortOption?:string,searchTerm?:string) {
    return ['integrated-agencies/list',pageIndex,sortOption,searchTerm].filter(
      (val) => val !== undefined
    );
  },
  ALL_AGENCIES_LIST: () => ['integrated-agencies/all'],
  USER_ROLES: (): string[] => ['/accounts/user-role', 'prod'],

  }


export const datasetQueryKeys = {
  DATASET_FILTERS: (): string[] => ['datasets/filters'],
  DATASET_OVERVIEW: function (
    pageIndex?: number,
    generationStatus?: string,
    sort?: string
  ) {
    return [
      'datasets/overview',
      pageIndex,
      generationStatus,
      sort,
    ].filter((val) => val !== undefined);
  },
  GET_META_DATA: function (datasetId?: number|string) {
    return ['datasets/metadata', `${datasetId}`].filter(
      (val) => val !== undefined
    );
  },
  GET_DATA_SETS: function (datasetId?: number|string, agencyId?:number|string, pageNum?: number) {
    return ['datasets/data', datasetId, agencyId,pageNum].filter(
      (val) => val !== undefined
    );
  },


  GET_DATASET_GROUP_PROGRESS: () => ['datasetgroups/progress'],
};

export const stopWordsQueryKeys = {
  GET_ALL_STOP_WORDS: () => [`datasetgroups/stopwords`],
};

export const authQueryKeys = {
  USER_DETAILS: () => ['global-classifier/auth/jwt/userinfo', 'prod'],
};

export const dataModelsQueryKeys = {
  DATA_MODEL_FILTERS: (): string[] => ['datamodels/filters'],
  DATA_MODEL_DEPLOYMENT_ENVIRONMENTS: (): string[] => ['datamodels/deployment-environments'],

  DATA_MODELS_OVERVIEW: function (
    pageIndex?: number,
    modelStatus?:string,
    trainingStatus?:string,
    maturity?:string,
    sort?:string,

  ) {
    return [
      'datamodels/list',
      pageIndex,
      modelStatus,
      trainingStatus,
      maturity,
      sort
    ].filter((val) => val !== undefined);
  },
  GET_META_DATA: function (modelId?: number) {
    return ['datamodels/metadata', `${modelId}`].filter(
      (val) => val !== undefined
    );
  },
  GET_DATA_MODELS_PROGRESS: () => ['datamodels/progress'],
};

export const testModelsQueryKeys = {
  GET_TEST_MODELS: () => ['testModels']
}
