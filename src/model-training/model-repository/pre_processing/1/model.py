import json
import numpy as np
import triton_python_backend_utils as pb_utils
from transformers import AutoTokenizer
import os


class TritonPythonModel:
    """
    Enhanced text preprocessing model for text classification with OOD detection support
    Handles tokenization for BERT, RoBERTa, XLM, and DistilBERT models
    Supports both regular and OOD-enhanced models
    """

    def initialize(self, args):
        """Initialize tokenizer and model configuration based on database info"""

        model_path = args["model_repository"]
        model_config = json.loads(args["model_config"])
        if "parameters" in model_config:
            for param in model_config["parameters"]:
                key = param["key"]
                if "string_value" in param["value"]:
                    self.params[key] = param["value"]["string_value"]
        label_file = os.path.join(model_path, "1", "label_mappings.json")

        self.logger = pb_utils.Logger

        # Load model configuration from database info (optional for regular models)
        try:
            self.model_config = self.get_model_config_from_db()

            # Extract model information
            self.model_name = self.params.get("model_name", None)
            self.max_length = self.params.get("sequence_length", None)
            self.ood_method = self.params.get(
                "ood_method", None
            )  # None, "energy", "sngp", "softmax"
            self.base_model_type = self.params.get(
                "base_model_type", None
            )  # estbert, xlm-roberta, mdistilbert

            self.logger.log_info(f"Model config loaded - Model: {self.model_name}")
            self.logger.log_info(f"Base model type: {self.base_model_type}")
            self.logger.log_info(f"OOD method: {self.ood_method}")
            self.logger.log_info(f"Max sequence length: {self.max_length}")

        except Exception as e:
            # Graceful fallback for regular models without model_config.json
            self.logger.log_info(
                f"No model config found ({e}) - using fallback configuration"
            )

        # Load label mappings for additional context (optional)
        try:
            with open(label_file, "r") as f:
                self.label_mappings = json.load(f)
            self.num_classes = self.label_mappings.get("num_classes", 2)
            self.logger.log_info(
                f"Loaded label mappings with {self.num_classes} classes"
            )
        except Exception as e:
            self.logger.log_info(f"No label mappings found ({e})")

        # Initialize tokenizer based on model type
        self.tokenizer = self._initialize_tokenizer()
        self.requires_token_type_ids = True

    def _initialize_tokenizer(self):
        """Initialize appropriate tokenizer based on model configuration"""
        try:
            tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.logger.log_info(f"Loaded tokenizer for {self.model_name}")
            return tokenizer
        except Exception as e:
            self.logger.log_warn(f"Failed to load tokenizer for {self.model_name}: {e}")

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
            batch_token_type_ids = []

            for text in texts:
                # Handle different text formats
                if isinstance(text, bytes):
                    text = text.decode("utf-8")
                elif isinstance(text, np.ndarray):
                    text = str(text.item())
                else:
                    text = str(text)

                # Tokenize with appropriate parameters
                tokenize_params = {
                    "text": text,
                    "add_special_tokens": True,
                    "max_length": self.max_length,
                    "padding": "max_length",
                    "truncation": True,
                    "return_attention_mask": True,
                    "return_tensors": "np",
                }

                # Only add token_type_ids for models that support it
                if self.requires_token_type_ids:
                    tokenize_params["return_token_type_ids"] = True

                encoding = self.tokenizer(**tokenize_params)

                batch_input_ids.append(encoding["input_ids"][0])
                batch_attention_mask.append(encoding["attention_mask"][0])

                if self.requires_token_type_ids:
                    batch_token_type_ids.append(encoding["token_type_ids"][0])
                else:
                    # Create dummy token_type_ids for consistency
                    batch_token_type_ids.append(np.zeros_like(encoding["input_ids"][0]))

            # Convert to numpy arrays
            input_ids = np.array(batch_input_ids, dtype=np.int64)
            attention_mask = np.array(batch_attention_mask, dtype=np.int64)
            token_type_ids = np.array(batch_token_type_ids, dtype=np.int64)

            # Create output tensors
            output_tensors = [
                pb_utils.Tensor("input_ids", input_ids),
                pb_utils.Tensor("attention_mask", attention_mask),
                pb_utils.Tensor("token_type_ids", token_type_ids),
            ]

            # Add additional tensors for OOD methods if needed
            if self.ood_method == "sngp":
                training_flag = np.array([False], dtype=bool)
                output_tensors.append(pb_utils.Tensor("training", training_flag))
                self.logger.log_info("Added training flag tensor for SNGP")
            # For regular models or other OOD methods, no additional tensors needed

            response = pb_utils.InferenceResponse(output_tensors=output_tensors)
            responses.append(response)

        return responses

    def finalize(self):
        """Clean up resources"""
        pass
