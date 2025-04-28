from fastapi import FastAPI, HTTPException, Request, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from dataset_processor import DatasetProcessor
import requests
import os
from dataset_validator import DatasetValidator

app = FastAPI()
processor = DatasetProcessor()
validator = DatasetValidator()
RUUTER_PRIVATE_URL = os.getenv("RUUTER_PRIVATE_URL")
VALIDATION_CONFIRMATION_URL = os.getenv("VALIDATION_CONFIRMATION_URL")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProcessHandlerRequest(BaseModel):
    dgId: int
    newDgId: int
    cookie: str
    updateType: str
    savedFilePath: str
    patchPayload: dict

async def authenticate_user(request: Request):
    cookie = request.cookies.get("customJwtCookie")
    if not cookie:
        raise HTTPException(status_code=401, detail="No cookie found in the request")

    url = f"{RUUTER_PRIVATE_URL}/auth/jwt/userinfo"
    headers = {
        'cookie': f'customJwtCookie={cookie}'
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Authentication failed")

@app.post("/init-dataset-process")
async def process_handler_endpoint(request: Request):
    print("STAGE 1")
    payload = await request.json()
    print("STAGE 1.1")
    await authenticate_user(request)
    print("STAGE 2")
    authCookie = payload["cookie"]
    result = processor.process_handler(int(payload["dgId"]), int(payload["newDgId"]), authCookie, payload["updateType"], payload["savedFilePath"], payload["patchPayload"], payload["sessionId"])
    print("STAGE 3")
    if result:
        return result
    else:
        raise HTTPException(status_code=500, detail="An unknown error occurred")

@app.post("/datasetgroup/update/validation/status")
async def forward_request(request: Request, response: Response):
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(e)}")
    
    validator_response = validator.process_request(int(payload["dgId"]), int(payload["newDgId"]), payload["cookie"], payload["updateType"], payload["savedFilePath"], payload["patchPayload"])
    forward_payload = {}
    print("@@@@")
    print(payload)
    print("------")
    print(validator_response)
    print("@@@@")
    forward_payload["dgId"] = int(payload["dgId"])
    forward_payload["newDgId"] = int(payload["newDgId"])
    forward_payload["updateType"] = payload["updateType"]
    forward_payload["patchPayload"] = payload["patchPayload"]
    forward_payload["savedFilePath"] = payload["savedFilePath"]
    forward_payload["sessionId"] = validator_response['response']["sessionId"] if validator_response['response']["sessionId"] is not None else 0

    headers = {
        'cookie': payload["cookie"],
        'Content-Type': 'application/json'
    }
    if validator_response["response"]["operationSuccessful"] != True:
        forward_payload["validationStatus"] = "fail"
        forward_payload["validationErrors"] = [validator_response["response"]["message"]]
    else:
        forward_payload["validationStatus"] = "in-progress"
        forward_payload["validationErrors"] = []

    try:
        print("#####")
        print(forward_payload)
        print("#####")
        forward_response = requests.post(VALIDATION_CONFIRMATION_URL, json=forward_payload, headers=headers)
        forward_response.raise_for_status()
        
        return JSONResponse(content=forward_response.json(), status_code=forward_response.status_code)
    except requests.HTTPError as e:
        forward_payload = {}
        forward_payload["dgId"] = int(payload["dgId"])
        forward_payload["newDgId"] = int(payload["newDgId"])
        forward_payload["updateType"] = payload["updateType"]
        forward_payload["patchPayload"] = payload["patchPayload"]
        forward_payload["savedFilePath"] = payload["savedFilePath"]
        forward_payload["validationStatus"] = "fail"
        forward_payload["validationErrors"] = [e]
        forward_response = requests.post(VALIDATION_CONFIRMATION_URL, json=forward_payload, headers=headers)
        print(e)
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        forward_payload = {}
        forward_payload["dgId"] = int(payload["dgId"])
        forward_payload["newDgId"] = int(payload["newDgId"])
        forward_payload["updateType"] = payload["updateType"]
        forward_payload["patchPayload"] = payload["patchPayload"]
        forward_payload["savedFilePath"] = payload["savedFilePath"]
        forward_payload["validationStatus"] = "fail"
        forward_payload["validationErrors"] = [e]
        forward_response = requests.post(VALIDATION_CONFIRMATION_URL, json=forward_payload, headers=headers)
        print(e)
        raise HTTPException(status_code=500, detail=str(e))