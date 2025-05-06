import { ValidationStatus } from 'enums/datasetEnums';

export interface ValidationRule {
  id: number | string;
  fieldName: string;
  dataType: string;
  isDataClass: boolean;
}

export interface Class {
  id: string;
  fieldName: string;
  level: number;
  children: Class[];
}

export interface LinkedModel {
  modelId: number;
  modelName: string;
  modelVersion: string;
  trainingTimestamp: number;
}

export interface Dataset {
  rowId: number;
  emailAddress: string;
  emailBody: string;
  emailSendTime: string;
  departmentCode: string;
  ministry: string;
  division: string;
}

export interface Operation {
  dgId: number | undefined;
  operationType: 'enable' | 'disable';
}

export interface ValidationRuleResponse {
  type: string;
  isDataClass: boolean;
}

export interface ValidationCriteria {
  fields: string[];
  validationRules: Record<string, ValidationRuleResponse>;
}

export interface ClassNode {
  class: string;
  subclasses: ClassNode[];
}

export interface DatasetGroup {
  dgId?: number;
  groupName?: string;
  validationCriteria: ValidationCriteria;
  classHierarchy: ClassNode[];
}

export interface ImportDataset {
  dgId: number | string;
  dataFile: File;
}

export type SingleDatasetType = {
  createdTimestamp: Date;
  enableAllowed: boolean;
  groupName: string;
  id: number;
  isEnabled: boolean;
  lastModelTrained: Date | null;
  lastTrainedTimestamp: Date | null;
  lastUpdatedTimestamp: Date | null;
  latest: boolean;
  majorVersion: number;
  minorVersion: number;
  patchVersion: number;
  totalPages: number;
  validationStatus: ValidationStatus;
};

export type TreeNode = {
  id: string;
  fieldName: string;
  level: number;
  children: TreeNode[] | [];
};

export type MinorPayLoad = {
  dgId: number;
  s3FilePath: any;
};

export type PatchPayLoad = {
  dgId: number;
  updateDataPayload: {
    deletedDataRows: any[];
    editedData: any;
  };
};

export type MetaData = {
  dgId: number;
  name: string;
  majorVersion: number;
  minorVersion: number;
  patchVersion: number;
  latest: boolean;
  operationSuccessful: boolean;
  isEnabled: boolean;
  numSamples: number;
  enableAllowed: boolean;
  validationStatus: ValidationStatus;
  validationErrors: string[];
  isValidated: boolean;
  linkedModels: LinkedModel[];
  validationCriteria: ValidationCriteria;
  classHierarchy: ClassNode[];
};

type DataPayload = Record<string, any>;

export type DatasetDetails = {
  dgId: number;
  numPages: number;
  dataPayload: DataPayload[];
  fields: string[];
};

export type FilterData = {
  datasetGroupName: string;
  version: string;
  validationStatus: string;
  sort: 'last_updated_timestamp desc' | 'last_updated_timestamp asc' | 'name asc' | 'name desc';
};


export type SelectedRowPayload = {
  rowId: number;
} & Record<string, string>;

export type ValidationProgressData = {
  id: string;
  groupName: string;
  majorVersion: number;
  minorVersion: number;
  patchVersion: number;
  latest: boolean;
  validationStatus: string;
  validationMessage?: string;
  progressPercentage: number;
};

export type SSEEventData = {
  sessionId: string;
  validationStatus: string;
  validationMessage?: string;
  progressPercentage: number;
};

export type StopWordsImportResponse = {
  response: {
    nonexistent: boolean;
    nonexistentItems: string[];
    operationSuccessful: boolean;
  }
};