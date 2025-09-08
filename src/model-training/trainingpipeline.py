from transformers import (
    XLMRobertaTokenizer,
    XLMRobertaForSequenceClassification,
    Trainer,
    TrainingArguments,
    DistilBertTokenizer,
    DistilBertForSequenceClassification,
    BertForSequenceClassification,
    BertTokenizer,
)
import json
from safetensors.torch import save_file
from torch.utils.data import Dataset
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import torch
import torch.nn as nn
import torch.nn.functional as F
import shutil
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Union
from loki_logger import LokiLogger
from constants import (
    MODEL_CONFIGS,
    SUPPORTED_BASE_MODELS,
    SUPPORTED_OOD_METHODS,
    DEFAULT_OOD_CONFIGS,
    DEFAULT_TRAINING_ARGS,
    MIN_SAMPLES_PER_CLASS,
    TARGET_SAMPLES_FOR_SMALL_DATASETS,
    TEST_SIZE_RATIO,
    SEQUENCE_LENGTH,
)
import os
from transformers import logging as transformers_logging
import warnings

warnings.filterwarnings(
    "ignore",
    message="Some weights of the model checkpoint were not used when initializing",
)
transformers_logging.set_verbosity_error()


logger = LokiLogger(service_name="model-trainer")


class CustomDataset(Dataset):
    def __init__(self, encodings, labels, ood_labels=None):
        self.encodings = encodings
        self.labels = torch.tensor(labels, dtype=torch.long)
        self.ood_labels = (
            torch.tensor(ood_labels, dtype=torch.long)
            if ood_labels is not None
            else None
        )

    def __getitem__(self, idx):
        item = {key: val[idx] for key, val in self.encodings.items()}
        item["labels"] = self.labels[idx]
        if self.ood_labels is not None:
            item["ood_labels"] = self.ood_labels[idx]
        return item

    def __len__(self):
        return len(self.labels)


class SpectralNormalization(nn.Module):
    """Spectral normalization layer for improved uncertainty estimation"""

    def __init__(self, layer, n_power_iterations=1, eps=1e-12):
        super().__init__()
        self.layer = layer
        self.n_power_iterations = n_power_iterations
        self.eps = eps

        # Initialize spectral norm
        with torch.no_grad():
            weight = getattr(layer, "weight")
            h, w = weight.size()
            u = nn.Parameter(torch.randn(h), requires_grad=False)
            v = nn.Parameter(torch.randn(w), requires_grad=False)
            self.register_parameter("u", u)
            self.register_parameter("v", v)

    def forward(self, x):
        if self.training:
            self._update_uv()
        return self.layer(x)

    def _update_uv(self):
        weight = getattr(self.layer, "weight")
        with torch.no_grad():
            for _ in range(self.n_power_iterations):
                self.v.data = F.normalize(
                    torch.mv(weight.t(), self.u), dim=0, eps=self.eps
                )
                self.u.data = F.normalize(torch.mv(weight, self.v), dim=0, eps=self.eps)

            sigma = torch.dot(self.u, torch.mv(weight, self.v))
            weight.data /= sigma


class OODLoss(nn.Module):
    """Combined loss for OOD detection"""

    def __init__(self, ood_weight=0.1, energy_margin=10.0, temperature=1.0):
        super().__init__()
        self.ood_weight = ood_weight
        self.energy_margin = energy_margin
        self.temperature = temperature
        self.ce_loss = nn.CrossEntropyLoss()

    def forward(self, logits, labels, ood_labels=None):
        # Standard classification loss
        ce_loss = self.ce_loss(logits, labels)

        if ood_labels is None:
            return ce_loss

        # Energy-based OOD loss
        energy = -torch.logsumexp(logits / self.temperature, dim=-1)

        # Separate ID and OOD samples
        is_ood = (ood_labels == 1).float()
        is_id = 1.0 - is_ood

        # Energy loss: low energy for ID, high energy for OOD
        energy_loss = (
            torch.relu(self.energy_margin - energy) * is_ood  # High energy for OOD
            + energy * is_id  # Low energy for ID
        )

        total_loss = ce_loss + self.ood_weight * energy_loss.mean()
        return total_loss


class EnhancedModel(nn.Module):
    """Enhanced model with optional OOD detection capabilities"""

    def __init__(
        self,
        base_model,
        num_labels,
        use_spectral_norm=False,
        hidden_dim=768,
        dropout_rate=0.1,
    ):
        super().__init__()
        self.base_model = base_model
        self.num_labels = num_labels
        self.use_spectral_norm = use_spectral_norm
        self.hidden_dim = hidden_dim
        self.dropout_rate = dropout_rate

        # Get the hidden size from the base model
        if hasattr(base_model.config, "hidden_size"):
            self.hidden_size = base_model.config.hidden_size
        else:
            self.hidden_size = hidden_dim

        # Additional layers for uncertainty estimation
        if use_spectral_norm:
            self.uncertainty_head = nn.Sequential(
                nn.Dropout(dropout_rate),
                SpectralNormalization(nn.Linear(self.hidden_size, hidden_dim)),
                nn.ReLU(),
                nn.Dropout(dropout_rate),
                SpectralNormalization(nn.Linear(hidden_dim, num_labels)),
            )
        else:
            self.uncertainty_head = None

    def forward(self, input_ids, attention_mask=None, labels=None, **kwargs):
        # Get outputs from base model
        outputs = self.base_model(
            input_ids=input_ids, attention_mask=attention_mask, **kwargs
        )

        if self.uncertainty_head is not None:
            # Extract hidden representation for uncertainty head
            hidden_state = None
            # Try different ways to get the hidden representation
            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                hidden_state = outputs.pooler_output
            elif hasattr(outputs, "last_hidden_state"):
                # Use [CLS] token representation (first token)
                hidden_state = outputs.last_hidden_state[:, 0, :]
            elif (
                hasattr(outputs, "hidden_states") and outputs.hidden_states is not None
            ):
                # Use the last hidden state if available
                hidden_state = outputs.hidden_states[-1][:, 0, :]
            else:
                # Fallback: try to find any tensor that looks like hidden states
                for attr_name in ["logits", "prediction_logits"]:
                    if hasattr(outputs, attr_name):
                        attr_value = getattr(outputs, attr_name)
                        if (
                            isinstance(attr_value, torch.Tensor)
                            and len(attr_value.shape) >= 2
                        ):
                            # Use the raw logits and add a linear layer to get hidden representation
                            if attr_value.shape[-1] == self.num_labels:
                                # This is likely the classification logits, skip uncertainty head
                                break
                            else:
                                raise ValueError(
                                    f"Could not extract hidden state from model outputs: {type(outputs)}"
                                )

            if hidden_state is not None:
                # Apply uncertainty head
                logits = self.uncertainty_head(hidden_state)
                # Create a new output object with updated logits
                outputs.logits = logits

        return outputs

    def save_pretrained(
        self,
        save_directory: Union[str, os.PathLike],
        push_to_hub: bool = False,
        safe_serialization: bool = True,
        **kwargs,
    ):
        """
        Save the model to a directory, following transformers conventions.

        Args:
            save_directory: Directory where to save the model
            push_to_hub: Whether to push to huggingface hub (not implemented)
            safe_serialization: Whether to use safetensors format
            **kwargs: Additional arguments passed to base_model.save_pretrained
        """
        save_directory = Path(save_directory)
        save_directory.mkdir(parents=True, exist_ok=True)
        if hasattr(self.base_model, "distilbert"):
            backbone = self.base_model.distilbert
        elif hasattr(self.base_model, "bert"):
            backbone = self.base_model.bert
        elif hasattr(self.base_model, "roberta"):
            backbone = self.base_model.roberta
        else:
            # Fallback: save the whole base model but this might cause issues
            backbone = self.base_model
            logger.warning("Could not extract backbone - saving full base model")
        # Save the base model first
        base_model_dir = save_directory / "base_model"
        backbone.save_pretrained(base_model_dir, **kwargs)

        # Save the enhanced model state dict
        if safe_serialization:
            try:
                # Save only the uncertainty head if it exists
                if self.uncertainty_head is not None:
                    uncertainty_state = self.uncertainty_head.state_dict()
                    save_file(
                        uncertainty_state,
                        save_directory / "uncertainty_head.safetensors",
                    )
            except ImportError:
                # Fallback to regular torch save
                safe_serialization = False

        if not safe_serialization:
            if self.uncertainty_head is not None:
                torch.save(
                    self.uncertainty_head.state_dict(),
                    save_directory / "uncertainty_head.bin",
                )

        # Save the model configuration
        config = {
            "model_type": "enhanced_model",
            "num_labels": self.num_labels,
            "use_spectral_norm": self.use_spectral_norm,
            "hidden_dim": self.hidden_dim,
            "dropout_rate": self.dropout_rate,
            "hidden_size": self.hidden_size,
            "base_model_type": self.base_model.__class__.__name__,
            "transformers_version": getattr(self.base_model, "_version", None),
        }

        # Add base model config if available
        if hasattr(self.base_model, "config"):
            config["base_model_config"] = self.base_model.config.to_dict()

        with open(save_directory / "enhanced_config.json", "w") as f:
            json.dump(config, f, indent=2)

        print(f"Enhanced model saved to {save_directory}")

    @classmethod
    def from_pretrained(
        cls,
        pretrained_model_path: Union[str, os.PathLike],
        base_model_class=None,
        **kwargs,
    ):
        """
        Load an enhanced model from a directory.

        Args:
            pretrained_model_path: Path to the saved model directory
            base_model_class: The class to use for loading the base model
            **kwargs: Additional arguments
        """
        pretrained_model_path = Path(pretrained_model_path)

        # Load configuration
        with open(pretrained_model_path / "enhanced_config.json", "r") as f:
            config = json.load(f)

        # Load base model
        base_model_dir = pretrained_model_path / "base_model"
        if base_model_class is not None:
            base_model = base_model_class.from_pretrained(base_model_dir)
        else:
            # Try to infer the base model class from transformers
            try:
                from transformers import AutoModel

                base_model = AutoModel.from_pretrained(base_model_dir)
            except Exception as e:
                raise ValueError(
                    f"Could not load base model. Please provide base_model_class. Error: {e}"
                )

        # Create enhanced model instance
        model = cls(
            base_model=base_model,
            num_labels=config["num_labels"],
            use_spectral_norm=config["use_spectral_norm"],
            hidden_dim=config["hidden_dim"],
            dropout_rate=config["dropout_rate"],
        )

        # Load uncertainty head if it exists
        if config["use_spectral_norm"] and model.uncertainty_head is not None:
            uncertainty_head_path = None
            if (pretrained_model_path / "uncertainty_head.safetensors").exists():
                try:
                    from safetensors.torch import load_file

                    uncertainty_state = load_file(
                        pretrained_model_path / "uncertainty_head.safetensors"
                    )
                    model.uncertainty_head.load_state_dict(uncertainty_state)
                except ImportError:
                    uncertainty_head_path = (
                        pretrained_model_path / "uncertainty_head.bin"
                    )
            elif (pretrained_model_path / "uncertainty_head.bin").exists():
                uncertainty_head_path = pretrained_model_path / "uncertainty_head.bin"

            if uncertainty_head_path:
                uncertainty_state = torch.load(
                    uncertainty_head_path, map_location="cpu"
                )
                model.uncertainty_head.load_state_dict(uncertainty_state)

        return model


class EnhancedModelInference(nn.Module):
    """
    Inference-only version of EnhancedModel - ONNX compatible
    """

    def __init__(self, base_model, num_labels, hidden_dim=768, dropout_rate=0.1):
        super().__init__()
        self.base_model = base_model
        self.num_labels = num_labels
        self.hidden_dim = hidden_dim
        self.dropout_rate = dropout_rate

        # Get the hidden size from the base model
        if hasattr(base_model.config, "hidden_size"):
            self.hidden_size = base_model.config.hidden_size
        else:
            self.hidden_size = hidden_dim

        # Simple uncertainty head - no spectral norm wrapper needed
        # The weights will be copied from the trained spectral normalized layers
        self.uncertainty_head = nn.Sequential(
            nn.Dropout(dropout_rate),
            nn.Linear(self.hidden_size, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden_dim, num_labels),
        )

    def _model_supports_token_type_ids(self):
        """
        Check if the base model supports token_type_ids
        """
        if hasattr(self.base_model, "config") and hasattr(
            self.base_model.config, "model_type"
        ):
            model_type = self.base_model.config.model_type

            # Models that explicitly reject token_type_ids
            if model_type in ["distilbert"]:
                return False

            # Models that use token_type_ids
            if model_type in ["bert"]:
                return True

            # Models that accept but ignore token_type_ids (like xlm-roberta, roberta)
            if model_type in ["xlm-roberta", "roberta"]:
                return True  # They accept it even though they ignore it

        # Fallback: check if model has type_vocab_size > 1
        if hasattr(self.base_model, "config") and hasattr(
            self.base_model.config, "type_vocab_size"
        ):
            return self.base_model.config.type_vocab_size > 1

        # Default: try to pass it (most models accept it)
        return True

    def forward(
        self, input_ids, attention_mask, token_type_ids=None, labels=None, **kwargs
    ):
        # Get outputs from base model

        if self._model_supports_token_type_ids():
            outputs = self.base_model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                token_type_ids=token_type_ids,
            )
        else:
            outputs = self.base_model(
                input_ids=input_ids, attention_mask=attention_mask
            )

        # Extract hidden representation
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            hidden_state = outputs.pooler_output
        elif hasattr(outputs, "last_hidden_state"):
            hidden_state = outputs.last_hidden_state[:, 0, :]
        else:
            # Fallback for ONNX
            batch_size = input_ids.shape[0]
            hidden_state = torch.zeros(
                batch_size, self.hidden_size, device=input_ids.device
            )

        # Apply uncertainty head (weights are already spectrally normalized!)
        logits = self.uncertainty_head(hidden_state)

        from transformers.modeling_outputs import SequenceClassifierOutput

        return SequenceClassifierOutput(
            logits=logits,
            hidden_states=getattr(outputs, "hidden_states", None),
            attentions=getattr(outputs, "attentions", None),
        )

    def save_pretrained(self, save_directory, tokenizer=None, **kwargs):
        """Save inference model"""
        save_directory = Path(save_directory)
        save_directory.mkdir(parents=True, exist_ok=True)

        # Save the base model
        base_model_dir = save_directory / "base_model"
        self.base_model.save_pretrained(base_model_dir, **kwargs)

        # Save tokenizer if provided
        if tokenizer is not None:
            tokenizer.save_pretrained(save_directory)
            tokenizer.save_pretrained(base_model_dir)

        # Save uncertainty head
        torch.save(
            self.uncertainty_head.state_dict(),
            save_directory / "uncertainty_head.bin",
        )

        # Save inference config
        config = {
            "model_type": "enhanced_model_inference",
            "num_labels": self.num_labels,
            "hidden_dim": self.hidden_dim,
            "dropout_rate": self.dropout_rate,
            "hidden_size": self.hidden_size,
            "base_model_type": self.base_model.__class__.__name__,
        }

        if hasattr(self.base_model, "config"):
            config["base_model_config"] = self.base_model.config.to_dict()

        with open(save_directory / "inference_config.json", "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Inference model saved to {save_directory}")

    @classmethod
    def from_pretrained(cls, pretrained_model_path, **kwargs):
        """Load inference model"""
        pretrained_model_path = Path(pretrained_model_path)

        # Load configuration
        with open(pretrained_model_path / "inference_config.json", "r") as f:
            config = json.load(f)

        # Load base model
        base_model_dir = pretrained_model_path / "base_model"
        from transformers import AutoModel

        base_model = AutoModel.from_pretrained(base_model_dir)

        # Create inference model instance
        model = cls(
            base_model=base_model,
            num_labels=config["num_labels"],
            hidden_dim=config["hidden_dim"],
            dropout_rate=config["dropout_rate"],
        )

        # Load uncertainty head
        uncertainty_head_path = pretrained_model_path / "uncertainty_head.bin"
        if uncertainty_head_path.exists():
            uncertainty_state = torch.load(uncertainty_head_path, map_location="cpu")
            model.uncertainty_head.load_state_dict(uncertainty_state)

        return model


def export_inference_model_to_onnx(model_dir: str):
    """
    Export inference model to ONNX - much simpler now!
    """
    try:
        from transformers import AutoTokenizer
        import torch

        model_dir = Path(model_dir)

        # Load inference model
        inference_model = EnhancedModelInference.from_pretrained(model_dir)
        inference_model.eval()

        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_dir)

        # Create dummy input
        dummy_input = tokenizer(
            "This is a sample text for ONNX export.",
            return_tensors="pt",
            return_token_type_ids=True,
            return_attention_mask=True,
            padding=True,
            truncation=True,
            max_length=SEQUENCE_LENGTH,
        )
        output_path = model_dir / "model.onnx"

        # Export to ONNX (should work smoothly now!)
        if inference_model._model_supports_token_type_ids():
            torch.onnx.export(
                inference_model,
                (
                    dummy_input["input_ids"],
                    dummy_input["attention_mask"],
                    dummy_input["token_type_ids"],
                ),
                str(output_path),
                input_names=["input_ids", "attention_mask", "token_type_ids"],
                output_names=["logits"],
                dynamic_axes={
                    "input_ids": {0: "batch_size", 1: "sequence_length"},
                    "attention_mask": {0: "batch_size", 1: "sequence_length"},
                    "token_type_ids": {0: "batch_size", 1: "sequence_length"},
                    "logits": {0: "batch_size"},
                },
                opset_version=14,
                do_constant_folding=True,
                export_params=True,
            )
        else:
            torch.onnx.export(
                inference_model,
                (
                    dummy_input["input_ids"],
                    dummy_input["attention_mask"],
                ),
                str(output_path),
                input_names=["input_ids", "attention_mask"],
                output_names=["logits"],
                dynamic_axes={
                    "input_ids": {0: "batch_size", 1: "sequence_length"},
                    "attention_mask": {0: "batch_size", 1: "sequence_length"},
                    "logits": {0: "batch_size"},
                },
                opset_version=13,
                do_constant_folding=True,
                export_params=True,
            )

        with torch.no_grad():
            test_output = inference_model(
                dummy_input["input_ids"],
                dummy_input["attention_mask"],
                dummy_input["token_type_ids"],
            )
            print(test_output)
            print("Forward pass successful")

        if output_path.exists():
            logger.info(f"ONNX export successful: {output_path}")
            return str(output_path)
        else:
            return None

    except Exception as e:
        logger.error(f"ONNX export failed: {e}")
        return None


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"TRAINING HARDWARE {device}")


class TrainingPipeline:
    def __init__(
        self, dfs, model_name, full_name=None, ood_method=None, ood_config=None
    ):
        self.model_name = model_name
        self.dfs = dfs
        self.ood_method = ood_method
        self.full_name = full_name
        self.ood_config = ood_config or {}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Validate model name
        if model_name not in SUPPORTED_BASE_MODELS:
            raise ValueError(
                f"Unsupported model: {model_name}. Supported: {SUPPORTED_BASE_MODELS}"
            )

        # Initialize base model
        self.base_model = self._initialize_base_model(model_name)

    def _initialize_base_model(self, model_name):
        """Initialize the base model based on model name"""
        config = MODEL_CONFIGS[model_name]

        if config["type"] == "bert":
            model = BertForSequenceClassification.from_pretrained(config["model_name"])
            self._freeze_and_unfreeze_bert_layers(model)

        elif config["type"] == "roberta":
            model = XLMRobertaForSequenceClassification.from_pretrained(
                config["model_name"]
            )
            self._freeze_and_unfreeze_roberta_layers(model)

        elif config["type"] == "distilbert":
            model = DistilBertForSequenceClassification.from_pretrained(
                config["model_name"]
            )
            self._freeze_and_unfreeze_distilbert_layers(model)

        else:
            raise ValueError(f"Unknown model type: {config['type']}")

        return model

    def _freeze_and_unfreeze_bert_layers(self, model):
        """Helper method for BERT-based models"""
        if hasattr(model, "bert"):
            bert_model = model.bert
        elif hasattr(model, "base_model"):
            bert_model = model.base_model
        else:
            # Fallback - assume the model itself is the BERT model
            bert_model = model

        # Freeze all parameters first
        for param in bert_model.parameters():
            param.requires_grad = False

        # Unfreeze last 2 layers
        if hasattr(bert_model, "encoder") and hasattr(bert_model.encoder, "layer"):
            for param in bert_model.encoder.layer[-2:].parameters():
                param.requires_grad = True

        # Unfreeze classifier if it exists
        if hasattr(model, "classifier"):
            for param in model.classifier.parameters():
                param.requires_grad = True

    def _freeze_and_unfreeze_roberta_layers(self, model):
        """Helper method for RoBERTa-based models"""
        if hasattr(model, "roberta"):
            roberta_model = model.roberta
        elif hasattr(model, "base_model"):
            roberta_model = model.base_model
        elif hasattr(model, "encoder"):
            roberta_model = model
        else:
            logger.warning(f"RoBERTa model structure: {type(model)}")
            for name, module in model.named_children():
                logger.info(f"  - {name}: {type(module)}")
                if hasattr(module, "encoder"):
                    roberta_model = module
                    break
            else:
                roberta_model = model

        # Freeze all parameters first
        for param in roberta_model.parameters():
            param.requires_grad = False

        encoder = None
        if hasattr(roberta_model, "encoder"):
            encoder = roberta_model.encoder
        elif hasattr(roberta_model, "transformer"):
            encoder = roberta_model.transformer

        if encoder and hasattr(encoder, "layer"):
            for param in encoder.layer[-2:].parameters():
                param.requires_grad = True
        else:
            logger.warning("Could not find encoder layers to unfreeze")

        # Unfreeze classifier if it exists
        if hasattr(model, "classifier"):
            for param in model.classifier.parameters():
                param.requires_grad = True

    def _freeze_and_unfreeze_distilbert_layers(self, model):
        """Helper method for DistilBERT-based models"""
        if hasattr(model, "distilbert"):
            distilbert_model = model.distilbert
        elif hasattr(model, "base_model"):
            distilbert_model = model.base_model
        else:
            distilbert_model = model

        # Freeze all parameters first
        for param in distilbert_model.parameters():
            param.requires_grad = False

        # Unfreeze last 2 layers
        if hasattr(distilbert_model, "transformer") and hasattr(
            distilbert_model.transformer, "layer"
        ):
            for param in distilbert_model.transformer.layer[-2:].parameters():
                param.requires_grad = True

        # Unfreeze classifier if it exists
        if hasattr(model, "classifier"):
            for param in model.classifier.parameters():
                param.requires_grad = True

    def preprocess_conversation(self, text):
        """Preprocess conversation data"""
        text = str(text).strip()

        # Handle common conversation patterns
        text = text.replace("\n", " [SEP] ")
        text = text.replace("\t", " ")

        # Limit length for transformer models
        max_length = 400
        if len(text.split()) > max_length:
            words = text.split()[:max_length]
            text = " ".join(words)

        return text

    def tokenize_data(self, data, tokenizer):
        """Enhanced tokenization for conversation data"""
        processed_data = [self.preprocess_conversation(text) for text in data]

        tokenized = tokenizer.batch_encode_plus(
            processed_data,
            truncation=True,
            padding=True,
            max_length=SEQUENCE_LENGTH,
            return_token_type_ids=False,
            return_attention_mask=True,
            return_tensors="pt",
        )
        return tokenized

    def data_split(self, df):
        """Improved data split for flat classification"""
        unique_classes = df["target"].unique()

        if len(df) < 100:
            # For small datasets, ensure each class has representation
            train_samples = []
            test_samples = []

            for class_name in unique_classes:
                class_samples = df[df["target"] == class_name]

                if len(class_samples) == 1:
                    train_samples.append(class_samples)
                else:
                    train_class, test_class = train_test_split(
                        class_samples, test_size=TEST_SIZE_RATIO, random_state=42
                    )
                    train_samples.append(train_class)
                    test_samples.append(test_class)

            train_df = pd.concat(train_samples) if train_samples else pd.DataFrame()
            test_df = pd.concat(test_samples) if test_samples else pd.DataFrame()

            # If test set is empty, duplicate some training samples
            if len(test_df) == 0:
                test_df = train_df.sample(min(len(train_df), 5), random_state=42)
        else:
            # For larger datasets, use stratified split
            try:
                train_df, test_df = train_test_split(
                    df,
                    test_size=TEST_SIZE_RATIO,
                    random_state=42,
                    stratify=df["target"],
                )
            except ValueError:
                train_df, test_df = train_test_split(
                    df, test_size=TEST_SIZE_RATIO, random_state=42
                )

        return train_df, test_df

    def get_tokenizer_and_model_for_training(self, model_name, num_labels):
        """Get appropriate tokenizer and model for training"""
        config = MODEL_CONFIGS[model_name]

        if config["type"] == "bert":
            model = BertForSequenceClassification.from_pretrained(
                config["model_name"],
                num_labels=num_labels,
                ignore_mismatched_sizes=True,
            )
            tokenizer = BertTokenizer.from_pretrained(config["tokenizer_name"])
            self._freeze_and_unfreeze_bert_layers(model)

        elif config["type"] == "roberta":
            model = XLMRobertaForSequenceClassification.from_pretrained(
                config["model_name"],
                num_labels=num_labels,
                ignore_mismatched_sizes=True,
            )
            tokenizer = XLMRobertaTokenizer.from_pretrained(config["tokenizer_name"])
            self._freeze_and_unfreeze_roberta_layers(model)

        elif config["type"] == "distilbert":
            model = DistilBertForSequenceClassification.from_pretrained(
                config["model_name"],
                num_labels=num_labels,
                ignore_mismatched_sizes=True,
            )
            tokenizer = DistilBertTokenizer.from_pretrained(config["tokenizer_name"])
            self._freeze_and_unfreeze_distilbert_layers(model)

        else:
            raise ValueError(f"Unknown model type: {config['type']}")

        return model, tokenizer

    def replicate_data(self, df, target_size):
        """Replicate data to reach target size"""
        if len(df) >= target_size:
            return df

        multiplier = target_size // len(df) + 1
        replicated_dfs = [df] * multiplier
        replicated_df = pd.concat(replicated_dfs, ignore_index=True)
        replicated_df = replicated_df.sample(n=target_size, random_state=42)
        return replicated_df

    def extract_model_components(self, model):
        """Extract model components based on model type with robust error handling"""
        config = MODEL_CONFIGS[self.model_name]

        try:
            if config["type"] == "bert":
                # Try different possible BERT model structures
                bert_layers = None
                if hasattr(model, "bert") and hasattr(model.bert, "encoder"):
                    bert_layers = model.bert.encoder.layer[-2:].state_dict()
                elif hasattr(model, "base_model") and hasattr(
                    model.base_model, "encoder"
                ):
                    bert_layers = model.base_model.encoder.layer[-2:].state_dict()
                else:
                    logger.warning(
                        "Could not extract BERT layers, using pattern matching"
                    )
                    bert_layers = {
                        k: v
                        for k, v in model.state_dict().items()
                        if "encoder.layer.10" in k or "encoder.layer.11" in k
                    }

                classifier_layers = (
                    model.classifier.state_dict()
                    if hasattr(model, "classifier")
                    else {}
                )
                return bert_layers, classifier_layers

            elif config["type"] == "roberta":
                # Handle XLM-RoBERTa structure
                roberta_layers = None

                # First try to find the main transformer layers
                if hasattr(model, "roberta") and hasattr(model.roberta, "encoder"):
                    roberta_layers = model.roberta.encoder.layer[-2:].state_dict()
                elif hasattr(model, "base_model") and hasattr(
                    model.base_model, "encoder"
                ):
                    roberta_layers = model.base_model.encoder.layer[-2:].state_dict()
                else:
                    # For XLM-RoBERTa, extract by parameter name pattern
                    logger.warning("Using pattern matching for XLM-RoBERTa layers")
                    roberta_layers = {}
                    for name, param in model.named_parameters():
                        # Extract last 2 encoder layers (typically layer 10 and 11 for base models)
                        if "encoder.layer.10." in name or "encoder.layer.11." in name:
                            # Remove the model prefix to get relative layer name
                            layer_name = name.split("encoder.layer.")[-1]
                            roberta_layers[f"encoder.layer.{layer_name}"] = (
                                param.data.clone()
                            )

                classifier_layers = (
                    model.classifier.state_dict()
                    if hasattr(model, "classifier")
                    else {}
                )
                return roberta_layers, classifier_layers

            elif config["type"] == "distilbert":
                # Try different possible DistilBERT model structures
                distilbert_layers = None
                if hasattr(model, "distilbert") and hasattr(
                    model.distilbert, "transformer"
                ):
                    distilbert_layers = model.distilbert.transformer.layer[
                        -2:
                    ].state_dict()
                elif hasattr(model, "base_model") and hasattr(
                    model.base_model, "transformer"
                ):
                    distilbert_layers = model.base_model.transformer.layer[
                        -2:
                    ].state_dict()
                else:
                    logger.warning(
                        "Could not extract DistilBERT layers, using pattern matching"
                    )
                    distilbert_layers = {
                        k: v
                        for k, v in model.state_dict().items()
                        if "transformer.layer.4." in k or "transformer.layer.5." in k
                    }  # DistilBERT has 6 layers

                classifier_layers = (
                    model.classifier.state_dict()
                    if hasattr(model, "classifier")
                    else {}
                )
                return distilbert_layers, classifier_layers

            else:
                raise ValueError(f"Unknown model type: {config['type']}")

        except Exception as e:
            logger.error(f"Error extracting model components: {e}")
            # Fallback: return relevant parts of model state dict
            logger.warning("Using fallback: extracting layers by name pattern")

            model_layers = {}
            classifier_layers = {}

            for name, param in model.named_parameters():
                if "classifier" in name:
                    classifier_layers[name] = param.data.clone()
                elif "encoder.layer." in name and any(
                    f"encoder.layer.{i}." in name for i in [10, 11, 4, 5]
                ):  # Last layers for different models
                    model_layers[name] = param.data.clone()

            return model_layers, classifier_layers

    def train(self):
        """Standard training method"""
        classes = []
        accuracies = []
        f1_scores = []
        label_encoders = []

        method_name = f"{self.model_name}" + (
            f"-{self.ood_method}" if self.ood_method else ""
        )
        logger.info(f"INITIATING TRAINING FOR {method_name}")

        for i in range(len(self.dfs)):
            logger.info(f"TRAINING FOR DATAFRAME {i + 1} of {len(self.dfs)}")
            current_df = self.dfs[i]

            if len(current_df) < MIN_SAMPLES_PER_CLASS:
                current_df = self.replicate_data(
                    current_df, TARGET_SAMPLES_FOR_SMALL_DATASETS
                ).reset_index(drop=True)

            train_df, test_df = self.data_split(current_df)
            label_encoder = LabelEncoder()
            train_labels = label_encoder.fit_transform(train_df["target"])
            test_labels = label_encoder.transform(test_df["target"])
            self.model_label2id = {}

            for idx, label in enumerate(label_encoder.classes_):
                self.model_label2id[label] = idx
            self.model_id2label = {v: k for k, v in self.model_label2id.items()}
            self.agency_label2id = {}
            agency_ids_column = "agency_id"
            for i, row in train_df.iterrows():
                agency_id = row[agency_ids_column]
                if agency_id not in self.agency_label2id:
                    self.agency_label2id[agency_id] = row["target"]
            self.agency_id2label = {v: k for k, v in self.agency_label2id.items()}
            print(
                self.agency_label2id,
                self.agency_id2label,
                self.model_label2id,
                self.model_id2label,
            )
            # Get model and tokenizer
            model, tokenizer = self.get_tokenizer_and_model_for_training(
                self.model_name, len(label_encoder.classes_)
            )

            # Apply OOD enhancements if specified
            if self.ood_method == "sngp":
                logger.info("Applying spectral normalization enhancement")
                model = EnhancedModel(
                    base_model=model,
                    num_labels=len(label_encoder.classes_),
                    use_spectral_norm=True,
                )

            train_encodings = self.tokenize_data(train_df["input"].tolist(), tokenizer)
            test_encodings = self.tokenize_data(test_df["input"].tolist(), tokenizer)

            # Prepare OOD labels if needed
            train_ood_labels = None
            test_ood_labels = None
            if self.ood_method in ["energy", "sngp"]:
                # All samples are ID (in practice, you'd have real OOD data)
                train_ood_labels = np.zeros(len(train_labels))
                test_ood_labels = np.zeros(len(test_labels))

            train_dataset = CustomDataset(
                train_encodings, train_labels, train_ood_labels
            )

            test_dataset = CustomDataset(test_encodings, test_labels, test_ood_labels)

            # Setup training arguments
            training_args = TrainingArguments(
                output_dir="tmp",
                **DEFAULT_TRAINING_ARGS,
                disable_tqdm=False,
            )

            # Use custom trainer for OOD methods
            if self.ood_method in ["energy", "sngp"]:
                trainer = self._get_ood_trainer(
                    model, training_args, train_dataset, test_dataset
                )
            else:
                trainer = Trainer(
                    model=model,
                    args=training_args,
                    train_dataset=train_dataset,
                    eval_dataset=test_dataset,
                    compute_metrics=lambda eval_pred: {
                        "accuracy": accuracy_score(
                            eval_pred.label_ids, eval_pred.predictions.argmax(axis=1)
                        )
                    },
                )

            trainer.train()
            # save the model
            from constants import MODEL_RESULTS_PATH

            # save the model
            model_dir = f"{MODEL_RESULTS_PATH}/{method_name}"
            os.makedirs(model_dir, exist_ok=True)
            inference_model = EnhancedModelInference(
                base_model=model.base_model,
                num_labels=len(label_encoder.classes_),
                hidden_dim=model.hidden_dim,
                dropout_rate=model.dropout_rate,
            )
            if (
                hasattr(model, "uncertainty_head")
                and model.uncertainty_head is not None
            ):
                # Extract weights from spectral normalized layers
                training_state = model.uncertainty_head.state_dict()

                # Map spectral norm weights to regular linear layers
                inference_state = {}

                # Map from SpectralNormalization layers to regular Linear layers
                layer_mappings = {
                    "1.layer.weight": "1.weight",  # First spectral norm -> first linear
                    "1.layer.bias": "1.bias",
                    "4.layer.weight": "4.weight",  # Second spectral norm -> second linear
                    "4.layer.bias": "4.bias",
                }

                for training_key, inference_key in layer_mappings.items():
                    if training_key in training_state:
                        inference_state[inference_key] = training_state[training_key]

                # Load the mapped weights
                inference_model.uncertainty_head.load_state_dict(
                    inference_state, strict=False
                )
                logger.info(
                    "Successfully transferred spectrally normalized weights to inference model"
                )

            inference_model.save_pretrained(model_dir, tokenizer=tokenizer)
            tokenizer.save_pretrained(model_dir)
            logger.info(f"Model saved to {model_dir}")
            # save labelmappings, ood config to config.json
            config = {
                "num_labels": len(label_encoder.classes_),
                "model_name": self.full_name,
                "hidden_dim": model.hidden_dim,
                "dropout_rate": model.dropout_rate,
                "sequence_length": SEQUENCE_LENGTH,
                "ood_method": self.ood_method,
                "ood_config": self.ood_config,
                "base_model_name": self.model_name,
                "base_model_type": model.base_model.__class__.__name__,
                "model_label2id": self.model_label2id,
                "model_id2label": self.model_id2label,
                "agency_label2id": self.agency_label2id,
                "agency_id2label": self.agency_id2label,
            }
            import json

            with open(os.path.join(model_dir, "config.json"), "w") as f:
                json.dump(config, f, indent=2)

            # Evaluate model
            predictions, labels, _ = trainer.predict(test_dataset)
            predictions = predictions.argmax(axis=-1)
            report = classification_report(
                labels,
                predictions,
                target_names=label_encoder.classes_,
                output_dict=True,
                zero_division=0,
            )

            # Log results
            logger.info(f"Classification Results for {method_name}:")
            for cls in label_encoder.classes_:
                if cls in report:
                    precision = report[cls]["precision"]
                    f1 = report[cls]["f1-score"]
                    logger.info(
                        f"  Class '{cls}': Precision={precision:.3f}, F1={f1:.3f}"
                    )

                    classes.append(cls)
                    accuracies.append(precision)
                    f1_scores.append(f1)

            label_encoders.append(label_encoder)

            # Clean up
            if os.path.exists("tmp"):
                shutil.rmtree("tmp")

        metrics = (classes, accuracies, f1_scores)
        return model_dir, metrics

    def _get_ood_trainer(self, model, training_args, train_dataset, test_dataset):
        """Get custom trainer for OOD methods"""

        class OODTrainer(Trainer):
            def __init__(self, ood_method, ood_config, **kwargs):
                super().__init__(**kwargs)
                self.ood_method = ood_method
                self.ood_config = ood_config

                if ood_method == "energy":
                    config = DEFAULT_OOD_CONFIGS["energy"]
                    config.update(ood_config)
                    self.ood_loss = OODLoss(
                        ood_weight=config.get("energy_weight", 0.1),
                        energy_margin=config.get("energy_margin", 10.0),
                        temperature=config.get("energy_temp", 1.0),
                    )

            def compute_loss(self, model, inputs, return_outputs=False):
                labels = inputs.get("labels")
                ood_labels = inputs.get("ood_labels")

                outputs = model(
                    **{
                        k: v
                        for k, v in inputs.items()
                        if k not in ["labels", "ood_labels"]
                    }
                )
                logits = outputs.get("logits")

                if ood_labels is not None and self.ood_method == "energy":
                    loss = self.ood_loss(logits, labels, ood_labels)
                else:
                    loss_fct = nn.CrossEntropyLoss()
                    loss = loss_fct(logits.view(-1, logits.size(-1)), labels.view(-1))

                return (loss, outputs) if return_outputs else loss

        return OODTrainer(
            ood_method=self.ood_method,
            ood_config=self.ood_config,
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=test_dataset,
            compute_metrics=lambda eval_pred: {
                "accuracy": accuracy_score(
                    eval_pred.label_ids, eval_pred.predictions.argmax(axis=1)
                )
            },
        )


def create_training_pipeline(
    dfs, model_name, full_name=None, ood_method=None, **ood_config
):
    """
    Factory function to create training pipelines.

    Args:
        dfs: List of dataframes
        model_name: Name of the base model
        ood_method: OOD method ("energy", "sngp", "softmax", or None for standard)
        **ood_config: Additional OOD configuration parameters

    Returns:
        TrainingPipeline: Configured training pipeline
    """
    if ood_method and ood_method not in SUPPORTED_OOD_METHODS:
        raise ValueError(
            f"Unsupported OOD method: {ood_method}. Supported: {SUPPORTED_OOD_METHODS}"
        )

    return TrainingPipeline(
        dfs=dfs,
        model_name=model_name,
        full_name=full_name,
        ood_method=ood_method,
        ood_config=ood_config,
    )
