from fastapi import  HTTPException
import httpx
import requests
import os
from constants import GRAPH_API_BASE_URL, HIERARCHY_VALIDATION_LOGS
OUTLOOK_ACCESS_TOKEN_API_URL=os.getenv("OUTLOOK_ACCESS_TOKEN_API_URL")

from loguru import logger

logger.add(sink=HIERARCHY_VALIDATION_LOGS)

async def fetch_folders(folder_id: str = 'root', outlook_access_token:str=''):  
    url = f"{GRAPH_API_BASE_URL}/me/mailFolders"
    if folder_id != 'root':
        url = f"{GRAPH_API_BASE_URL}/me/mailFolders/{folder_id}/childFolders"
    
    headers = {
        "Authorization": f"Bearer {outlook_access_token}",
        "Content-Type": "application/json"
    }
    
    all_folders = []
    async with httpx.AsyncClient() as client:
        while url:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Failed to fetch folders: {response.text}")
            
            data = response.json()
            all_folders.extend(data['value'])
            url = data.get('@odata.nextLink')
    
    return all_folders

async def build_folder_hierarchy(outlook_access_token:str, folder_id: str = 'root'):
    
    folders = await fetch_folders(folder_id, outlook_access_token=outlook_access_token)
    
    async def build_hierarchy(folder):
        child_folders = await build_folder_hierarchy(outlook_access_token=outlook_access_token, folder_id=folder['id'])

        hierarchy = {}
        hierarchy["id"] = folder['id']
        hierarchy["displayName"] = folder['displayName']
        hierarchy["childFolders"] = child_folders
        return hierarchy
    
    return [await build_hierarchy(folder) for folder in folders]

async def validate_hierarchy(class_hierarchies,  outlook_access_token):
    logger.info("ENTERING VALIDATE HIERARCHY FUNCTION")
    try:
        errors = []
        folder_hierarchy = await build_folder_hierarchy(outlook_access_token=outlook_access_token)
        logger.info("OUTLOOK FOLDER HIERARCHY SUCCESS")
        # logger.info(f"folder_hierarchy: {folder_hierarchy}")
        def find_folder(name, folders):
            return next((folder for folder in folders if folder["displayName"] == name), None)

        def check_hierarchy(classes, folders, path):
            for cls in classes:
                folder = find_folder(cls["class"], folders)
                if not folder:
                    current_cls = cls["class"]
                    errors.append(f"Folder {current_cls} not found at path '{path}'")
                    return False
                if cls["subclasses"]:
                    current_cls = cls["class"]
                    if not check_hierarchy(cls["subclasses"], folder["childFolders"], f"{path}/{current_cls}"):
                        return False
            return True

        # logger.info(f"CLASS HIERARCHY IN UTIL FUNCTION - {class_hierarchies}")
        # logger.info(f"FOLDER HIERARCHY IN OUTLOOK UTIL FUNCTION - {folder_hierarchy}")

        result = check_hierarchy(class_hierarchies, folder_hierarchy, '')
        logger.info(f"ERRORS IN VALIDATE HIERARCHY: {errors}")
        logger.info(f"FINAL OUTPUT OF THE validate_hierarchy FUNCTION: {result}")
        return {"isValid": result, "errors": errors}
    
    except Exception as e:
        logger.info(f"ERROR IN validate_hierarchy function {e}")
        logger.info(f"ERRORS IN VALIDATE HIERARCHY catched in the excepton: {errors}")
        raise Exception(f"ERROR IN validate_hierarchy function {e}")


def find_folder_id(hierarchy, path):
    current_level = hierarchy
    for folder_name in path:
        found = False
        for folder in current_level:
            if folder["displayName"].lower() == folder_name.lower():
                if folder_name == path[-1]:
                    return folder["id"]
                current_level = folder["childFolders"]
                found = True
                break
        if not found:
            raise ValueError(f"Folder '{folder_name}' not found in the given path")
    raise ValueError("Path is empty or invalid")

def get_corrected_folder_hierarchy(hierarchy, final_folder_id):
    def search_hierarchy(folders, target_id, current_path):
        for folder in folders:
            new_path = current_path + [folder["displayName"]]
            if folder["id"] == target_id:
                return new_path
            if folder["childFolders"]:
                result = search_hierarchy(folder["childFolders"], target_id, new_path)
                if result:
                    return result
        return []

    result = search_hierarchy(hierarchy, final_folder_id, [])
    if not result:
        raise ValueError(f"Folder with ID '{final_folder_id}' not found in the hierarchy")
    return result


def get_outlook_access_token(model_id):    
    try:
        outlook_access_token_url = OUTLOOK_ACCESS_TOKEN_API_URL
        response = requests.post(outlook_access_token_url, json={"modelId": model_id})
        data = response.json()

        logger.info(f"RESPONSE OF get_outlook_access_token {data}")

        access_token = data["response"]["outlook_access_token"]
        return access_token
    except Exception as e:
        logger.error(f"ERROR IN get_outlook_access_token: {e}")
        raise Exception(f"Failed to retrieve Outlook Access Token Reason: {e}") 
    