

export interface LinkedModel {
  modelId: number;
  modelName: string;
  modelVersion: string;
  trainingTimestamp: number;
}

export interface Operation {
  dgId: number | undefined;
  operationType: 'enable' | 'disable';
}

export type Dataset = {
  id: number |string;
  major: number;
  minor: number;
  createdAt: string;
  generationStatus: string;
  lastModelTrained: string;
  lastTrained: string;
  totalPages: number;
};

export type MinorPayLoad = {
  dgId: number;
  s3FilePath: any;
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


export type SelectedRowPayload = {itemId:string |number, dataItem: string; agencyName: string; agencyId?: number | string }

export type ValidationProgressData = {
  id: string;
  groupName: string;
  majorVersion: number;
  minorVersion: number;
  patchVersion: number;
  latest: boolean;
  generationStatus: string;
  generationMessage?: string;
  progressPercentage: number;
};

export type SSEEventData = {
  sessionId: string;
  generationStatus: string;
  generationMessage?: string;
  progressPercentage: number;
};
