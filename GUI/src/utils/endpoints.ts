export const userManagementEndpoints = {
  FETCH_USERS: (): string => `/global-classifier/accounts/users`,
  ADD_USER: (): string => `/global-classifier/accounts/add`,
  CHECK_ACCOUNT_AVAILABILITY: (): string => `/global-classifier/accounts/exists`,
  EDIT_USER: (): string => `/global-classifier/accounts/edit`,
  DELETE_USER: (): string => `/global-classifier/accounts/delete`,
  FETCH_USER_ROLES: (): string => `/global-classifier/accounts/user-role`,
};

export const integratedAgenciesEndPoints = {
  GET_INTEGRATED_AGENCIES: (): string =>
    `/global-classifier/agencies/list`,
  GET_ALL_AGENCIES: (): string =>
    `/global-classifier/agencies/all`,
};

export const datasetsEndpoints = {
  GET_OVERVIEW: (): string => '/global-classifier/datasets/list',
  GET_METADATA: (): string => `/global-classifier/datasets/metadata`,
  GET_DATASETS_DATA: (): string => '/global-classifier/datasets/data',
  GET_ALL_DATASET_VERSIONS: (): string => '/global-classifier/datasets/versions',
  GET_DATA_GENERATION_PROGRESS: (): string => `/global-classifier/datasets/progress`,
  UPDATE_DATASET: (): string => `/global-classifier/datasets/update`,
  DELETE_DATASET: (): string => `/global-classifier/datasets/delete`,



  GET_DATASET_FILTERS: (): string =>
    '/global-classifier/datasetgroup/overview/filters',
  GET_DATASETS: (): string => `/global-classifier/datasetgroup/group/data`,
  EXPORT_DATASETS: (): string => `/datasetgroup/data/download`,
  DATASET_GROUP_MINOR_UPDATE: (): string =>
    `/global-classifier/datasetgroup/update/minor`,
  DATASET_GROUP_MAJOR_UPDATE: (): string =>
    `/global-classifier/datasetgroup/update/major`,
};

export const correctedTextEndpoints = {
  GET_CORRECTED_WORDS: (
    pageNumber: number,
    pageSize: number,
    platform: string,
    sortType: string
  ) =>
    `/global-classifier/inference/corrected-metadata?pageNum=${pageNumber}&pageSize=${pageSize}&platform=${platform}&sortType=${sortType}`,
  EXPORT_CORRECTED_TEXTS: () => `/datamodel/data/corrected/download`
};

export const authEndpoints = {
  GET_EXTENDED_COOKIE: () :string => `/global-classifier/auth/jwt/extend`,
  LOGOUT: (): string => `/global-classifier/accounts/logout`
}

export const dataModelsEndpoints = {
  GET_OVERVIEW: (): string => '/global-classifier/datamodels/list',
  GET_PRODUCTION_DATA_MODEL: (): string => '/global-classifier/datamodels/production-model',
  GET_MODEL_METADATA: (): string => '/global-classifier/datamodels/metadata',
  GET_DEPLOYMENT_ENVIRONMENTS: (): string => '/global-classifier/datamodels/configs/environments',
  CREATE_MODEL: (): string => '/global-classifier/datamodels/create',
  CREATE_MAJOR_VERSION: (): string => '/global-classifier/datamodels/major',
  CREATE_MINOR_VERSION: (): string => '/global-classifier/datamodels/minor',
  DELETE_MODEL: (): string => '/global-classifier/datamodels/delete',
  GET_ALL_DATAMODELS_VERSIONS: (): string => '/global-classifier/datamodels/versions',
  LOAD_MODEL: (): string => '/global-classifier/testmodel/load',
  GET_DATA_MODEL_PROGRESS: (): string => `global-classifier/datamodels/progress`,
  DEPLOY_MODEL: (): string => '/global-classifier/inference/deploy',

  
  GET_DATAMODELS_FILTERS: (): string =>
    '/global-classifier/datamodel/overview/filters',
  GET_METADATA: (): string => `/global-classifier/datamodel/metadata`,
  GET_CREATE_OPTIONS: (): string => `global-classifier/datamodel/create/options`,
  CREATE_DATA_MODEL: (): string => `global-classifier/datamodel/create`,
  UPDATE_DATA_MODEL: (): string => `global-classifier/datamodel/update`,
  DELETE_DATA_MODEL: (): string => `global-classifier/datamodel/delete`,
  RETRAIN_DATA_MODEL: (): string => `global-classifier/datamodel/retrain`,
};

export const testModelsEndpoints = {
  GET_MODELS: (): string => `/global-classifier/testmodel/models`,
  CLASSIFY_TEST_MODELS: (): string => `/global-classifier/testmodel/classify`,
};

