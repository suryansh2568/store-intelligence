"""
Event ingestion with deduplication and validation.
"""
from typing import List, Tuple, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import StoreEvent, IngestResponse
from app.database import EventRecord
from app.logging_config import get_logger

logger = get_logger(__name__)


class EventIngestionService:
    """Service for ingesting and storing events."""

    def __init__(self, db: Session):
        self.db = db

    def ingest_batch(self, events: List[StoreEvent]) -> IngestResponse:
        """
        Ingest a batch of events with deduplication.
        
        This method is idempotent - calling it multiple times with the same
        events will not create duplicates.
        
        Args:
            events: List of events to ingest
            
        Returns:
            IngestResponse with counts and any errors
        """
        accepted = 0
        rejected = 0
        errors = []

        for event in events:
            try:
                # Check if event already exists (idempotency)
                existing = self.db.query(EventRecord).filter(
                    EventRecord.event_id == str(event.event_id)
                ).first()

                if existing:
                    logger.debug(
                        "event_already_exists",
                        event_id=str(event.event_id),
                        store_id=event.store_id
                    )
                    accepted += 1  # Count as accepted (idempotent)
                    continue

                # Create new event record
                event_record = EventRecord(
                    event_id=str(event.event_id),
                    store_id=event.store_id,
                    camera_id=event.camera_id,
                    visitor_id=event.visitor_id,
                    event_type=event.event_type.value,
                    timestamp=event.timestamp,
                    zone_id=event.zone_id,
                    dwell_ms=event.dwell_ms,
                    is_staff=event.is_staff,
                    confidence=event.confidence,
                    event_metadata=event.metadata.model_dump()
                )

                self.db.add(event_record)
                self.db.flush()  # Flush to catch integrity errors

                accepted += 1
                logger.debug(
                    "event_ingested",
                    event_id=str(event.event_id),
                    store_id=event.store_id,
                    event_type=event.event_type.value
                )

            except IntegrityError as e:
                self.db.rollback()
                rejected += 1
                error_detail = {
                    "event_id": str(event.event_id),
                    "error": "duplicate_event",
                    "message": "Event ID already exists"
                }
                errors.append(error_detail)
                logger.warning(
                    "event_rejected_integrity",
                    event_id=str(event.event_id),
                    error=str(e)
                )

            except Exception as e:
                self.db.rollback()
                rejected += 1
                error_detail = {
                    "event_id": str(event.event_id),
                    "error": "ingestion_failed",
                    "message": str(e)
                }
                errors.append(error_detail)
                logger.error(
                    "event_ingestion_failed",
                    event_id=str(event.event_id),
                    error=str(e),
                    exc_info=True
                )

        # Commit all successful inserts
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error("batch_commit_failed", error=str(e), exc_info=True)
            raise

        logger.info(
            "batch_ingestion_complete",
            total=len(events),
            accepted=accepted,
            rejected=rejected
        )

        return IngestResponse(
            accepted=accepted,
            rejected=rejected,
            errors=errors
        )

    def get_event_count(self, store_id: str) -> int:
        """Get total event count for a store."""
        return self.db.query(EventRecord).filter(
            EventRecord.store_id == store_id
        ).count()

    def get_latest_event_timestamp(self, store_id: str):
        """Get timestamp of most recent event for a store."""
        result = self.db.query(EventRecord.timestamp).filter(
            EventRecord.store_id == store_id
        ).order_by(EventRecord.timestamp.desc()).first()
        
        return result[0] if result else None
