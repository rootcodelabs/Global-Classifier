

DATA_DOWNLOAD_ENDPOINT = "http://file-handler:8000/datasetgroup/data/download/json"

GET_DATASET_METADATA_ENDPOINT = "http://ruuter-private:8088/classifier/datasetgroup/group/metadata"

GET_MODEL_METADATA_ENDPOINT= "http://ruuter-private:8088/classifier/datamodel/metadata"

UPDATE_MODEL_TRAINING_STATUS_ENDPOINT = "http://ruuter-private:8088/classifier/datamodel/update/training/status"

CREATE_TRAINING_PROGRESS_SESSION_ENDPOINT = "http://ruuter-private:8088/classifier/datamodel/progress/create"

UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT = "http://ruuter-private:8088/classifier/datamodel/progress/update"

OUTLOOK_DEPLOYMENT_ENDPOINT = "http://172.25.0.7:8003/classifier/datamodel/deployment/outlook/update"

JIRA_DEPLOYMENT_ENDPOINT = "http://172.25.0.7:8003/classifier/datamodel/deployment/jira/update"

TEST_DEPLOYMENT_ENDPOINT = "http://172.25.0.7:8003/classifier/datamodel/deployment/testing/update"

TRAINING_LOGS_PATH = "/app/model_trainer/training_logs.log"

MODEL_RESULTS_PATH = "/shared/model_trainer/results" #stored in the shared folder which is connected to s3-ferry

LOCAL_BASEMODEL_TRAINED_LAYERS_SAVE_PATH = "/shared/model_trainer/results/{model_id}/trained_base_model_layers" #stored in the shared folder which is connected to s3-ferry

LOCAL_CLASSIFICATION_LAYER_SAVE_PATH = "/shared/model_trainer/results/{model_id}/classifier_layers" #stored in the shared folder which is connected to s3-ferry

LOCAL_LABEL_ENCODER_SAVE_PATH = "/shared/model_trainer/results/{model_id}/label_encoders" #stored in the shared folder which is connected to s3-ferry

S3_FERRY_MODEL_STORAGE_PATH = "/models" #folder path in s3 bucket


BASE_MODEL_FILENAME = "base_model_trainable_layers_{model_id}"

CLASSIFIER_MODEL_FILENAME = "classifier_{model_id}.pth"

MODEL_TRAINING_IN_PROGRESS = "training in-progress"

MODEL_TRAINING_SUCCESSFUL  = "trained"

MODEL_TRAINING_FAILED = "not trained"


# MODEL TRAINING PROGRESS SESSION CONSTANTS

INITIATING_TRAINING_PROGRESS_STATUS = "Initiating Training"

TRAINING_IN_PROGRESS_PROGRESS_STATUS = "Training In-Progress"

DEPLOYING_MODEL_PROGRESS_STATUS = "Deploying Model"

MODEL_TRAINED_AND_DEPLOYED_PROGRESS_STATUS = "Model Trained And Deployed"


INITIATING_TRAINING_PROGRESS_MESSAGE = "Download and preparing dataset"

TRAINING_IN_PROGRESS_PROGRESS_MESSAGE = "The dataset is being trained on all selected models"

DEPLOYING_MODEL_PROGRESS_MESSAGE = "Model training complete. The trained model is now being deployed"

MODEL_TRAINED_AND_DEPLOYED_PROGRESS_MESSAGE = "The model was trained and deployed successfully to the environment"

MODEL_TRAINING_FAILED_ERROR = "Training Failed"


INITIATING_TRAINING_PROGRESS_PERCENTAGE=30

TRAINING_IN_PROGRESS_PROGRESS_PERCENTAGE=50

DEPLOYING_MODEL_PROGRESS_PERCENTAGE=80

MODEL_TRAINED_AND_DEPLOYED_PROGRESS_PERCENTAGE=100

OUTLOOK = "outlook"

JIRA="jira"

TESTING="testing"

UNDEPLOYED="undeployed"