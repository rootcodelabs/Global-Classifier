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
  GET_DATASETS_DATA: (): string => '/global-classifier/datasets/overview',



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
  GET_OVERVIEW: (): string => '/global-classifier/datamodel/overview',
  GET_DATAMODELS_FILTERS: (): string =>
    '/global-classifier/datamodel/overview/filters',
  GET_METADATA: (): string => `/global-classifier/datamodel/metadata`,
  GET_CREATE_OPTIONS: (): string => `global-classifier/datamodel/create/options`,
  CREATE_DATA_MODEL: (): string => `global-classifier/datamodel/create`,
  UPDATE_DATA_MODEL: (): string => `global-classifier/datamodel/update`,
  DELETE_DATA_MODEL: (): string => `global-classifier/datamodel/delete`,
  RETRAIN_DATA_MODEL: (): string => `global-classifier/datamodel/retrain`,
  GET_DATA_MODEL_PROGRESS: (): string => `global-classifier/datamodel/progress`,
};

export const testModelsEndpoints = {
  GET_MODELS: (): string => `/global-classifier/testmodel/models`,
  CLASSIFY_TEST_MODELS: (): string => `/global-classifier/testmodel/test-data`,
};

