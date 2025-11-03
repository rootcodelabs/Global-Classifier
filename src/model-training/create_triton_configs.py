def generate_ensemble_config(
    model_name: str,
    model_type: str,
    sequence_length: int = 512,
    max_batch_size: int = 32,
    pre_processing_name: str = "pre_processing",
    text_classifier_name: str = "text_classifier",
    post_processing_name: str = "post_processing",
    is_sngp: bool = False,
) -> str:
    """
    Generate Triton ensemble config based on model type.

    Args:
        model_name: Name of the ensemble model (e.g., "classifier_ensemble")
        model_type: Type of model ("distilbert", "bert", "xlm-roberta", "roberta")
        sequence_length: Maximum sequence length for the model
        max_batch_size: Maximum batch size for inference
        pre_processing_name: Name of the preprocessing model
        text_classifier_name: Name of the text classifier model
        post_processing_name: Name of the postprocessing model
        is_sngp: Whether this is an SNGP model (affects outputs)

    Returns:
        str: Complete Triton ensemble config as string
    """

    # Define which models support token_type_ids
    models_with_token_type_ids = ["bert", "xlm-roberta", "roberta", "estbert"]
    supports_token_type_ids = model_type.lower() in models_with_token_type_ids

    # Base config template
    config = f"""name: "{model_name}"
platform: "ensemble"
max_batch_size: {max_batch_size}
input [
  {{
    name: "TEXT"
    data_type: TYPE_STRING
    dims: [-1]
  }},
  {{
    name: "top_k"
    data_type: TYPE_INT32
    dims: [ 1 ]
    optional: true
  }}
]
output [
  {{
    name: "TOP_K_PREDICTIONS"
    data_type: TYPE_STRING
    dims: [ -1 ]
  }}
]
ensemble_scheduling {{
  step [
    {{
      model_name: "{pre_processing_name}"
      model_version: -1
      input_map {{
        key: "TEXT"
        value: "TEXT"
      }}
      output_map {{
        key: "input_ids"
        value: "input_ids"
      }}
      output_map {{
        key: "attention_mask"
        value: "attention_mask"
      }}"""

    # Add token_type_ids output mapping if supported
    if supports_token_type_ids:
        config += """
      output_map {
        key: "token_type_ids"
        value: "token_type_ids"
      }"""

    config += f"""
    }},
    {{
      model_name: "{text_classifier_name}"
      model_version: -1
      input_map {{
        key: "input_ids"
        value: "input_ids"
      }}
      input_map {{
        key: "attention_mask"
        value: "attention_mask"
      }}"""

    # Add token_type_ids input mapping if supported
    if supports_token_type_ids:
        config += """
      input_map {
        key: "token_type_ids"
        value: "token_type_ids"
      }"""

    config += f"""
      output_map {{
        key: "logits"
        value: "logits"
      }}
      
    }},
    {{
      model_name: "{post_processing_name}"
      model_version: -1
      input_map {{
        key: "logits"
        value: "logits"
      }}
      input_map {{
        key: "top_k"
        value: "top_k"
      }}
      output_map {{
        key: "TOP_K_PREDICTIONS"
        value: "TOP_K_PREDICTIONS"
      }}
    }}
  ]
}}"""

    return config


def generate_preprocessing_config(
    model_name: str,
    model_type: str,
    sequence_length: int = 512,
    max_batch_size: int = 32,
    ood_method: str = None,
    base_model_type: str = None,
) -> str:
    """
    Generate Triton preprocessing config based on model type.

    Args:
        model_name: Name of the preprocessing model (e.g., "pre_processing")
        model_type: Type of model ("distilbert", "bert", "xlm-roberta", "roberta")
        sequence_length: Maximum sequence length for the model
        max_batch_size: Maximum batch size for inference
        ood_method: OOD method ("sngp", "energy", "softmax", or None)
        base_model_type: Base model type for parameter passing

    Returns:
        str: Complete Triton preprocessing config as string
    """

    # Define which models support token_type_ids
    models_with_token_type_ids = ["bert", "xlm-roberta", "roberta", "estbert"]
    supports_token_type_ids = model_type.lower() in models_with_token_type_ids

    config = f"""name: "{model_name}"
backend: "python"
max_batch_size: {max_batch_size}

input [
  {{
    name: "TEXT"
    data_type: TYPE_STRING
    dims: [ -1 ]
  }}
]

output [
  {{
    name: "input_ids"
    data_type: TYPE_INT64
    dims: [ -1 ]
  }},
  {{
    name: "attention_mask"
    data_type: TYPE_INT64
    dims: [ -1 ]
  }}"""

    if supports_token_type_ids:
        config += """,
  {
    name: "token_type_ids"
    data_type: TYPE_INT64
    dims: [ -1 ]
  }"""

    config += f"""
]

parameters [
  {{
    key: "model_name"
    value: {{
      string_value: "{model_name}"
    }}
  }},
  {{
    key: "sequence_length"
    value: {{
      string_value: "{sequence_length}"
    }}
  }},
  {{
    key: "ood_method"
    value: {{
      string_value: "{ood_method if ood_method else "none"}"
    }}
  }},
  {{
    key: "base_model_type"
    value: {{
      string_value: "{base_model_type if base_model_type else model_type}"
    }}
  }}
]"""

    return config


def generate_text_classifier_config(
    model_name: str,
    model_type: str,
    num_labels: int,
    sequence_length: int = 512,
    max_batch_size: int = 32,
    ood_method: str = None,
) -> str:
    """
    Generate Triton text classifier config based on model type.
    """

    # Define which models support token_type_ids
    models_with_token_type_ids = ["bert", "xlm-roberta", "roberta", "estbert"]
    supports_token_type_ids = model_type.lower() in models_with_token_type_ids

    config = f"""name: "{model_name}"
platform: "onnxruntime_onnx"
max_batch_size: {max_batch_size}

input [
  {{
    name: "input_ids"
    data_type: TYPE_INT64
    dims: [ -1 ]
  }},
  {{
    name: "attention_mask"
    data_type: TYPE_INT64
    dims: [ -1 ]
  }}"""

    if supports_token_type_ids:
        config += """,
  {
    name: "token_type_ids"
    data_type: TYPE_INT64
    dims: [ -1 ]
  }"""

    config += f"""
]

output [
  {{
    name: "logits"
    data_type: TYPE_FP32
    dims: [ {num_labels} ]
  }}
]

dynamic_batching {{
  max_queue_delay_microseconds: 100
}}"""

    return config


def generate_postprocessing_config(
    model_name: str,
    num_labels: int,
    max_batch_size: int = 32,
    ood_method: str = None,
    ood_threshold: float = 0.5,
    uncertainty_threshold: float = 0.8,
    human_handoff_threshold: float = 0.8,
    uncertainty_strategy: str = None,
    energy_temp: float = 1.0,
    softmax_temp: float = 1.0,
    confidence_scaling: bool = False,
) -> str:
    """
    Generate Triton postprocessing config matching your existing implementation.

    Args:
        model_name: Name of the postprocessing model (e.g., "post_processing")
        num_labels: Number of output labels/classes
        max_batch_size: Maximum batch size for inference
        ood_method: OOD method ("sngp", "energy", "softmax", or None)
        ood_threshold: Threshold for OOD detection
        uncertainty_threshold: Threshold for uncertainty-based decisions
        human_handoff_threshold: Threshold for human handoff decisions
        uncertainty_strategy: Strategy for handling uncertainty ("inject_class", "confidence_scaling", "threshold_filter", or None)
        energy_temp: Temperature for energy-based OOD detection
        softmax_temp: Temperature for softmax-based OOD detection
        confidence_scaling: Whether to enable confidence scaling

    Returns:
        str: Complete Triton postprocessing config as string
    """

    config = f"""name: "{model_name}"
backend: "python"
max_batch_size: {max_batch_size}

input [
  {{
    name: "logits"
    data_type: TYPE_FP32
    dims: [ {num_labels} ]
  }},
  {{
    name: "top_k"
    data_type: TYPE_INT32
    dims: [ 1 ]
    optional: true
  }}
]"""

    config += f"""


output [
  {{
    name: "TOP_K_PREDICTIONS"
    data_type: TYPE_STRING
    dims: [ -1 ]
  }}
]



parameters [
  {{
    key: "ood_method"
    value: {{
      string_value: "{ood_method if ood_method else "none"}"
    }}
  }},
  {{
    key: "ood_threshold"
    value: {{
      string_value: "{ood_threshold}"
    }}
  }},
  {{
    key: "energy_temp"
    value: {{
      string_value: "{energy_temp}"
    }}
  }},
  {{
    key: "softmax_temp"
    value: {{
      string_value: "{softmax_temp}"
    }}
  }},
  {{
    key: "uncertainty_strategy"
    value: {{
      string_value: "{uncertainty_strategy if uncertainty_strategy else "none"}"
    }}
  }},
  {{
    key: "human_handoff_threshold"
    value: {{
      string_value: "{human_handoff_threshold}"
    }}
  }},
  {{
    key: "confidence_scaling"
    value: {{
      string_value: "{str(confidence_scaling).lower()}"
    }}
  }}
]"""

    return config


def generate_all_triton_configs(
    model_id: str,
    model_type: str,
    num_labels: int,
    sequence_length: int = 512,
    max_batch_size: int = 32,
    ood_method: str = None,
    ood_threshold: float = 0.5,
    uncertainty_threshold: float = 0.8,
    human_handoff_threshold: float = 0.8,
    uncertainty_strategy: str = None,
    energy_temp: float = 1.0,
    softmax_temp: float = 1.0,
    confidence_scaling: bool = False,
    base_model_type: str = None,
) -> dict:
    """
    Generate all Triton config files for a complete pipeline matching your implementation.

    Args:
        model_id: Unique identifier for the model (used in naming)
        model_type: Type of model ("distilbert", "bert", "xlm-roberta", "roberta")
        num_labels: Number of output labels/classes
        sequence_length: Maximum sequence length for the model
        max_batch_size: Maximum batch size for inference
        ood_method: OOD method ("sngp", "energy", "softmax", or None)
        ood_threshold: Threshold for OOD detection
        uncertainty_threshold: Threshold for uncertainty-based decisions
        human_handoff_threshold: Threshold for human handoff decisions
        uncertainty_strategy: Strategy for handling uncertainty
        energy_temp: Temperature for energy-based OOD detection
        softmax_temp: Temperature for softmax-based OOD detection
        confidence_scaling: Whether to enable confidence scaling
        base_model_type: Base model type for parameter passing

    Returns:
        dict: Dictionary containing all config files with their names as keys
    """

    # Generate model names with model_id prefix
    ensemble_name = f"{model_id}-classifier-ensemble"
    preprocessing_name = f"{model_id}-pre-processing"
    text_classifier_name = f"{model_id}-text-classifier"
    postprocessing_name = f"{model_id}-post-processing"

    configs = {
        f"{ensemble_name}/config.pbtxt": generate_ensemble_config(
            model_name=ensemble_name,
            model_type=model_type,
            sequence_length=sequence_length,
            max_batch_size=max_batch_size,
            pre_processing_name=preprocessing_name,
            text_classifier_name=text_classifier_name,
            post_processing_name=postprocessing_name,
        ),
        f"{preprocessing_name}/config.pbtxt": generate_preprocessing_config(
            model_name=preprocessing_name,
            model_type=model_type,
            sequence_length=sequence_length,
            max_batch_size=max_batch_size,
            ood_method=ood_method,
            base_model_type=base_model_type,
        ),
        f"{text_classifier_name}/config.pbtxt": generate_text_classifier_config(
            model_name=text_classifier_name,
            model_type=model_type,
            num_labels=num_labels,
            sequence_length=sequence_length,
            max_batch_size=max_batch_size,
            ood_method=ood_method,
        ),
        f"{postprocessing_name}/config.pbtxt": generate_postprocessing_config(
            model_name=postprocessing_name,
            num_labels=num_labels,
            max_batch_size=max_batch_size,
            ood_method=ood_method,
            ood_threshold=ood_threshold,
            uncertainty_threshold=uncertainty_threshold,
            human_handoff_threshold=human_handoff_threshold,
            uncertainty_strategy=uncertainty_strategy,
            energy_temp=energy_temp,
            softmax_temp=softmax_temp,
            confidence_scaling=confidence_scaling,
        ),
    }

    return configs
