"""FastAPI endpoints for chunk download operations."""

from fastapi import FastAPI, HTTPException
from loguru import logger

from models.schemas import (
    ChunkDownloadRequest,
    ChunkDownloadResponse,
    MultiChunkDownloadRequest,
    MultiChunkDownloadResponse
)
from single_chunk_handler import ChunkService
from multiple_chunk_handler import MultiChunkService

# Create FastAPI app
app = FastAPI(
    title="Dataset File Handler API",
    description="API for handling dataset file operations including chunk downloads",
    version="1.0.0",
)

# Initialize services
chunk_service = ChunkService()
multi_chunk_service = MultiChunkService()


@app.post("/download-chunk", response_model=ChunkDownloadResponse)
async def download_chunk(request: ChunkDownloadRequest):
    """
    Download a single chunk from S3.
    
    Args:
        request: Chunk download request containing dataset_id and page_num
        
    Returns:
        Chunk data or error information
    """
    try:
        logger.info(f"Chunk download request - Dataset: {request.dataset_id}, Page: {request.page_num}")
        
        result = chunk_service.download_chunk_from_s3(request.dataset_id, request.page_num)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result)
        
        return ChunkDownloadResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal error during chunk download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/download-multiple-chunks", response_model=MultiChunkDownloadResponse)
async def download_multiple_chunks(request: MultiChunkDownloadRequest):
    """
    Download and aggregate multiple chunks from S3.
    
    Args:
        request: Multi-chunk download request containing dataset_id and chunk_ids
        
    Returns:
        Aggregated chunk data or error information
    """
    try:
        logger.info(f"Multi-chunk download request - Dataset: {request.dataset_id}, Chunks: {request.chunk_ids}")
        
        if not request.chunk_ids:
            raise HTTPException(status_code=400, detail="No chunk IDs provided")
        
        result = multi_chunk_service.download_multiple_chunks(request.dataset_id, request.chunk_ids)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result)
        
        return MultiChunkDownloadResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal error during multi-chunk download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/health")
async def chunk_health_check():
    """Health check endpoint for chunk services."""
    return {"status": "healthy", "service": "chunk-download"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)