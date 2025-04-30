from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import requests
from constants import HierarchyCheckRequest, FlattenedFolderHierarchy, FolderHierarchyRequest, CorrectedFolderRequest, HIERARCHY_VALIDATION_LOGS
from utils import build_folder_hierarchy, validate_hierarchy, find_folder_id, get_corrected_folder_hierarchy,get_outlook_access_token
from loguru import logger

logger.add(sink=HIERARCHY_VALIDATION_LOGS)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_credentials = True,
    allow_methods = ["GET", "POST"],
    allow_headers = ["*"]
)

RUUTER_PRIVATE_URL = os.getenv("RUUTER_PRIVATE_URL")

@app.post("/folder-hierarchy")
async def get_folder_hierarchy(request: Request, modelData:FolderHierarchyRequest):
    try:

        logger.info(f"MODEL ID {modelData.modelId}")

        outlook_access_token = get_outlook_access_token(model_id=modelData.modelId)

        logger.info(f"OUTLOOK ACCESS TOKEN {outlook_access_token}")

        hierarchy = await build_folder_hierarchy(outlook_access_token=outlook_access_token)

        logger.info(f"HIERARCHY IN get_folder_hierarchy: {hierarchy}")

        return hierarchy
    except Exception as e:

        logger.error(f"ERROR IN get_folder_hierarchy function - {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch folder hierarchy: {str(e)}")

@app.post("/check-folder-hierarchy")
async def check_folder_hierarchy(request: Request, hierarchyData: HierarchyCheckRequest): 
    try:
        outlook_access_token = get_outlook_access_token(model_id=hierarchyData.modelId)

        logger.info(f"OUTLOOK ACCESS TOKEN {outlook_access_token}")

        result = await validate_hierarchy(class_hierarchies=hierarchyData.classHierarchies, outlook_access_token=outlook_access_token)
        return result
    except Exception as e:

        logger.error(f"ERROR IN check_folder_hierarchy function - {e}")
        raise HTTPException(status_code=500, detail=f"Failed to validate folder hierarchy: {str(e)}")

@app.post("/find-folder-id")
async def get_folder_id(request: Request, flattened_hierarchy: FlattenedFolderHierarchy):
    try:

        logger.info(f"PREDICTED FOLDER HIERARCHY - {flattened_hierarchy}")

        outlook_access_token = get_outlook_access_token(model_id=flattened_hierarchy.modelId)
        logger.info(f"OUTLOOK ACCESS TOKEN - {outlook_access_token}")

        hierarchy = await build_folder_hierarchy(outlook_access_token=outlook_access_token)
        logger.info(f"OUTLOOK FOLDER HIEARARCHY - {hierarchy}")

        folder_id = find_folder_id(hierarchy, flattened_hierarchy.hierarchy)
        logger.info(f"FINAL FOLDER ID - {folder_id}")

        return {"folder_id": folder_id}
    except ValueError as e:

        logger.info(f"VALUE ERROR - {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:

        logger.info(f"EXCEPTION IN FIND FOLDER ID - {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred in retriving the final folder id: {str(e)}")
    
@app.post("/corrected-folder-hierarchy")
async def get_hierarchy(request: Request, correctedData:CorrectedFolderRequest ):
    try:
        outlook_access_token = get_outlook_access_token(model_id=correctedData.modelId)
        hierarchy = await build_folder_hierarchy(outlook_access_token=outlook_access_token)
        folder_path = get_corrected_folder_hierarchy(hierarchy, correctedData.folderId)
        return {"folder_hierarchy": folder_path}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred in corrected-folder-hierarchy: {str(e)}")