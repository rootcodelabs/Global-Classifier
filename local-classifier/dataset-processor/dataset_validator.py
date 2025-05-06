import os
import re
import json
import requests
import urllib.parse
import datetime
from constants import *

class DatasetValidator:
    def __init__(self):
        pass

    def process_request(self, dgId, newDgId, cookie, updateType, savedFilePath, patchPayload=None):
        print(MSG_PROCESS_REQUEST_STARTED)
        print(f"dgId: {dgId}, updateType: {updateType}, savedFilePath: {savedFilePath}")

        if updateType == "minor":
            metadata = self.get_datagroup_metadata(newDgId, cookie)
            if not metadata:
                return self.generate_response(False, MSG_REQUEST_FAILED.format("Metadata"), None)
            session_id = self.create_progress_session(metadata, cookie, False)
            print(f"Progress Session ID : {session_id}")
            if not session_id:
                return self.generate_response(False, MSG_REQUEST_FAILED.format("Progress session creation"), None)
        elif updateType == "patch":
            metadata = self.get_datagroup_metadata(dgId, cookie)
            if not metadata:
                return self.generate_response(False, MSG_REQUEST_FAILED.format("Metadata"), None)

            session_id = self.create_progress_session(metadata, cookie, True)
            print(f"Progress Session ID : {session_id}")
            if not session_id:
                return self.generate_response(False, MSG_REQUEST_FAILED.format("Progress session creation"), None)
        else:
            return self.generate_response(False, "Unknown update type", None)

        try:
            # Initializing dataset processing
            self.update_progress(cookie, PROGRESS_INITIATING, MSG_INIT_VALIDATION, STATUS_MSG_VALIDATION_INIT, session_id)

            if updateType == "minor":
                result = self.handle_minor_update(dgId, cookie, savedFilePath, session_id)
            elif updateType == "patch":
                result = self.handle_patch_update(dgId, cookie, patchPayload, session_id)
            else:
                result = self.generate_response(False, "Unknown update type", None)

            if result["response"]["operationSuccessful"] == True:
                # Final progress update upon successful completion
                self.update_progress(cookie, PROGRESS_VALIDATION_COMPLETE, MSG_VALIDATION_SUCCESS, STATUS_MSG_VALIDATION_INPROGRESS, session_id)
            return result
        except Exception as e:
            self.update_progress(cookie, PROGRESS_FAIL, MSG_INTERNAL_ERROR.format(e), STATUS_MSG_FAIL, session_id)
            return self.generate_response(False, MSG_INTERNAL_ERROR.format(e), None)

    def handle_minor_update(self, dgId, cookie, savedFilePath, session_id):
        try:
            print(MSG_HANDLING_MINOR_UPDATE)
            self.update_progress(cookie, 10, MSG_DOWNLOADING_DATASET, STATUS_MSG_VALIDATION_INPROGRESS, session_id)
            data = self.get_dataset_by_location(savedFilePath, cookie)
            if data is None:
                self.update_progress(cookie, PROGRESS_FAIL, "Failed to download and load data", STATUS_MSG_FAIL, session_id)
                return self.generate_response(False, "Failed to download and load data", None)
            print("Data downloaded and loaded successfully")

            self.update_progress(cookie, 20, MSG_FETCHING_VALIDATION_CRITERIA, STATUS_MSG_VALIDATION_INPROGRESS, session_id)
            validation_criteria, class_hierarchy = self.get_validation_criteria(dgId, cookie)
            if validation_criteria is None:
                self.update_progress(cookie, PROGRESS_FAIL, "Failed to get validation criteria", STATUS_MSG_FAIL, session_id)
                return self.generate_response(False, "Failed to get validation criteria", None)
            print("Validation criteria retrieved successfully")

            self.update_progress(cookie, 30, MSG_VALIDATING_FIELDS, STATUS_MSG_VALIDATION_INPROGRESS, session_id)
            field_validation_result = self.validate_fields(data, validation_criteria)
            if not field_validation_result['success']:
                self.update_progress(cookie, PROGRESS_FAIL, field_validation_result['message'], STATUS_MSG_FAIL, session_id)
                return self.generate_response(False, field_validation_result['message'], None)
            print(MSG_VALIDATION_FIELDS_SUCCESS)

            self.update_progress(cookie, 35, MSG_VALIDATING_CLASS_HIERARCHY, STATUS_MSG_VALIDATION_INPROGRESS, session_id)
            hierarchy_validation_result = self.validate_class_hierarchy(data, validation_criteria, class_hierarchy)
            if not hierarchy_validation_result['success']:
                self.update_progress(cookie, PROGRESS_FAIL, hierarchy_validation_result['message'], STATUS_MSG_FAIL, session_id)
                return self.generate_response(False, hierarchy_validation_result['message'], None)
            print(MSG_CLASS_HIERARCHY_SUCCESS)

            print("Minor update processed successfully")
            self.update_progress(cookie, 40, "Minor update processed successfully", STATUS_MSG_VALIDATION_INPROGRESS, session_id)
            return self.generate_response(True, "Minor update processed successfully", session_id)

        except Exception as e:
            print(MSG_INTERNAL_ERROR.format(e))
            self.update_progress(cookie, PROGRESS_FAIL, MSG_INTERNAL_ERROR.format(e), STATUS_MSG_FAIL, session_id)
            return self.generate_response(False, MSG_INTERNAL_ERROR.format(e), None)

    def get_dataset_by_location(self, fileLocation, custom_jwt_cookie):
        print(MSG_DOWNLOADING_DATASET)
        params = {'saveLocation': fileLocation}
        headers = {'cookie': custom_jwt_cookie}
        try:
            response = requests.get(os.getenv("FILE_HANDLER_DOWNLOAD_LOCATION_JSON_URL"), params=params, headers=headers)
            response.raise_for_status()
            print("Dataset downloaded successfully")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(MSG_REQUEST_FAILED.format("Dataset download"))
            print(e)
            return None

    def get_validation_criteria(self, dgId, cookie):
        print(MSG_FETCHING_VALIDATION_CRITERIA)
        params = {'dgId': dgId}
        headers = {'cookie': cookie}
        try:
            response = requests.get(os.getenv("GET_VALIDATION_SCHEMA"), params=params, headers=headers)
            response.raise_for_status()
            print("Validation criteria fetched successfully")
            validation_criteria = response.json().get('response', {}).get('validationCriteria', {})
            class_hierarchy = response.json().get('response', {}).get('classHierarchy', {})
            return validation_criteria, class_hierarchy
        except requests.exceptions.RequestException as e:
            print(MSG_REQUEST_FAILED.format("Validation criteria fetch"))
            return None

    def validate_fields(self, data, validation_criteria):
        print(MSG_VALIDATING_FIELDS)
        try:
            fields = validation_criteria.get('fields', [])
            validation_rules = validation_criteria.get('validationRules', {})

            for field in fields:
                if field not in data[0]:
                    print(MSG_MISSING_FIELD.format(field))
                    return {'success': False, 'message': MSG_MISSING_FIELD.format(field)}
                if field.lower() == "rowid":
                    print(MSG_ROWID_CANNOT_BE_A_FIELD)
                    return {'success': False, 'message': MSG_ROWID_CANNOT_BE_A_FIELD}


            for idx, row in enumerate(data):
                for field, rules in validation_rules.items():
                    if field in row:
                        value = row[field]
                        if not self.validate_value(value, rules['type']):
                            if value is not None:
                                print(MSG_VALIDATION_FIELD_FAIL.format(field, idx + 1))
                                return {'success': False, 'message': MSG_VALIDATION_FIELD_FAIL.format(field, idx + 1)}
            print(MSG_VALIDATION_FIELDS_SUCCESS)
            return {'success': True, 'message': MSG_VALIDATION_FIELDS_SUCCESS}
        except Exception as e:
            print(MSG_INTERNAL_ERROR.format(e))
            return {'success': False, 'message': MSG_INTERNAL_ERROR.format(e)}

    def validate_value(self, value, value_type):
        if value_type == 'email':
            return re.match(r"[^@]+@[^@]+\.[^@]+", value) is not None
        elif value_type == 'text' or value_type == 'file_attachments':
            return isinstance(value, str)
        elif value_type == 'numbers':
            if isinstance(value, (int, float)):
                return True
            else:
                try:
                    float(value)
                    return True
                except ValueError:
                    return False
        elif value_type == 'datetime':
            try:
                datetime.datetime.fromisoformat(value)
                return True
            except ValueError:
                return False
        return False

    def validate_class_hierarchy(self, data, validation_criteria, class_hierarchy):
        print(MSG_VALIDATING_CLASS_HIERARCHY)
        try:
            data_class_columns = [field for field, rules in validation_criteria.get('validationRules', {}).items() if rules.get('isDataClass', False)]

            hierarchy_values = self.extract_hierarchy_values(class_hierarchy)
            data_values = self.extract_data_class_values(data, data_class_columns)

            missing_in_hierarchy = data_values - hierarchy_values
            missing_in_hierarchy = [item for item in missing_in_hierarchy if item is not None]
            missing_in_data = hierarchy_values - data_values

            if missing_in_hierarchy:
                print(MSG_CLASS_HIERARCHY_FAIL.format("class hierarchy", missing_in_hierarchy))
                return {'success': False, 'message': MSG_CLASS_HIERARCHY_FAIL.format("class hierarchy", missing_in_hierarchy)}
            if missing_in_data:
                print(MSG_CLASS_HIERARCHY_FAIL.format("data class columns", missing_in_data))
                return {'success': False, 'message': MSG_CLASS_HIERARCHY_FAIL.format("data class columns", missing_in_data)}

            print(MSG_CLASS_HIERARCHY_SUCCESS)
            return {'success': True, 'message': MSG_CLASS_HIERARCHY_SUCCESS}
        except Exception as e:
            print(MSG_INTERNAL_ERROR.format(e))
            return {'success': False, 'message': MSG_INTERNAL_ERROR.format(e)}

    def extract_hierarchy_values(self, hierarchy):
        print(MSG_EXTRACTING_HIERARCHY_VALUES)
        values = set()

        def traverse(node):
            if 'class' in node:
                values.add(node['class'])
            if 'subclasses' in node:
                for subclass in node['subclasses']:
                    traverse(subclass)

        for item in hierarchy:
            traverse(item)
        print(f"Hierarchy values extracted: {values}")
        return values

    def extract_data_class_values(self, data, columns):
        print(MSG_EXTRACTING_DATA_CLASS_VALUES)
        values = set()
        for row in data:
            for col in columns:
                values.add(row.get(col))
        print(f"Data class values extracted: {values}")
        return values

    def handle_patch_update(self, dgId, cookie, patchPayload, session_id):
        print(MSG_HANDLING_PATCH_UPDATE)
        min_label_value = 1

        try:
            # Start with a small progress value
            self.update_progress(cookie, 5, MSG_FETCHING_VALIDATION_CRITERIA, STATUS_MSG_VALIDATION_INPROGRESS, session_id)
            validation_criteria, class_hierarchy = self.get_validation_criteria(dgId, cookie)
            if validation_criteria is None:
                self.update_progress(cookie, PROGRESS_FAIL, "Failed to get validation criteria", STATUS_MSG_FAIL, session_id)
                return self.generate_response(False, "Failed to get validation criteria", None)

            if patchPayload is None:
                self.update_progress(cookie, PROGRESS_FAIL, "No patch payload provided", STATUS_MSG_FAIL, session_id)
                return self.generate_response(False, "No patch payload provided", None)

            decoded_patch_payload = urllib.parse.unquote(patchPayload)
            patch_payload_dict = json.loads(decoded_patch_payload)

            edited_data = patch_payload_dict.get("editedData", [])

            if edited_data:
                self.update_progress(cookie, 10, "Processing edited data", STATUS_MSG_VALIDATION_INPROGRESS, session_id)
                for row in edited_data:
                    row_id = row.pop("rowId", None)
                    if row_id is None:
                        self.update_progress(cookie, PROGRESS_FAIL, "Missing rowId in edited data", STATUS_MSG_FAIL, session_id)
                        return self.generate_response(False, "Missing rowId in edited data", None)

                    for key, value in row.items():
                        if key not in validation_criteria['validationRules']:
                            self.update_progress(cookie, PROGRESS_FAIL, f"Invalid field: {key}", STATUS_MSG_FAIL, session_id)
                            return self.generate_response(False, f"Invalid field: {key}", None)

                        if not self.validate_value(value, validation_criteria['validationRules'][key]['type']):
                            self.update_progress(cookie, PROGRESS_FAIL, f"Validation failed for field type '{key}' in row {row_id}", STATUS_MSG_FAIL, session_id)
                            return self.generate_response(False, f"Validation failed for field type '{key}' in row {row_id}", None)

                self.update_progress(cookie, 20, "Validating data class hierarchy", STATUS_MSG_VALIDATION_INPROGRESS, session_id)
                data_class_columns = [field for field, rules in validation_criteria['validationRules'].items() if rules.get('isDataClass', False)]
                hierarchy_values = self.extract_hierarchy_values(class_hierarchy)
                for row in edited_data:
                    for col in data_class_columns:
                        if row.get(col) and row[col] not in hierarchy_values:
                            self.update_progress(cookie, PROGRESS_FAIL, f"New class '{row[col]}' does not exist in the schema hierarchy", STATUS_MSG_FAIL, session_id)
                            return self.generate_response(False, f"New class '{row[col]}' does not exist in the schema hierarchy", None)

                self.update_progress(cookie, 30, "Downloading aggregated dataset", STATUS_MSG_VALIDATION_INPROGRESS, session_id)
                aggregated_data = self.get_dataset_by_location(f"/dataset/{dgId}/primary_dataset/dataset_{dgId}_aggregated.json", cookie)
                if aggregated_data is None:
                    self.update_progress(cookie, PROGRESS_FAIL, "Failed to download aggregated dataset", STATUS_MSG_FAIL, session_id)
                    return self.generate_response(False, "Failed to download aggregated dataset", None)

                self.update_progress(cookie, 35, "Checking label counts for edited data", STATUS_MSG_VALIDATION_INPROGRESS, session_id)
                if not self.check_label_counts(aggregated_data, edited_data, data_class_columns, min_label_value):
                    self.update_progress(cookie, PROGRESS_FAIL, "Editing this data will cause the dataset to have insufficient data examples for one or more labels.", STATUS_MSG_FAIL, session_id)
                    return self.generate_response(False, "Editing this data will cause the dataset to have insufficient data examples for one or more labels.", None)

            deleted_data_rows = patch_payload_dict.get("deletedDataRows", [])
            if deleted_data_rows:
                self.update_progress(cookie, 40, "Processing deleted data rows", STATUS_MSG_VALIDATION_INPROGRESS, session_id)
                if 'aggregated_data' not in locals():
                    aggregated_data = self.get_dataset_by_location(f"/dataset/{dgId}/primary_dataset/dataset_{dgId}_aggregated.json", cookie)
                    if aggregated_data is None:
                        self.update_progress(cookie, PROGRESS_FAIL, "Failed to download aggregated dataset", STATUS_MSG_FAIL, session_id)
                        return self.generate_response(False, "Failed to download aggregated dataset", None)

                data_class_columns = [field for field, rules in validation_criteria['validationRules'].items() if rules.get('isDataClass', False)]

                self.update_progress(cookie, 45, "Checking label counts after deletion", STATUS_MSG_VALIDATION_INPROGRESS, session_id)
                if not self.check_label_counts_after_deletion(aggregated_data, deleted_data_rows, data_class_columns, min_label_value):
                    self.update_progress(cookie, PROGRESS_FAIL, "Deleting this data will cause the dataset to have insufficient data examples for one or more labels.", STATUS_MSG_FAIL, session_id)
                    return self.generate_response(False, "Deleting this data will cause the dataset to have insufficient data examples for one or more labels.", None)

            self.update_progress(cookie, PROGRESS_VALIDATION_COMPLETE, MSG_PATCH_UPDATE_SUCCESS, STATUS_MSG_VALIDATION_INPROGRESS, session_id)
            return self.generate_response(True, MSG_PATCH_UPDATE_SUCCESS, session_id)

        except Exception as e:
            print(MSG_INTERNAL_ERROR.format(e))
            self.update_progress(cookie, PROGRESS_FAIL, MSG_INTERNAL_ERROR.format(e), STATUS_MSG_FAIL, session_id)
            return self.generate_response(False, MSG_INTERNAL_ERROR.format(e), None)


    def check_label_counts(self, aggregated_data, edited_data, data_class_columns, min_label_value):
        # Aggregate data class values from edited data
        edited_values = {col: set() for col in data_class_columns}
        for row in edited_data:
            for col in data_class_columns:
                if col in row:
                    edited_values[col].add(row[col])

        # Aggregate counts from the existing dataset
        class_counts = {col: {} for col in data_class_columns}
        for row in aggregated_data:
            for col in data_class_columns:
                value = row.get(col)
                if value:
                    class_counts[col][value] = class_counts[col].get(value, 0) + 1

        # Add counts from the edited data
        for col, values in edited_values.items():
            for value in values:
                class_counts[col][value] = class_counts[col].get(value, 0) + 1

        # Check the counts against min_label_value
        for col, counts in class_counts.items():
            for value, count in counts.items():
                if count < min_label_value:
                    return False
        return True

    def check_label_counts_after_deletion(self, aggregated_data, deleted_data_rows, data_class_columns, min_label_value):
        # Aggregate counts from the existing dataset
        class_counts = {col: {} for col in data_class_columns}
        for row in aggregated_data:
            for col in data_class_columns:
                value = row.get(col)
                if value:
                    class_counts[col][value] = class_counts[col].get(value, 0) + 1

        # Subtract counts from the deleted data
        for row_id in deleted_data_rows:
            for row in aggregated_data:
                if row.get('rowId') == row_id:
                    for col in data_class_columns:
                        value = row.get(col)
                        if value:
                            class_counts[col][value] = class_counts[col].get(value, 0) - 1

        # Check the counts against min_label_value
        for col, counts in class_counts.items():
            for value, count in counts.items():
                if count < min_label_value:
                    return False
        return True

    def generate_response(self, success, message, session_id):
        print(MSG_GENERATING_RESPONSE.format(success, message))
        return {
            'response': {
                'operationSuccessful': success,
                'message': message,
                'sessionId': session_id
            }
        }

    def get_datagroup_metadata(self, dgId, cookie):
        url = GET_DATAGROUP_METADATA_URL.replace('dgId', str(dgId))
        headers = {'Cookie': cookie}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(e)
            print(MSG_REQUEST_FAILED.format("Metadata fetch"))
            return None

    def create_progress_session(self, metadata, cookie, patch_update_needed):
        print(f"METADATA : >>>>>>>>>> {metadata}")
        if patch_update_needed:
            patch_number = int(metadata['response']['data'][0]['patchVersion'])+1
        else:
            patch_number = int(metadata['response']['data'][0]['patchVersion'])

        url = CREATE_PROGRESS_SESSION_URL
        headers = {'Content-Type': 'application/json', 'Cookie': cookie}
        payload = {
            'dgId': metadata['response']['data'][0]['dgId'],
            'groupName': metadata['response']['data'][0]['name'],
            'majorVersion': metadata['response']['data'][0]['majorVersion'],
            'minorVersion': metadata['response']['data'][0]['minorVersion'],
            'patchVersion': patch_number,
            'latest': metadata['response']['data'][0]['latest']
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json().get('response', {})
            session_id = response_data.get('sessionId')
            return session_id
        except requests.exceptions.RequestException as e:
            print(MSG_REQUEST_FAILED.format("Progress session creation"))
            print(f"Progress session creation failed due to : {e}")
            return None

    def update_progress(self, cookie, progress, message, status, session_id=None):

        if progress == PROGRESS_FAIL:
            process_complete = True
        else:
            process_complete = False

        url = UPDATE_PROGRESS_SESSION_URL
        headers = {'Content-Type': 'application/json', 'Cookie': cookie}
        payload = {
            'sessionId': session_id,
            'validationStatus': status,
            'validationMessage': message,
            'progressPercentage': progress,
            'processComplete': process_complete
        }
        try:
            print(f"Update Payload : {payload}")
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"Response : {response}")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Progress update error : {e}")
            print(MSG_REQUEST_FAILED.format("Progress update"))
            return None
