"""
Pydantic models for event schema and API responses.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    """Event type enumeration."""
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"


class EventMetadata(BaseModel):
    """Event metadata structure."""
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: int = Field(..., ge=1)


class StoreEvent(BaseModel):
    """
    Core event schema emitted by detection pipeline.
    
    This schema must be followed exactly by the detection layer.
    """
    event_id: UUID = Field(default_factory=uuid4)
    store_id: str = Field(..., pattern=r"^STORE_[A-Z]{3}_\d{3}$")
    camera_id: str = Field(..., pattern=r"^CAM_[A-Z_]+_\d{2}$")
    visitor_id: str = Field(..., pattern=r"^VIS_[a-f0-9]+$")
    event_type: EventType
    timestamp: datetime
    zone_id: Optional[str] = None
    dwell_ms: int = Field(default=0, ge=0)
    is_staff: bool = False
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: EventMetadata

    @field_validator('zone_id')
    @classmethod
    def validate_zone_id(cls, v, info):
        """Zone ID must be null for ENTRY/EXIT events."""
        event_type = info.data.get('event_type')
        if event_type in [EventType.ENTRY, EventType.EXIT]:
            if v is not None:
                raise ValueError(f"zone_id must be null for {event_type} events")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_ENTRY_01",
                "visitor_id": "VIS_c8a2f1",
                "event_type": "ZONE_DWELL",
                "timestamp": "2026-03-03T14:22:10Z",
                "zone_id": "SKINCARE",
                "dwell_ms": 8400,
                "is_staff": False,
                "confidence": 0.91,
                "metadata": {
                    "queue_depth": None,
                    "sku_zone": "MOISTURISER",
                    "session_seq": 5
                }
            }
        }


class EventBatch(BaseModel):
    """Batch of events for ingestion."""
    events: list[StoreEvent] = Field(..., max_length=500)


class IngestResponse(BaseModel):
    """Response from event ingestion."""
    accepted: int
    rejected: int
    errors: list[Dict[str, Any]] = []


class StoreMetrics(BaseModel):
    """Real-time store metrics."""
    store_id: str
    date: str
    unique_visitors: int
    total_entries: int
    total_exits: int
    conversion_rate: float
    avg_dwell_per_zone: Dict[str, float]
    current_queue_depth: int
    abandonment_rate: float
    staff_excluded: int


class FunnelStage(BaseModel):
    """Single stage in conversion funnel."""
    stage: str
    count: int
    drop_off_pct: float


class ConversionFunnel(BaseModel):
    """Conversion funnel analysis."""
    store_id: str
    date: str
    stages: list[FunnelStage]


class HeatmapZone(BaseModel):
    """Zone data for heatmap."""
    zone_id: str
    visit_count: int
    avg_dwell_ms: float
    normalized_score: int = Field(..., ge=0, le=100)


class Heatmap(BaseModel):
    """Store heatmap data."""
    store_id: str
    date: str
    zones: list[HeatmapZone]
    data_confidence: bool


class AnomalySeverity(str, Enum):
    """Anomaly severity levels."""
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class Anomaly(BaseModel):
    """Detected anomaly."""
    anomaly_type: str
    severity: AnomalySeverity
    description: str
    suggested_action: str
    detected_at: datetime
    metadata: Dict[str, Any] = {}


class AnomalyResponse(BaseModel):
    """Active anomalies for a store."""
    store_id: str
    anomalies: list[Anomaly]


class StoreHealth(BaseModel):
    """Health status for a store."""
    store_id: str
    last_event_timestamp: Optional[datetime]
    is_stale: bool
    stale_duration_minutes: Optional[int]


class HealthResponse(BaseModel):
    """Overall service health."""
    status: str
    stores: list[StoreHealth]
    warnings: list[str] = []
