"""
Store Intelligence API - Main FastAPI application.
"""
import os
import time
from datetime import date
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import (
    EventBatch,
    IngestResponse,
    StoreMetrics,
    ConversionFunnel,
    Heatmap,
    AnomalyResponse,
    HealthResponse
)
from app.ingestion import EventIngestionService
from app.metrics import MetricsService
from app.funnel import FunnelService
from app.heatmap import HeatmapService
from app.anomalies import AnomalyDetectionService
from app.health import HealthService
from app.logging_config import configure_logging, get_logger, set_trace_id, get_trace_id
import uuid


# Configure logging
configure_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("application_starting")
    
    # Initialize database (with retry logic for Render)
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            init_db()
            logger.info("database_initialized")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    "database_init_retry",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e)
                )
                time.sleep(retry_delay)
            else:
                logger.error("database_init_failed", error=str(e), exc_info=True)
                # Don't raise - let app start anyway for health checks
                logger.warning("starting_without_database")
    
    yield
    
    logger.info("application_shutting_down")


# Create FastAPI app
app = FastAPI(
    title="Store Intelligence API",
    description="Real-time retail analytics from CCTV footage",
    version="1.0.0",
    lifespan=lifespan
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """
    Structured logging middleware.
    
    Logs: trace_id, store_id, endpoint, latency_ms, event_count, status_code
    """
    # Generate trace ID
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    
    # Extract store_id from path if present
    store_id = None
    if "stores" in request.url.path:
        path_parts = request.url.path.split("/")
        if "stores" in path_parts:
            idx = path_parts.index("stores")
            if idx + 1 < len(path_parts):
                store_id = path_parts[idx + 1]
    
    # Start timer
    start_time = time.time()
    
    # Process request
    try:
        response = await call_next(request)
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log request
        logger.info(
            "request_completed",
            trace_id=trace_id,
            method=request.method,
            endpoint=request.url.path,
            store_id=store_id,
            latency_ms=latency_ms,
            status_code=response.status_code
        )
        
        # Add trace ID to response headers
        response.headers["X-Trace-ID"] = trace_id
        
        return response
        
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "request_failed",
            trace_id=trace_id,
            method=request.method,
            endpoint=request.url.path,
            store_id=store_id,
            latency_ms=latency_ms,
            error=str(e),
            exc_info=True
        )
        raise


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with structured error responses."""
    logger.error(
        "unhandled_exception",
        trace_id=get_trace_id(),
        endpoint=request.url.path,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "trace_id": get_trace_id()
        }
    )


@app.post(
    "/events/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK
)
async def ingest_events(
    batch: EventBatch,
    db: Session = Depends(get_db)
):
    """
    Ingest a batch of events (up to 500).
    
    Features:
    - Idempotent by event_id
    - Partial success on malformed events
    - Structured error responses
    """
    try:
        service = EventIngestionService(db)
        
        logger.info(
            "ingesting_batch",
            event_count=len(batch.events),
            trace_id=get_trace_id()
        )
        
        result = service.ingest_batch(batch.events)
        
        logger.info(
            "batch_ingested",
            accepted=result.accepted,
            rejected=result.rejected,
            trace_id=get_trace_id()
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "ingestion_error",
            error=str(e),
            trace_id=get_trace_id(),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ingestion_failed",
                "message": str(e),
                "trace_id": get_trace_id()
            }
        )


@app.get(
    "/stores/{store_id}/metrics",
    response_model=StoreMetrics
)
async def get_store_metrics(
    store_id: str,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get real-time metrics for a store.
    
    Returns:
    - Unique visitors (staff excluded)
    - Conversion rate
    - Average dwell per zone
    - Current queue depth
    - Abandonment rate
    """
    try:
        target_date = date_from_string(date) if date else None
        
        service = MetricsService(db)
        metrics = service.get_store_metrics(store_id, target_date)
        
        return metrics
        
    except Exception as e:
        logger.error(
            "metrics_error",
            store_id=store_id,
            error=str(e),
            trace_id=get_trace_id(),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "metrics_computation_failed",
                "message": str(e),
                "trace_id": get_trace_id()
            }
        )


@app.get(
    "/stores/{store_id}/funnel",
    response_model=ConversionFunnel
)
async def get_conversion_funnel(
    store_id: str,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get conversion funnel analysis.
    
    Stages: Entry → Zone Visit → Billing Queue → Purchase
    
    Returns counts and drop-off percentages per stage.
    """
    try:
        target_date = date_from_string(date) if date else None
        
        service = FunnelService(db)
        funnel = service.get_conversion_funnel(store_id, target_date)
        
        return funnel
        
    except Exception as e:
        logger.error(
            "funnel_error",
            store_id=store_id,
            error=str(e),
            trace_id=get_trace_id(),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "funnel_computation_failed",
                "message": str(e),
                "trace_id": get_trace_id()
            }
        )


@app.get(
    "/stores/{store_id}/heatmap",
    response_model=Heatmap
)
async def get_heatmap(
    store_id: str,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get zone visit heatmap.
    
    Returns normalized scores (0-100) for each zone based on
    visit frequency and dwell time.
    """
    try:
        target_date = date_from_string(date) if date else None
        
        service = HeatmapService(db)
        heatmap = service.get_heatmap(store_id, target_date)
        
        return heatmap
        
    except Exception as e:
        logger.error(
            "heatmap_error",
            store_id=store_id,
            error=str(e),
            trace_id=get_trace_id(),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "heatmap_generation_failed",
                "message": str(e),
                "trace_id": get_trace_id()
            }
        )


@app.get(
    "/stores/{store_id}/anomalies",
    response_model=AnomalyResponse
)
async def get_anomalies(
    store_id: str,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get active anomalies for a store.
    
    Detects:
    - Queue spikes
    - Conversion drops vs 7-day average
    - Dead zones (no visits in 30+ minutes)
    """
    try:
        target_date = date_from_string(date) if date else None
        
        service = AnomalyDetectionService(db)
        anomalies = service.detect_anomalies(store_id, target_date)
        
        return anomalies
        
    except Exception as e:
        logger.error(
            "anomaly_detection_error",
            store_id=store_id,
            error=str(e),
            trace_id=get_trace_id(),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "anomaly_detection_failed",
                "message": str(e),
                "trace_id": get_trace_id()
            }
        )


@app.get(
    "/health",
    response_model=HealthResponse
)
async def health_check(db: Session = Depends(get_db)):
    """
    Service health check.
    
    Returns:
    - Overall status
    - Last event timestamp per store
    - STALE_FEED warnings (>10 min lag)
    """
    try:
        service = HealthService(db)
        health = service.get_health_status()
        
        return health
        
    except Exception as e:
        logger.error(
            "health_check_error",
            error=str(e),
            trace_id=get_trace_id(),
            exc_info=True
        )
        
        # Return unhealthy status
        return HealthResponse(
            status="unhealthy",
            stores=[],
            warnings=[f"Health check failed: {str(e)}"]
        )


def date_from_string(date_str: str) -> date:
    """Parse date string (YYYY-MM-DD)."""
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD"
        )


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "service": "Store Intelligence API",
        "version": "1.0.0",
        "status": "operational"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
