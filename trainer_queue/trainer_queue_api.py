from fastapi import FastAPI
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from queue import Queue
import requests


app = FastAPI()

request_queue = Queue()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_TRAINER_URL = os.getenv("MODEL_TRAINER_URL")
MODEL_CHECKER_URL = os.getenv("MODEL_CHECKER_URL")

print("INIT STARTED MAIN.PY - Log recorded")

class SessionPayload(BaseModel):
    cookie: str
    old_model_id: str
    new_model_id: str
    update_type: str
    prev_deployment_env: Optional[str] = None
    progress_session_id: int
    deployment_env: str
    model_details: str

@app.post("/add_session")
def add_session(payload: SessionPayload):
    try:
        print("ADDING payload")
        request_queue.put(payload)
        print("AFTER ADDING payload")
        print("payload for model_checker", payload)
        response = requests.get(MODEL_CHECKER_URL)
        if response.status_code == 200:
            print("response from model_checker: ", response.json())
            training_status = response.json()
            print(f"training _Status : {training_status} > {training_status['Training'] == False}")
            if training_status['Training'] == False:
                print("inside loop")
                print("payload for model_trainer", payload)
                response = requests.post(MODEL_TRAINER_URL, json=payload.dict())
                print("response from model_trainer: ", response)
                request_queue.get()
            return {"message": "Session added successfully", "payload": payload}
    except Exception as e:
        print(f"Exception in add_session in training queue : {e}")

@app.get("/get_session")
def get_session():
    if request_queue.qsize() != 0:
        payload = request_queue.get()
        response = requests.post(MODEL_TRAINER_URL, json=payload)
        return response

    else:
        return "queue is empty"

@app.delete("/remove_session")
def remove_session():
    if request_queue.empty():
        raise HTTPException(status_code=404, detail="No sessions available in the queue to remove")
    request_queue.get()  
    return {"message": "First session removed successfully"}
