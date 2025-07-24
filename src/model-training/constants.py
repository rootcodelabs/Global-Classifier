DATA_DOWNLOAD_ENDPOINT = "http://file-handler:8000/datasetgroup/data/download/json"

GET_DATASET_METADATA_ENDPOINT = (
    "http://ruuter-private:8088/classifier/datasetgroup/group/metadata"
)

GET_MODEL_METADATA_ENDPOINT = "http://ruuter-private:8088/classifier/datamodel/metadata"

UPDATE_MODEL_TRAINING_STATUS_ENDPOINT = (
    "http://ruuter-private:8088/classifier/datamodel/update/training/status"
)

CREATE_TRAINING_PROGRESS_SESSION_ENDPOINT = (
    "http://ruuter-private:8088/classifier/datamodel/progress/create"
)

UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT = (
    "http://ruuter-private:8088/classifier/datamodel/progress/update"
)

TEST_DEPLOYMENT_ENDPOINT = (
    "http://deployment-service:8003/classifier/datamodel/deployment/testing/update"
)

TRAINING_LOGS_PATH = "/app/model_trainer/training_logs.log"

MODEL_RESULTS_PATH = "/shared/model_trainer/results"  # stored in the shared folder which is connected to s3-ferry

LOCAL_BASEMODEL_TRAINED_LAYERS_SAVE_PATH = "/shared/model_trainer/results/{model_id}/trained_base_model_layers"  # stored in the shared folder which is connected to s3-ferry

LOCAL_CLASSIFICATION_LAYER_SAVE_PATH = "/shared/model_trainer/results/{model_id}/classifier_layers"  # stored in the shared folder which is connected to s3-ferry

LOCAL_LABEL_ENCODER_SAVE_PATH = "/shared/model_trainer/results/{model_id}/label_encoders"  # stored in the shared folder which is connected to s3-ferry

S3_FERRY_MODEL_STORAGE_PATH = "/models"  # folder path in s3 bucket

S3_FERRY_ENDPOINT = "http://s3-ferry:3000/v1/files/copy"

BASE_MODEL_FILENAME = "base_model_trainable_layers_{model_id}"

CLASSIFIER_MODEL_FILENAME = "classifier_{model_id}.pth"

MODEL_TRAINING_IN_PROGRESS = "training in-progress"

MODEL_TRAINING_SUCCESSFUL = "trained"

MODEL_TRAINING_FAILED = "not trained"


# MODEL TRAINING PROGRESS SESSION CONSTANTS

INITIATING_TRAINING_PROGRESS_STATUS = "Initiating Training"

TRAINING_IN_PROGRESS_PROGRESS_STATUS = "Training In-Progress"

DEPLOYING_MODEL_PROGRESS_STATUS = "Deploying Model"

MODEL_TRAINED_AND_DEPLOYED_PROGRESS_STATUS = "Model Trained And Deployed"


INITIATING_TRAINING_PROGRESS_MESSAGE = "Download and preparing dataset"

TRAINING_IN_PROGRESS_PROGRESS_MESSAGE = (
    "The dataset is being trained on all selected models"
)

DEPLOYING_MODEL_PROGRESS_MESSAGE = (
    "Model training complete. The trained model is now being deployed"
)

MODEL_TRAINED_AND_DEPLOYED_PROGRESS_MESSAGE = (
    "The model was trained and deployed successfully to the environment"
)

MODEL_TRAINING_FAILED_ERROR = "Training Failed"


INITIATING_TRAINING_PROGRESS_PERCENTAGE = 30

TRAINING_IN_PROGRESS_PROGRESS_PERCENTAGE = 50

DEPLOYING_MODEL_PROGRESS_PERCENTAGE = 80

MODEL_TRAINED_AND_DEPLOYED_PROGRESS_PERCENTAGE = 100


# Supported Models for Testing
SUPPORTED_BASE_MODELS = ["estbert", "xlm-roberta", "multilingual-distilbert"]


SUPPORTED_BASE_MODELS = ["estbert", "xlm-roberta", "multilingual-distilbert"]

# Model configurations
MODEL_CONFIGS = {
    "estbert": {
        "model_name": "tartuNLP/EstBERT",
        "tokenizer_name": "tartuNLP/EstBERT",
        "type": "bert",
    },
    "xlm-roberta": {
        "model_name": "xlm-roberta-base",
        "tokenizer_name": "xlm-roberta-base",
        "type": "roberta",
    },
    "multilingual-distilbert": {
        "model_name": "distilbert-base-multilingual-cased",
        "tokenizer_name": "distilbert-base-multilingual-cased",
        "type": "distilbert",
    },
}

# OOD Training configurations
SUPPORTED_OOD_METHODS = ["energy", "sngp", "softmax"]

# OOD Default parameters
DEFAULT_OOD_CONFIGS = {
    "energy": {
        "energy_temp": 1.0,
        "energy_margin": 10.0,
        "energy_weight": 0.1,
        "use_energy_loss": True,
    },
    "sngp": {
        "spec_norm_bound": 0.9,
        "gp_hidden_dim": 128,
        "gp_scale": 2.0,
        "gp_bias": 0.0,
        "gp_input_normalization": True,
        "gp_random_feature_type": "orf",
        "gp_cov_momentum": 0.999,
        "gp_cov_ridge_penalty": 1e-3,
    },
    "softmax": {"temperature": 1.0, "use_entropy": True, "calibrate": False},
}

# Training parameters
DEFAULT_TRAINING_ARGS = {
    "num_train_epochs": 4,
    "per_device_train_batch_size": 8,
    "per_device_eval_batch_size": 8,
    "learning_rate": 2e-5,
    "warmup_steps": 100,
    "weight_decay": 0.01,
    "logging_steps": 50,
    "eval_strategy": "epoch",
    "save_strategy": "epoch",
    "load_best_model_at_end": True,
    "metric_for_best_model": "accuracy",
}


# Data pipeline constants
MIN_SAMPLES_PER_CLASS = 10
TARGET_SAMPLES_FOR_SMALL_DATASETS = 50
TEST_SIZE_RATIO = 0.2

# Model evaluation constants
ACCURACY_WEIGHT = 0.7
F1_WEIGHT = 0.3
