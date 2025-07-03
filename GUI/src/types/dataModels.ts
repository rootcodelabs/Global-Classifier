export type DataModel = {
  modelId: number;
  modelName: string;
  dgName?: string;
  datasetId: string | number;
  baseModels: string[];
  deploymentEnvironment: string;
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
  modelId: number | string;
  modelName: string;
  major: number;
  minor: number;
  latest: boolean;
  datasetVersion?: string;
  dataModelName: string;
  lastTrained: string;
  trainingStatus: string;
  deploymentEnvironment: string;
  modelStatus: string;
  trainingResults?: string | null;
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
  modelStatus: string;
  trainingStatus: string;
  deploymentEnvironment: string;
  sort: 'createdAt desc' | 'createdAt asc' | 'modelName asc' | 'modelName desc';
};

export type ErrorsType = {
  modelName?: string;
  dgName?: string;
  deploymentEnvironment?: string;
  baseModels?: string;
  datasetId?: string;
};