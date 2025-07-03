from datapipeline import DataPipeline
from trainingpipeline import TrainingPipeline, create_training_pipeline
import os
import sys
import requests
import torch
import pickle
import shutil
import json
from datetime import datetime, timezone
from s3_ferry import S3Ferry
from constants import (
    TEST_DEPLOYMENT_ENDPOINT,
    UPDATE_MODEL_TRAINING_STATUS_ENDPOINT,
    UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT,
    MODEL_RESULTS_PATH,
    LOCAL_BASEMODEL_TRAINED_LAYERS_SAVE_PATH,
    LOCAL_CLASSIFICATION_LAYER_SAVE_PATH,
    LOCAL_LABEL_ENCODER_SAVE_PATH,
    S3_FERRY_MODEL_STORAGE_PATH,
    MODEL_TRAINING_SUCCESSFUL,
    INITIATING_TRAINING_PROGRESS_STATUS,
    TRAINING_IN_PROGRESS_PROGRESS_STATUS,
    DEPLOYING_MODEL_PROGRESS_STATUS,
    MODEL_TRAINED_AND_DEPLOYED_PROGRESS_STATUS,
    INITIATING_TRAINING_PROGRESS_MESSAGE,
    INITIATING_TRAINING_PROGRESS_PERCENTAGE,
    TRAINING_IN_PROGRESS_PROGRESS_PERCENTAGE,
    DEPLOYING_MODEL_PROGRESS_PERCENTAGE,
    MODEL_TRAINED_AND_DEPLOYED_PROGRESS_PERCENTAGE,
    MODEL_TRAINING_FAILED_ERROR,
    MODEL_TRAINING_FAILED,
    SUPPORTED_BASE_MODELS,
    SUPPORTED_OOD_METHODS,
    ACCURACY_WEIGHT,
    F1_WEIGHT,
)
from loguru import logger

logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


class ModelTrainer:
    def __init__(
        self,
        cookie,
        new_model_id,
        old_model_id,
        prev_deployment_env,
        update_type,
        progress_session_id,
        model_details,
        current_deployment_platform,
    ) -> None:
        try:
            self.new_model_id = int(new_model_id)
            self.old_model_id = int(old_model_id)
            self.prev_deployment_env = prev_deployment_env
            self.cookie = cookie
            self.update_type = update_type

            self.cookies_payload = {"customJwtCookie": cookie}
            self.progress_session_id = int(progress_session_id)

            logger.info(f"COOKIES PAYLOAD - {self.cookies_payload}")

            if self.update_type == "retrain":
                logger.info(
                    f"ENTERING INTO RETRAIN SEQUENCE FOR MODELID - {self.new_model_id}"
                )

            # Determine if this is a replacement deployment
            if self.old_model_id == self.new_model_id:
                self.replace_deployment = False
            else:
                self.replace_deployment = True

            self.model_details = model_details
            self.current_deployment_platform = current_deployment_platform

        except Exception as e:
            logger.error(f"EXCEPTION IN MODEL_TRAINER INIT : {e}")
            self.send_error_progress_session(str(e))

    @staticmethod
    def create_training_folders(folder_paths):
        logger.info("CREATING FOLDER PATHS")
        try:
            for folder_path in folder_paths:
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
            logger.success(f"SUCCESSFULLY CREATED MODEL FOLDER PATHS : {folder_paths}")
        except Exception as e:
            logger.error(f"FAILED TO CREATE MODEL FOLDER PATHS : {folder_paths}")
            raise RuntimeError(e)

    def update_model_db_training_status(
        self,
        training_status,
        model_s3_location,
        last_trained_time_stamp,
        training_results,
        inference_routes,
    ):
        training_results_payload = {"trainingResults": {}}

        if len(training_results) == 3:
            logger.info(
                f"UPDATE TRAINING STATUS DB RESULTS PAYLOAD: {training_results}"
            )
            training_results_payload["trainingResults"]["classes"] = training_results[0]
            training_results_payload["trainingResults"]["accuracy"] = training_results[
                1
            ]
            training_results_payload["trainingResults"]["f1_score"] = training_results[
                2
            ]
        else:
            training_results_payload["trainingResults"]["classes"] = ""
            training_results_payload["trainingResults"]["accuracy"] = "0.0"
            training_results_payload["trainingResults"]["f1_score"] = "0"

        payload = {
            "modelId": self.new_model_id,
            "trainingStatus": training_status,
            "modelS3Location": model_s3_location,
            "lastTrainedTimestamp": last_trained_time_stamp,
            "trainingResults": training_results_payload,
            "inferenceRoutes": {"inference_routes": inference_routes},
        }

        logger.info(f"{training_status} UPLOAD PAYLOAD - \n {payload}")

        response = requests.post(
            url=UPDATE_MODEL_TRAINING_STATUS_ENDPOINT,
            json=payload,
            cookies=self.cookies_payload,
        )

        if response.status_code == 200:
            logger.info(
                f"REQUEST TO UPDATE MODEL TRAINING STATUS TO {training_status} SUCCESSFUL"
            )
        else:
            logger.error(
                f"REQUEST TO UPDATE MODEL TRAINING STATUS TO {training_status} FAILED"
            )
            logger.error(f"ERROR RESPONSE {response.text}")
            self.send_error_progress_session(f"Error :{str(response.text)}")
            raise RuntimeError(response.text)

    def send_error_progress_session(self, error_msg):
        response = self.update_model_training_progress_session(
            MODEL_TRAINING_FAILED_ERROR, error_msg, 100, True
        )
        current_timestamp = self.get_current_timestamp()
        self.update_model_db_training_status(
            training_status=MODEL_TRAINING_FAILED,
            model_s3_location="",
            last_trained_time_stamp=current_timestamp,
            training_results=[],
            inference_routes=[],
        )
        return response

    def update_model_training_progress_session(
        self,
        training_status,
        training_progress_update_message,
        training_progress_percentage,
        process_complete,
    ):
        payload = {
            "sessionId": self.progress_session_id,
            "trainingStatus": training_status,
            "trainingMessage": training_progress_update_message,
            "progressPercentage": training_progress_percentage,
            "processComplete": process_complete,
        }

        logger.info(
            f"Update training progress session for model id - {self.new_model_id} payload \n {payload}"
        )

        response = requests.post(
            url=UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT,
            json=payload,
            cookies=self.cookies_payload,
        )

        if response.status_code == 200:
            logger.info(
                f"REQUEST TO UPDATE TRAINING PROGRESS SESSION FOR MODEL ID {self.new_model_id} SUCCESSFUL"
            )
            session_id = response.json()["response"]["sessionId"]
        else:
            logger.error(
                f"REQUEST TO UPDATE TRAINING PROGRESS SESSION FOR MODEL ID {self.new_model_id} FAILED"
            )
            logger.error(f"ERROR RESPONSE {response.text}")
            raise RuntimeError(response.text)

        return session_id

    def deploy_model(self, best_model_info, progress_session_id, dg_id):
        payload = {
            "modelId": self.new_model_id,
            "oldModelId": self.old_model_id,
            "replaceDeployment": self.replace_deployment,
            "replaceDeploymentPlatform": self.prev_deployment_env,
            "bestBaseModel": best_model_info["name"],
            "bestModelType": best_model_info["type"],
            "progressSessionId": progress_session_id,
            "updateType": self.update_type,
            "dgId": dg_id,
        }

        if self.update_type == "retrain":
            payload["replaceDeploymentPlatform"] = self.current_deployment_platform

        logger.info(
            f"SENDING MODEL DEPLOYMENT REQUEST FOR MODEL ID - {self.new_model_id}"
        )
        logger.info(f"MODEL DEPLOYMENT PAYLOAD - {payload}")

        if self.current_deployment_platform == "testing":
            deployment_url = TEST_DEPLOYMENT_ENDPOINT
        elif self.current_deployment_platform == "undeployed":
            logger.info("DEPLOYMENT ENVIRONMENT IS UNDEPLOYED")
            return None
        else:
            logger.error(
                f"UNRECOGNIZED DEPLOYMENT PLATFORM - {self.current_deployment_platform}"
            )
            self.send_error_progress_session(
                f"UNRECOGNIZED DEPLOYMENT PLATFORM - {str(self.current_deployment_platform)}"
            )
            raise RuntimeError(
                f"RUNTIME ERROR - UNRECOGNIZED DEPLOYMENT PLATFORM - {self.current_deployment_platform}"
            )

        response = requests.post(
            url=deployment_url, json=payload, cookies=self.cookies_payload
        )

        if response.status_code == 200:
            logger.info(f"REQUEST TO DEPLOY MODEL ID {self.new_model_id} SUCCESSFUL")
        else:
            logger.error(f"REQUEST TO DEPLOY MODEL ID {self.new_model_id} FAILED")
            logger.error(f"ERROR RESPONSE {response.text}")
            raise RuntimeError(response.text)

    def get_current_timestamp(self):
        current_timestamp = int(datetime.now(timezone.utc).timestamp())
        return current_timestamp

    def calculate_combined_score(self, accuracies, f1_scores):
        """Calculate combined score using weighted average"""
        if not accuracies or not f1_scores:
            return 0.0

        avg_accuracy = sum(accuracies) / len(accuracies)
        avg_f1 = sum(f1_scores) / len(f1_scores)

        combined_score = (ACCURACY_WEIGHT * avg_accuracy) + (F1_WEIGHT * avg_f1)
        return combined_score

    def train(self):
        """UNIFIED TRAINING METHOD - TRAINS ALL VARIANTS"""
        try:
            logger.info("ENTERING UNIFIED TRAINING FUNCTION")
            logger.info(f"DEPLOYMENT PLATFORM - {self.current_deployment_platform}")

            session_id = self.progress_session_id
            logger.info(f"SESSION ID - {session_id}")

            # Update initial progress
            self.update_model_training_progress_session(
                training_status=INITIATING_TRAINING_PROGRESS_STATUS,
                training_progress_update_message=INITIATING_TRAINING_PROGRESS_MESSAGE,
                training_progress_percentage=INITIATING_TRAINING_PROGRESS_PERCENTAGE,
                process_complete=False,
            )

            # Initialize services
            s3_ferry = S3Ferry()
            dg_id = self.model_details["response"]["data"][0]["connectedDgId"]

            # Load data
            data_pipeline = DataPipeline(dg_id, self.cookie)
            dfs = data_pipeline.create_dataframes()
            models_inference_metadata, _ = data_pipeline.models_and_filters()

            logger.info(f"MODELS_INFERENCE_METADATA : {models_inference_metadata}")

            # Setup paths
            local_basemodel_layers_save_path = (
                LOCAL_BASEMODEL_TRAINED_LAYERS_SAVE_PATH.format(
                    model_id=self.new_model_id
                )
            )
            local_classification_layer_save_path = (
                LOCAL_CLASSIFICATION_LAYER_SAVE_PATH.format(model_id=self.new_model_id)
            )
            local_label_encoder_save_path = LOCAL_LABEL_ENCODER_SAVE_PATH.format(
                model_id=self.new_model_id
            )

            self.create_training_folders(
                [
                    local_basemodel_layers_save_path,
                    local_classification_layer_save_path,
                    local_label_encoder_save_path,
                ]
            )

            # Save inference metadata
            with open(
                f"{MODEL_RESULTS_PATH}/{self.new_model_id}/models_dets.pkl", "wb"
            ) as file:
                pickle.dump(models_inference_metadata, file)

            # Generate all model variants to train
            model_variants = []

            # Add standard models
            for base_model in SUPPORTED_BASE_MODELS:
                model_variants.append(
                    {
                        "name": base_model,
                        "base_model": base_model,
                        "ood_method": None,
                        "type": "standard",
                    }
                )

            # Add OOD variants
            for base_model in SUPPORTED_BASE_MODELS:
                for ood_method in SUPPORTED_OOD_METHODS:
                    model_variants.append(
                        {
                            "name": f"{base_model}-{ood_method}",
                            "base_model": base_model,
                            "ood_method": ood_method,
                            "type": "ood",
                        }
                    )

            logger.info(f"TRAINING {len(model_variants)} MODEL VARIANTS:")
            for variant in model_variants:
                logger.info(f"  - {variant['name']} ({variant['type']})")

            # Update progress to training phase
            self.update_model_training_progress_session(
                training_status=TRAINING_IN_PROGRESS_PROGRESS_STATUS,
                training_progress_update_message=f"Training {len(model_variants)} model variants (Standard + OOD)",
                training_progress_percentage=TRAINING_IN_PROGRESS_PROGRESS_PERCENTAGE,
                process_complete=False,
            )

            # Train all variants
            all_results = []

            for i, variant in enumerate(model_variants):
                logger.info(
                    f"TRAINING VARIANT {i + 1}/{len(model_variants)}: {variant['name']}"
                )

                try:
                    # Create training pipeline
                    if variant["ood_method"]:
                        training_pipeline = create_training_pipeline(
                            dfs=dfs,
                            model_name=variant["base_model"],
                            ood_method=variant["ood_method"],
                        )
                    else:
                        training_pipeline = TrainingPipeline(dfs, variant["base_model"])

                    # Train the variant
                    metrics, models, classifiers, label_encoders, basic_model = (
                        training_pipeline.train()
                    )

                    # Calculate combined score
                    _, accuracies, f1_scores = metrics
                    combined_score = self.calculate_combined_score(
                        accuracies, f1_scores
                    )

                    # Store results
                    result = {
                        "variant": variant,
                        "metrics": metrics,
                        "models": models,
                        "classifiers": classifiers,
                        "label_encoders": label_encoders,
                        "basic_model": basic_model,
                        "combined_score": combined_score,
                        "avg_accuracy": (
                            sum(accuracies) / len(accuracies) if accuracies else 0
                        ),
                        "avg_f1": sum(f1_scores) / len(f1_scores) if f1_scores else 0,
                    }

                    all_results.append(result)

                    logger.info(
                        f"COMPLETED {variant['name']} - Combined Score: {combined_score:.4f}"
                    )
                    logger.info(
                        f"  Avg Accuracy: {result['avg_accuracy']:.4f}, Avg F1: {result['avg_f1']:.4f}"
                    )

                except Exception as e:
                    logger.error(f"FAILED TO TRAIN {variant['name']}: {e}")
                    continue

            # Select best model across all variants
            if not all_results:
                raise RuntimeError("No models were successfully trained")

            best_result = max(all_results, key=lambda x: x["combined_score"])
            best_variant = best_result["variant"]

            logger.info(f"BEST MODEL SELECTED: {best_variant['name']}")
            logger.info(f"BEST COMBINED SCORE: {best_result['combined_score']:.4f}")
            logger.info(f"BEST MODEL TYPE: {best_variant['type']}")

            # Save best model artifacts
            for i, (model, classifier, label_encoder) in enumerate(
                zip(
                    best_result["models"],
                    best_result["classifiers"],
                    best_result["label_encoders"],
                )
            ):
                torch.save(
                    model,
                    f"{local_basemodel_layers_save_path}/last_two_layers_dfs_{i}.pth",
                )
                torch.save(
                    classifier,
                    f"{local_classification_layer_save_path}/classifier_{i}.pth",
                )

                label_encoder_path = (
                    f"{local_label_encoder_save_path}/label_encoder_{i}.pkl"
                )
                with open(label_encoder_path, "wb") as file:
                    pickle.dump(label_encoder, file)

            # Save basic model
            torch.save(
                best_result["basic_model"],
                f"{MODEL_RESULTS_PATH}/{self.new_model_id}/model_state_dict.pth",
            )

            # Save training summary
            training_summary = {
                "best_model": best_variant,
                "best_score": best_result["combined_score"],
                "all_results": [
                    {
                        "variant": r["variant"],
                        "combined_score": r["combined_score"],
                        "avg_accuracy": r["avg_accuracy"],
                        "avg_f1": r["avg_f1"],
                    }
                    for r in all_results
                ],
                "total_variants_trained": len(all_results),
                "training_timestamp": self.get_current_timestamp(),
            }

            with open(
                f"{MODEL_RESULTS_PATH}/{self.new_model_id}/training_summary.json", "w"
            ) as f:
                json.dump(training_summary, f, indent=2)

            # Create model archive
            model_zip_path = f"{MODEL_RESULTS_PATH}/{str(self.new_model_id)}"
            shutil.make_archive(
                base_name=model_zip_path, root_dir=model_zip_path, format="zip"
            )

            # Upload to S3
            s3_save_location = f"{S3_FERRY_MODEL_STORAGE_PATH}/{str(self.new_model_id)}/{str(self.new_model_id)}.zip"
            local_source_location = f"{MODEL_RESULTS_PATH.replace('/shared/', '')}/{str(self.new_model_id)}.zip"

            logger.info("INITIATING MODEL UPLOAD TO S3")
            _ = s3_ferry.transfer_file(
                s3_save_location, "S3", local_source_location, "FS"
            )

            # Cleanup local files
            MODEL_RESULT_FOLDER = f"{MODEL_RESULTS_PATH}/{self.new_model_id}"
            MODEL_RESULT_ZIP_FILE = f"{MODEL_RESULTS_PATH}/{self.new_model_id}.zip"

            if os.path.exists(MODEL_RESULT_FOLDER):
                try:
                    shutil.rmtree(MODEL_RESULT_FOLDER)
                    logger.info(f"Cleaned up folder '{MODEL_RESULT_FOLDER}'")
                except Exception as e:
                    logger.warning(
                        f"Could not delete folder '{MODEL_RESULT_FOLDER}': {e}"
                    )

            if os.path.exists(MODEL_RESULT_ZIP_FILE):
                try:
                    os.remove(MODEL_RESULT_ZIP_FILE)
                    logger.info(f"Cleaned up zip file '{MODEL_RESULT_ZIP_FILE}'")
                except Exception as e:
                    logger.warning(
                        f"Could not delete zip file '{MODEL_RESULT_ZIP_FILE}': {e}"
                    )

            # Update database with best model results
            current_timestamp = self.get_current_timestamp()
            self.update_model_db_training_status(
                training_status=MODEL_TRAINING_SUCCESSFUL,
                model_s3_location=s3_save_location,
                last_trained_time_stamp=current_timestamp,
                training_results=best_result["metrics"],
                inference_routes=models_inference_metadata,
            )

            # Update progress to deployment phase
            self.update_model_training_progress_session(
                training_status=DEPLOYING_MODEL_PROGRESS_STATUS,
                training_progress_update_message=f"Deploying best model: {best_variant['name']}",
                training_progress_percentage=DEPLOYING_MODEL_PROGRESS_PERCENTAGE,
                process_complete=False,
            )

            # Deploy the best model
            if self.current_deployment_platform == "undeployed":
                logger.info("MODEL DEPLOYMENT PLATFORM IS UNDEPLOYED")
                self.update_model_training_progress_session(
                    training_status=MODEL_TRAINED_AND_DEPLOYED_PROGRESS_STATUS,
                    training_progress_update_message=f"Best model ({best_variant['name']}) trained successfully - No deployment",
                    training_progress_percentage=MODEL_TRAINED_AND_DEPLOYED_PROGRESS_PERCENTAGE,
                    process_complete=True,
                )
                logger.info("UNIFIED TRAINING COMPLETED")
            else:
                logger.info(
                    f"INITIATING DEPLOYMENT OF {best_variant['name']} TO {self.current_deployment_platform}"
                )
                self.deploy_model(
                    best_model_info=best_variant,
                    progress_session_id=session_id,
                    dg_id=dg_id,
                )

                self.update_model_training_progress_session(
                    training_status=MODEL_TRAINED_AND_DEPLOYED_PROGRESS_STATUS,
                    training_progress_update_message=f"Best model ({best_variant['name']}) trained and deployed successfully",
                    training_progress_percentage=MODEL_TRAINED_AND_DEPLOYED_PROGRESS_PERCENTAGE,
                    process_complete=True,
                )

            logger.info("=" * 60)
            logger.info("UNIFIED TRAINING COMPLETED SUCCESSFULLY")
            logger.info(f"BEST MODEL: {best_variant['name']}")
            logger.info(f"FINAL SCORE: {best_result['combined_score']:.4f}")
            logger.info(f"VARIANTS TRAINED: {len(all_results)}")
            logger.info("=" * 60)

        except Exception as e:
            import traceback

            logger.error(f"EXCEPTION IN UNIFIED MODEL TRAINER: {e}")
            logger.error(traceback.format_exc())
            self.send_error_progress_session(
                f"UNIFIED TRAINING CRASHED - ERROR - {str(e)}"
            )
            raise
