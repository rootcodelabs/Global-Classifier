from __unknown__ import TritonPythonModel
import numpy as np
import triton_python_backend_utils as pb_utils

class TritonPythonModel:
    """
    Dummy model that returns a static payload.
    This model is used to ensure the Triton server starts without errors.
    """

    def initialize(self, args):
        """Initialize the dummy model."""
        self.logger = pb_utils.Logger
        self.logger.log_info("Dummy model initialized")

    def execute(self, requests):
        """Return a static response for each request."""
        responses = []
        for request in requests:
            # Create a dummy output tensor with static values
            output_tensor = pb_utils.Tensor.from_numpy("text_output", np.array([["Hello, world!"]], dtype=object))
            response = pb_utils.InferenceResponse(output_tensors=[output_tensor])
            responses.append(response)
        
        return responses
