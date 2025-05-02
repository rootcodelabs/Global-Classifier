import os
import requests
from dataset_validator import DatasetValidator
from fastapi import HTTPException
from fastapi.responses import JSONResponse

def validate_dataset():
    try:
        dg_id = int(os.getenv("dgId"))
        new_dg_id = int(os.getenv("newDgId"))
        update_type = os.getenv("updateType")
        saved_file_path = os.getenv("savedFilePath")
        patch_payload = os.getenv("patchPayload")
        cookie = os.getenv("cookie")

        validator = DatasetValidator()

        # Call the process_request method
        validator_response = validator.process_request(dg_id, new_dg_id, cookie, update_type, saved_file_path, patch_payload)
        forward_payload = {}

        forward_payload["dgId"] = dg_id
        forward_payload["newDgId"] = new_dg_id
        forward_payload["updateType"] = update_type
        forward_payload["patchPayload"] = patch_payload
        forward_payload["savedFilePath"] = saved_file_path
        forward_payload["sessionId"] = validator_response['response']["sessionId"] if validator_response['response']["sessionId"] is not None else 0

        headers = {
            'cookie': cookie,
            'Content-Type': 'application/json'
        }

        if validator_response["response"]["operationSuccessful"] != True:
            forward_payload["validationStatus"] = "fail"
            forward_payload["validationErrors"] = [validator_response["response"]["message"]]
        else:
            forward_payload["validationStatus"] = "success"
            forward_payload["validationErrors"] = []

        try:
            forward_response = requests.post(os.getenv("VALIDATION_CONFIRMATION_URL"), json=forward_payload, headers=headers)
            forward_response.raise_for_status()

            print(forward_response.json())
        
        except requests.HTTPError as e:
            print(f"HTTP Error: {e.response.status_code}, {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

        except Exception as e:
            print(f"Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    validate_dataset()
