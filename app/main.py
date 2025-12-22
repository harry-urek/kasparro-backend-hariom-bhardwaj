"""
FastAPI Main Application
"""
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

app = FastAPI(
    title="Kasparro Backend Service",
    description="Lightweight backend service with data and health endpoints",
    version="1.0.0"
)


class DataResponse(BaseModel):
    """Response model for /data endpoint"""
    request_id: str
    api_latency_ms: float
    data: list
    page: int
    page_size: int
    total_items: int


class HealthResponse(BaseModel):
    """Response model for /health endpoint"""
    status: str
    db_connected: bool
    etl_last_run: Optional[str] = None
    etl_status: Optional[str] = None


@app.get("/data", response_model=DataResponse)
async def get_data(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    filter_by: Optional[str] = Query(None, description="Filter criteria")
):
    """
    GET /data endpoint with pagination and filtering support.
    Returns metadata including request_id and api_latency_ms.
    
    Args:
        page: Page number (starting from 1)
        page_size: Number of items per page (1-100)
        filter_by: Optional filter criteria
        
    Returns:
        DataResponse with request metadata and paginated data
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # TODO: Implement actual data fetching logic
    # TODO: Apply filtering based on filter_by parameter
    # TODO: Implement pagination logic
    
    # Skeleton response
    data = []
    total_items = 0
    
    latency_ms = (time.time() - start_time) * 1000
    
    return DataResponse(
        request_id=request_id,
        api_latency_ms=round(latency_ms, 2),
        data=data,
        page=page,
        page_size=page_size,
        total_items=total_items
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    GET /health endpoint.
    Reports database connectivity and ETL last-run status.
    
    Returns:
        HealthResponse with service health information
    """
    # TODO: Implement actual database connectivity check
    db_connected = False
    
    # TODO: Implement ETL status check
    etl_last_run = None
    etl_status = None
    
    status = "healthy" if db_connected else "degraded"
    
    return HealthResponse(
        status=status,
        db_connected=db_connected,
        etl_last_run=etl_last_run,
        etl_status=etl_status
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Kasparro Backend Service",
        "version": "1.0.0",
        "endpoints": ["/data", "/health"]
    }
