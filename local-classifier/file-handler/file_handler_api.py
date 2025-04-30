from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import os
import json
import uuid
import requests
from pydantic import BaseModel
from file_converter import FileConverter
from constants import *
from s3_ferry import S3Ferry
import yaml
import pandas as pd
from typing import List
from io import BytesIO, TextIOWrapper
from dataset_deleter import DatasetDeleter
from dataset_deleter import ModelDeleter
from datetime import datetime
from loguru import logger

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

s3_ferry = S3Ferry(S3_FERRY_URL)

class ExportFile(BaseModel):
    dgId: int
    exportType: str

class ExportCorrectedDataFile(BaseModel):
    platform: str
    exportType: str

class ImportChunks(BaseModel):
    dg_id: int
    chunks: list
    exsistingChunks: int

class ImportJsonMajor(BaseModel):
    dgId: int
    dataset: list

class CopyPayload(BaseModel):
    dgId: int
    newDgId: int
    fileLocations: list

if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

if not os.path.exists(CHUNK_UPLOAD_DIRECTORY):
    os.makedirs(CHUNK_UPLOAD_DIRECTORY)

def get_ruuter_private_url():
    return os.getenv("RUUTER_PRIVATE_URL")

async def authenticate_user(cookie: str):
    try:
        if not cookie:
            raise HTTPException(status_code=401, detail="No cookie found in the request")

        url = f"{RUUTER_PRIVATE_URL}/auth/jwt/userinfo"
        headers = {
            'cookie': cookie
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Authentication failed")
    except Exception as e:
        print(f"Error in file handler authentication : {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

def custom_serializer(obj):
    if isinstance(obj, (datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

@app.post("/datasetgroup/data/import")
async def upload_and_copy(request: Request, dgId: int = Form(...), dataFile: UploadFile = File(...)):
    try:
        cookie = request.cookies.get("customJwtCookie")
        await authenticate_user(f'customJwtCookie={cookie}')

        print(f"Received dgId: {dgId}")
        print(f"Received filename: {dataFile.filename}")

        file_converter = FileConverter()
        file_type = file_converter._detect_file_type(dataFile.filename)
        file_name = f"{uuid.uuid4()}.{file_type}"
        file_location = os.path.join(UPLOAD_DIRECTORY, file_name)
        
        with open(file_location, "wb") as f:
            f.write(dataFile.file.read())

        success, converted_data = file_converter.convert_to_json(file_location)
        if not success:
            upload_failed = UPLOAD_FAILED.copy()
            upload_failed["reason"] = "Json file convert failed."
            raise HTTPException(status_code=500, detail=upload_failed)
        
        for idx, record in enumerate(converted_data, start=1):
            record["rowId"] = idx
        
        json_local_file_path = file_location.replace(YAML_EXT, JSON_EXT).replace(YML_EXT, JSON_EXT).replace(XLSX_EXT, JSON_EXT)
        with open(json_local_file_path, 'w') as json_file:
            json.dump(converted_data, json_file, indent=4, default=custom_serializer)

        save_location = TEMP_DATASET_LOCATION.format(dg_id=dgId)
        source_file_path = file_name.replace(YML_EXT, JSON_EXT).replace(YAML_EXT, JSON_EXT).replace(XLSX_EXT, JSON_EXT)
        
        response = s3_ferry.transfer_file(save_location, "S3", source_file_path, "FS")
        if response.status_code == 201:
            os.remove(file_location)
            if file_location != json_local_file_path:
                os.remove(json_local_file_path)
            upload_success = UPLOAD_SUCCESS.copy()
            upload_success["saved_file_path"] = save_location
            return JSONResponse(status_code=200, content=upload_success)
        else:
            raise HTTPException(status_code=500, detail=S3_UPLOAD_FAILED)
    except Exception as e:
        print(f"Exception in data/import : {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/datasetgroup/data/download")
async def download_and_convert(request: Request, exportData: ExportFile, backgroundTasks: BackgroundTasks):
    cookie = request.cookies.get("customJwtCookie")
    await authenticate_user(f'customJwtCookie={cookie}')
    dg_id = exportData.dgId
    export_type = exportData.exportType

    if export_type not in ["xlsx", "yaml", "json"]:
        raise HTTPException(status_code=500, detail=EXPORT_TYPE_ERROR)

    save_location = PRIMARY_DATASET_LOCATION.format(dg_id=dg_id)
    local_file_name = f"group_{dg_id}_aggregated"

    response = s3_ferry.transfer_file(f"{local_file_name}{JSON_EXT}", "FS", save_location, "S3")
    if response.status_code != 201:
        raise HTTPException(status_code=500, detail=S3_DOWNLOAD_FAILED)

    json_file_path = os.path.join(JSON_FILE_DIRECTORY, f"{local_file_name}{JSON_EXT}")

    file_converter = FileConverter()
    with open(f"{json_file_path}", 'r') as json_file:
        json_data = json.load(json_file)
    
    if export_type == "xlsx":
        output_file = f"{local_file_name}{XLSX_EXT}"
        file_converter.convert_json_to_xlsx(json_data, output_file)
    elif export_type == "yaml":
        output_file = f"{local_file_name}{YAML_EXT}"
        file_converter.convert_json_to_yaml(json_data, output_file)
    elif export_type == "json":
        output_file = f"{json_file_path}"
    else:
        raise HTTPException(status_code=500, detail=EXPORT_TYPE_ERROR)

    backgroundTasks.add_task(os.remove, json_file_path)
    if output_file != json_file_path:
        backgroundTasks.add_task(os.remove, output_file)

    return FileResponse(output_file, filename=os.path.basename(output_file))

@app.get("/datasetgroup/data/download/json")
async def download_and_convert(request: Request, dgId: int, background_tasks: BackgroundTasks):
    cookie = request.cookies.get("customJwtCookie")
    await authenticate_user(f'customJwtCookie={cookie}')

    save_location = PRIMARY_DATASET_LOCATION.format(dg_id=dgId)
    local_file_name = f"group_{dgId}_aggregated"

    response = s3_ferry.transfer_file(f"{local_file_name}{JSON_EXT}", "FS", save_location, "S3")
    if response.status_code != 201:
        raise HTTPException(status_code=500, detail=S3_DOWNLOAD_FAILED)

    json_file_path = os.path.join(JSON_FILE_DIRECTORY, f"{local_file_name}{JSON_EXT}")

    with open(f"{json_file_path}", 'r') as json_file:
        json_data = json.load(json_file)

    background_tasks.add_task(os.remove, json_file_path)

    return json_data

@app.get("/datasetgroup/data/download/json/location")
async def download_and_convert(request: Request, saveLocation:str, background_tasks: BackgroundTasks):
    cookie = request.cookies.get("customJwtCookie")
    await authenticate_user(f'customJwtCookie={cookie}')

    local_file_name = saveLocation.split("/")[-1]

    response = s3_ferry.transfer_file(f"{local_file_name}", "FS", saveLocation, "S3")
    if response.status_code != 201:
        raise HTTPException(status_code=500, detail=S3_DOWNLOAD_FAILED)

    json_file_path = os.path.join(JSON_FILE_DIRECTORY, f"{local_file_name}")

    with open(f"{json_file_path}", 'r') as json_file:
        json_str = json_file.read().replace('NaN', 'null')
        json_data = json.loads(json_str)

    background_tasks.add_task(os.remove, json_file_path)

    return json_data

@app.post("/datasetgroup/data/import/chunk")
async def upload_and_copy(request: Request, import_chunks: ImportChunks):
    cookie = request.cookies.get("customJwtCookie")
    await authenticate_user(f'customJwtCookie={cookie}')

    dgID = import_chunks.dg_id
    chunks = import_chunks.chunks
    exsisting_chunks = import_chunks.exsistingChunks

    fileLocation = os.path.join(CHUNK_UPLOAD_DIRECTORY, f"{exsisting_chunks}.json")
    s3_ferry_view_file_location = os.path.join("/chunks", f"{exsisting_chunks}.json")
    with open(fileLocation, 'w') as jsonFile:
        json.dump(chunks, jsonFile, indent=4)

    saveLocation = CHUNK_DATASET_LOCATION.format(dg_id=dgID, chunk_id=exsisting_chunks)

    response = s3_ferry.transfer_file(saveLocation, "S3", s3_ferry_view_file_location, "FS")
    if response.status_code == 201:
        os.remove(fileLocation)
    else:
        raise HTTPException(status_code=500, detail=S3_UPLOAD_FAILED)

@app.get("/datasetgroup/data/download/chunk")
async def download_and_convert(request: Request, dgId: int, pageId: int, backgroundTasks: BackgroundTasks):
    try:
        cookie = request.cookies.get("customJwtCookie")
        await authenticate_user(f'customJwtCookie={cookie}')

        save_location = CHUNK_DATASET_LOCATION.format(dg_id=dgId, chunk_id=pageId)
        local_file_name = f"group_{dgId}_chunk_{pageId}"

        response = s3_ferry.transfer_file(f"{local_file_name}{JSON_EXT}", "FS", save_location, "S3")
        if response.status_code != 201:
            return {}

        json_file_path = os.path.join(JSON_FILE_DIRECTORY, f"{local_file_name}{JSON_EXT}")

        with open(f"{json_file_path}", 'r') as json_file:
            json_data = json.load(json_file)

        backgroundTasks.add_task(os.remove, json_file_path)

        return json_data
    except Exception as e:
        print(f"Error in download/chunk : {e}")

@app.post("/datasetgroup/data/import/json")
async def upload_and_copy(request: Request, importData: ImportJsonMajor):
    cookie = request.cookies.get("customJwtCookie")
    await authenticate_user(f'customJwtCookie={cookie}')

    fileName = f"{uuid.uuid4()}.{JSON_EXT}"
    fileLocation = os.path.join(UPLOAD_DIRECTORY, fileName)
    
    with open(fileLocation, 'w') as jsonFile:
        json.dump(importData.dataset, jsonFile, indent=4)

    saveLocation = PRIMARY_DATASET_LOCATION.format(dg_id=importData.dgId)
    sourceFilePath = fileName.replace(YML_EXT, JSON_EXT).replace(XLSX_EXT, JSON_EXT)
    
    response = s3_ferry.transfer_file(saveLocation, "S3", sourceFilePath, "FS")
    if response.status_code == 201:
        os.remove(fileLocation)
        upload_success = UPLOAD_SUCCESS.copy()
        upload_success["saved_file_path"] = saveLocation
        return JSONResponse(status_code=200, content=upload_success)
    else:
        raise HTTPException(status_code=500, detail=S3_UPLOAD_FAILED)
    
@app.post("/datasetgroup/data/copy")
async def upload_and_copy(request: Request, copyPayload: CopyPayload):
    try:
        cookie = request.cookies.get("customJwtCookie")
        await authenticate_user(f'customJwtCookie={cookie}')

        dg_id = copyPayload.dgId
        new_dg_id = copyPayload.newDgId
        files = copyPayload.fileLocations

        if len(files)>0:
            local_storage_location = TEMP_COPY_FILE
        else:
            print("Abort copying since sent file list does not have any entry.")
            upload_success = UPLOAD_SUCCESS.copy()
            upload_success["saved_file_path"] = ""
            return JSONResponse(status_code=200, content=upload_success)

        for file in files:
            old_location = f"/dataset/{dg_id}/{file}"
            new_location = NEW_DATASET_LOCATION.format(new_dg_id=new_dg_id) + file
            response = s3_ferry.transfer_file(local_storage_location, "FS", old_location, "S3")
            response = s3_ferry.transfer_file(new_location, "S3", local_storage_location, "FS")

            if response.status_code == 201:
                print(f"Copying completed : {file}")
            else:
                print(f"Copying failed : {file}")
                raise HTTPException(status_code=500, detail=S3_UPLOAD_FAILED)
        else:
            os.remove(f"../shared/{local_storage_location}")
            upload_success = UPLOAD_SUCCESS.copy()
            upload_success["saved_file_path"] = NEW_DATASET_LOCATION.format(new_dg_id=new_dg_id)
            return JSONResponse(status_code=200, content=upload_success)
    except Exception as e:
        print(f"Error in /datasetgroup/data/copy : {e}")
        return JSONResponse(status_code=200, content="File Copy Failed")

def extract_stop_words(file: UploadFile) -> List[str]:
    file_converter = FileConverter()
    file_type = file_converter._detect_file_type(file.filename)
    
    if file_type == 'txt':
        content = file.file.read().decode('utf-8')
        return [word.strip() for word in content.split(',') if word.strip()]
    elif file_type == 'json':
        content = json.load(file.file)
        return content if isinstance(content, list) else []
    elif file_type == 'yaml':
        content = yaml.safe_load(file.file)
        return content if isinstance(content, list) else []
    elif file_type == 'xlsx':
        content = file.file.read()
        excel_file = BytesIO(content)
        data = pd.read_excel(excel_file, sheet_name=None)
        stop_words = []
        for sheet in data:
            stop_words.extend(data[sheet].columns.tolist())
            stop_words.extend(data[sheet].stack().tolist())
        return stop_words
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

@app.post("/datasetgroup/data/import/stop-words")
async def import_stop_words(request: Request, stopWordsFile: UploadFile = File(...)):
    try:
        cookie = request.cookies.get("customJwtCookie")
        await authenticate_user(f'customJwtCookie={cookie}')

        words_list = extract_stop_words(stopWordsFile)

        url = IMPORT_STOPWORDS_URL
        headers = {
            'Content-Type': 'application/json',
            'Cookie': f'customJwtCookie={cookie}'
        }

        response = requests.post(url, headers=headers, json={"stopWords": words_list})

        if response.status_code == 200 or response.status_code == 400:
            response_data = response.json()
            print(f"response_data : {response_data}")
            if response_data['response']['operationSuccessful']:
                return response_data
            elif response_data['response']['duplicate']:
                duplicate_items = response_data['response']['duplicateItems']
                new_words_list = [word for word in words_list if word not in duplicate_items]
                if new_words_list:
                    response = requests.post(url, headers=headers, json={"stopWords": new_words_list})
                    return response.json()
                else:
                    return response_data
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to update stop words")
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to update stop words")
        
    except Exception as e:
        print(f"Error in import/stop-words: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/datasetgroup/data/delete/stop-words")
async def delete_stop_words(request: Request, stopWordsFile: UploadFile = File(...)):
    try:
        cookie = request.cookies.get("customJwtCookie")
        await authenticate_user(f'customJwtCookie={cookie}')

        words_list = extract_stop_words(stopWordsFile)

        url = DELETE_STOPWORDS_URL
        headers = {
            'Content-Type': 'application/json',
            'Cookie': f'customJwtCookie={cookie}'
        }

        response = requests.post(url, headers=headers, json={"stopWords": words_list})

        if response.status_code == 200 or response.status_code == 400:
            response_data = response.json()
            if response_data['response']['operationSuccessful']:
                return response_data
            elif response_data['response']['nonexistent']:
                nonexistent_items = response_data['response']['nonexistentItems']
                new_words_list = [word for word in words_list if word not in nonexistent_items]
                if new_words_list:
                    response = requests.post(url, headers=headers, json={"stopWords": new_words_list})
                    return response.json()
                else:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "message": f"The following words are not in the list and cannot be deleted: {', '.join(nonexistent_items)}"
                        }
                    )
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to delete stop words")
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to delete stop words")
        
    except Exception as e:
        print(f"Error in delete/stop-words: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/datasetgroup/data/delete")
async def delete_dataset_files(request: Request):
    try:
        cookie = request.cookies.get("customJwtCookie")
        await authenticate_user(f'customJwtCookie={cookie}')

        payload = await request.json()
        dgId = int(payload["dgId"])

        deleter = DatasetDeleter(S3_FERRY_URL)
        success, files_deleted = deleter.delete_dataset_files(dgId, f'customJwtCookie={cookie}')

        if success:
            headers = {
                'cookie': f'customJwtCookie={cookie}',
                'Content-Type': 'application/json'
            }
            payload = {"dgId": dgId}

            response = requests.post(DATAGROUP_DELETE_CONFIRMATION_URL, headers=headers, json=payload)
            if response.status_code != 200:
                print(f"Failed to notify deletion endpoint. Status code: {response.status_code}")
            else:
                response = requests.post(DATAMODEL_DELETE_CONFIRMATION_URL, headers=headers, json=payload)
                if response.status_code != 200:
                    print(f"Failed to notify model dataset deletion endpoint. Status code: {response.status_code}")

            return JSONResponse(status_code=200, content={"message": "Dataset deletion completed successfully.", "files_deleted": files_deleted})
        else:
            return JSONResponse(status_code=500, content={"message": "Dataset deletion failed.", "files_deleted": files_deleted})
    except Exception as e:
        print(f"Error in delete_dataset_files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/datamodel/data/corrected/download")
async def download_and_convert(request: Request, exportData: ExportCorrectedDataFile, backgroundTasks: BackgroundTasks):
    cookie = request.cookies.get("customJwtCookie")
    await authenticate_user(f'customJwtCookie={cookie}')
    platform = exportData.platform
    export_type = exportData.exportType

    if export_type not in ["xlsx", "yaml", "json"]:
        raise HTTPException(status_code=500, detail=EXPORT_TYPE_ERROR)

    headers = {
                'Content-Type': 'application/json',
                'Cookie': f'customJwtCookie={cookie}'
            }
    
    payload = {
        "platform" : platform,
        "sortType" : "asc"
    }

    response = requests.get(CORRECTED_TEXT_EXPORT, headers=headers, params=payload)
    response.raise_for_status()

    response_data = response.json()
    print(response_data)
    json_data = response_data["response"]["data"]
    now = datetime.now()
    formatted_time_date = now.strftime("%Y%m%d_%H%M%S")
    result_string = f"corrected_text_{formatted_time_date}"
    
    file_converter = FileConverter()
    
    if export_type == "xlsx":
        output_file = f"{result_string}{XLSX_EXT}"
        file_converter.convert_json_to_xlsx(json_data, output_file)
    elif export_type == "yaml":
        output_file = f"{result_string}{YAML_EXT}"
        file_converter.convert_json_to_yaml(json_data, output_file)
    elif export_type == "json":
        output_file = f"{result_string}{JSON_EXT}"
        with open(output_file, 'w') as json_file:
            json.dump(json_data, json_file, indent=4)
    else:
        raise HTTPException(status_code=500, detail=EXPORT_TYPE_ERROR)

    backgroundTasks.add_task(os.remove, output_file)

    return FileResponse(output_file, filename=os.path.basename(output_file))

@app.post("/datamodel/model/delete")
async def delete_datamodels(request: Request):
    try:
        cookie = request.cookies.get("customJwtCookie")
        await authenticate_user(f'customJwtCookie={cookie}')

        payload = await request.json()

        logger.info(f"MODEL PAYLOAD - {payload}")
        model_id = int(payload["modelId"])
        deployment_env = payload["deploymentEnv"]

        deleter = ModelDeleter(S3_FERRY_URL)
        success = deleter.delete_model_files(model_id)

        if success:
            headers = {
                'Content-Type': 'application/json',
                'Cookie': f'customJwtCookie={cookie}'
            }
            active_models_deleted = False
            if deployment_env.lower() == "jira":
                
                logger.info("DELETING JIRA ACTIVE MODEL")
                response = requests.post(JIRA_ACTIVE_MODEL_DELETE_URL, headers=headers)
                if response.status_code == 200:
                    active_models_deleted = True
            elif deployment_env.lower() == "outlook":

                logger.info("DELETING OUTLOOK ACTIVE MODEL")
                response = requests.post(OUTLOOK_ACTIVE_MODEL_DELETE_URL, headers=headers)
                if response.status_code == 200:
                    active_models_deleted = True
            elif deployment_env.lower() == "testing":

                logger.info("DELETING TESTING ACTIVE MODEL")
                response = requests.post(TEST_MODEL_DELETE_URL, headers=headers, json={"deleteModelId": model_id})
                logger.info("TESTING ACTIVE OMDEL")
                if response.status_code == 200:
                    active_models_deleted = True
            else:
                active_models_deleted = True


            if active_models_deleted:
                response = requests.post(MODEL_METADATA_DELETE_URL, headers=headers, json={"modelId": model_id})
                if response.status_code == 200:
                    active_models_deleted = True
                    logger.info(f"MODEL DELETION PAYLOAD - {response.text}")
                    return JSONResponse(status_code=200, content={"message": "Data model deletion completed successfully."})
                else:
                    return JSONResponse(status_code=500, content={"message": "Data model metadata deletion failed."})
            else:
                return JSONResponse(status_code=500, content={"message": "Active data model deletion failed."})
        else:
            return JSONResponse(status_code=500, content={"message": "Data model deletion failed."})
    except Exception as e:
        print(f"Error in delete_datamodel_files: {e}")
        raise HTTPException(status_code=500, detail=str(e))