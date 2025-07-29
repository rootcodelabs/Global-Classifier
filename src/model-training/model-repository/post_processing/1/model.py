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

        # Store args and handle different argument formats
        try:
            # Handle different argument formats that Triton might pass
            if isinstance(args, dict):
                model_path = args.get("model_repository", "")
            else:
                # Fallback if args is not a dict
                model_path = str(args)

        except Exception as e:

            print(f"Warning: Failed to parse args in initialize: {e}")

        label_file = os.path.join(model_path, "1", "label_mappings.json")

        self.logger = pb_utils.Logger

        # Load label mappings
        self.id_to_label = {}
        self.num_classes = 0

        if os.path.exists(label_file):
            try:
                with open(label_file, "r") as f:
                    self.label_mappings = json.load(f)
                self.ood_method = self.label_mappings.get("ood_method", "none")
                self.ood_threshold = 0.5
                # Uncertainty handling strategy
                self.uncertainty_strategy = "inject_class"
                self.human_handoff_threshold = 0.8
                self.confidence_scaling = False
                # Handle different label mapping formats
                if "model_id2label" in self.label_mappings:
                    self.id_to_label = self.label_mappings["model_id2label"]
                if "agency_id2label" in self.label_mappings:
                    self.agency_id2label = self.label_mappings["agency_id2label"]

                # Get number of classes
                if "num_labels" in self.label_mappings:
                    self.num_classes = self.label_mappings["num_labels"]
                elif "num_classes" in self.label_mappings:
                    self.num_classes = self.label_mappings["num_classes"]
                else:
                    self.num_classes = len(self.id_to_label)
            except Exception as e:
                self.logger.log_warn(f"Failed to load label mappings: {e}")
        else:
            self.logger.log_warn(f"Label file not found: {label_file}")
            # Create default mappings

    def compute_uncertainty(self, logits, covariance_matrix=None):
        """Compute uncertainty score based on configured method"""

        if self.ood_method == "sngp" and covariance_matrix is not None:
            # Handle different covariance matrix shapes
            if covariance_matrix.ndim == 3:
                # Shape: [batch_size, num_classes, num_classes]
                variance = np.array([np.trace(cov) for cov in covariance_matrix])
            elif covariance_matrix.ndim == 2:
                if covariance_matrix.shape[0] == covariance_matrix.shape[1]:
                    # Single covariance matrix: [num_classes, num_classes]
                    variance = np.full(logits.shape[0], np.trace(covariance_matrix))
                else:
                    # Batch of diagonal variances: [batch_size, num_classes]
                    variance = np.mean(covariance_matrix, axis=-1)
            else:
                # 1D array: [batch_size] or [num_classes]
                if len(covariance_matrix) == logits.shape[0]:
                    variance = covariance_matrix
                else:
                    variance = np.full(logits.shape[0], np.mean(covariance_matrix))

            return variance

        # Fallback to max probability confidence for any method
        probabilities = softmax(logits, axis=1)
        max_probs = np.max(probabilities, axis=1)
        return 1.0 - max_probs

    def apply_uncertainty_strategy_new_format(
        self, sample_result, uncertainty_score, probabilities, batch_idx
    ):
        """Apply uncertainty handling strategy to modify predictions - new format version"""

        # If no strategy is set, just return original predictions
        if self.uncertainty_strategy is None or self.uncertainty_strategy == "none":
            return sample_result

        confidence_score = 1.0 - uncertainty_score
        is_high_uncertainty = uncertainty_score > self.ood_threshold
        needs_human_handoff = uncertainty_score > self.human_handoff_threshold

        # Log important cases (even if not modifying output)
        if needs_human_handoff:
            if hasattr(self.logger, "log_warn"):
                self.logger.log_warn(
                    f"Sample {batch_idx}: High uncertainty ({uncertainty_score:.3f}) - Human handoff recommended"
                )
        elif is_high_uncertainty:
            if hasattr(self.logger, "log_info"):
                self.logger.log_info(
                    f"Sample {batch_idx}: OOD detected ({uncertainty_score:.3f})"
                )

        if self.uncertainty_strategy == "inject_class":
            if needs_human_handoff:
                # Inject human handoff signal as top prediction
                handoff_item = {
                    "agency_id": -1,
                    "agency_name": "human_handoff_required",
                    "confidence": float(uncertainty_score),
                }
                # Add at the beginning and shift others
                return [handoff_item] + sample_result

            elif is_high_uncertainty:
                # Inject OOD/uncertain class
                ood_item = {
                    "agency_id": -2,
                    "agency_name": "out_of_domain",
                    "confidence": float(uncertainty_score),
                }
                # Add at the beginning and shift others
                return [ood_item] + sample_result

        elif self.uncertainty_strategy == "confidence_scaling":
            # Scale probabilities by confidence
            if self.confidence_scaling and confidence_score < 0.8:
                scaled_result = []
                for item in sample_result:
                    scaled_item = item.copy()
                    scaled_item["confidence"] = float(
                        item["confidence"] * confidence_score
                    )
                    scaled_result.append(scaled_item)
                return scaled_result

        elif self.uncertainty_strategy == "threshold_filter":
            # If too uncertain, return generic "uncertain" response
            if needs_human_handoff:
                return [
                    {
                        "agency_id": -3,
                        "agency_name": "uncertain_input",
                        "confidence": 1.0,
                    }
                ]
            elif is_high_uncertainty:
                return [
                    {
                        "agency_id": -4,
                        "agency_name": "low_confidence",
                        "confidence": float(confidence_score),
                    }
                ]

        # Return original predictions if no strategy applied
        return sample_result

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
            if logits_tensor is None:
                self.logger.log_error("No logits tensor found in request")
                continue

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
                        self.logger.log_info(
                            f"Got covariance matrix with shape: {covariance_matrix.shape}"
                        )
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

            # Compute uncertainty if OOD method is enabled
            uncertainty_scores = None
            if self.ood_method != "none":
                try:
                    uncertainty_scores = self.compute_uncertainty(
                        logits, covariance_matrix
                    )
                except Exception as e:
                    self.logger.log_warn(f"Failed to compute uncertainty: {e}")
                    uncertainty_scores = None

            batch_size = probabilities.shape[0]
            top_k_results = []

            for i in range(batch_size):
                # Get standard top-k predictions
                top_k_indices = np.argsort(probabilities[i])[-top_k:][::-1]
                top_k_probs = probabilities[i][top_k_indices]

                # Build result in the new format
                sample_result = []
                for idx, prob in zip(top_k_indices, top_k_probs):
                    label_name = self.id_to_label.get(str(idx), f"class_{idx}")

                    # Create the new format with agency_id, agency_name, and confidence
                    prediction_item = {
                        "agency_id": self.agency_id2label.get(label_name),
                        "agency_name": label_name,
                        "confidence": float(prob),
                    }
                    sample_result.append(prediction_item)

                # Apply uncertainty strategy to potentially modify result
                if self.ood_method != "none" and uncertainty_scores is not None:
                    sample_result = self.apply_uncertainty_strategy_new_format(
                        sample_result, uncertainty_scores[i], probabilities[i], i
                    )

                top_k_results.append(sample_result)

            # Create output tensor - new format
            # Convert the list of results to JSON string
            results_json = json.dumps(top_k_results)

            # Create output tensor as single JSON string containing the array
            output_tensor = pb_utils.Tensor(
                "TOP_K_PREDICTIONS", np.array([results_json], dtype=object)
            )

            response = pb_utils.InferenceResponse(output_tensors=[output_tensor])
            responses.append(response)

        return responses

    def finalize(self):
        """Clean up resources"""
        pass
