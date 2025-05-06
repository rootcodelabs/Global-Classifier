from pydantic import BaseModel
from typing import List, Optional


INFERENCE_LOGS_PATH = "/app/inference_logs.log"

LABEL_ENCODERS_FOLDER = "label_encoders"

CLASSIFIER_LAYERS_FOLDER = "classifier_layers"

TRAINED_BASE_MODEL_LAYERS = "trained_base_model_layers"

MODEL_DETS_FILE = "models_dets.pkl"

DISTIL_BERT = "distil-bert"

ROBERTA = "roberta"

BERT = "bert"

OUTLOOK_MODELS_FOLDER_PATH = "/shared/models/outlook"

JIRA_MODELS_FOLDER_PATH = "/shared/models/jira"

SHARED_MODELS_ROOT_FOLDER = "/shared/models"

MODEL_TRAINED_AND_DEPLOYED_PROGRESS_PERCENTAGE=100

MODEL_TRAINED_AND_DEPLOYED_PROGRESS_MESSAGE = "The model was trained and deployed successfully to environment"

MODEL_TRAINED_AND_DEPLOYED_PROGRESS_STATUS = "Model Trained And Deployed"


S3_DOWNLOAD_FAILED = {
    "upload_status": 500,
    "operation_successful": False,
    "saved_file_path": None,
    "reason": "Failed to download from S3"
}

class UpdateRequest(BaseModel):
    modelId: int
    oldModelId: int
    replaceDeployment:bool
    replaceDeploymentPlatform:Optional[str] = None
    bestBaseModel:str
    updateType: Optional[str] = None
    progressSessionId: int
    dgId:Optional[int]= None

class OutlookInferenceRequest(BaseModel):
    inputId:str
    inputText:str
    finalFolderId:str
    mailId:str

class JiraInferenceRequest(BaseModel):
    inputId:str
    inputText:str
    finalLabels:Optional[List[str]] = None

class TestInferenceRequest(BaseModel):
    modelId:int
    text:str

class DeleteTestRequest(BaseModel):
    deleteModelId:int
