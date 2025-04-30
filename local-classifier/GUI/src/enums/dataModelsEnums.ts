export enum TrainingStatus {
  NOT_TRAINED = 'not trained',
  TRAINING_INPROGRESS = 'training in-progress',
  TRAINED = 'trained',
  RETRAINING_NEEDED = 'retraining needed',
  UNTRAINABLE = 'untrainable',
}

export enum Maturity {
  PRODUCTION = 'production ready',
  STAGING = 'staging',
  DEVELOPMENT = 'development',
  TESTING = 'testing',
}

export enum Platform {
  JIRA = 'jira',
  OUTLOOK = 'outlook',
  UNDEPLOYED = 'undeployed',
}

export enum UpdateType {
  MAJOR = 'major',
  MINOR = 'minor',
  MATURITY_LABEL = 'maturityLabel',
}

export enum TrainingSessionsStatuses {
  TRAINING_SUCCESS_STATUS = 'Model Trained And Deployed',
  TRAINING_FAILED_STATUS = 'Training Failed'
}