export const userManagementEndpoints = {
  FETCH_USERS: (): string => `/classifier/accounts/users`,
  ADD_USER: (): string => `/classifier/accounts/add`,
  CHECK_ACCOUNT_AVAILABILITY: (): string => `/classifier/accounts/exists`,
  EDIT_USER: (): string => `/classifier/accounts/edit`,
  DELETE_USER: (): string => `/classifier/accounts/delete`,
  FETCH_USER_ROLES: (): string => `/classifier/accounts/user-role`,
};

export const integrationsEndPoints = {
  GET_INTEGRATION_STATUS: (): string =>
    `/classifier/integration/platform-status`,
  TOGGLE_PLATFORM: (): string => `/classifier/integration/toggle-platform`,
};

export const datasetsEndpoints = {
  GET_OVERVIEW: (): string => '/classifier/datasetgroup/overview',
  GET_DATASET_FILTERS: (): string =>
    '/classifier/datasetgroup/overview/filters',
  ENABLE_DATASET: (): string => `/classifier/datasetgroup/update/status`,
  GET_DATASETS: (): string => `/classifier/datasetgroup/group/data`,
  GET_METADATA: (): string => `/classifier/datasetgroup/group/metadata`,
  CREATE_DATASET_GROUP: (): string => `/classifier/datasetgroup/create`,
  IMPORT_DATASETS: (): string => `/datasetgroup/data/import`,
  EXPORT_DATASETS: (): string => `/datasetgroup/data/download`,
  DATASET_GROUP_PATCH_UPDATE: (): string =>
    `/classifier/datasetgroup/update/patch`,
  DATASET_GROUP_MINOR_UPDATE: (): string =>
    `/classifier/datasetgroup/update/minor`,
  DATASET_GROUP_MAJOR_UPDATE: (): string =>
    `/classifier/datasetgroup/update/major`,
  DELETE_DATASET_GROUP:(): string =>`classifier/datasetgroup/delete`,
  GET_STOP_WORDS: (): string => `/classifier/datasetgroup/stop-words`,
  POST_STOP_WORDS: (): string => `/classifier/datasetgroup/update/stop-words`,
  DELETE_STOP_WORD: (): string => `/classifier/datasetgroup/delete/stop-words`,
  IMPORT_STOP_WORDS: (): string => `/datasetgroup/data/import/stop-words`,
  DELETE_STOP_WORDS: (): string => `/datasetgroup/data/delete/stop-words`,
};

export const correctedTextEndpoints = {
  GET_CORRECTED_WORDS: (
    pageNumber: number,
    pageSize: number,
    platform: string,
    sortType: string
  ) =>
    `/classifier/inference/corrected-metadata?pageNum=${pageNumber}&pageSize=${pageSize}&platform=${platform}&sortType=${sortType}`,
  EXPORT_CORRECTED_TEXTS: () => `/datamodel/data/corrected/download`
};

export const authEndpoints = {
  GET_EXTENDED_COOKIE: () :string => `/classifier/auth/jwt/extend`,
  LOGOUT: (): string => `/classifier/accounts/logout`
}

export const dataModelsEndpoints = {
  GET_OVERVIEW: (): string => '/classifier/datamodel/overview',
  GET_DATAMODELS_FILTERS: (): string =>
    '/classifier/datamodel/overview/filters',
  GET_METADATA: (): string => `/classifier/datamodel/metadata`,
  GET_CREATE_OPTIONS: (): string => `classifier/datamodel/create/options`,
  CREATE_DATA_MODEL: (): string => `classifier/datamodel/create`,
  UPDATE_DATA_MODEL: (): string => `classifier/datamodel/update`,
  DELETE_DATA_MODEL: (): string => `classifier/datamodel/delete`,
  RETRAIN_DATA_MODEL: (): string => `classifier/datamodel/retrain`,
  GET_DATA_MODEL_PROGRESS: (): string => `classifier/datamodel/progress`,
};

export const testModelsEndpoints = {
  GET_MODELS: (): string => `/classifier/testmodel/models`,
  CLASSIFY_TEST_MODELS: (): string => `/classifier/testmodel/test-data`,
};

