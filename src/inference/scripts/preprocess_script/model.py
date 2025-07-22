import json
import numpy as np
import triton_python_backend_utils as pb_utils
from transformers import AutoTokenizer
import os

class TritonPythonModel:
    """
    Text preprocessing model for text classification
    Handles tokenization for BERT, RoBERTa, and XLM models
    """
    def __init__(self):


        # TODO - This should be retrieved from the database during initialize 
        # TODO - Liquibase changelogs should be updated to include default model configuratons, tokenizer name and max_lenght
        # TODO - We need to have a ruuter/resql endpoint to retrieve this model_configs
        self.model_configs = {
            "bert": {
                "tokenizer_name": "bert-base-uncased",
                "max_length": 128
            },
            "roberta": {
                "tokenizer_name": "roberta-base",
                "max_length": 512
            },
            "xlm": {
                "tokenizer_name": "xlm-mlm-en-2048",
                "max_length": 512
            }
        }

    def initialize(self, args):
        """Initialize tokenizer based on model type detection"""

        # TODO - MODEL TYPE , TOKENIZER AND MAX LENGTH should be retrieved from the database during initialize        

        model_path = args['model_repository'] 
        label_file = os.path.join(model_path, "1", "label_mappings.json")
        self.logger = pb_utils.Logger
        try:
            with open(label_file, 'r') as f:
                self.label_mappings = json.load(f)


            self.model_type = "bert"
            self.tokenizer_name = "bert-base-uncased"
            self.max_length = 128
        
        except Exception as e:

            #TODO - Incase of an exception we should stop defaulting to BERT and raise an error
            self.logger.log_error(f"Failed to load label mappings or model type: {e}")
            self.model_type = "bert"
            self.tokenizer_name = "bert-base-uncased"
            self.max_length = 128
        # Initialize tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_name)
        
        
        self.logger.log_info(f"Initialized text preprocessing with {self.model_type} tokenizer")
        self.logger.log_info(f"Max length: {self.max_length}")
    

    #TODO - We should get model type by querying the database
    def detect_model_type(self, args):
        """Detect model type based on label mappings or default to BERT"""
        original_metadata = self.label_mappings.get("original_metadata", {})
        model_type = original_metadata.get("model_type", "bert")
        
        if model_type not in self.model_configs: 
            model_type = "bert"
        
        return model_type
    
    
    def execute(self, requests):
        """Execute preprocessing on input texts"""
        responses = []
        
        for request in requests:
            # Get input text
            input_text = pb_utils.get_input_tensor_by_name(request, "TEXT")
            texts = input_text.as_numpy()
            
            # Tokenize all texts in the batch
            batch_input_ids = []
            batch_attention_mask = []
            batch_token_type_ids = []  # Add this line
            
            for text in texts:
                # Handle different text formats
                if isinstance(text, bytes):
                    text = text.decode('utf-8')
                elif isinstance(text, np.ndarray):
                    text = str(text.item())
                else:
                    text = str(text)
                
                encoding = self.tokenizer(
                    text,
                    add_special_tokens=True,
                    max_length=self.max_length,
                    padding='max_length',
                    truncation=True,
                    return_attention_mask=True,
                    return_token_type_ids=True,  
                    return_tensors='np'
                )
                
                batch_input_ids.append(encoding['input_ids'][0])
                batch_attention_mask.append(encoding['attention_mask'][0])
                batch_token_type_ids.append(encoding['token_type_ids'][0]) 
            
            # Convert to numpy arrays
            input_ids = np.array(batch_input_ids, dtype=np.int64)
            attention_mask = np.array(batch_attention_mask, dtype=np.int64)
            token_type_ids = np.array(batch_token_type_ids, dtype=np.int64) 
            
            # Create output tensors
            input_ids_tensor = pb_utils.Tensor("input_ids", input_ids)
            attention_mask_tensor = pb_utils.Tensor("attention_mask", attention_mask)
            token_type_ids_tensor = pb_utils.Tensor("token_type_ids", token_type_ids) 
            
            response = pb_utils.InferenceResponse(
                output_tensors=[input_ids_tensor, attention_mask_tensor, token_type_ids_tensor]
            )
            responses.append(response)
    
        return responses
    
    def finalize(self):
        """Clean up resources"""
        pass