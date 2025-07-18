export type DataModel = {
  modelId: number;
  modelName: string;
  dgName?: string;
  datasetId: string | number;
  baseModels: string[];
  deploymentEnvironment: string;
  version?: string;
  trainingResults?: TrainingResultsResponse | null;
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
  connectedDsMajorVersion?: string;
  connectedDsMinorVersion?: string;
  dataModelName: string;
  lastTrained: string;
  trainingStatus: string;
  deploymentEnv: string;
  modelStatus: string;
  trainingResults?: string | null;
};

export type ClassMetrics = {
  f1?: number;
  recall?: number;
  accuracy?: number;
  precision?: number;
};

export type ModelPerformance = {
  model_type?: string;
  class_metrics: {
    [className: string]: ClassMetrics;
  };
};

export type ModelResultsProps = {
  models?: ModelPerformance[];
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

export type TrainingResults = {
  best_model_info: {
    model_type: string;
    class_metrics: {
      [className: string]: {
        f1: number;
        recall: number;
        accuracy: number;
        precision: number;
      };
    };
    overall_metrics: {
      recall: number;
      roc_auc: number;
      accuracy: number;
      f1_score: number;
      precision: number;
    };
  };
  training_summary: {
    model_id: number;
    timestamp: string;
    dataset_id: string;
    failed_models: number;
    best_overall_f1: number;
    successful_models: number;
    best_overall_model: string;
    total_models_attempted: number;
  };
  models_performance: Array<{
    status: string;
    best_epoch: number;
    model_name: string;
    model_type: string;
    best_val_f1: number;
    class_metrics: {
      [className: string]: {
        f1: number;
        recall: number;
        accuracy: number;
        precision: number;
      };
    };
    num_parameters: number;
    overall_metrics: {
      f1: number;
      recall: number;
      roc_auc: number;
      accuracy: number;
      precision: number;
    };
    training_time_seconds: number;
    inference_time_seconds: number;
  }>;
};

export type TrainingResultsResponse = {
 type: "jsonb";
 value: string;
 null: boolean;
};