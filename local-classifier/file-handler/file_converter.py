import os
import json
import yaml
import pandas as pd

class FileConverter:
    
    def _detect_file_type(self, filePath):
        if filePath.endswith('.json'):
            return 'json'
        elif filePath.endswith('.yaml') or filePath.endswith('.yml'):
            return 'yaml'
        elif filePath.endswith('.xlsx'):
            return 'xlsx'
        elif filePath.endswith('.txt'):
            return 'txt'
        else:
            return None
    
    def convert_to_json(self, filePath):
        fileType = self._detect_file_type(filePath)
        if fileType is None:
            print(f"Error: Unsupported file type for '{filePath}'")
            return (False, {})
        
        try:
            if fileType == 'json':
                return self._load_json(filePath)
            elif fileType == 'yaml':
                return self._convert_yaml_to_json(filePath)
            elif fileType == 'xlsx':
                return self._convert_xlsx_to_json(filePath)
        except Exception as e:
            print(f"Error processing '{filePath}': {e}")
            return (False, {})
    
    def _load_json(self, filePath):
        try:
            with open(filePath, 'r') as file:
                data = json.load(file)
            return (True, data)
        except Exception as e:
            print(f"Error loading JSON file '{filePath}': {e}")
            return (False, {})
    
    def _convert_yaml_to_json(self, filePath):
        try:
            with open(filePath, 'r') as file:
                data = yaml.safe_load(file)
            return (True, data)
        except Exception as e:
            print(f"Error converting YAML file '{filePath}' to JSON: {e}")
            return (False, {})
    
    # def _convert_xlsx_to_json(self, filePath):
    #     try:
    #         data = pd.read_excel(filePath, sheet_name=None)
    #         jsonData = {sheet: data[sheet].to_dict(orient='records') for sheet in data}
    #         return (True, jsonData)
    #     except Exception as e:
    #         print(f"Error converting XLSX file '{filePath}' to JSON: {e}")
    #         return (False, {})

    def _convert_xlsx_to_json(self, filePath):
        try:
            data = pd.read_excel(filePath, sheet_name=None)
            combined_data = []
            for sheet in data:
                combined_data.extend(data[sheet].to_dict(orient='records'))
            return (True, combined_data)
        except Exception as e:
            print(f"Error converting XLSX file '{filePath}' to JSON: {e}")
            return (False, [])
    
    def convert_json_to_xlsx(self, jsonData, outputPath):
        try:
            if isinstance(jsonData, list):
                df = pd.DataFrame(jsonData)
                with pd.ExcelWriter(outputPath) as writer:
                    df.to_excel(writer, sheet_name='Sheet1', index=False)
            elif isinstance(jsonData, dict):
                with pd.ExcelWriter(outputPath) as writer:
                    for sheetName, data in jsonData.items():
                        if isinstance(data, list):
                            df = pd.DataFrame(data)
                            df.to_excel(writer, sheet_name=sheetName, index=False)
                        else:
                            print(f"Error: Expected list of dictionaries for sheet '{sheetName}', but got {type(data)}")
                            return False
            else:
                print(f"Error: Unsupported JSON data format '{type(jsonData)}'")
                return False
            print(f"JSON data successfully converted to XLSX and saved at '{outputPath}'")
            return True
        except Exception as e:
            print(f"Error converting JSON to XLSX: {e}")
            return False
    
    def convert_json_to_yaml(self, jsonData, outputPath):
        try:
            with open(outputPath, 'w') as file:
                yaml.dump(jsonData, file)
            print(f"JSON data successfully converted to YAML and saved at '{outputPath}'")
            return True
        except Exception as e:
            print(f"Error converting JSON to YAML: {e}")
            return False