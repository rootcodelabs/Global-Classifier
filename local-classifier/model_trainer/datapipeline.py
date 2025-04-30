import pandas as pd
import requests
from constants import DATA_DOWNLOAD_ENDPOINT,GET_DATASET_METADATA_ENDPOINT,TRAINING_LOGS_PATH
from loguru import logger
logger.add(sink=TRAINING_LOGS_PATH)


class DataPipeline:
    
    def __init__(self, dg_id,cookie):
        
        logger.info(f"DOWNLOADING DATASET WITH DGID - {dg_id}")
        
        cookies = {'customJwtCookie': cookie}
        response = requests.get(DATA_DOWNLOAD_ENDPOINT, params={'dgId': dg_id}, cookies=cookies)

        if response.status_code == 200:
            logger.info("DATA DOWNLOAD SUCCESSFUL")
            data = response.json()
            df = pd.DataFrame(data)
            df = df.drop('rowId', axis=1)
            self.df = df
        else:
            logger.error(f"DATA DOWNLOAD FAILED WITH ERROR CODE: {response.status_code}")
            logger.error(f"RESPONSE: {response.text}")

            raise RuntimeError(f"ERROR RESPONSE {response.text}")

        logger.info(f"###############################################################")
        logger.info(f"****** Calling init function of DataPipeline Class ******")  
        logger.info(f"Endpoint : {GET_DATASET_METADATA_ENDPOINT}") 
        logger.info(f"Cookie : {cookies}")
        logger.info(f"DGID : {dg_id}")
        
        response_hierarchy = requests.get(GET_DATASET_METADATA_ENDPOINT, params={'groupId': dg_id}, cookies=cookies)
        
        logger.info(f"response_hierarchy : {response_hierarchy}")
        
        if response_hierarchy.status_code == 200:
            logger.info("DATASET HIERARCHY RETREIVAL SUCCESSFUL")
            hierarchy = response_hierarchy.json()
            self.hierarchy  = hierarchy['response']['data'][0]

        else:
            logger.error(f"DATASET HIERARCHY RETRIEVAL FAILED: {response_hierarchy.status_code}")
            logger.error(f"RESPONSE: {response.text}")
            raise RuntimeError(f"ERROR RESPONSE\n {response_hierarchy.text}")
    
    def extract_input_columns(self):
        
        validation_rules = self.hierarchy['validationCriteria']['validationRules']

        input_columns = [key for key, value in validation_rules.items() if value['isDataClass'] == False]
        return input_columns
    
    def models_and_filters(self):
        data = self.hierarchy['classHierarchy']
        models = []
        filters = []
        model_num = 1

        if len(data) >= 2:
            top_level_classes = [node['class'] for node in data]
            models.append({model_num: top_level_classes})
            filters.append([top_level_classes])
            model_num += 1

        def traverse(node, current_filters):
            nonlocal model_num
            if node.get('subclasses'):
                if len(node['subclasses']) >= 2:
                    class_names = [subclass['class'] for subclass in node['subclasses']]
                    models.append({node['class']: class_names})
                    filters.append(current_filters + [[node['class']]] + [class_names])
                    model_num += 1
                for subclass in node['subclasses']:
                    traverse(subclass, current_filters + [[node['class']]])

        for root_node in data:
            traverse(root_node, [])

        return models, filters

    
    def filter_dataframe_by_values(self, filters):
        filtered_df = self.df.copy()
        for filter_list in filters:
            filtered_df = filtered_df[filtered_df.apply(lambda row: any(value in row.values for value in filter_list), axis=1)]
        return filtered_df
    
    def create_dataframes(self):

        logger.info("CREATING DATAFRAME")

        dfs = []
        input_columns = self.extract_input_columns()
        models, filters = self.models_and_filters()
        for i in range(len(models)):
            filtered_df = self.filter_dataframe_by_values(filters[i])
            target_column = self.find_target_column(filtered_df, filters[i][-1])[0]
            filtered_df['input'] = filtered_df[input_columns].apply(lambda row: ' '.join(row.dropna().astype(str)), axis=1)
            filtered_df = filtered_df.rename(columns={target_column: 'target'})
            filtered_df = filtered_df[['input', 'target']]
            filtered_df = filtered_df.dropna()
            dfs.append(filtered_df)
        
        return dfs
    
    def find_target_column(self,df , filter_list):
        
        value_set = set(filter_list)
        columns_with_exact_or_subset_values = []

        for column in df.columns:
            unique_values = set(df[column].dropna().unique())
            if unique_values and unique_values.issubset(value_set):
                columns_with_exact_or_subset_values.append(column)

        return columns_with_exact_or_subset_values