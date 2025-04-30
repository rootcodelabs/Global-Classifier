import os
from dataset_processor import DatasetProcessor
from fastapi import HTTPException

def process_dataset():
    try:
        dg_id = int(os.getenv("dgId"))
        new_dg_id = int(os.getenv("newDgId"))
        update_type = os.getenv("updateType")
        saved_file_path = os.getenv("savedFilePath")
        patch_payload = os.getenv("patchPayload")
        cookie = os.getenv("cookie")
        session_id = os.getenv("sessionId")

        processor = DatasetProcessor()

        # Call the process_handler method
        result = processor.process_handler(dg_id, new_dg_id, cookie, update_type, saved_file_path, patch_payload, session_id)

        if result:
            print(result)
        else:
            raise HTTPException(status_code=500, detail="An unknown error occurred")
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    process_dataset()
