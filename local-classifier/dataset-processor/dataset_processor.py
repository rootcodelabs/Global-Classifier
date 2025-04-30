import re
import os
import json
import urllib.parse
import requests
from constants import *

RUUTER_PRIVATE_URL = os.getenv("RUUTER_PRIVATE_URL")
GET_VALIDATION_SCHEMA = os.getenv("GET_VALIDATION_SCHEMA")
GET_STOPWORDS_URL = os.getenv("GET_STOPWORDS_URL")
FILE_HANDLER_IMPORT_CHUNKS_URL = os.getenv("FILE_HANDLER_IMPORT_CHUNKS_URL")
FILE_HANDLER_DOWNLOAD_LOCATION_JSON_URL = os.getenv("FILE_HANDLER_DOWNLOAD_LOCATION_JSON_URL")
GET_PAGE_COUNT_URL = os.getenv("GET_PAGE_COUNT_URL")
SAVE_JSON_AGGREGRATED_DATA_URL = os.getenv("SAVE_JSON_AGGREGRATED_DATA_URL")
DOWNLOAD_CHUNK_URL = os.getenv("DOWNLOAD_CHUNK_URL")
FILE_HANDLER_COPY_CHUNKS_URL = os.getenv("FILE_HANDLER_COPY_CHUNKS_URL")

class DatasetProcessor:
    def __init__(self):
        pass

    def check_and_convert(self, data):
        print(data)
        if self._is_multple_sheet_structure(data):
            return self._convert_to_single_sheet_structure(data)
        elif self._is_single_sheet_structure(data):
            return data
        else:
            print("The provided dictionary does not match the expected structures.")
            return None

    def _is_multple_sheet_structure(self, data):
        if isinstance(data, dict):
            for key, value in data.items():
                if not isinstance(key, str) or not isinstance(value, list):
                    return False
                for item in value:
                    if not isinstance(item, dict):
                        return False
            return True
        return False

    def _is_single_sheet_structure(self, data):
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict) or len(item) <= 1:
                    return False
            return True
        return False

    def _convert_to_single_sheet_structure(self, data):
        result = []
        for value in data.values():
            result.extend(value)
        return result

    def enrich_data(self, data, selected_fields, record_count):
        try:
            enriched_data = []
            for entry in data:
                enriched_entry = {}
                enrich_server = True
                for key, value in entry.items():
                    if isinstance(value, str) and (key in selected_fields):
                        enriched_value = self._get_paraphrases(value)
                        if enriched_value != []:
                            enriched_entry[key] = enriched_value[0]
                        else:
                            enrich_server = False
                            break
                    else:
                        enriched_entry[key] = value
                if enrich_server:
                    record_count += 1
                    enriched_entry["rowId"] = record_count
                    enriched_data.append(enriched_entry)
            return enriched_data
        except Exception as e:
            print(f"Internal Error occurred while data enrichment : {e}")
            return None

    def _get_paraphrases(self, text):
        payload = {
            "text": text,
            "num_return_sequences": 1
        }
        try:
            response = requests.post(PARAPHRASE_API_URL, json=payload)
            if response.status_code == 200:
                paraphrases = response.json().get("paraphrases", [])
                return paraphrases
            else:
                print(f"Failed to get paraphrases: {response.status_code}, {response.text}")
                return []
        except Exception as e:
            print(f"Error calling paraphrase API: {e}")
            return []

    
    def chunk_data(self, data, chunk_size=CHUNK_SIZE):
        try:
            return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        except Exception as e:
            print("Error while splitting data into chunks")
            return None
        
    def copy_chunked_datafiles(self, dgId, newDgId, cookie, exsistingChunks=None):
        try:
            headers = {
                'cookie': cookie,
                'Content-Type': 'application/json'
            }

            if exsistingChunks == None:
                exsistingChunks = self.get_page_count(dgId, cookie)
                if exsistingChunks == None:
                    exsistingChunks = 0

            file_locations = []
            for filenumber in range(1, exsistingChunks+1):
                file_locations.append(f"chunks/{filenumber}.json")

            payload = {
                "dgId": dgId,
                "newDgId": newDgId,
                "fileLocations": file_locations
            }

            response = requests.post(FILE_HANDLER_COPY_CHUNKS_URL, json=payload, headers=headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while coping chunk and calling the service to copy: {e}")
            return None
        except Exception as e2:
            print(f"An error occurred while coping chunk: {e}")
            return None
    
    def save_chunked_data(self, chunked_data, cookie, dgId, exsistingChunks=0):
        headers = {
            'cookie': cookie,
            'Content-Type': 'application/json'
        }

        for index, chunk in enumerate(chunked_data):
            print("%$%$")
            print(chunk)
            payload = {
                "dg_id": dgId,
                "chunks": chunk,
                "exsistingChunks": exsistingChunks+index+1
            }
            try:
                response = requests.post(FILE_HANDLER_IMPORT_CHUNKS_URL, json=payload, headers=headers)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"An error occurred while uploading chunk: {e}")
                return None
        
        return True

    def get_selected_data_fields(self, dgId:int, cookie:str):
        try:
            data_dict = self.get_validation_data(dgId, cookie)
            validation_rules = data_dict.get("response", {}).get("validationCriteria", {}).get("validationRules", {})
            text_fields = []
            for field, rules in validation_rules.items():
                if rules.get("type") == "text" and rules.get("isDataClass")!=True:
                    text_fields.append(field)
            return text_fields
        except Exception as e:
            print(e)
            return None
    
    def get_validation_data(self, dgId, custom_jwt_cookie):
        try:
            params = {'dgId': dgId}
            headers = {
            'cookie': custom_jwt_cookie
            }
            response = requests.get(GET_VALIDATION_SCHEMA, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None
        
    def get_dataset(self, dg_id, custom_jwt_cookie):
        params = {'dgId': dg_id}
        headers = {
            'cookie': custom_jwt_cookie
        }

        try:
            response = requests.get(FILE_HANDLER_DOWNLOAD_JSON_URL, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None
        
    def get_dataset_by_location(self, fileLocation, custom_jwt_cookie):
        params = {'saveLocation': fileLocation}
        headers = {
            'cookie': custom_jwt_cookie
        }

        try:
            response = requests.get(FILE_HANDLER_DOWNLOAD_LOCATION_JSON_URL, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None
        
    def get_stopwords(self, custom_jwt_cookie):
        headers = {
            'Cookie': custom_jwt_cookie
        }

        try:
            response = requests.get(GET_STOPWORDS_URL, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            if response_data.get("operationSuccessful", False):
                return response_data.get("stopwords", [])
            else:
                return []
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return []

        
    def remove_stop_words(self, data, stop_words):
        try:
            stop_words_set = set(stop_words)
            stop_words_pattern = re.compile(r'\b(' + r'|'.join(re.escape(word) for word in stop_words_set) + r')\b', re.IGNORECASE)

            def clean_text(text):
                return stop_words_pattern.sub('', text).strip()

            cleaned_data = []
            for entry in data:
                entry["rowId"] = int(entry["rowId"])
                cleaned_entry = {key: clean_text(value) if isinstance(value, str) else value for key, value in entry.items()}
                cleaned_data.append(cleaned_entry)

            return cleaned_data
        except Exception as e:
            print(f"Error while removing Stop Words : {e}")
            return None
        
    def get_page_count(self, dg_id, custom_jwt_cookie):
        headers = {
            'cookie': custom_jwt_cookie
        }

        try:
            page_count_url = GET_PAGE_COUNT_URL.replace("dgId",str(dg_id))
            response = requests.get(page_count_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            page_count = data["response"]["data"][0]["numPages"]
            return page_count
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None
    
    def save_aggregrated_data(self, dgId, cookie, aggregratedData):
        headers = {
            'cookie': cookie,
            'Content-Type': 'application/json'
        }

        payload = {
            "dgId": dgId,
            "dataset": aggregratedData
        }
        try:
            response = requests.post(SAVE_JSON_AGGREGRATED_DATA_URL, json=payload, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while uploading aggregrated dataset: {e}")
            return None
        
        return True

    def download_chunk(self, dgId, cookie, pageId):
        params = {'dgId': dgId, 'pageId': pageId}
        headers = {
            'cookie': cookie
        }

        try:

            response = requests.get(DOWNLOAD_CHUNK_URL, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while downloading chunk: {e}")
            return None
        
    def add_row_id(self, structured_data, max_row_id):
        try:
            processed_data = []
            for data in structured_data:
                max_row_id = max_row_id + 1
                data["rowId"] = max_row_id
                processed_data.append(data)
            return processed_data
        except Exception as e:
            print(e)
            return None
        
    def update_preprocess_status(self,dg_id, cookie, processed_data_available, raw_data_available, preprocess_data_location, raw_data_location, enable_allowed, num_samples, num_pages, validationStatus):
        url = STATUS_UPDATE_URL
        
        print(url)
        headers = {
            'Content-Type': 'application/json',
            'Cookie': cookie
        }
        data = {
            "dgId": dg_id,
            "processedDataAvailable": processed_data_available,
            "rawDataAvailable": raw_data_available,
            "preprocessDataLocation": preprocess_data_location,
            "rawDataLocation": raw_data_location,
            "enableAllowed": enable_allowed,
            "numSamples": num_samples,
            "numPages": num_pages,
            "validationStatus": validationStatus
        }

        try:
            print(data)
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None

    def update_dataset_model_status(self,dg_id, cookie):
        url = DATASET_MODEL_STATUS_UPDATE_URL
        
        print(url)
        headers = {
            'Content-Type': 'application/json',
            'Cookie': cookie
        }
        data = {
            "dgId": dg_id
        }

        try:
            print(data)
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None


    def process_handler(self, dgId, newDgId, cookie, updateType, savedFilePath, patchPayload, sessionId):
        print("IN DATASET PROCESSOR PROCESS_HANDLER")
        
        print(MSG_PROCESS_HANDLER_STARTED.format(updateType))
        page_count = self.get_page_count(dgId, cookie)
        print(MSG_PAGE_COUNT.format(page_count))

        if int(sessionId) >= 0:
            session_id = sessionId
        if not session_id:
                return self.generate_response(False, MSG_FAIL)
        
        if page_count > 0 and updateType == 'minor':
            updateType = "minor_append_update"
        elif page_count <= 0 and updateType == 'minor':
            updateType = "minor_initial_update"

        if updateType == "minor_initial_update":
            result = self.handle_minor_initial_update(dgId, newDgId, cookie, savedFilePath, session_id)
        elif updateType == "minor_append_update":
            result = self.handle_minor_append_update(dgId, newDgId, cookie, savedFilePath, session_id)
        elif updateType == "patch":
            result = self.handle_patch_update(dgId, cookie, patchPayload, session_id)
        else:
            print(f"Update TYPE {updateType}")
        
        self.update_progress(cookie, PROGRESS_SUCCESS if result['response']['operationSuccessful'] else PROGRESS_FAIL, MSG_SUCCESS if result['response']['operationSuccessful'] else MSG_FAIL, STATUS_MSG_SUCCESS if result['response']['operationSuccessful'] else STATUS_MSG_FAIL, session_id)
        return result

    def handle_minor_initial_update(self, dgId, newDgId, cookie, savedFilePath, session_id):
        self.update_progress(cookie, PROGRESS_CLEANING_PROCESSING, MSG_CLEANING_PROCESSING, STATUS_MSG_CLEANING_DATASET, session_id)
        
        dataset = self.get_dataset_by_location(savedFilePath, cookie)
        if dataset is None:
            return self.generate_response(False, MSG_FAIL)
        
        structured_data = self.check_and_convert(dataset)
        if structured_data is None:
            return self.generate_response(False, MSG_FAIL)
        
        selected_data_fields_to_enrich = self.get_selected_data_fields(newDgId, cookie)
        if selected_data_fields_to_enrich is None:
            return self.generate_response(False, MSG_FAIL)
        
        max_row_id = max(item["rowId"] for item in structured_data)
        enriched_data = self.enrich_data(structured_data, selected_data_fields_to_enrich, max_row_id)
        if enriched_data is None:
            return self.generate_response(False, MSG_FAIL)
        
        self.update_progress(cookie, PROGRESS_GENERATING_DATA, MSG_GENERATING_DATA, STATUS_MSG_GENERATING_DATA, session_id)
        
        aggregated_dataset = structured_data + enriched_data
        stop_words = self.get_stopwords(cookie)
        if stop_words is None:
            return self.generate_response(False, MSG_FAIL)
        
        cleaned_data = self.remove_stop_words(aggregated_dataset, stop_words)
        if cleaned_data is None:
            return self.generate_response(False, MSG_FAIL)
        
        self.update_progress(cookie, PROGRESS_CHUNKING_UPLOADING, MSG_CHUNKING_UPLOADING, STATUS_MSG_GENERATING_DATA, session_id)
        
        chunked_data = self.chunk_data(cleaned_data)
        if chunked_data is None:
            return self.generate_response(False, MSG_FAIL)
        
        operation_result = self.save_chunked_data(chunked_data, cookie, newDgId, 0)
        if not operation_result:
            return self.generate_response(False, MSG_FAIL)
        
        aggregated_dataset_operation = self.save_aggregrated_data(newDgId, cookie, cleaned_data)
        if not aggregated_dataset_operation:
            return self.generate_response(False, MSG_FAIL)
        
        return_data = self.update_preprocess_status(newDgId, cookie, True, False, f"/dataset/{newDgId}/chunks/", "", True, len(cleaned_data), len(chunked_data), "success")
        return self.generate_response(True, MSG_PROCESS_COMPLETE)

    def handle_minor_append_update(self, dgId, newDgId, cookie, savedFilePath, session_id):
        self.update_progress(cookie, PROGRESS_CLEANING_PROCESSING, MSG_CLEANING_PROCESSING, STATUS_MSG_CLEANING_DATASET, session_id)
        
        aggregated_dataset = self.get_dataset(dgId, cookie)
        if aggregated_dataset is None:
            return self.generate_response(False, MSG_FAIL)
        
        max_row_id = max(item["rowId"] for item in aggregated_dataset)
        minor_update_dataset = self.get_dataset_by_location(savedFilePath, cookie)
        if minor_update_dataset is None:
            return self.generate_response(False, MSG_FAIL)
        
        structured_data = self.check_and_convert(minor_update_dataset)
        if structured_data is None:
            return self.generate_response(False, MSG_FAIL)
        
        structured_data = self.add_row_id(structured_data, max_row_id)
        selected_data_fields_to_enrich = self.get_selected_data_fields(newDgId, cookie)
        if selected_data_fields_to_enrich is None:
            return self.generate_response(False, MSG_FAIL)
        
        enriched_data = self.enrich_data(structured_data, selected_data_fields_to_enrich, max_row_id)
        if enriched_data is None:
            return self.generate_response(False, MSG_FAIL)
        
        self.update_progress(cookie, PROGRESS_GENERATING_DATA, MSG_GENERATING_DATA, STATUS_MSG_GENERATING_DATA, session_id)
        
        stop_words = self.get_stopwords(cookie)
        if stop_words is None:
            return self.generate_response(False, MSG_FAIL)
        
        combined_new_dataset = structured_data + enriched_data
        cleaned_data = self.remove_stop_words(combined_new_dataset, stop_words)
        if cleaned_data is None:
            return self.generate_response(False, MSG_FAIL)
        
        chunked_data = self.chunk_data(cleaned_data)
        if chunked_data is None:
            return self.generate_response(False, MSG_FAIL)
        
        page_count = self.get_page_count(dgId, cookie)
        if page_count is None:
            return self.generate_response(False, MSG_FAIL)
        
        copy_existing_files = self.copy_chunked_datafiles(dgId, newDgId, cookie, page_count)
        if copy_existing_files is None:
            return self.generate_response(False, MSG_FAIL)
        
        operation_result = self.save_chunked_data(chunked_data, cookie, newDgId, page_count)
        if not operation_result:
            return self.generate_response(False, MSG_FAIL)
        
        aggregated_dataset += cleaned_data
        aggregated_dataset_operation = self.save_aggregrated_data(newDgId, cookie, aggregated_dataset)
        if not aggregated_dataset_operation:
            return self.generate_response(False, MSG_FAIL)
        
        return_data = self.update_preprocess_status(newDgId, cookie, True, False, f"/dataset/{newDgId}/chunks/", "", True, len(aggregated_dataset), (len(chunked_data) + page_count), "success")
        return self.generate_response(True, MSG_PROCESS_COMPLETE)

    def handle_patch_update(self, dgId, cookie, patchPayload, session_id):
        decoded_string = urllib.parse.unquote(patchPayload)
        data_payload = json.loads(decoded_string)
        
        if data_payload["editedData"]:
            self.update_progress(cookie, PROGRESS_CLEANING_PROCESSING, MSG_CLEANING_PROCESSING, STATUS_MSG_CLEANING_DATASET, session_id)
            stop_words = self.get_stopwords(cookie)
            if stop_words is None:
                return self.generate_response(False, MSG_FAIL)
            
            cleaned_patch_payload = self.remove_stop_words(data_payload["editedData"], stop_words)
            if cleaned_patch_payload is None:
                return self.generate_response(False, MSG_FAIL)
            
            page_count = self.get_page_count(dgId, cookie)
            if page_count is None:
                return self.generate_response(False, MSG_FAIL)
            
            chunk_updates = self.prepare_chunk_updates(cleaned_patch_payload)
            if chunk_updates is None:
                return self.generate_response(False, MSG_FAIL)
            
            for chunk_num, entries in chunk_updates.items():
                chunk_data = self.download_chunk(dgId, cookie, chunk_num)
                if chunk_data is None:
                    return self.generate_response(False, MSG_FAIL)
                
                for entry in entries:
                    row_id = int(entry.get("rowId"))
                    for idx, chunk_entry in enumerate(chunk_data):
                        if chunk_entry.get("rowId") == row_id:
                            chunk_data[idx] = entry
                            break
                
                chunk_save_operation = self.save_chunked_data([chunk_data], cookie, dgId, chunk_num - 1)
                if chunk_save_operation is None:
                    return self.generate_response(False, MSG_FAIL)
            
            aggregated_dataset = self.get_dataset(dgId, cookie)
            if aggregated_dataset is None:
                return self.generate_response(False, MSG_FAIL)
            
            for entry in cleaned_patch_payload:
                row_id = int(entry.get("rowId"))
                for index, item in enumerate(aggregated_dataset):
                    if item.get("rowId") == row_id:
                        aggregated_dataset[index] = entry
                        break
            
            save_result_update = self.save_aggregrated_data(dgId, cookie, aggregated_dataset)
            if not save_result_update:
                return self.generate_response(False, MSG_FAIL)
        
        if data_payload["deletedDataRows"]:
            self.update_progress(cookie, PROGRESS_CLEANING_PROCESSING, MSG_CLEANING_PROCESSING, STATUS_MSG_CLEANING_DATASET, session_id)
            deleted_rows = data_payload["deletedDataRows"]
            aggregated_dataset = self.get_dataset(dgId, cookie)
            if aggregated_dataset is None:
                return self.generate_response(False, MSG_FAIL)
            
            initial_chunk_count = (len(aggregated_dataset) + CHUNK_SIZE - 1) // CHUNK_SIZE
            
            updated_dataset = [row for row in aggregated_dataset if row.get('rowId') not in deleted_rows]

            updated_chunk_count = (len(updated_dataset) + CHUNK_SIZE - 1) // CHUNK_SIZE

            updated_dataset = self.reindex_dataset(updated_dataset)
            if updated_dataset is None:
                return self.generate_response(False, MSG_FAIL)
            
            chunked_data = self.chunk_data(updated_dataset)
            if chunked_data is None:
                return self.generate_response(False, MSG_FAIL)

            if initial_chunk_count > updated_chunk_count:
                empty_chunk_count = initial_chunk_count - updated_chunk_count
                for _ in range(empty_chunk_count):
                    chunked_data.append([])

            operation_result = self.save_chunked_data(chunked_data, cookie, dgId, 0)
            if not operation_result:
                return self.generate_response(False, MSG_FAIL)
            
            save_result_delete = self.save_aggregrated_data(dgId, cookie, updated_dataset)
            if not save_result_delete:
                return self.generate_response(False, MSG_FAIL)
        return_data = self.update_preprocess_status(dgId, cookie, True, False, f"/dataset/{dgId}/chunks/", "", True, len(updated_dataset), updated_chunk_count, "success")
        update_dataset_model_response = self.update_dataset_model_status(dgId, cookie)
        return self.generate_response(True, MSG_PROCESS_COMPLETE)

    def get_session_id(self, dgId, cookie):
        headers = {'Cookie': cookie}
        try:
            response = requests.get(GET_PROGRESS_SESSIONS_URL, headers=headers)
            response.raise_for_status()
            sessions = response.json().get("response", {}).get("data", [])
            print("Sessions")
            print(sessions)
            for session in sessions:
                if session['dgId'] == dgId:
                    return session['id']
            return None
        except requests.exceptions.RequestException as e:
            print(e)
            print(MSG_FAIL)
            return None

    def update_progress(self, cookie, progress, message, status, session_id):

        if progress == PROGRESS_SUCCESS or progress == PROGRESS_FAIL:
            process_complete = True
        else:
            process_complete = False

        url = UPDATE_PROGRESS_SESSION_URL
        headers = {'Content-Type': 'application/json', 'Cookie': cookie}
        payload = {
            'sessionId': int(session_id),
            'validationStatus': status,
            'validationMessage': message,
            'progressPercentage': progress,
            'processComplete': process_complete
        }
        try:
            print(f"Progress Update > {payload}")
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(e)
            print(MSG_FAIL)
            return None

    def generate_response(self, success, message):
        return {
            'response': {
                'operationSuccessful': success,
                'message': message
            }
        }

    def prepare_chunk_updates(self, cleaned_patch_payload):
        try:
            chunk_updates = {}
            for entry in cleaned_patch_payload:
                row_id = int(entry.get("rowId"))
                chunk_num = (row_id - 1) // 5 + 1
                if chunk_num not in chunk_updates:
                    chunk_updates[chunk_num] = []
                chunk_updates[chunk_num].append(entry)
            return chunk_updates
        except Exception as e:
            print(e)
            print(MSG_FAIL)
            return None

    def reindex_dataset(self, dataset):
        try:
            for idx, row in enumerate(dataset, start=1):
                row['rowId'] = idx
            return dataset
        except Exception as e:
            print(e)
            print(MSG_FAIL)
            return None