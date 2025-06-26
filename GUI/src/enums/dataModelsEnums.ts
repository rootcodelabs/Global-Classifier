export enum TrainingStatus {
  NOT_TRAINED = 'not_trained',
  TRAINING_INPROGRESS = 'training_in_progress',
  TRAINED = 'trained',
  RETRAINING_NEEDED = 'retraining_needed',
  FAILED = 'training_failed',
}

export enum Maturity {
  PRODUCTION = 'production',
  UNDEPLOYED = 'undeployed',
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