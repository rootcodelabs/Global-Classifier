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

        # Store args for later use and handle different argument formats
        self.args = args
        self.logger = pb_utils.Logger
        try:
            # Handle different argument formats that Triton might pass
            if isinstance(args, dict):
                model_path = args.get("model_repository", "")
            else:
                # Fallback if args is not a dict
                model_path = str(args)

        except Exception as e:
            self.logger.log_warn(f"Warning: Failed to parse args in initialize: {e}")

        label_file = os.path.join(model_path, "1", "label_mappings.json")

        # Load model configuration parameters with safe defaults

        # Load label mappings for additional context (optional)
        try:
            with open(label_file, "r") as f:
                self.label_mappings = json.load(f)
            self.num_classes = self.label_mappings.get("num_classes", 2)
            self.model_name = self.label_mappings.get("model_name", None)
            self.base_model_type = self.label_mappings.get("base_model_name", None)
            self.max_length = self.label_mappings.get("sequence_length", 512)
            self.logger.log_info(
                f"Loaded label mappings with {self.num_classes} classes"
            )
        except Exception as e:
            self.logger.log_info(f"No label mappings found ({e})")

        # Initialize tokenizer based on model type
        self.tokenizer = self._initialize_tokenizer()

        self.requires_token_type_ids = self._model_supports_token_type_ids()

        if hasattr(self.logger, "log_info"):
            self.logger.log_info(
                f"Token type IDs required: {self.requires_token_type_ids}"
            )
        else:
            print(f"Token type IDs required: {self.requires_token_type_ids}")

    def _model_supports_token_type_ids(self):
        """
        Check if the base model supports token_type_ids based on model type
        """
        # Clean the model type name
        model_type = self.base_model_type.lower()
        if "multilingual-" in model_type:
            model_type = model_type.replace("multilingual-", "")

        # Models that explicitly reject token_type_ids
        if model_type in ["distilbert"]:
            return False

        # Models that use token_type_ids
        if model_type in ["bert"]:
            return True

        if model_type in ["xlm-roberta", "roberta"]:
            return True

        # Fallback: try to detect from tokenizer
        try:
            if hasattr(self.tokenizer, "model_max_length"):
                # Test tokenization to see if token_type_ids are returned
                test_encoding = self.tokenizer(
                    "test", return_token_type_ids=True, return_tensors="np"
                )
                return "token_type_ids" in test_encoding
        except Exception as e:
            self.logger.log_warn(f"Token type ID detection failed: {e}")

        return False

    def _initialize_tokenizer(self):
        """Initialize appropriate tokenizer based on model configuration"""
        try:
            # Try to load from the model directory first

            tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.logger.log_info(f"Loaded tokenizer for {self.model_name}")

            return tokenizer
        except Exception as e:
            self.logger.log_error(
                f"Failed to load tokenizer for {self.model_name}: {e}"
            )

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

                try:
                    encoding = self.tokenizer(**tokenize_params)
                except Exception as e:
                    self.logger.log_error(
                        f"Tokenization failed for text: {text[:50]}... Error: {e}"
                    )
                    # Create fallback encoding
                    encoding = {
                        "input_ids": np.zeros((1, self.max_length), dtype=np.int64),
                        "attention_mask": np.zeros(
                            (1, self.max_length), dtype=np.int64
                        ),
                    }
                    if self.requires_token_type_ids:
                        encoding["token_type_ids"] = np.zeros(
                            (1, self.max_length), dtype=np.int64
                        )

                batch_input_ids.append(encoding["input_ids"][0])
                batch_attention_mask.append(encoding["attention_mask"][0])

                if self.requires_token_type_ids and "token_type_ids" in encoding:
                    batch_token_type_ids.append(encoding["token_type_ids"][0])
                else:
                    # Create dummy token_type_ids for consistency (always output them)
                    batch_token_type_ids.append(np.zeros_like(encoding["input_ids"][0]))

            # Convert to numpy arrays with correct dtypes
            input_ids = np.array(batch_input_ids, dtype=np.int64)
            attention_mask = np.array(batch_attention_mask, dtype=np.int64)
            token_type_ids = np.array(batch_token_type_ids, dtype=np.int64)

            # Create output tensors
            output_tensors = [
                pb_utils.Tensor("input_ids", input_ids),
                pb_utils.Tensor("attention_mask", attention_mask),
                pb_utils.Tensor("token_type_ids", token_type_ids),
            ]
            response = pb_utils.InferenceResponse(output_tensors=output_tensors)
            responses.append(response)

        return responses

    def finalize(self):
        """Clean up resources"""
        if hasattr(self, "tokenizer"):
            del self.tokenizer