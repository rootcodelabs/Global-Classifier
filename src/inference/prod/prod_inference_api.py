import os
from typing import Dict, Any, List
import json
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
import numpy as np
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Global Classifier API",
    description="API for serving Global Classifier predictions",
    version="1.0.0"
)

# Define request and response models
class PredictionRequest(BaseModel):
    text: str
    additional_context: Dict[str, Any] = {}

class PredictionResponse(BaseModel):
    prediction: str
    confidence: float
    scores: Dict[str, float]

# Mock model class (replace with your actual model implementation)
class GlobalClassifier:
    def __init__(self, model_path: str = None):
        logger.info(f"Initializing model from {model_path if model_path else 'default location'}")
        self.model_path = model_path
        self.labels = ["class_1", "class_2", "class_3"]  # Replace with your actual classes
        # TODO: Load your actual model here
        
    def predict(self, text: str, **kwargs) -> Dict[str, Any]:
        # TODO: Replace with actual prediction logic
        logger.info(f"Making prediction for text: {text[:50]}...")
        
        # Mock prediction - replace with actual model inference
        mock_scores = np.random.uniform(0, 1, len(self.labels))
        mock_scores = mock_scores / mock_scores.sum()  # Normalize to probabilities
        
        prediction_idx = np.argmax(mock_scores)
        prediction = self.labels[prediction_idx]
        confidence = float(mock_scores[prediction_idx])
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "scores": {label: float(score) for label, score in zip(self.labels, mock_scores)}
        }

# Load model at startup
@app.on_event("startup")
async def startup_event():
    global model
    model_path = os.environ.get("MODEL_PATH")
    model = GlobalClassifier(model_path)
    logger.info("Model loaded and ready for inference")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Prediction endpoint
@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    try:
        result = model.predict(request.text, **request.additional_context)
        return result
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

# Batch prediction endpoint
@app.post("/predict_batch", response_model=List[PredictionResponse])
async def predict_batch(requests: List[PredictionRequest]):
    try:
        results = [
            model.predict(req.text, **req.additional_context)
            for req in requests
        ]
        return results
    except Exception as e:
        logger.error(f"Batch prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch prediction error: {str(e)}")

if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8000))
    
    # Run the API server
    uvicorn.run(app, host="0.0.0.0", port=port)