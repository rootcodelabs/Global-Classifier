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

export const integrationQueryKeys = {
  INTEGRATION_STATUS: (): string[] => [
    `classifier/integration/platform-status`,
  ],
  USER_ROLES: (): string[] => ['/accounts/user-role', 'prod'],
};

export const datasetQueryKeys = {
  DATASET_FILTERS: (): string[] => ['datasets/filters'],
  DATASET_OVERVIEW: function (
    pageIndex?: number,
    datasetGroupName?: string,
    versionMajor?: number,
    versionMinor?: number,
    versionPatch?: number,
    validationStatus?: string,
    sort?: string
  ) {
    return [
      'datasetgroup/overview',
      pageIndex,
      datasetGroupName,
      versionMajor,
      versionMinor,
      versionPatch,
      validationStatus,
      sort,
    ].filter((val) => val !== undefined);
  },
  GET_META_DATA: function (dgId?: number) {
    return ['datasets/groups/metadata', `${dgId}`].filter(
      (val) => val !== undefined
    );
  },
  GET_DATA_SETS: function (dgId?: number, pagination?: PaginationState) {
    return ['datasets/groups/data', `${dgId}`, pagination].filter(
      (val) => val !== undefined
    );
  },
  GET_DATASET_GROUP_PROGRESS: () => ['datasetgroups/progress'],
};

export const stopWordsQueryKeys = {
  GET_ALL_STOP_WORDS: () => [`datasetgroups/stopwords`],
};

export const authQueryKeys = {
  USER_DETAILS: () => ['classifier/auth/jwt/userinfo', 'prod'],
};

export const dataModelsQueryKeys = {
  DATA_MODEL_FILTERS: (): string[] => ['datamodels/filters'],
  DATA_MODELS_OVERVIEW: function (
    pageIndex?: number,
    modelName?: string,
    versionMajor?: number,
    versionMinor?: number,
    platform?: string,
    datasetGroup?: number,
    trainingStatus?:string,
    maturity?:string,
    sort?:string,
    isProduction?:boolean

  ) {
    return [
      'datamodels/overview',
      pageIndex,
      modelName,
      versionMajor,
      versionMinor,
      platform,
      datasetGroup,
      trainingStatus,
      maturity,
      sort,
      isProduction
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
