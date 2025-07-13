from model-training.trainingpipeline import device
import os
from typing import Optional, Dict, List, Any
import litserve as ls

#TODO - Add endpoint to download model file from S3 ferry
#TODO - Add endpoint to hot swap model file from S3 ferry
#TODO - Add ruuter API calls to update model handler endpoint
#TODO - Add endpoint to remove serving of model and replace with default empty model


class ProdInferenceAPI(ls.LitAPI):
    """
    Production inference API for serving models.
    """

    def setup(self, device="cpu") -> None:
        """
        Setup the inference API with the specified device.
        """

        self.model = default_model()
        ``
        