export enum ValidationStatus {
  SUCCESS = 'success',
  FAIL = 'fail',
  UNVALIDATED = 'unvalidated',
  IN_PROGRESS = 'in-progress',
}

export enum DatasetViewEnum {
  LIST = 'list',
  INDIVIDUAL = 'individual',
}

export enum CreateDatasetGroupModals {
  SUCCESS = 'SUCCESS',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  NULL = 'NULL',
}

export enum ViewDatasetGroupModalContexts {
  EXPORT_MODAL = 'EXPORT_MODAL',
  IMPORT_MODAL = 'IMPORT_MODAL',
  PATCH_UPDATE_MODAL = 'PATCH_UPDATE_MODAL',
  DELETE_ROW_MODAL = 'DELETE_ROW_MODAL',
  CONFIRMATION_MODAL = 'CONFIRMATION_MODAL',
  NULL = 'NULL',
}

export enum UpdatePriority {
  MAJOR = 'MAJOR',
  MINOR = 'MINOR',
  PATCH = 'PATCH',
  NULL = 'NULL',
}

export enum ImportExportDataTypes {
  XLSX = 'xlsx',
  JSON = 'json',
  YAML = 'yaml',
}

export enum StopWordImportOptions {
  ADD = 'add',
  DELETE = 'delete',
}

export enum ValidationErrorTypes {
  NAME = 'NAME',
  CLASS_HIERARCHY = 'CLASS_HIERARCHY',
  VALIDATION_CRITERIA = 'VALIDATION_CRITERIA',
  NULL = 'NULL',
}

export enum ValidationSessionsStatuses {
  VALIDATION_SUCCESS_STATUS = 'Success',
  VALIDATION_FAILED_STATUS = 'Fail'
}