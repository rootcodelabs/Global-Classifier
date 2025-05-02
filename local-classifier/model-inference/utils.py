import zipfile
import os
import shutil
from typing import Optional

def unzip_file(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)


def clear_folder_contents(folder_path: str):
    try:
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  
    except Exception as e:
        raise Exception(f"Failed to delete contents in {folder_path}. Reason: {e}")
    
def get_s3_payload(destination_file_path:str, destination_storage_type:str, source_file_path:str, source_storage_type:str):
    S3_FERRY_PAYLOAD = {
            "destinationFilePath": destination_file_path,
            "destinationStorageType": destination_storage_type,
            "sourceFilePath": source_file_path,
            "sourceStorageType": source_storage_type
        }
    return S3_FERRY_PAYLOAD

def get_inference_create_payload(inference_input_id:str, inference_text:str, predicted_labels:list, average_predicted_classes_probability:int, platform:str, primary_folder_id: Optional[str] = None, mail_id : Optional[str] = None ):   
    INFERENCE_CREATE_PAYLOAD = {       
        "inputId": inference_input_id,
        "inferenceText": inference_text,
        "predictedLabels": predicted_labels,
        "averagePredictedClassesProbability": average_predicted_classes_probability,
        "platform": platform,
        "primaryFolderId": primary_folder_id,
        "mailId":mail_id
    }
    
    return INFERENCE_CREATE_PAYLOAD


def get_inference_update_payload(inference_id:str, is_corrected:bool, corrected_labels:list, average_predicted_classes_probability:int, platform:str, primary_folder_id: Optional[str] = None ):   
    INFERENCE_UPDATE_PAYLOAD = {       
        "inferenceId": inference_id,
        "isCorrected": is_corrected,
        "correctedLabels": corrected_labels,
        "averageCorrectedClassesProbability": average_predicted_classes_probability,
        "primaryFolderId": primary_folder_id,
        "platform": platform 
    }
    
    return INFERENCE_UPDATE_PAYLOAD
   

def calculate_average_predicted_class_probability(class_probabilities):
    
    total_probability = sum(class_probabilities)
    average_probability = total_probability / len(class_probabilities)
    
    return average_probability     

def get_test_inference_success_payload(predicted_classes:list, average_confidence:float, predicted_probabilities:list ):   
    
    TEST_INFERENCE_SUCCESS_PAYLOAD = {
    "predictedClasses":predicted_classes,
    "averageConfidence":average_confidence,
    "predictedProbabilities": predicted_probabilities
    }

    return TEST_INFERENCE_SUCCESS_PAYLOAD  

def delete_folder(folder_path: str):
    try:
        if os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
        else:
            raise FileNotFoundError(f"The path {folder_path} is not a directory.")
    except Exception as e:
        raise Exception(f"Failed to delete the folder {folder_path}. Reason: {e}")