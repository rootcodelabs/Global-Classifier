from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from model_trainer import ModelTrainer
import json
import os
from typing import List, Optional
from loguru import logger
from pydantic import BaseModel
import requests
from constants import TRAINING_LOGS_PATH

# Environment variable for the update endpoint
UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT = os.getenv("UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT")

print("INIT STARTED MAIN.PY")
logger.add(sink=TRAINING_LOGS_PATH)
logger.info("INIT STARTED MAIN.PY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as necessary
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("INIT STARTED model_trainer_api.py - Log recorded")
logger.info("PROCESS STARTED model_trainer_api.py")
print("PROCESS STARTED model_trainer_api.py - Log recorded")


class SessionPayload(BaseModel):
    cookie: str
    old_model_id: str
    new_model_id: str
    update_type: str
    prev_deployment_env: Optional[str] = None
    progress_session_id: int
    deployment_env: str
    model_details: str


# Use global variable to track training status
Training = False


@app.post("/model_trainer/")
async def model_train(payload: SessionPayload):
    global Training  # Declare that we intend to modify the global variable
    try:
        print("I'm inside model_trainer")
        print("payload: ", payload)

        # Extract payload data
        cookie = payload.cookie
        newModelId = payload.new_model_id
        oldModelId = payload.old_model_id
        prev_deployment_env = payload.prev_deployment_env
        update_type = payload.update_type
        progress_session_id = payload.progress_session_id
        model_details = json.loads(payload.model_details)
        current_deployment_platform = payload.deployment_env

        # Update training progress to "In-Progress"
        update_model_training_progress_session(
            progress_session_id=progress_session_id,
            new_model_id=newModelId,
            training_status="Training In-Progress",
            training_progress_update_message="Model training in progress",
            training_progress_percentage=10,
            process_complete=False,
            cookie=cookie
        )

        # Initialize and start training
        trainer = ModelTrainer(
            cookie, newModelId, oldModelId, prev_deployment_env,
            update_type, progress_session_id, model_details, current_deployment_platform
        )
        Training = True
        trainer.train()
        Training = False

        # Notify the session service
        response = requests.post("http://trainer-queue:8901/get_session")
        print(response)
        logger.info("TRAINING SCRIPT COMPLETED")
        print("TRAINING SCRIPT COMPLETED - Log recorded")

    except Exception as e:
        Training = False
        logger.error(f"Error in model_trainer_api.PY : {e}")
        print(f"Error in model_trainer_api.PY - Log recorded {e}")

        # Update training progress to "Failed"
        try:
            update_model_training_progress_session(
                progress_session_id=payload.progress_session_id,
                new_model_id=payload.new_model_id,
                training_status="Training Failed",
                training_progress_update_message="Training Failed",
                training_progress_percentage=100,
                process_complete=True,
                cookie=payload.cookie
            )
        except Exception as update_error:
            logger.error(f"Failed to update training progress on error: {update_error}")
            print(f"Failed to update training progress on error: {update_error}")

        # Optionally, re-raise the exception if you want the API to return an error
        raise e


@app.get("/model_checker/")
async def model_checker():
    print("I'm inside model_checker")
    print("Training: ", Training)
    return {"Training": Training}


def update_model_training_progress_session(progress_session_id, new_model_id, training_status, 
                                          training_progress_update_message, training_progress_percentage,
                                          process_complete, cookie):

    payload = {
        "sessionId": progress_session_id,
        "trainingStatus": training_status,
        "trainingMessage": training_progress_update_message,
        "progressPercentage": training_progress_percentage,
        "processComplete": process_complete
    }

    logger.info(f"Update training progress session for model id - {new_model_id} payload \n {payload}")

    response = requests.post(
        url=UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT,
        json=payload,
        cookies={'customJwtCookie': cookie}
    )

    if response.status_code == 200:
        logger.info(f"REQUEST TO UPDATE TRAINING PROGRESS SESSION FOR MODEL ID {new_model_id} SUCCESSFUL")
        logger.info(f"RESPONSE PAYLOAD \n {response.json()}")
        print(f"REQUEST TO UPDATE TRAINING PROGRESS SESSION FOR MODEL ID {new_model_id} SUCCESSFUL")
        print(f"RESPONSE PAYLOAD \n {response.json()}")
        session_id = response.json()["response"]["sessionId"]
    else:
        logger.error(f"REQUEST TO UPDATE TRAINING PROGRESS SESSION FOR MODEL ID {new_model_id} FAILED")
        logger.error(f"ERROR RESPONSE JSON {response.json()}")
        logger.error(f"ERROR RESPONSE TEXT {response.text}")
        print(f"REQUEST TO UPDATE TRAINING PROGRESS SESSION FOR MODEL ID {new_model_id} FAILED")
        print(f"ERROR RESPONSE JSON {response.json()}")
        print(f"ERROR RESPONSE TEXT {response.text}")
        raise RuntimeError(response.text)

    return session_id
