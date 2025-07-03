from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from model_trainer import ModelTrainer
import json
import os
from typing import Optional
from loguru import logger
from pydantic import BaseModel
import requests
import sys

logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
print("INIT STARTED model_trainer_api.py")


logger.info("INIT STARTED model_trainer_api.py")

app = FastAPI(title="Model Training API - Unified Training")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("PROCESS STARTED model_trainer_api.py")
logger.info("PROCESS STARTED model_trainer_api.py")


class SessionPayload(BaseModel):
    """Unified payload for all training (standard + OOD variants)"""

    cookie: str
    old_model_id: str
    new_model_id: str
    update_type: str
    prev_deployment_env: Optional[str] = None
    progress_session_id: int
    deployment_env: str
    model_details: str


# Global training status
Training = False


@app.post("/model_trainer/")
async def unified_model_train(payload: SessionPayload):
    """
    Unified training endpoint that trains all model variants:
    - Standard models: estbert, xlm-roberta, multilingual-distilbert
    - OOD variants: energy, SNGP, softmax for each base model

    Selects and deploys the best performing model across all variants.
    """
    global Training

    try:
        print("Starting unified model training")
        print("payload: ", payload.dict())

        # Extract payload data
        cookie = payload.cookie
        new_model_id = payload.new_model_id
        old_model_id = payload.old_model_id
        prev_deployment_env = payload.prev_deployment_env
        update_type = payload.update_type
        progress_session_id = payload.progress_session_id
        model_details = json.loads(payload.model_details)
        current_deployment_platform = payload.deployment_env

        logger.info(f"UNIFIED TRAINING STARTED FOR MODEL {new_model_id}")
        logger.info("TRAINING ALL VARIANTS: Standard + OOD methods")

        Training = True

        # Update initial progress
        update_model_training_progress_session(
            progress_session_id=progress_session_id,
            new_model_id=new_model_id,
            training_status="Training In-Progress",
            training_progress_update_message="Starting unified training of all model variants (Standard + OOD)",
            training_progress_percentage=10,
            process_complete=False,
            cookie=cookie,
        )

        # Initialize and start unified training
        logger.info("INITIALIZING UNIFIED MODEL TRAINER")

        trainer = ModelTrainer(
            cookie=cookie,
            new_model_id=new_model_id,
            old_model_id=old_model_id,
            prev_deployment_env=prev_deployment_env,
            update_type=update_type,
            progress_session_id=progress_session_id,
            current_deployment_platform=current_deployment_platform,
            model_details=model_details,
        )

        # Train all variants
        logger.info("STARTING UNIFIED TRAINING")
        trainer.train()
        logger.info("UNIFIED TRAINING COMPLETED")

        # Final progress update
        update_model_training_progress_session(
            progress_session_id=progress_session_id,
            new_model_id=new_model_id,
            training_status="Training Completed",
            training_progress_update_message="Unified training completed - best model selected and deployed",
            training_progress_percentage=100,
            process_complete=True,
            cookie=cookie,
        )

        Training = False
        logger.info("UNIFIED TRAINING SCRIPT COMPLETED")

        return {
            "status": "success",
            "message": "Unified training completed successfully",
            "model_id": new_model_id,
            "session_id": progress_session_id,
            "training_type": "unified_standard_and_ood",
        }

    except Exception as e:
        Training = False
        logger.error(f"Error in unified model training: {e}")
        print(f"Error in unified model training: {e}")

        # Update error status
        try:
            update_model_training_progress_session(
                progress_session_id=payload.progress_session_id,
                new_model_id=payload.new_model_id,
                training_status="Training Failed",
                training_progress_update_message=f"Unified Training Failed: {str(e)}",
                training_progress_percentage=100,
                process_complete=True,
                cookie=payload.cookie,
            )
        except Exception as update_error:
            logger.error(f"Failed to update training progress on error: {update_error}")

        return {
            "status": "error",
            "message": f"Unified training failed: {str(e)}",
            "error_type": type(e).__name__,
            "training_type": "unified_standard_and_ood",
        }


@app.get("/model_checker/")
async def model_checker():
    """Check current training status"""
    print("Checking training status")
    print("Training: ", Training)
    return {"Training": Training}


@app.get("/supported_models/")
async def get_supported_models():
    """Return all supported model variants"""
    base_models = ["estbert", "xlm-roberta", "multilingual-distilbert"]
    ood_methods = ["energy", "sngp", "softmax"]

    models = []

    # Add standard models
    for model in base_models:
        models.append(
            {
                "name": model,
                "type": "standard",
                "description": f"Standard {model} training",
            }
        )

    # Add OOD variants
    for model in base_models:
        for ood_method in ood_methods:
            models.append(
                {
                    "name": f"{model}-{ood_method}",
                    "type": "ood",
                    "base_model": model,
                    "ood_method": ood_method,
                    "description": f"{model} with {ood_method.upper()} OOD detection",
                }
            )

    return {
        "base_models": base_models,
        "ood_methods": ood_methods,
        "all_variants": models,
        "total_variants": len(models),
    }


@app.get("/training_status/{session_id}")
async def get_training_status(session_id: int):
    """Get detailed training status for a specific session"""
    return {
        "session_id": session_id,
        "is_training": Training,
        "status": "in_progress" if Training else "idle",
        "message": "Unified training in progress" if Training else "No active training",
        "training_type": "unified_standard_and_ood",
    }


def update_model_training_progress_session(
    progress_session_id,
    new_model_id,
    training_status,
    training_progress_update_message,
    training_progress_percentage,
    process_complete,
    cookie,
):
    """Update model training progress session"""
    payload = {
        "sessionId": progress_session_id,
        "trainingStatus": training_status,
        "trainingMessage": training_progress_update_message,
        "progressPercentage": training_progress_percentage,
        "processComplete": process_complete,
    }

    logger.info(
        f"Update training progress session for model id - {new_model_id} payload \n {payload}"
    )

    # Use environment variable for endpoint
    update_endpoint = os.getenv(
        "UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT",
        "http://ruuter-private:8088/classifier/datamodel/progress/update",
    )

    try:
        response = requests.post(
            url=update_endpoint,
            json=payload,
            cookies={"customJwtCookie": cookie},
            timeout=10,
        )

        if response.status_code == 200:
            logger.info(
                f"UPDATE TRAINING PROGRESS SESSION FOR MODEL ID {new_model_id} SUCCESSFUL"
            )
            session_id = response.json()["response"]["sessionId"]
            return session_id
        else:
            logger.error(
                f"UPDATE TRAINING PROGRESS SESSION FOR MODEL ID {new_model_id} FAILED"
            )
            logger.error(f"Response: {response.text}")
            raise RuntimeError(response.text)

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for progress update: {e}")
        # In case of network issues, just return the session ID
        return progress_session_id
    except Exception as e:
        logger.error(f"Unexpected error in progress update: {e}")
        return progress_session_id
