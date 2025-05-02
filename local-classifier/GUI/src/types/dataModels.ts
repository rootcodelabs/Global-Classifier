export type DataModel = {
  modelId: number;
  modelName: string;
  dgName?: string;
  dgId: string | number;
  platform: string;
  baseModels: string[];
  maturity: string;
  version?: string;
};

export type TrainingProgressData = {
  id: string;
  modelName: string;
  majorVersion: number;
  minorVersion: number;
  latest: boolean;
  trainingStatus: string;
  progressPercentage: number;
  trainingMessage?:string;
};

export type SSEEventData = {
  sessionId: string;
  trainingStatus: string;
  progressPercentage: number;
};

export type UpdatedDataModelPayload = {
  modelId: number;
  connectedDgId: string | null | undefined;
  deploymentEnv: string | null | undefined;
  baseModels: string | null | undefined;
  maturityLabel: string | null | undefined;
  updateType: string | undefined;
};

export type CreateDataModelPayload = {
  modelName: string | undefined;
  dgId: string | number | undefined;
  baseModels: string[] | undefined;
  deploymentPlatform: string | undefined;
  maturityLabel: string | undefined;
};

export type FilterData = {
  modelNames: string[];
  modelVersions: string[];
  deploymentsEnvs: string[];
  datasetGroups: Array<{ id: number; name: string }>;
  trainingStatuses: string[];
  maturityLabels: string[];
};

export type DataModelResponse = {
  id: number;
  modelName: string;
  connectedDgName: string;
  majorVersion: number;
  minorVersion: number;
  latest: boolean;
  dgVersion: string;
  lastTrainedTimestamp: string;
  trainingStatus: string;
  deploymentEnv: string;
  maturityLabel: string;
  trainingResults?: string | null;
  connectedDgMajorVersion?: number;
  connectedDgMinorVersion?: number;
  connectedDgPatchVersion?: number;
};

export type TrainingResults ={
  trainingResults: {
    classes: string[];
    accuracy: string[];
    f1_score: string[];
  };
};

export type DataModelsFilters = {
  modelName: string;
  version: string;
  platform: string;
  datasetGroup: number;
  trainingStatus: string;
  maturity: string;
  sort: 'created_timestamp desc' | 'created_timestamp asc' | 'name asc' | 'name desc';
};

export type ErrorsType = {
  modelName?: string;
  dgName?: string;
  platform?: string;
  baseModels?: string;
  maturity?: string;
  dgId?: string;
};