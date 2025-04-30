from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks
from pydantic import BaseModel
from ner import NERProcessor
from text_processing import TextProcessor
from fake_replacements import FakeReplacer
from webhook_request_retention import RequestRetentionList
from html_cleaner import HTMLCleaner
import os
import requests
import hmac
import hashlib
import json
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import pandas as pd
import io
import uvicorn

app = FastAPI()

request_validator = RequestRetentionList()
ner_processor = NERProcessor()
html_cleaner = HTMLCleaner()

JIRA_INFERENCE_ENDPOINT = os.getenv("JIRA_INFERENCE_ENDPOINT")
OUTLOOK_INFERENCE_ENDPOINT = os.getenv("OUTLOOK_INFERENCE_ENDPOINT")

def anonymizer_functions(payload):
    try:
        if(payload.get("platform", "").lower()=="outlook"):
            orginal_request = request_validator.add_email(payload.get("mailId", "")+payload.get("parentFolderId", ""))
            if not orginal_request:
                return False


        data_dict = payload.get("data", {})

        if len(data_dict["attachments"]) <= 0:
            data_dict["attachments"] = ""
        else:
            data_dict["attachments"] = ', '.join(data_dict["attachments"])

        concatenated_text = " ".join(str(value) for value in data_dict.values())

        cleaned_text = html_cleaner.remove_html_tags(concatenated_text)
        text_chunks = TextProcessor.split_text(cleaned_text, 2000)
        processed_chunks = []

        for chunk in text_chunks:
            entities = ner_processor.identify_entities(chunk)
            processed_chunk = FakeReplacer.replace_entities(chunk, entities)
            processed_chunks.append(processed_chunk)

        processed_text = TextProcessor.combine_chunks(processed_chunks)

        output_payload = {key: value for key, value in payload.items() if key != "data"}
        output_payload["inputText"] = processed_text

        platform = payload.get("platform", "").lower()

        headers = {
                'Content-Type': 'application/json'
            }
        if platform == "jira":
            del output_payload["platform"]
            del output_payload["parentFolderId"]
            del output_payload["mailId"]
            output_payload["inputId"] = output_payload.pop("key")
            output_payload["finalLabels"] = output_payload.pop("labels")

            print(f"Output payload : {output_payload}")
            response = requests.post(JIRA_INFERENCE_ENDPOINT, json=output_payload, headers=headers)
        elif platform == "outlook":
            del output_payload["labels"]
            del output_payload["platform"]
            output_payload["inputId"] = output_payload.pop("key")
            output_payload["finalFolderId"] = output_payload.pop("parentFolderId")

            print(f"Output payload : {output_payload}")
            response = requests.post(OUTLOOK_INFERENCE_ENDPOINT, json=output_payload, headers=headers)
        else:
            print("Platform not recognized... ")
            response = None

        print(f"Response from {platform} : {response}")

        return output_payload
    except Exception as e:
        print(f"Error while annonymizing the data : {e}")
        return False

@app.post("/anonymize")
async def process_text(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()

        print("-----------------------------")
        print(payload)
        print("-----------------------------")

        background_tasks.add_task(anonymizer_functions, payload=payload)

        return JSONResponse(status_code=200, content={"status":True, "detail":"Anonymizing process started"})

    except Exception as e:
        return JSONResponse(status_code=200, content={"status":False, "detail":"Anonymizing process failed.", "error":e})

@app.post("/anonymize-file")
async def anonymize_file(file: UploadFile = File(...), columns: str = Form(...)):
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        column_names = columns.split(',')

        for column in column_names:
            if column in df.columns:
                df[column] = df[column].apply(lambda text: process_text(text))

        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)

        return StreamingResponse(
            output, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=anonymized_{file.filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def process_text(text):
    text_chunks = TextProcessor.split_text(text, 2000)
    processed_chunks = []

    for chunk in text_chunks:
        entities = ner_processor.identify_entities(chunk)
        processed_chunk = FakeReplacer.replace_entities(chunk, entities)
        processed_chunks.append(processed_chunk)

    processed_text = TextProcessor.combine_chunks(processed_chunks)
    
    return processed_text


if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8010)
