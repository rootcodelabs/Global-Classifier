import json
import numpy as np
import triton_python_backend_utils as pb_utils
from scipy.special import softmax
import os


class TritonPythonModel:
    """
    Text postprocessing with uncertainty-based class injection
    Maintains original format but injects uncertainty information when needed
    """

    def initialize(self, args):
        """Initialize label mappings and OOD detection configuration"""

        model_path = args["model_repository"]
        model_config = json.loads(args["model_config"])
        if "parameters" in model_config:
            for param in model_config["parameters"]:
                key = param["key"]
                if "string_value" in param["value"]:
                    self.params[key] = param["value"]["string_value"]

        label_file = os.path.join(model_path, "1", "label_mappings.json")

        self.logger = pb_utils.Logger

        try:

            self.ood_method = self.params.get("ood_method", None)
            self.ood_threshold = self.params.get("ood_threshold", 0.5)
            self.energy_temp = self.params.get("energy_temp", 1.0)
            self.softmax_temp = self.params.get("softmax_temp", 1.0)
            self.use_entropy = self.params.get("use_entropy", False)

            # Uncertainty handling strategy
            self.uncertainty_strategy = self.params.get("uncertainty_strategy", None)
            self.human_handoff_threshold = self.params.get(
                "human_handoff_threshold", 0.8
            )
            self.confidence_scaling = self.params.get("confidence_scaling", False)

            self.logger.log_info(f"Model config loaded - OOD method: {self.ood_method}")

        except Exception as e:
            # Graceful fallback for regular models without config
            self.logger.log_info(f"No model config found ({e}) ")

        # Load label mappings
        if os.path.exists(label_file):
            with open(label_file, "r") as f:
                self.label_mappings = json.load(f)

            self.id_to_label = self.label_mappings["id_to_label"]
            self.num_classes = self.label_mappings["num_classes"]

        self.logger.log_info(f"OOD method: {self.ood_method}")
        self.logger.log_info(f"Uncertainty strategy: {self.uncertainty_strategy}")
        self.logger.log_info(f"Human handoff threshold: {self.human_handoff_threshold}")

    def compute_uncertainty(self, logits, covariance_matrix=None):
        """Compute uncertainty score based on configured method"""

        if self.ood_method == "energy":
            logits_scaled = logits / self.energy_temp
            energy = -np.log(np.sum(np.exp(logits_scaled), axis=1))
            return energy

        elif self.ood_method == "softmax":
            logits_scaled = logits / self.softmax_temp
            probabilities = softmax(logits_scaled, axis=1)

            if self.use_entropy:
                probabilities = np.clip(probabilities, 1e-10, 1.0)
                entropy = -np.sum(probabilities * np.log(probabilities), axis=1)
                return entropy
            else:
                max_probs = np.max(probabilities, axis=1)
                return 1.0 - max_probs

        elif self.ood_method == "sngp" and covariance_matrix is not None:
            if (
                covariance_matrix.ndim == 2
                and covariance_matrix.shape[0] == covariance_matrix.shape[1]
            ):
                variance = np.diag(covariance_matrix)
            else:
                variance = np.mean(covariance_matrix, axis=-1)

            if variance.ndim == 0:
                variance = np.full(logits.shape[0], variance)
            elif len(variance) != logits.shape[0]:
                variance = np.full(logits.shape[0], np.mean(variance))

            return variance

        # Fallback to max probability confidence
        probabilities = softmax(logits, axis=1)
        max_probs = np.max(probabilities, axis=1)
        return 1.0 - max_probs

    def apply_uncertainty_strategy(
        self, sample_result, uncertainty_score, probabilities, batch_idx
    ):
        """Apply uncertainty handling strategy to modify predictions"""

        # If no strategy is set, just return original predictions
        if self.uncertainty_strategy is None or self.uncertainty_strategy == "none":
            return sample_result

        confidence_score = 1.0 - uncertainty_score
        is_high_uncertainty = uncertainty_score > self.ood_threshold
        needs_human_handoff = uncertainty_score > self.human_handoff_threshold

        # Log important cases (even if not modifying output)
        if needs_human_handoff:
            self.logger.log_warn(
                f"Sample {batch_idx}: High uncertainty ({uncertainty_score:.3f}) - Human handoff recommended"
            )
        elif is_high_uncertainty:
            self.logger.log_info(
                f"Sample {batch_idx}: OOD detected ({uncertainty_score:.3f})"
            )

        if self.uncertainty_strategy == "inject_class":
            if needs_human_handoff:
                # Inject human handoff signal as top prediction
                new_result = {1: {"human_handoff_required": float(uncertainty_score)}}
                # Shift other predictions down
                for rank, prediction in sample_result.items():
                    new_result[rank + 1] = prediction
                return new_result

            elif is_high_uncertainty:
                # Inject OOD/uncertain class
                new_result = {1: {"out_of_domain": float(uncertainty_score)}}
                # Shift other predictions down
                for rank, prediction in sample_result.items():
                    new_result[rank + 1] = prediction
                return new_result

        elif self.uncertainty_strategy == "confidence_scaling":
            # Scale probabilities by confidence
            if self.confidence_scaling and confidence_score < 0.8:
                scaled_result = {}
                for rank, prediction in sample_result.items():
                    for label, prob in prediction.items():
                        # Scale probability by confidence
                        scaled_prob = prob * confidence_score
                        scaled_result[rank] = {label: float(scaled_prob)}
                return scaled_result

        elif self.uncertainty_strategy == "threshold_filter":
            # If too uncertain, return generic "uncertain" response
            if needs_human_handoff:
                return {1: {"uncertain_input": 1.0}}
            elif is_high_uncertainty:
                return {1: {"low_confidence": float(confidence_score)}}

        # Return original predictions if no strategy applied
        return sample_result

    def execute(self, requests):
        """Execute postprocessing with uncertainty-aware prediction modification"""
        responses = []

        for request in requests:
            logits_tensor = pb_utils.get_input_tensor_by_name(request, "logits")
            logits = logits_tensor.as_numpy()

            # Get covariance matrix for SNGP
            covariance_matrix = None
            if self.ood_method == "sngp":
                try:
                    cov_tensor = pb_utils.get_input_tensor_by_name(
                        request, "covariance_matrix"
                    )
                    if cov_tensor:
                        covariance_matrix = cov_tensor.as_numpy()
                except Exception as e:
                    self.logger.log_warn(f"Failed to get covariance matrix: {e}")

            # Get top_k parameter
            top_k = 5
            try:
                top_k_tensor = pb_utils.get_input_tensor_by_name(request, "top_k")
                if top_k_tensor:
                    top_k = int(top_k_tensor.as_numpy()[0])
            except Exception as e:
                self.logger.log_warn(f"Failed to get top_k parameter: {e}")

            top_k = min(top_k, self.num_classes)

            # Compute probabilities and uncertainty
            probabilities = softmax(logits, axis=1)
            uncertainty_scores = self.compute_uncertainty(logits, covariance_matrix)

            batch_size = probabilities.shape[0]
            top_k_results = []

            for i in range(batch_size):
                # Get standard top-k predictions
                top_k_indices = np.argsort(probabilities[i])[-top_k:][::-1]
                top_k_probs = probabilities[i][top_k_indices]

                # Build standard result
                sample_result = {}
                for rank, (idx, prob) in enumerate(zip(top_k_indices, top_k_probs), 1):
                    label = self.id_to_label.get(str(idx), f"class_{idx}")
                    sample_result[rank] = {label: float(prob)}

                # Apply uncertainty strategy to potentially modify result
                if self.ood_method and uncertainty_scores is not None:
                    sample_result = self.apply_uncertainty_strategy(
                        sample_result, uncertainty_scores[i], probabilities[i], i
                    )
                # If no OOD method, just use original predictions (regular BERT mode)

                top_k_results.append(sample_result)

            # Create output tensor - same format as original
            results_json = json.dumps(top_k_results)
            output_tensor = pb_utils.Tensor(
                "TOP_K_PREDICTIONS", np.array([results_json], dtype=object)
            )

            response = pb_utils.InferenceResponse(output_tensors=[output_tensor])
            responses.append(response)

        return responses

    def finalize(self):
        """Clean up resources"""
        pass
