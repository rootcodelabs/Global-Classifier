from datapipeline import DataPipeline
from trainingpipeline import TrainingPipeline, create_training_pipeline
import os
import sys
import shutil
import json
from datetime import datetime, timezone
from s3_ferry import S3Ferry
from create_triton_configs import generate_all_triton_configs
from constants import (
    MODEL_RESULTS_PATH,
    S3_FERRY_MODEL_STORAGE_PATH,
    ACCURACY_WEIGHT,
    UNCERTAINTY_CONFIGS,
    F1_WEIGHT,
    SEQUENCE_LENGTH,
    MODEL_TRAINING_SOURCE_PATH,    
    DEPLOYMENT_ENDPOINT, 
    CREATE_TRAINING_PROGRESS_SESSION_ENDPOINT, 
    UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT
)

from loguru import logger
import requests

import argparse

from loki_logger import LokiLogger
logger = LokiLogger(service_name="model-trainer")


class ModelTrainer:
    def __init__(
        self,
        model_id,
        model_name,
        dataset_id,
        model_types,
        major_version,
        minor_version,
        latest,
        current_deployment_env,
        progress_session_id,
        target_deployment_platform,
    ) -> None:
        try:
            logger.info("INITIALIZING MODEL TRAINER")
            self.model_id = model_id
            self.model_name = model_name
            self.dataset_id = dataset_id
            self.model_types = model_types
            self.major_version = major_version
            self.minor_version = minor_version
            self.latest = latest
            self.current_deployment_platform = current_deployment_env
            self.target_deployment_platform = target_deployment_platform

            self.progress_session_id = int(progress_session_id)

        except Exception as e:
            logger.error(f"EXCEPTION IN MODEL_TRAINER INIT : {e}")

    @staticmethod
    def create_training_folders(folder_paths):
        logger.info("CREATING FOLDER PATHS")
        try:
            for folder_path in folder_paths:
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
            logger.info(f"SUCCESSFULLY CREATED MODEL FOLDER PATHS : {folder_paths}")
        except Exception as e:
            logger.error(f"FAILED TO CREATE MODEL FOLDER PATHS : {folder_paths}")
            raise RuntimeError(e)

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

    def deploy_model(self, deployment_environment) :
        """Deploy the model to the specified environment"""
        logger.info(f"DEPLOYING MODEL TO {deployment_environment}")
        # Placeholder for deployment logic
        # This could involve calling a deployment service, updating configs, etc.
        # For now, just log the action

        logger.info(f"MODEL {self.model_name} (ID: {self.model_id}) deployed to {deployment_environment}")

    def train(self):
        """UNIFIED TRAINING METHOD - TRAINS ALL VARIANTS"""
        try:
            logger.info("ENTERING UNIFIED TRAINING FUNCTION")
            logger.info(f"DEPLOYMENT PLATFORM - {self.current_deployment_platform}")

            # Initialize services
            s3_ferry = S3Ferry()

            # Load data
            data_pipeline = DataPipeline(self.dataset_id)
            dfs = data_pipeline.create_dataframes()
            models_inference_metadata, _ = data_pipeline.models_and_filters()

            logger.info(f"MODELS_INFERENCE_METADATA : {models_inference_metadata}")

            # Setup paths

            # Generate all model variants to train
            model_variants = []

            # Add standard models
            for base_model in self.model_types:

                model_variants.append(
                    {
                        "name": base_model + "-sngp",
                        "base_model": base_model,
                        "full_model_name": base_model,
                        "ood_method": "sngp",
                        "type": "ood",
                        "uncertainty_strategy": UNCERTAINTY_CONFIGS.get(
                            "uncertainty_strategy", None
                        ),
                        "human_handoff_threshold": UNCERTAINTY_CONFIGS.get(
                            "human_handoff_threshold", 0.8
                        ),
                        "confidence_scaling": UNCERTAINTY_CONFIGS.get(
                            "confidence_scaling", False
                        ),
                    }
                )
            logger.info(f"TRAINING {len(model_variants)} MODEL VARIANTS:")
            for variant in model_variants:
                logger.info(f"  - {variant['name']} ({variant['type']})")

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
                            full_name=variant["full_model_name"],
                            ood_method=variant["ood_method"],
                        )
                    else:
                        training_pipeline = TrainingPipeline(dfs, variant["base_model"],full_name=variant["full_model_name"],)

                    # Train the variant
                    model_dir, metrics = training_pipeline.train()

                    # Calculate combined score
                    _, accuracies, f1_scores = metrics
                    combined_score = self.calculate_combined_score(
                        accuracies, f1_scores
                    )

                    # Store results
                    result = {
                        "variant": variant,
                        "model_path": model_dir,
                        "metrics": metrics,
                        "avg_accuracy": (
                            sum(accuracies) / len(accuracies) if accuracies else 0
                        ),
                        "avg_f1": sum(f1_scores) / len(f1_scores) if f1_scores else 0,
                        "combined_score": combined_score,  # <-- Add this line
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

            with open(f"{MODEL_RESULTS_PATH}/training_summary.json", "w") as f:
                json.dump(training_summary, f, indent=2)
            from trainingpipeline import export_inference_model_to_onnx

            # Convert best model to ONNX
            # check if it is sngp
            logger.info("CONVERTING SNGP MODEL TO ONNX")
            onnx_path = export_inference_model_to_onnx(best_result["model_path"])
            logger.info(f"ONNX MODEL SAVED AT: {onnx_path}")

            # create model-id folder and copy model-repository directory contents there
            new_model_repo_path = f"{MODEL_RESULTS_PATH}/{self.model_id}"
            if not os.path.exists(new_model_repo_path):
                os.makedirs(new_model_repo_path)
            # this is the pre-defined model-repository path
            model_repository_path = f"{MODEL_TRAINING_SOURCE_PATH}/model-repository"

            # copy all contents and directories of model-repository to new_model_repo_path
            shutil.copytree(
                src=model_repository_path,
                dst=new_model_repo_path,
                dirs_exist_ok=True,
            )
            # add labels-mapping.json to new_model_repo_path pre-processing and post-processing directories
            label_mappings_path = f"{new_model_repo_path}/pre-processing/1"
            if not os.path.exists(label_mappings_path):
                os.makedirs(label_mappings_path)
            shutil.copy(
                src=f"{best_result['model_path']}/config.json",
                dst=f"{label_mappings_path}/label_mappings.json",
            )
            shutil.copy(
                src=f"{best_result['model_path']}/config.json",
                dst=f"{new_model_repo_path}/post-processing/1/label_mappings.json",
            )
            top_level_dirs = [
                d
                for d in os.listdir(new_model_repo_path)
                if os.path.isdir(os.path.join(new_model_repo_path, d))
            ]
            # add modelId-{model-id} to all folders inside the new_model_repo_path
            for dir_name in top_level_dirs:
                old_path = os.path.join(new_model_repo_path, dir_name)
                new_dir_name = f"{self.model_id}-{dir_name}"
                new_path = os.path.join(new_model_repo_path, new_dir_name)

                logger.info(f"Renaming {dir_name} to {new_dir_name}")
                os.rename(old_path, new_path)

            # move onnx model to the new model-id folder inside model-id/text-classifier/1/model.onnx
            onnx_model_path = f"{new_model_repo_path}/{self.model_id}-text-classifier/1"
            if not os.path.exists(onnx_model_path):
                os.makedirs(onnx_model_path)
            shutil.move(
                src=f"{best_result['model_path']}/model.onnx",
                dst=f"{onnx_model_path}/model.onnx",
            )

            triton_configs = generate_all_triton_configs(
                model_id=str(self.model_id),
                model_type=best_variant["base_model"],  # "distilbert", "bert", etc.
                num_labels=len(best_result["metrics"][0]),
                sequence_length=SEQUENCE_LENGTH,
                max_batch_size=16,
                ood_method=best_variant.get("ood_method"),  # "sngp", "energy", etc.
                ood_threshold=0.5,
                uncertainty_threshold=best_variant.get("uncertainty_strategy", "sngp"),
                human_handoff_threshold=best_variant.get(
                    "human_handoff_threshold", 0.8
                ),
                uncertainty_strategy="inject_class",  # or other strategies
                confidence_scaling=best_variant.get("confidence_scaling", False),
                base_model_type=best_variant.get("base_model_type", "bert"),
            )
            # Save Triton configs to model repository
            for config_path, config_content in triton_configs.items():
                config_full_path = os.path.join(new_model_repo_path, config_path)
                os.makedirs(os.path.dirname(config_full_path), exist_ok=True)
                with open(config_full_path, "w") as f:
                    f.write(config_content)
            # Create model archive
            model_zip_path = new_model_repo_path
            shutil.make_archive(
                base_name=model_zip_path, root_dir=model_zip_path, format="zip"
            )

            # Upload to S3
            s3_save_location = f"{S3_FERRY_MODEL_STORAGE_PATH}/{str(self.model_id)}/{str(self.model_id)}.zip"

            # Removing /app from path since S3 Ferry will already add /app to the path as defined in the config.env
            local_source_location =  f"{MODEL_RESULTS_PATH.replace('/app/', '')}/{str(self.model_id)}.zip"
            

            logger.info("INITIATING MODEL UPLOAD TO S3")
            _ = s3_ferry.transfer_file(
                s3_save_location, "S3", local_source_location, "FS"
            )

            # Cleanup local files
            MODEL_RESULT_FOLDER = f"{MODEL_RESULTS_PATH}/{self.model_id}"
            MODEL_RESULT_ZIP_FILE = f"{MODEL_RESULTS_PATH}/{self.model_id}.zip"

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

            # Deploy the best model
            if self.current_deployment_platform == "undeployed":
                logger.info("MODEL DEPLOYMENT PLATFORM IS UNDEPLOYED")

                logger.info("UNIFIED TRAINING COMPLETED")
            else:
                logger.info(
                    f"INITIATING DEPLOYMENT OF {best_variant['name']} TO {self.current_deployment_platform}"
                )
                # self.deploy_model(
                #     best_model_info=best_variant,
                #     progress_session_id=session_id,
                #     dg_id=dg_id,
                # )

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
            raise
    
    def deploy(self):

        """
        Deploy a model from current environment to target environment using Ruuter endpoint.
        
        Args:
            model_id: The ID of the model to deploy
            current_env: Current deployment environment (e.g., 'testing', 'production')
            target_env: Target deployment environment to deploy to
            first_deployment: Whether this is the first deployment (default: False)
            
        """
        


        logger.info("Starting model deployment")
        
        # Prepare request payload
        payload = {
            "modelId": self.model_id,
            "currentEnv": self.current_deployment_platform,
            "targetEnv": self.target_deployment_platform,
            "firstDeployment": True
        }

        logger.info(f"Prepared deployment payload {payload}")
        
        try:
            # Make request to deployment endpoint
            response = requests.post(
                DEPLOYMENT_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300  # 5 minute timeout for deployment operations
            )
            
            logger.info(f"Deployment endpoint response - {response.status_code} - {response.text}")
            
            # Check if request was successful
            response.raise_for_status()
            
            logger.info("Model deployment completed successfully")
            
            return response.json()
            
        except requests.HTTPError as e:
            error_msg = f"HTTP error during model deployment: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg, model_id=self.model_id, 
                        current_env=self.current_deployment_platform, target_env=self.target_deployment_platform,
                        status_code=e.response.status_code)
            raise
            
        except requests.RequestException as e:
            error_msg = f"Network error during model deployment: {str(e)}"
            logger.error(error_msg, model_id=self.model_id,
                        current_env=self.current_deployment_platform, target_env=self.target_deployment_platform)
            raise
            
        except Exception as e:
            error_msg = f"Unexpected error during model deployment: {str(e)}"
            logger.error(error_msg, model_id=self.model_id,
                        current_env=self.current_deployment_platform, target_env=self.target_deployment_platform)
            raise

 


# ----------------------TODO: Uncomment the CLI section when needed----------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Model Trainer CLI")
    parser.add_argument(
        "--model_types",
        type=str,
        required=True,
        help="Model types (JSON string or list)",
    )
    parser.add_argument("--model_id", type=int, required=True, help="Model ID")
    parser.add_argument("--job_id", type=int, required=True, help="Job ID")
    parser.add_argument("--dataset_id", type=int, required=True, help="Dataset ID")
    parser.add_argument("--model_name", type=str, required=True, help="Model Name")
    parser.add_argument(
        "--major_version", type=int, required=True, help="Major Version"
    )
    parser.add_argument(
        "--minor_version", type=int, required=True, help="Minor Version"
    )
    parser.add_argument(
        "--latest", type=str, required=True, help="Is Latest (true/false)"
    )
    parser.add_argument(
        "--deployment_environment",
        type=str,
        required=True,
        help="Deployment Environment",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    model_id = args.model_id
    model_name = args.model_name
    dataset_id = args.dataset_id
    model_types = (
        json.loads(args.model_types)
        if isinstance(args.model_types, str)
        else args.model_types
    )
    major_version = args.major_version
    minor_version = args.minor_version
    latest = args.latest.lower() == "true"
    current_deployment_env = "undeployed"
    progress_session_id = args.job_id
    target_deployment_platform = args.deployment_environment

    trainer = ModelTrainer(
        model_id=model_id,
        model_name=model_name,
        dataset_id=dataset_id,
        model_types=model_types,
        major_version=major_version,
        minor_version=minor_version,
        latest=latest,
        current_deployment_env=current_deployment_env,
        progress_session_id=progress_session_id,
        target_deployment_platform=target_deployment_platform,
    )
    trainer.train()
    trainer.deploy()