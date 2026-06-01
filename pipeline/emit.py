"""
Event emission and streaming to API.
"""
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import requests


class EventEmitter:
    """
    Emit structured events to file or API.
    
    Handles:
    - Event schema validation
    - Batch emission
    - API streaming
    - File output
    """
    
    def __init__(
        self,
        output_path: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        batch_size: int = 100
    ):
        """
        Initialize event emitter.
        
        Args:
            output_path: Path to output JSONL file
            api_endpoint: API endpoint for streaming (e.g., http://localhost:8000/events/ingest)
            batch_size: Number of events to batch before sending
        """
        self.output_path = output_path
        self.api_endpoint = api_endpoint
        self.batch_size = batch_size
        
        self.event_buffer: List[Dict[str, Any]] = []
        self.file_handle = None
        
        if output_path:
            self.file_handle = open(output_path, 'w')
    
    def emit_entry(
        self,
        store_id: str,
        camera_id: str,
        visitor_id: str,
        timestamp: datetime,
        is_staff: bool,
        confidence: float,
        session_seq: int
    ):
        """Emit ENTRY event."""
        event = self._create_event(
            store_id=store_id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            event_type="ENTRY",
            timestamp=timestamp,
            zone_id=None,
            dwell_ms=0,
            is_staff=is_staff,
            confidence=confidence,
            metadata={
                "queue_depth": None,
                "sku_zone": None,
                "session_seq": session_seq
            }
        )
        
        self._write_event(event)
    
    def emit_exit(
        self,
        store_id: str,
        camera_id: str,
        visitor_id: str,
        timestamp: datetime,
        is_staff: bool,
        confidence: float,
        session_seq: int
    ):
        """Emit EXIT event."""
        event = self._create_event(
            store_id=store_id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            event_type="EXIT",
            timestamp=timestamp,
            zone_id=None,
            dwell_ms=0,
            is_staff=is_staff,
            confidence=confidence,
            metadata={
                "queue_depth": None,
                "sku_zone": None,
                "session_seq": session_seq
            }
        )
        
        self._write_event(event)
    
    def emit_zone_enter(
        self,
        store_id: str,
        camera_id: str,
        visitor_id: str,
        timestamp: datetime,
        zone_id: str,
        is_staff: bool,
        confidence: float,
        session_seq: int,
        sku_zone: Optional[str] = None
    ):
        """Emit ZONE_ENTER event."""
        event = self._create_event(
            store_id=store_id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            event_type="ZONE_ENTER",
            timestamp=timestamp,
            zone_id=zone_id,
            dwell_ms=0,
            is_staff=is_staff,
            confidence=confidence,
            metadata={
                "queue_depth": None,
                "sku_zone": sku_zone,
                "session_seq": session_seq
            }
        )
        
        self._write_event(event)
    
    def emit_zone_dwell(
        self,
        store_id: str,
        camera_id: str,
        visitor_id: str,
        timestamp: datetime,
        zone_id: str,
        dwell_ms: int,
        is_staff: bool,
        confidence: float,
        session_seq: int,
        sku_zone: Optional[str] = None
    ):
        """Emit ZONE_DWELL event."""
        event = self._create_event(
            store_id=store_id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            event_type="ZONE_DWELL",
            timestamp=timestamp,
            zone_id=zone_id,
            dwell_ms=dwell_ms,
            is_staff=is_staff,
            confidence=confidence,
            metadata={
                "queue_depth": None,
                "sku_zone": sku_zone,
                "session_seq": session_seq
            }
        )
        
        self._write_event(event)
    
    def emit_billing_queue_join(
        self,
        store_id: str,
        camera_id: str,
        visitor_id: str,
        timestamp: datetime,
        zone_id: str,
        queue_depth: int,
        is_staff: bool,
        confidence: float,
        session_seq: int
    ):
        """Emit BILLING_QUEUE_JOIN event."""
        event = self._create_event(
            store_id=store_id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            event_type="BILLING_QUEUE_JOIN",
            timestamp=timestamp,
            zone_id=zone_id,
            dwell_ms=0,
            is_staff=is_staff,
            confidence=confidence,
            metadata={
                "queue_depth": queue_depth,
                "sku_zone": None,
                "session_seq": session_seq
            }
        )
        
        self._write_event(event)
    
    def emit_reentry(
        self,
        store_id: str,
        camera_id: str,
        visitor_id: str,
        timestamp: datetime,
        is_staff: bool,
        confidence: float,
        session_seq: int
    ):
        """Emit REENTRY event."""
        event = self._create_event(
            store_id=store_id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            event_type="REENTRY",
            timestamp=timestamp,
            zone_id=None,
            dwell_ms=0,
            is_staff=is_staff,
            confidence=confidence,
            metadata={
                "queue_depth": None,
                "sku_zone": None,
                "session_seq": session_seq
            }
        )
        
        self._write_event(event)
    
    def _create_event(
        self,
        store_id: str,
        camera_id: str,
        visitor_id: str,
        event_type: str,
        timestamp: datetime,
        zone_id: Optional[str],
        dwell_ms: int,
        is_staff: bool,
        confidence: float,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create event dictionary."""
        return {
            "event_id": str(uuid.uuid4()),
            "store_id": store_id,
            "camera_id": camera_id,
            "visitor_id": visitor_id,
            "event_type": event_type,
            "timestamp": timestamp.isoformat() + "Z",
            "zone_id": zone_id,
            "dwell_ms": int(dwell_ms),
            "is_staff": bool(is_staff),  # Convert to Python bool
            "confidence": float(confidence),  # Convert to Python float
            "metadata": metadata
        }
    
    def _write_event(self, event: Dict[str, Any]):
        """Write event to buffer and flush if needed."""
        self.event_buffer.append(event)
        
        # Write to file immediately
        if self.file_handle:
            self.file_handle.write(json.dumps(event) + '\n')
            self.file_handle.flush()
        
        # Batch send to API
        if self.api_endpoint and len(self.event_buffer) >= self.batch_size:
            self.flush()
    
    def flush(self):
        """Flush buffered events to API."""
        if not self.api_endpoint or len(self.event_buffer) == 0:
            return
        
        try:
            # Send batch to API
            response = requests.post(
                self.api_endpoint,
                json={"events": self.event_buffer},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"✓ Sent {len(self.event_buffer)} events to API")
                self.event_buffer = []
            else:
                print(f"✗ API error: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"✗ Failed to send events to API: {e}")
    
    def close(self):
        """Close emitter and flush remaining events."""
        self.flush()
        
        if self.file_handle:
            self.file_handle.close()
