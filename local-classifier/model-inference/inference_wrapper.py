from typing import List
from inference_pipeline import InferencePipeline
from loguru import logger
from constants import INFERENCE_LOGS_PATH
import json
import os

logger.add(sink=INFERENCE_LOGS_PATH)


class InferenceWrapper:
    
    def __init__(self) -> None:
        self.active_jira_model = None
        self.active_outlook_model = None
        self.active_jira_model_id = None
        self.active_outlook_model_id = None

    def load_model(self, model_path:str, best_performing_model:str, deployment_platform:str, class_hierarchy:list, model_id:int):
        try:
            
            logger.info("LOGGING INSIDE model_swapping")
            logger.info(f"MODEL PATH - {model_path} ")
            logger.info(f"BEST PERFORMING MODEL - {best_performing_model}")
            
            logger.info(f"DEPLOYMENT PLATFORM - {deployment_platform}")
            logger.info(f"MODEL ID - {model_id}")

            logger.info(f"CLASS HIERARCHY - {class_hierarchy}")

            if(deployment_platform == "jira"):
                temp_jira_model = InferencePipeline(hierarchy_file=class_hierarchy,model_name=best_performing_model,results_folder=model_path)
                self.active_jira_model = temp_jira_model
                self.active_jira_model_id = model_id
                return True
            
            elif(deployment_platform == "outlook"):
                

                temp_outlook_model = InferencePipeline(hierarchy_file=class_hierarchy,model_name=best_performing_model,results_folder=model_path)
                self.active_outlook_model = temp_outlook_model
                self.active_outlook_model_id = model_id

                logger.info(f"self.active_outlook_model_id VALUE IN model_swapping: {self.active_outlook_model}")

                return True
                
        except Exception as e:
            raise Exception(f"Failed to instantiate the Inference Pipeline. Reason: {e}")
            return False

    def inference(self, text:str, deployment_platform:str):
        try:

            logger.info("ENTERING INFERENCE WRAPPER .inference() FUNCTION")
            predicted_labels = None
            probabilities = None

            logger.info(f"TEXT {text}")
            logger.info(f"DEPLOYMENT PLATFORM - {deployment_platform}")

            if(deployment_platform == "jira" and self.active_jira_model):

                logger.info("ENTERING JIRA INFERENCE")
                predicted_labels, probabilities = self.active_jira_model.predict_class(text, deployment_platform)
                
                logger.info(f"PREDICTED LABELS INSIDE .inference() FUNCTION - {predicted_labels}")
                logger.info(f"PROBABILITIES INSIDE .inference() FUNCTION - {probabilities}")


            if(deployment_platform == "outlook" and self.active_outlook_model):
                logger.info("ENTERING OUTLOOK INFERENCE")
                predicted_labels, probabilities = self.active_outlook_model.predict_class(text, deployment_platform)


                logger.info(f"PREDICTED LABELS INSIDE .inference() FUNCTION - {predicted_labels}")
                logger.info(f"PROBABILITIES INSIDE .inference() FUNCTION - {probabilities}")



            return predicted_labels, probabilities
        
        except Exception as e:

            logger.info(f"INFERENCE CRASHED - ERROR - {e}")
            raise Exception(f"Failed to call the inference. Reason: {e}") 
    
    def stop_model(self,deployment_platform:str):
        if(deployment_platform == "jira"):
            self.active_jira_model = None
            self.active_jira_model_id = None
        if(deployment_platform == "outlook"):
            self.active_outlook_model = None
            self.active_outlook_model_id = None
            
            
    def get_outlook_model_id(self):
        logger.info("Get Outlook Model Id Calling")

        logger.info(f"Outlook Model Exists : {'Yes' if self.active_outlook_model else 'No'}")
        outlook_model_id = None

        if not self.active_outlook_model :
            file_location = "/shared/models/outlook/outlook_inference_metadata.json"
            logger.info("RETRIEVING DATA FROM JSON FILE IN get_outlook_model_id function ")
            if os.path.exists(file_location):
                with open(file_location, 'r') as json_file:
                    data = json.load(json_file)
                    
                model_path = data.get("model_path")
                best_model = data.get("best_model")
                deployment_platform = data.get("deployment_platform")
                class_hierarchy = data.get("class_hierarchy")
                model_id = data.get("model_id")
                
                self.load_model(model_path=model_path, best_performing_model=best_model, deployment_platform=deployment_platform,class_hierarchy=class_hierarchy, model_id=model_id)
                
            else:
               return None            

        if(self.active_outlook_model):
            outlook_model_id= self.active_outlook_model_id
            logger.info(f"Outlook Model Id : {outlook_model_id}")
            
        return outlook_model_id
    

    def get_jira_model_id(self):
        logger.info("Get Jira Model Id Calling")

        logger.info(f"Jira Model Exists : {'Yes' if self.active_jira_model else 'No'}")
        jira_model_id = None

        if not self.active_jira_model :
            file_location = "/shared/models/jira/jira_inference_metadata.json"
            logger.info("RETRIEVING DATA FROM JSON FILE IN get_jira_model_id function ")
            if os.path.exists(file_location):
                with open(file_location, 'r') as json_file:
                    data = json.load(json_file)
                    
                model_path = data.get("model_path")
                best_model = data.get("best_model")
                deployment_platform = data.get("deployment_platform")
                class_hierarchy = data.get("class_hierarchy")
                model_id = data.get("model_id")
                
                self.load_model(model_path=model_path, best_performing_model=best_model, deployment_platform=deployment_platform,class_hierarchy=class_hierarchy, model_id=model_id)
                
            else:
               return None

        if(self.active_jira_model):
            jira_model_id= self.active_jira_model_id
            logger.info(f"Jira Model Id : {jira_model_id}")

        return jira_model_id

    
    def get_corrected_probabilities(self, text, corrected_labels , deployment_platform):
        try:
            
            logger.info(f"TEXT IN get_corrected_probabilities - {text}")
            logger.info(f"CORRECTED LABELS IN get_corrected_probabilities - {corrected_labels}")
            logger.info(f"DEPLOYMENT PLATFORM IN get_corrected_probabilities - {deployment_platform}")

            corrected_probabilities = None
            if(deployment_platform == "jira" and self.active_jira_model):
                corrected_probabilities = self.active_jira_model.user_corrected_probabilities(text_input=text, user_classes=corrected_labels)

            if(deployment_platform == "outlook" and self.active_outlook_model):
                corrected_probabilities = self.active_outlook_model.user_corrected_probabilities(text_input=text, user_classes=corrected_labels)


            logger.info(f"CORRECTED PROBABILITIES - {corrected_probabilities}")
            return corrected_probabilities
        
        except Exception as e:
            logger.info(f"ERROR IN get_corrected_probabilities - {corrected_probabilities}")
            raise RuntimeError(f"Failed to retrieve corrected probabilities from the inference pipeline. Reason: {e}")     
