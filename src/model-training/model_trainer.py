from datapipeline import DataPipeline
from trainingpipeline import TrainingPipeline, create_training_pipeline
import os
import sys
import requests
import pickle
import shutil
import json
from datetime import datetime, timezone
from s3_ferry import S3Ferry
from constants import (
    TEST_DEPLOYMENT_ENDPOINT,
    MODEL_RESULTS_PATH,
    LOCAL_BASEMODEL_TRAINED_LAYERS_SAVE_PATH,
    LOCAL_CLASSIFICATION_LAYER_SAVE_PATH,
    LOCAL_LABEL_ENCODER_SAVE_PATH,
    S3_FERRY_MODEL_STORAGE_PATH,
    SUPPORTED_BASE_MODELS,
    SUPPORTED_OOD_METHODS,
    ACCURACY_WEIGHT,
    DEFAULT_OOD_CONFIGS,
    UNCERTAINTY_CONFIGS,
    F1_WEIGHT,
    SEQUENCE_LENGTH,
)
from loguru import logger

# import argparse

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
                            "model_name": base_model,
                            "ood_method": ood_method,
                            "type": "ood",
                            "energy_temp": DEFAULT_OOD_CONFIGS.get(ood_method, {}).get(
                                "energy_temp", 1.0
                            ),
                            "softmax_temp": DEFAULT_OOD_CONFIGS.get(ood_method, {}).get(
                                "temperature", 1.0
                            ),
                            "ood_threshold": DEFAULT_OOD_CONFIGS.get(
                                ood_method, {}
                            ).get("ood_threshold", 0.5),
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
                            ood_method=variant["ood_method"],
                        )
                    else:
                        training_pipeline = TrainingPipeline(dfs, variant["base_model"])

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

            with open(
                f"{MODEL_RESULTS_PATH}/{self.new_model_id}/training_summary.json", "w"
            ) as f:
                json.dump(training_summary, f, indent=2)
            from trainingpipeline import convert_model_to_onnx, EnhancedModel

            # Convert best model to ONNX
            # check if it is sngp
            if best_variant["ood_method"] == "sngp":
                logger.info("CONVERTING SNGP MODEL TO ONNX")
                convert_model_to_onnx(
                    model_path=best_result["model_path"],
                    enhanced_model_class=EnhancedModel,
                )
            else:
                logger.info("CONVERTING STANDARD MODEL TO ONNX")
            convert_model_to_onnx(
                model_path=best_result["model_path"],
                enhanced_model_class=None,  # No custom class for standard models
            )

            # create model-id folder and copy model-repository directory contents there
            new_model_repo_path = f"{MODEL_RESULTS_PATH}/modelId-{self.new_model_id}"
            if not os.path.exists(new_model_repo_path):
                os.makedirs(new_model_repo_path)
            model_repository_path = "model-repository"
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
                src=f"{MODEL_RESULTS_PATH}/{self.new_model_id}/label_mappings.json",
                dst=f"{label_mappings_path}/label_mappings.json",
            )
            shutil.copy(
                src=f"{MODEL_RESULTS_PATH}/{self.new_model_id}/label_mappings.json",
                dst=f"{new_model_repo_path}/post-processing/1/label_mappings.json",
            )
            # add modelId-{model-id} to all folders inside the new_model_repo_path
            for root, dirs, files in os.walk(new_model_repo_path):
                for dir_name in dirs:
                    old_path = os.path.join(root, dir_name)
                    new_path = os.path.join(
                        root, f"modelId-{self.new_model_id}", dir_name
                    )
                    if not os.path.exists(new_path):
                        os.makedirs(new_path)
                    shutil.move(old_path, new_path)

            # move onnx model to the new model-id folder inside model-id/text_classifier/1/model.onnx
            onnx_model_path = (
                f"{new_model_repo_path}/modelId-{self.new_model_id}-text_classifier/1"
            )
            if not os.path.exists(onnx_model_path):
                os.makedirs(onnx_model_path)
            shutil.move(
                src=f"{best_result['model_path']}/model.onnx",
                dst=f"{onnx_model_path}/model.onnx",
            )

            model_config = {
                "model_name": best_variant["name"],
                "sequence_length": SEQUENCE_LENGTH,
                "ood_method": best_variant.get("ood_method", "standard"),
                "ood_threshold": best_variant.get("ood_threshold", 0.5),
                "energy_temp": best_variant.get("energy_temp", 1.0),
                "softmax_temp": best_variant.get("softmax_temp", 1.0),
                "uncertainty_strategy": best_variant.get(
                    "uncertainty_strategy", "none"
                ),
                "human_handoff_threshold": best_variant.get(
                    "human_handoff_threshold", 0.5
                ),
                "confidence_scaling": best_variant.get("confidence_scaling", "linear"),
                "base_model_type": best_variant.get("base_model_type", "bert"),
            }

            for root, dirs, files in os.walk(new_model_repo_path):
                for file_name in files:
                    if file_name == "config.pbtxt":
                        config_file_path = os.path.join(root, file_name)
                        with open(config_file_path, "r") as f:
                            config_content = f.read()

                        # Add parameters section if not present
                        if "parameters:" not in config_content:
                            config_content += "\nparameters:\n["

                        # Add each parameter
                        for key, value in model_config.items():
                            config_content += f'{key}: {{\n    value: "{value}"\n}}\n'
                        config_content += "]\n"

                        # Write back the updated content
                        with open(config_file_path, "w") as f:
                            f.write(config_content)

            # Create model archive
            model_zip_path = new_model_repo_path
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

            # Deploy the best model
            if self.current_deployment_platform == "undeployed":
                logger.info("MODEL DEPLOYMENT PLATFORM IS UNDEPLOYED")

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


# ----------------------TODO: Uncomment the CLI section when needed----------------------
def parse_args():
    import argparse

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
    old_model_id = args.model_id
    prev_deployment_env = "undeployed"  # Or fetch as needed
    update_type = "train"  # Or fetch as needed
    progress_session_id = args.job_id  # Or fetch as needed
    model_details = {"response": {"data": [{"connectedDgId": args.dataset_id}]}}
    current_deployment_platform = "undeployed"  # Or fetch as needed

    trainer = ModelTrainer(
        new_model_id=args.model_id,
        old_model_id=old_model_id,
        prev_deployment_env=prev_deployment_env,
        update_type=update_type,
        progress_session_id=progress_session_id,
        model_details=model_details,
        current_deployment_platform=current_deployment_platform,
    )
    trainer.train()
