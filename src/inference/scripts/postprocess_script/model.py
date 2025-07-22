import json
import numpy as np
import triton_python_backend_utils as pb_utils
from scipy.special import softmax
import os

class TritonPythonModel:
    """
    Text postprocessing model for text classification
    Converts logits to top-k predictions with labels and probabilities
    """
    
    def initialize(self, args):
        """Initialize label mappings"""
        
        model_path = args['model_repository']

        # TODO - Convert "label_mappings.json" filename to be retrieved from a config.py config file with the variable name DEFAULT_LABEL_MAPPINGS_FILE
        # TODO - Convert default model version ("1") to be retrieved from config file with variable name DEFAULT_MODEL_VERSION
        # TODO - Implement config file import

        label_file = os.path.join(model_path, "1", "label_mappings.json")
        if os.path.exists(label_file):
            with open(label_file, 'r') as f:
                self.label_mappings = json.load(f)
            
            self.id_to_label = self.label_mappings["id_to_label"]
            self.num_classes = self.label_mappings["num_classes"]
            
            self.logger = pb_utils.Logger
            self.logger.log_info(f"Loaded {self.num_classes} classes for postprocessing")
            

            # TODO - TOP K 5 should be read from a default config file with variable name DEFAULT_TOP_K
            class_names = [self.id_to_label[str(i)] for i in range(min(5, self.num_classes))]
            self.logger.log_info(f"Sample classes: {class_names}")
            
        else:
            # fail if no label mappings found

            #TODO - We need to raise an error here if no label mappings are found and update model training / deployment status to "FAILED"
            self.id_to_label = {"0": "unknown"}
            self.num_classes = 1
            self.logger = pb_utils.Logger
            self.logger.log_warn("No label mappings found, using fallback")

        self.logger.log_info(model_path)
        self.logger.log_info(args["model_name"])
        self.logger.log_info(args["model_repository"])
        self.logger.log_info("Text postprocessing model initialized")
    
    def execute(self, requests):
        """Execute postprocessing on model logits"""
        responses = []
        
        for request in requests:
            logits_tensor = pb_utils.get_input_tensor_by_name(request, "logits")
            logits = logits_tensor.as_numpy()


            # TODO - TOP-K should be read from a config file with variable name DEFAULT_TOP_K            
            top_k = 5
            try:
                top_k_tensor = pb_utils.get_input_tensor_by_name(request, "top_k")
                if top_k_tensor:
                    top_k = int(top_k_tensor.as_numpy()[0])
            except Exception as e:
                self.logger.log_warn(f"Failed to get top_k from request: {e}")
                pass

            top_k = min(top_k, self.num_classes)
            
            probabilities = softmax(logits, axis=1)
            
            batch_size = probabilities.shape[0]
            top_k_results = []
            
            for i in range(batch_size):
                top_k_indices = np.argsort(probabilities[i])[-top_k:][::-1]
                top_k_probs = probabilities[i][top_k_indices]
                
                sample_result = {}
                for rank, (idx, prob) in enumerate(zip(top_k_indices, top_k_probs), 1):
                    label = self.id_to_label.get(str(idx), f"class_{idx}")
                    sample_result[rank] = {label: float(prob)}
                
                top_k_results.append(sample_result)
            
            results_json = json.dumps(top_k_results)
            
            output_tensor = pb_utils.Tensor("TOP_K_PREDICTIONS", 
                                          np.array([results_json], dtype=object))
            
            response = pb_utils.InferenceResponse(output_tensors=[output_tensor])
            responses.append(response)
        
        return responses
    
    def finalize(self):
        """Clean up resources"""
        pass