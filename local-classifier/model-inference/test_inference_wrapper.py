from typing import List, Dict
from inference_pipeline import InferencePipeline
from loguru import logger
from constants import INFERENCE_LOGS_PATH
import json
import os

logger.add(sink=INFERENCE_LOGS_PATH)


class TestInferenceWrapper:
    def __init__(self) -> None:
        self.model_dictionary: Dict[int, InferencePipeline] = {}

    def load_model(self, model_id: int, model_path: str, best_performing_model: str, class_hierarchy: list) -> bool:
        try:
            new_model = InferencePipeline(hierarchy_file=class_hierarchy,model_name=best_performing_model,results_folder=model_path)
            self.model_dictionary[model_id] = new_model
            return True
        except Exception as e:
            logger.info(f"Failed to instantiate the TEST Inference Pipeline. Reason: {e}")
            raise Exception(f"Failed to instantiate the TEST Inference Pipeline. Reason: {e}")

    def inference(self, text: str, model_id: int):
        try:
            if not self.model_dictionary:
                self.load_models_from_metadata()
                          
            if model_id in self.model_dictionary:
                predicted_labels = None
                probabilities = None
                model = self.model_dictionary[model_id]
                predicted_labels, probabilities = model.predict_class(text_input=text, platform="test")
                return predicted_labels, probabilities
            else:
                raise Exception(f"Model with ID {model_id} not found")
        except Exception as e:
            raise Exception(f"Failed to call the inference. Reason: {e}")
    
    def stop_model(self, model_id: int):
        if model_id in self.model_dictionary:
            del self.model_dictionary[model_id]
        
        try:
            meta_data_save_location = '/shared/models/testing/test_inference_metadata.json'
                
   
            if os.path.exists(meta_data_save_location):
                with open(meta_data_save_location, 'r') as json_file:
                    metadata_array = json.load(json_file)
                    
                updated_metadata_array = [metadata for metadata in metadata_array if metadata["model_id"] != model_id]
        
                with open(meta_data_save_location, 'w') as json_file:
                    json.dump(updated_metadata_array, json_file, indent=4)
                
        except Exception as e:
                raise Exception(f"Failed to remove model metadata from JSON file. Reason: {e}")


    def load_models_from_metadata(self):
        try:
            meta_data_save_location = '/shared/models/testing/test_inference_metadata.json'
            
            if os.path.exists(meta_data_save_location):

                with open(meta_data_save_location, 'r') as json_file:
                    metadata_array = json.load(json_file)
            
                for metadata in metadata_array:
                    model_id = metadata["model_id"]
                    model_path = metadata["model_path"]
                    best_performing_model = metadata["best_model"]
                    class_hierarchy = metadata["class_hierarchy"]
                    
                    self.load_model(model_id, model_path, best_performing_model, class_hierarchy)
            else:
                raise Exception("Unable to find test models meta data file : No active test models exists")
        
        except Exception as e:
            raise Exception(f"Failed to load models from metadata. Reason: {e}")