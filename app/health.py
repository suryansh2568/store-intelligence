"""
Service health monitoring.
"""
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from app.models import HealthResponse, StoreHealth
from app.database import EventRecord
from app.logging_config import get_logger

logger = get_logger(__name__)


class HealthService:
    """Service for monitoring system health."""

    STALE_THRESHOLD_MINUTES = 10

    def __init__(self, db: Session):
        self.db = db

    def get_health_status(self) -> HealthResponse:
        """
        Get overall service health status.
        
        Checks:
        - Database connectivity
        - Last event timestamp per store
        - Stale feed detection (>10 min since last event)
        
        Returns:
            HealthResponse with status and warnings
        """
        logger.info("checking_health_status")

        warnings = []
        stores = []

        try:
            # Get all unique store IDs
            store_ids = self.db.query(
                distinct(EventRecord.store_id)
            ).all()

            store_ids = [sid[0] for sid in store_ids]

            if not store_ids:
                warnings.append("No stores found in database")
                return HealthResponse(
                    status="degraded",
                    stores=[],
                    warnings=warnings
                )

            # Check each store
            now = datetime.now()
            stale_threshold = now - timedelta(minutes=self.STALE_THRESHOLD_MINUTES)

            for store_id in store_ids:
                # Get latest event timestamp
                latest = self.db.query(
                    func.max(EventRecord.timestamp)
                ).filter(
                    EventRecord.store_id == store_id
                ).scalar()

                is_stale = False
                stale_duration = None

                if latest:
                    if latest < stale_threshold:
                        is_stale = True
                        stale_duration = int((now - latest).total_seconds() / 60)
                        warnings.append(
                            f"STALE_FEED: {store_id} - no events for {stale_duration} minutes"
                        )
                else:
                    is_stale = True
                    warnings.append(f"NO_DATA: {store_id} - no events recorded")

                stores.append(StoreHealth(
                    store_id=store_id,
                    last_event_timestamp=latest,
                    is_stale=is_stale,
                    stale_duration_minutes=stale_duration
                ))

            # Determine overall status
            if len(warnings) == 0:
                status = "healthy"
            elif len(warnings) < len(store_ids):
                status = "degraded"
            else:
                status = "unhealthy"

            logger.info(
                "health_check_complete",
                status=status,
                stores_count=len(stores),
                warnings_count=len(warnings)
            )

            return HealthResponse(
                status=status,
                stores=stores,
                warnings=warnings
            )

        except Exception as e:
            logger.error(
                "health_check_failed",
                error=str(e),
                exc_info=True
            )
            return HealthResponse(
                status="unhealthy",
                stores=[],
                warnings=[f"Health check failed: {str(e)}"]
            )
