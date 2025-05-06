from fastapi import FastAPI,HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from s3_ferry import S3Ferry
from utils import unzip_file, clear_folder_contents, calculate_average_predicted_class_probability, get_inference_create_payload, get_inference_update_payload, get_test_inference_success_payload, delete_folder
from constants import S3_DOWNLOAD_FAILED, INFERENCE_LOGS_PATH, JiraInferenceRequest, \
    OutlookInferenceRequest, UpdateRequest, OUTLOOK_MODELS_FOLDER_PATH, JIRA_MODELS_FOLDER_PATH,\
    SHARED_MODELS_ROOT_FOLDER, TestInferenceRequest, DeleteTestRequest
from inference_wrapper import InferenceWrapper
from test_inference_wrapper import TestInferenceWrapper
from model_inference import ModelInference
from loguru import logger
import json

logger.add(sink=INFERENCE_LOGS_PATH)


logger.info("ENTERING MODEL INFERENCE API")

app = FastAPI()
model_inference = ModelInference()

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_credentials = True,
    allow_methods = ["GET", "POST"],
    allow_headers = ["*"],
)

model_inference_wrapper = InferenceWrapper()
test_inference_wrapper = TestInferenceWrapper()

S3_FERRY_URL = os.getenv("S3_FERRY_URL")
s3_ferry = S3Ferry(S3_FERRY_URL)
RUUTER_PRIVATE_URL = os.getenv("RUUTER_PRIVATE_URL")
JIRA_MODEL_DOWNLOAD_DIRECTORY = os.getenv("JIRA_MODEL_DOWNLOAD_DIRECTORY", "/shared/models/jira")
OUTLOOK_MODEL_DOWNLOAD_DIRECTORY = os.getenv("OUTLOOK_MODEL_DOWNLOAD_DIRECTORY", "/shared/models/outlook")
TEST_MODEL_DOWNLOAD_ROOT_DIRECTORY = os.getenv("TEST_MODEL_DOWNLOAD_DIRECTORY", "/shared/models/testing")

if not os.path.exists(JIRA_MODEL_DOWNLOAD_DIRECTORY):
    os.makedirs(JIRA_MODEL_DOWNLOAD_DIRECTORY)   
    
if not os.path.exists(OUTLOOK_MODEL_DOWNLOAD_DIRECTORY):
    os.makedirs(OUTLOOK_MODEL_DOWNLOAD_DIRECTORY) 

if not os.path.exists(TEST_MODEL_DOWNLOAD_ROOT_DIRECTORY):
    os.makedirs(TEST_MODEL_DOWNLOAD_ROOT_DIRECTORY)
    logger.info("GIVING PERMISSIONS")
    os.chmod(TEST_MODEL_DOWNLOAD_ROOT_DIRECTORY,mode=0o777)


@app.post("/classifier/datamodel/deployment/outlook/update")
async def download_outlook_model(request: Request, model_data:UpdateRequest):
    
    save_location = f"/models/{model_data.modelId}/{model_data.modelId}.zip"    
    logger.info(f"MODEL DATA PAYLOAD - {model_data}")
    
    try:  

        ## Authenticating User Cookie
        cookie = request.cookies.get("customJwtCookie")
        await model_inference.authenticate_user(f'customJwtCookie={cookie}')


        local_file_name = f"{model_data.modelId}.zip"
        local_file_path = f"/models/outlook/{local_file_name}"
        
        model_progress_session_id = model_data.progressSessionId

        ## Get class hierarchy and validate it
        is_valid, class_hierarchy = model_inference.get_outlook_class_hierarchy_and_validate(model_data.modelId)

        logger.info(f"IS VALID VALUE : {is_valid}")
        logger.info(f"CLASS HIERARCHY VALUE : {class_hierarchy}")
        
        if(is_valid and class_hierarchy):

            # 1. Clear the current content inside the folder
            outlook_models_folder_path = OUTLOOK_MODELS_FOLDER_PATH
            clear_folder_contents(outlook_models_folder_path)  
        
            # 2. Download the new Model
            response = s3_ferry.transfer_file(local_file_path, "FS", save_location, "S3")
            if response.status_code != 201:
                raise HTTPException(status_code = 500, detail = S3_DOWNLOAD_FAILED)
        
            zip_file_path = f"{outlook_models_folder_path}/{local_file_name}"
            extract_file_path = outlook_models_folder_path
         
            # 3. Unzip  Model Content 
            unzip_file(zip_path=zip_file_path, extract_to=extract_file_path)
            shared_models_root_folder = SHARED_MODELS_ROOT_FOLDER
        
            os.remove(zip_file_path)
            # 3. Replace the content in other folder if it a replacement 
            if(model_data.replaceDeployment and model_data.replaceDeploymentPlatform!="undeployed"  and model_data.updateType!="retrain"):
                
                logger.info("INSIDE REPLACE DEPLOYMENT")
                # Special Scenario - Handle swapping from Testing
                if(model_data.replaceDeploymentPlatform =="testing"):
                    
                    # Clear the testing model folder
                    logger.info("DELETING OLD MODEL FROM TESTING")
                    folder_path = f"{TEST_MODEL_DOWNLOAD_ROOT_DIRECTORY}/{model_data.oldModelId}"
                    delete_folder(folder_path)
                    
                    # Stop the testing model
                    test_inference_wrapper.stop_model(model_id=model_data.oldModelId)
                
                else:
                
                    replace_deployment_folder_path = f"{shared_models_root_folder}/{model_data.replaceDeploymentPlatform}"
                    logger.info(f"REPLACE DEPLOYMENT FOLDER PATH - {replace_deployment_folder_path}")
                    clear_folder_contents(replace_deployment_folder_path)
                    model_inference_wrapper.stop_model(deployment_platform=model_data.replaceDeploymentPlatform)
        
            # 4. Instantiate Inference Model
            model_path = "/shared/models/outlook"
            best_model = model_data.bestBaseModel

            data = {
                "model_path" : model_path,
                "best_model":best_model,
                "deployment_platform":"outlook",
                "class_hierarchy": class_hierarchy,
                "model_id": model_data.modelId
            }

            meta_data_save_location = '/shared/models/outlook/outlook_inference_metadata.json'
            with open(meta_data_save_location, 'w') as json_file:
                json.dump(data, json_file, indent=4)

            
            model_initiate = model_inference_wrapper.load_model(model_path, best_model, deployment_platform="outlook", class_hierarchy=class_hierarchy, model_id=model_data.modelId)
            
            logger.info(f"MODEL INITIATE - {model_initiate}")
            


            if(model_initiate):
                

                model_inference.update_model_training_progress_session(session_id=model_progress_session_id,
                                                                       model_id=model_data.modelId,
                                                                       cookie=cookie)
                
                logger.info(f"OUTLOOK MODEL UPDATE SUCCESSFUL FOR MODEL ID - {model_data.modelId}")
                return JSONResponse(status_code=200, content={"replacementStatus": 200})
            else:
                raise HTTPException(status_code = 500, detail = "Failed to initiate inference object")
        
        else:
            raise HTTPException(status_code = 500, detail = "Error in obtaining the class hierarchy or class hierarchy is invalid")
        
    except Exception as e:
        raise HTTPException(status_code = 500, detail=str(e))
    
    

@app.post("/classifier/datamodel/deployment/jira/update")
async def download_jira_model(request: Request, model_data:UpdateRequest):
    
    save_location = f"/models/{model_data.modelId}/{model_data.modelId}.zip"
    logger.info(f"JIRA MODEL DATA PAYLOAD - {model_data}")
    
    try:

        ## Authenticating User Cookie
        cookie = request.cookies.get("customJwtCookie")
        await model_inference.authenticate_user(f'customJwtCookie={cookie}')


        local_file_name = f"{model_data.modelId}.zip"
        local_file_path = f"/models/jira/{local_file_name}"

        model_progress_session_id = model_data.progressSessionId
        
        logger.info(f"MODEL DATA - {model_data}")
        # 1. Clear the current content inside the folder
        jira_models_folder_path = JIRA_MODELS_FOLDER_PATH
        clear_folder_contents(jira_models_folder_path)
        
        # 2. Download the new Model
        response = s3_ferry.transfer_file(local_file_path, "FS", save_location, "S3")
        if response.status_code != 201:
            raise HTTPException(status_code = 500, detail = S3_DOWNLOAD_FAILED)
        
        
        zip_file_path = f"{jira_models_folder_path}/{local_file_name}"
        extract_file_path = jira_models_folder_path
         
        # 3. Unzip  Model Content 
        unzip_file(zip_path=zip_file_path, extract_to=extract_file_path)
        
        os.remove(zip_file_path)
        
        #3. Replace the content in other folder if it a replacement --> Call the delete endpoint
        logger.info("JUST ABOUT TO ENTER   - if(model_data.replaceDeployment):")

        shared_models_root_folder = SHARED_MODELS_ROOT_FOLDER

        if(model_data.replaceDeployment and model_data.replaceDeploymentPlatform!="undeployed"  and model_data.updateType!="retrain"):
            
            if(model_data.replaceDeploymentPlatform =="testing"):    
                    # Clear the testing model folder
                    logger.info("DELETING OLD MODEL FROM TESTING")
                    folder_path = f"{TEST_MODEL_DOWNLOAD_ROOT_DIRECTORY}/{model_data.oldModelId}"
                    delete_folder(folder_path)
                    
                    # Stop the testing model
                    test_inference_wrapper.stop_model(model_id=model_data.oldModelId)
                
            else:  
                    replace_deployment_folder_path = f"{shared_models_root_folder}/{model_data.replaceDeploymentPlatform}"
                    logger.info(f"REPLACE DEPLOYMENT FOLDER PATH - {replace_deployment_folder_path}")
                    clear_folder_contents(replace_deployment_folder_path)
                    model_inference_wrapper.stop_model(deployment_platform=model_data.replaceDeploymentPlatform)

            logger.info("INSIDE REPLACE DEPLOYMENT")
            replace_deployment_folder_path = f"{shared_models_root_folder}/{model_data.replaceDeploymentPlatform}"

            logger.info(f"REPLACE DEPLOYMENT FOLDER PATH - {replace_deployment_folder_path}")
            clear_folder_contents(replace_deployment_folder_path)
        
            model_inference_wrapper.stop_model(deployment_platform=model_data.replaceDeploymentPlatform)
        
        # 4. Instantiate Inference Model

        logger.info("JUST ABOUT TO ENTER get_class_hierarchy_by_model_id")

        class_hierarchy = model_inference.get_class_hierarchy_by_dg_id(cookies=cookie, dg_id=model_data.dgId)

        logger.info(f"JIRA UPDATE CLASS HIERARCHY - {class_hierarchy}")

        if(class_hierarchy):
        
            model_path = JIRA_MODELS_FOLDER_PATH
            best_model = model_data.bestBaseModel

            data = {
                "model_path" : model_path,
                "best_model":best_model,
                "deployment_platform":"jira",
                "class_hierarchy": class_hierarchy,
                "model_id": model_data.modelId
            }


            meta_data_save_location = f"{model_path}/jira_inference_metadata.json"
            with open(meta_data_save_location, 'w') as json_file:
                json.dump(data, json_file, indent=4)

            model_initiate = model_inference_wrapper.load_model(model_path, best_model, deployment_platform="jira", class_hierarchy=class_hierarchy, model_id=model_data.modelId)
            logger.info(f"JIRA MODEL INITITATE - {model_initiate}")

            if(model_initiate):
                logger.info(f"MODEL INITIATE - {model_initiate}")


                model_inference.update_model_training_progress_session(session_id=model_progress_session_id,
                                                                       model_id=model_data.modelId,
                                                                       cookie=cookie)
                
                logger.info(f"JIRA MODEL UPDATE SUCCESSFUL FOR MODEL ID - {model_data.modelId}")

                logger.info("JIRA DEPLOYMENT SUCCESSFUL")
                return JSONResponse(status_code=200, content={"replacementStatus": 200})
            else:
                raise HTTPException(status_code = 500, detail = "Failed to initiate inference object")
        else:
            raise HTTPException(status_code = 500, detail = "Error in obtaining the class hierarchy")
        
    except Exception as e:
        raise HTTPException(status_code = 500, detail=str(e))
    
@app.post("/classifier/datamodel/deployment/testing/update")
async def download_test_model(request: Request, model_data:UpdateRequest):
    
    save_location = f"/models/{model_data.modelId}/{model_data.modelId}.zip"
    logger.info(f"TEST MODEL DATA PAYLOAD - {model_data}")
    
    try:

        ## Authenticating User Cookie
        cookie = request.cookies.get("customJwtCookie")
        await model_inference.authenticate_user(f'customJwtCookie={cookie}')


        local_file_name = f"{model_data.modelId}.zip"

        # This path is actually under /shared since the root directory of s3 ferry is anyways /shared we don't use it when referring the local filepath 
        local_file_path = f"/models/testing/{model_data.modelId}/{local_file_name}"

        model_progress_session_id = model_data.progressSessionId
        
        logger.info(f"MODEL DATA - {model_data}")
        # 1. Clear the current content inside the folder
        test_models_folder_path = f"/shared/models/testing/{model_data.modelId}"

        if not os.path.exists(test_models_folder_path):
            logger.info("CREATING FOLDER INSIDE MODEL EXIST")
            os.makedirs(test_models_folder_path)
            logger.info("GIVING PERMISSIONS")
            os.chmod(test_models_folder_path,mode=0o777)

        if os.path.exists(test_models_folder_path):
            logger.info("CLEARING TEST MODEL CONTAINERS")
            clear_folder_contents(test_models_folder_path)
        
        # 2. Download the new Model
        response = s3_ferry.transfer_file(destination_file_path=local_file_path, 
                                          destination_storage_type="FS", 
                                          source_file_path=save_location, 
                                          source_storage_type="S3")
        
        logger.info("ZIP FILE DOWNLOADED")
        
        if response.status_code!=201:
            raise HTTPException(status_code = 500, detail = S3_DOWNLOAD_FAILED)
        

        
        
        zip_file_path = f"{test_models_folder_path}/{local_file_name}"

        extract_file_path = test_models_folder_path

        logger.info(f"TESTING LOG FILE PATH - {zip_file_path}")
        logger.info(f"EXTRACT FILE PATH - {extract_file_path}")

        # 3. Unzip  Model Content 
        unzip_file(zip_path=zip_file_path, extract_to=extract_file_path)
        
        os.remove(zip_file_path)
        
        #3. Replace the content in other folder if it a replacement --> Call the delete endpoint
        logger.info("JUST ABOUT TO ENTER   - if(model_data.replaceDeployment):")

        shared_models_root_folder = SHARED_MODELS_ROOT_FOLDER

        if(model_data.replaceDeployment and model_data.replaceDeploymentPlatform!="undeployed"  and model_data.updateType!="retrain"):
            
            logger.info("INSIDE REPLACE DEPLOYMENT")
            replace_deployment_folder_path = f"{shared_models_root_folder}/{model_data.replaceDeploymentPlatform}"

            logger.info(f"REPLACE DEPLOYMENT FOLDER PATH - {replace_deployment_folder_path}")
            clear_folder_contents(replace_deployment_folder_path)
        
            model_inference_wrapper.stop_model(deployment_platform=model_data.replaceDeploymentPlatform)
        
        # 4. Instantiate Inference Model

        logger.info("JUST ABOUT TO ENTER get_class_hierarchy_by_model_id")

        class_hierarchy = model_inference.get_class_hierarchy_by_dg_id(cookies=cookie, dg_id=model_data.dgId)

        logger.info(f"TEST UPDATE CLASS HIERARCHY - {class_hierarchy}")

        if(class_hierarchy):
        
            model_path = test_models_folder_path
            best_model = model_data.bestBaseModel

            new_metadata = {
                    "model_path": model_path,
                    "best_model": best_model,
                    "deployment_platform": "testing",
                    "class_hierarchy": class_hierarchy,
                    "model_id": model_data.modelId
                }
                
            meta_data_save_location = '/shared/models/testing/test_inference_metadata.json'
            
       
            if os.path.exists(meta_data_save_location):
                with open(meta_data_save_location, 'r') as json_file:
                    existing_data = json.load(json_file)
            else:
                existing_data = []
                
            existing_data.append(new_metadata)
                
            with open(meta_data_save_location, 'w') as json_file:
                json.dump(existing_data, json_file, indent=4)

            model_initiate = test_inference_wrapper.load_model(model_path=model_path, 
                                                        best_performing_model=best_model, 
                                                       class_hierarchy=class_hierarchy, 
                                                           model_id=model_data.modelId)
            
            logger.info(f"TEST MODEL INITITATE - {model_initiate}")

            if(model_initiate):
                logger.info(f"TEST MODEL INITIATE - {model_initiate}")


                model_inference.update_model_training_progress_session(session_id=model_progress_session_id,
                                                                       model_id=model_data.modelId,
                                                                       cookie=cookie)
                
                logger.info(f"TEST MODEL UPDATE SUCCESSFUL FOR MODEL ID - {model_data.modelId}")

                logger.info("TEST DEPLOYMENT SUCCESSFUL")
                return JSONResponse(status_code=200, content={"replacementStatus": 200})
            else:
                raise HTTPException(status_code = 500, detail = "Failed to initiate inference object")
        else:
            raise HTTPException(status_code = 500, detail = "Error in obtaining the class hierarchy")
        
    except Exception as e:
        raise HTTPException(status_code = 500, detail=str(e))
    
@app.post("/classifier/datamodel/deployment/jira/delete")
async def delete_folder_content(request:Request):
    try:
        jira_models_folder_path = JIRA_MODELS_FOLDER_PATH
        clear_folder_contents(jira_models_folder_path)  
        
        # Stop the model
        model_inference_wrapper.stop_model(deployment_platform="jira")
        
        delete_success = {"message" : "Model Deleted Successfully!"}
        return JSONResponse(status_code = 200, content = delete_success)                        
    
    except Exception as e:
        raise HTTPException(status_code = 500, detail=str(e))
 
    
@app.post("/classifier/datamodel/deployment/outlook/delete")
async def delete_folder_content(request:Request):
    try:
        outlook_models_folder_path = OUTLOOK_MODELS_FOLDER_PATH
        clear_folder_contents(outlook_models_folder_path)  
        
        # Stop the model
        model_inference_wrapper.stop_model(deployment_platform="outlook")
        
        delete_success = {"message" : "Model Deleted Successfully!"}
        return JSONResponse(status_code = 200, content = delete_success)                        
    
    except Exception as e:
        raise HTTPException(status_code = 500, detail=str(e)) 

   
@app.post("/classifier/deployment/outlook/inference")
async def outlook_inference(request:Request, inference_data:OutlookInferenceRequest):
    try:
        logger.info("Inference Endpoint Calling") 
        logger.info(f"Inference Data : {inference_data}")

        model_id = model_inference_wrapper.get_outlook_model_id()
        logger.info(f"Model Id : {model_id}")
        if(model_id):
            # If there is a active model
        
            # 1 . Check whether the if the Inference Exists
            is_exist, inference_id = model_inference.check_inference_data_exists(input_id=inference_data.inputId)

            logger.info(f"Inference Exists : {is_exist}")
            logger.info(f"Inference ID - {inference_id}")
            
            if(is_exist): # Update Inference Scenario
                #  Create Corrected Folder Hierarchy using the final folder id
                corrected_folder_hierarchy = model_inference.build_corrected_folder_hierarchy(final_folder_id=inference_data.finalFolderId, 
                                                                                             model_id=model_id)
                
                logger.info(f"CORRECTED FOLDER HIERARCHY - {corrected_folder_hierarchy}")
                # Call user_corrected_probablities
                corrected_probs = model_inference_wrapper.get_corrected_probabilities(text=inference_data.inputText, 
                                                                            corrected_labels=corrected_folder_hierarchy, 
                                                                            deployment_platform="outlook")
                
                logger.info(f"CORRECTED PROBABILITIES IN MODEL INFERENCE API - {corrected_probs}")

                if(corrected_probs):
                    # Calculate Average Predicted Class Probability
                    average_probability = calculate_average_predicted_class_probability(corrected_probs)

                    logger.info(f"AVERAGE PROBABILITY - {average_probability}")
                    # Build request payload for inference/update endpoint
                    inference_update_payload = get_inference_update_payload(inference_id=inference_id,is_corrected=True, 
                                                                            corrected_labels=corrected_folder_hierarchy,
                                                                            average_predicted_classes_probability=average_probability, 
                                                                            platform="OUTLOOK", 
                                                                            primary_folder_id=inference_data.finalFolderId)

                    logger.info(f"INFERENCE PAYLOAD - {inference_update_payload}")
                    # Call inference/update endpoint
                    is_success = model_inference.update_inference(payload=inference_update_payload)
                    
                    logger.info(f"IS SUCCESS - {is_success}")

                    if(is_success):
                        return JSONResponse(status_code=200, content={"operationSuccessful": True})
                    else:
                        raise HTTPException(status_code = 500, detail="Failed to call the update inference")  
                
                else:
                    raise HTTPException(status_code = 500, detail="Failed to retrieve the corrected class probabilities from the inference pipeline")
                
                    
            else: # Create Inference Scenario
                # Call Inference
                logger.info("CREATE INFERENCE SCENARIO OUTLOOK")
                predicted_hierarchy, probabilities  = model_inference_wrapper.inference(inference_data.inputText, deployment_platform="outlook")

                logger.info(f"PREDICTED HIERARCHIES AND PROBABILITIES {predicted_hierarchy}")
                logger.info(f"PROBABILITIES {probabilities}")
                
                if (probabilities and predicted_hierarchy):
                    
                    # Calculate Average Predicted Class Probability
                    average_probability = calculate_average_predicted_class_probability(probabilities)
                    logger.info(f"average probability - {average_probability}")

                    # Get the final folder id of the predicted folder hierarchy
                    final_folder_id = model_inference.find_final_folder_id(flattened_folder_hierarchy=predicted_hierarchy, model_id=model_id)
                    logger.info(f"final folder id - {final_folder_id}")

                    
                    # Build request payload for inference/create endpoint
                    inference_create_payload = get_inference_create_payload(inference_input_id=inference_data.inputId,inference_text=inference_data.inputText,predicted_labels=predicted_hierarchy, average_predicted_classes_probability=average_probability, platform="OUTLOOK", primary_folder_id=final_folder_id, mail_id=inference_data.mailId)
                    logger.info(f"INFERENCE CREATE PAYLOAD - {inference_create_payload}")
                    # Call inference/create endpoint
                    is_success = model_inference.create_inference(payload=inference_create_payload)
                    logger.info(f"IS SUCCESS - {is_success}")
                    
                    if(is_success):

                        logger.info("\n\n OPERATION SUCCESSFUL AND EMAIL SUCCESSFULLY UPDATED \n\n")
                        return JSONResponse(status_code=200, content={"operationSuccessful": True})
                    else:
                        raise HTTPException(status_code = 500, detail="Failed to call the create inference")  
                
                else:
                    
                    logger.info("probabilities and predicted_hierarchy are empty")
                    logger.info(f"probabilities - {probabilities}")
                    logger.info(f"predicted_hierarchy - {predicted_hierarchy}")

                    raise HTTPException(status_code = 500, detail="Failed to call inference")
        
        else:
            raise HTTPException(status_code = 500, detail="No active model currently exists for the Outlook inference")
            
                
        
                               
    except Exception as e:
        raise HTTPException(status_code = 500, detail=str(e))
    

@app.post("/classifier/deployment/jira/inference")
async def jira_inference(request:Request, inferenceData:JiraInferenceRequest):
    try:

        logger.info(f"INFERENCE DATA IN JIRA INFERENCE - {inferenceData}")

        model_id = model_inference_wrapper.get_jira_model_id()

        if(model_id):        
            # 1 . Check whether the if the Inference Exists
            is_exist, inference_id = model_inference.check_inference_data_exists(input_id=inferenceData.inputId)
            
            logger.info(f"LOGGING IS EXIST IN JIRA IN JIRA UPDATE INFERENCE - {is_exist}")
            if(is_exist): # Update Inference Scenario
                # Call user_corrected_probablities
                corrected_probs = model_inference_wrapper.get_corrected_probabilities(text=inferenceData.inputText, corrected_labels=inferenceData.finalLabels, deployment_platform="jira")
                
                logger.info(f"CORRECT PROBS IN JIRA UPDATE INFERENCE - {corrected_probs}")
                if(corrected_probs):
                    # Calculate Average Predicted Class Probability
                    average_probability = calculate_average_predicted_class_probability(corrected_probs)
                
                    # Build request payload for inference/update endpoint
                    inference_update_payload = get_inference_update_payload(inference_id=inference_id,is_corrected=True, corrected_labels=inferenceData.finalLabels, average_predicted_classes_probability=average_probability, platform="JIRA", primary_folder_id=None)

                    logger.info(f"INFERENCE UPDATE PAYLOAD - {inference_update_payload}")
                    # Call inference/update endpoint
                    is_success = model_inference.update_inference(payload=inference_update_payload)

                    logger.info(f"IS SUCCESS IN JIRA UPDATE INFERENCE - {is_success} ")
                    

                    if(is_success):

                        logger.info("JIRA UPDATE INFERENCE SUCCESSFUL")
                        return JSONResponse(status_code=200, content={"operationSuccessful": True})
                    else:
                        raise HTTPException(status_code = 500, detail="Failed to call the update inference")  
                
                else:
                    raise HTTPException(status_code = 500, detail="Failed to retrieve the corrected class probabilities from the inference pipeline")
                
                    
            else: # Create Inference Scenario
                # Call Inference
                predicted_hierarchy, probabilities  = model_inference_wrapper.inference(inferenceData.inputText, deployment_platform="jira")
                
                logger.info(f"JIRA PREDICTED HIERARCHY - {predicted_hierarchy}")
                logger.info(f"JIRA PROBABILITIES - {probabilities}")

                if (probabilities and predicted_hierarchy):
                    
                    # Calculate Average Predicted Class Probability
                    average_probability = calculate_average_predicted_class_probability(probabilities)
                    
                    # Build request payload for inference/create endpoint
                    inference_create_payload = get_inference_create_payload(inference_input_id=inferenceData.inputId,inference_text=inferenceData.inputText,predicted_labels=predicted_hierarchy, average_predicted_classes_probability=average_probability, platform="JIRA", primary_folder_id=None, mail_id=None)
                    
                    # Call inference/create endpoint
                    is_success = model_inference.create_inference(payload=inference_create_payload)
                    
                    logger.info(f"JIRA inference is_success - {is_success}")
                    if(is_success):
                        logger.info("JIRA CREATE INFERENCE SUCCESSFUL")
                        return JSONResponse(status_code=200, content={"operationSuccessful": True})
                    else:
                        raise HTTPException(status_code = 500, detail="Failed to call the create inference")  
                
                else:
                    raise HTTPException(status_code = 500, detail="Failed to call inference")   
        
        else:
             raise HTTPException(status_code = 500, detail="No active model currently exists for the Jira inference")
              
    except Exception as e:
        raise HTTPException(status_code = 500, detail=str(e))



@app.post("/classifier/deployment/testing/inference")
async def test_inference(request:Request, inference_data:TestInferenceRequest):
    try:
                
        # Call Inference

        logger.info("ENTERING INTO TESTING INFERENCE")
        cookie = request.cookies.get("customJwtCookie")

        logger.info(f"COOKIE - {cookie}")
        await model_inference.authenticate_user(f'customJwtCookie={cookie}')
        
        
        predicted_hierarchy, probabilities  = test_inference_wrapper.inference(model_id=inference_data.modelId, text=inference_data.text)
        logger.info(f"PREDICTED HIERARCHY - {predicted_hierarchy}")
        logger.info(f"PROBABILITIEs - {probabilities}")


        if (probabilities and predicted_hierarchy):
                
            # Calculate Average Predicted Class Probability
            average_probability = calculate_average_predicted_class_probability(probabilities)
            
            logger.info(f"AVERAGE PROBABILITY - {average_probability}")
            # Build request payload for inference/create endpoint
            inference_success_payload = get_test_inference_success_payload(predicted_classes=predicted_hierarchy, average_confidence=average_probability, predicted_probabilities=probabilities)                

            logger.info(f"INFERENCE PAYLOAD - {inference_success_payload}")
            return JSONResponse(status_code=200, content=inference_success_payload)

        else:

            logger.info("PREDICTION FAILED IN TESTING")
            raise HTTPException(status_code = 500, detail="Failed to call inference")     
                               
    
    except Exception as e:

        logger.info(f"crash happened in model inference testing - {e}")
        raise RuntimeError(f"crash happened in model inference testing - {e}")


@app.post("/classifier/datamodel/deployment/testing/delete")
async def delete_folder_content(request:Request, model_data:DeleteTestRequest):
    try:

        folder_path = f"{TEST_MODEL_DOWNLOAD_ROOT_DIRECTORY}/{model_data.deleteModelId}"
        delete_folder(folder_path)  
        
        # Stop the model
        test_inference_wrapper.stop_model(model_id=model_data.deleteModelId)
        
        delete_success = {"message" : "Model Deleted Successfully!"}
        return JSONResponse(status_code = 200, content = delete_success)                        
    
    except Exception as e:
        raise HTTPException(status_code = 500, detail=str(e))
     

