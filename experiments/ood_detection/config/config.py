"""
Configuration file for the OOD detection experiments.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ModelConfig:
    """Base configuration for all models."""

    name: str
    model_type: str
    hidden_dims: List[int] = None
    dropout_rate: float = 0.1
    learning_rate: float = 1e-4
    batch_size: int = 32
    epochs: int = 10
    max_seq_length: int = 512
    pretrained_model: str = "xlm-roberta-base"
    seed: int = 42


@dataclass
class SNGPConfig(ModelConfig):
    """Configuration for SNGP model."""

    model_type: str = "sngp"
    spec_norm_bound: float = 0.9
    gp_hidden_dim: int = 1024
    gp_scale_random_features: bool = True
    gp_cov_momentum: float = -1.0  # No momentum, reset covariance each epoch
    gp_cov_ridge_penalty: float = 1.0


@dataclass
class EnergyConfig(ModelConfig):
    """Configuration for Energy-based OOD detection."""

    model_type: str = "energy"
    energy_temp: float = 1.0


@dataclass
class SNGPEnergyConfig(SNGPConfig, EnergyConfig):
    """Configuration for combined SNGP and Energy-based OOD detection."""

    model_type: str = "sngp_energy"
    alpha: float = 0.5  # Weight for combining SNGP and Energy scores (0-1)


@dataclass
class OODClassConfig(ModelConfig):
    """Configuration for OOD as a class approach."""

    model_type: str = "ood_class"
    # Percentage of data to use as synthetic OOD
    synthetic_ood_ratio: float = 0.2


@dataclass
class SoftmaxConfig(ModelConfig):
    """Configuration for Softmax threshold OOD detection."""

    model_type: str = "softmax"
    # Temperature scaling for softmax calibration
    temperature: float = 1.0
    # Whether to use entropy instead of max probability
    use_entropy: bool = False


@dataclass
class TrainingConfig:
    """Configuration for training process."""

    train_file: str
    dev_file: str
    test_file: str
    ood_test_file: Optional[str] = None
    output_dir: str = "outputs"
    mlflow_tracking_uri: str = "mlruns"
    mlflow_experiment_name: str = "ood_detection"
    model_config: ModelConfig = None
    num_train_epochs: int = 10
    per_device_train_batch_size: int = 32
    per_device_eval_batch_size: int = 32
    warmup_steps: int = 0
    weight_decay: float = 0.01
    logging_steps: int = 100
    evaluation_strategy: str = "epoch"
    save_strategy: str = "epoch"
    fp16: bool = False


@dataclass
class EvaluationConfig:
    """Configuration for evaluation metrics."""

    metrics: List[str] = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = [
                "accuracy",
                "precision",
                "recall",
                "f1",
                "roc_auc",
                "pr_auc",
                "fpr_at_95_tpr",
                "auroc",
                "aupr",
                "confusion_matrix",
            ]


# Default configurations
DEFAULT_SNGP_CONFIG = SNGPConfig(name="sngp_model")
DEFAULT_ENERGY_CONFIG = EnergyConfig(name="energy_model")
DEFAULT_SNGP_ENERGY_CONFIG = SNGPEnergyConfig(name="sngp_energy_model")
DEFAULT_OOD_CLASS_CONFIG = OODClassConfig(name="ood_class_model")
DEFAULT_SOFTMAX_CONFIG = SoftmaxConfig(name="softmax_model")

# Experiment configurations
EXPERIMENT_CONFIGS = {
    "sngp": DEFAULT_SNGP_CONFIG,
    "energy": DEFAULT_ENERGY_CONFIG,
    "sngp_energy": DEFAULT_SNGP_ENERGY_CONFIG,
    "ood_class": DEFAULT_OOD_CLASS_CONFIG,
    "softmax": DEFAULT_SOFTMAX_CONFIG,
}

# Training configurations
TRAINING_CONFIG = TrainingConfig(
    train_file="data/train.csv",
    dev_file="data/dev.csv",
    test_file="data/test.csv",
    ood_test_file="data/ood_test.csv",
)

# Evaluation configuration
EVALUATION_CONFIG = EvaluationConfig()
