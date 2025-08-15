export enum SyncStatus {
  SYNCED = 'Synced_with_CKB',
  UNAVAILABLE = 'Unavailable_in_CKB',
  RESYNC_NEEDED = 'Resync_needed_with_CKB',
  IN_PROGRESS ='Sync_in_progress_with_CKB',
  RESYNC_IN_PROGRESS ='Resync_in_progress_with_CKB',
  FAILED='Sync_with_CKB_Failed'
}

export enum DataGenerationStatus {
  IN_PROGRESS = 'Generation_in_Progress',
  FAILED = 'Generation_Failed',
  SUCCESS = 'Generation_Success',
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

export enum DataGenerationSessionsStatuses {
  VALIDATION_SUCCESS_STATUS = 'Success',
  VALIDATION_FAILED_STATUS = 'Fail'
}