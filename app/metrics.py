"""
Real-time metrics computation.
"""
from datetime import datetime, date, timedelta
from typing import Dict, Optional
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models import StoreMetrics, EventType
from app.database import EventRecord, POSTransaction
from app.logging_config import get_logger

logger = get_logger(__name__)


class MetricsService:
    """Service for computing real-time store metrics."""

    def __init__(self, db: Session):
        self.db = db

    def get_store_metrics(
        self,
        store_id: str,
        target_date: Optional[date] = None
    ) -> StoreMetrics:
        """
        Compute real-time metrics for a store.
        
        Args:
            store_id: Store identifier
            target_date: Date to compute metrics for (default: today)
            
        Returns:
            StoreMetrics with all computed values
        """
        if target_date is None:
            target_date = date.today()

        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = datetime.combine(target_date, datetime.max.time())

        logger.info(
            "computing_metrics",
            store_id=store_id,
            date=str(target_date)
        )

        # Base query for non-staff events
        base_query = self.db.query(EventRecord).filter(
            and_(
                EventRecord.store_id == store_id,
                EventRecord.timestamp >= start_time,
                EventRecord.timestamp <= end_time,
                EventRecord.is_staff == False
            )
        )

        # Count staff events (for reporting)
        staff_count = self.db.query(func.count(EventRecord.event_id)).filter(
            and_(
                EventRecord.store_id == store_id,
                EventRecord.timestamp >= start_time,
                EventRecord.timestamp <= end_time,
                EventRecord.is_staff == True
            )
        ).scalar() or 0

        # Get unique visitors (distinct visitor_ids with ENTRY events)
        unique_visitors = self.db.query(
            func.count(func.distinct(EventRecord.visitor_id))
        ).filter(
            and_(
                EventRecord.store_id == store_id,
                EventRecord.timestamp >= start_time,
                EventRecord.timestamp <= end_time,
                EventRecord.event_type == EventType.ENTRY.value,
                EventRecord.is_staff == False
            )
        ).scalar() or 0

        # Total entries and exits
        total_entries = base_query.filter(
            EventRecord.event_type == EventType.ENTRY.value
        ).count()

        total_exits = base_query.filter(
            EventRecord.event_type == EventType.EXIT.value
        ).count()

        # Get visitors who entered billing zone
        billing_visitors = set()
        billing_events = base_query.filter(
            EventRecord.zone_id.like('%BILLING%')
        ).all()
        
        for event in billing_events:
            billing_visitors.add(event.visitor_id)

        # Get POS transactions for conversion calculation
        pos_transactions = self.db.query(POSTransaction).filter(
            and_(
                POSTransaction.store_id == store_id,
                POSTransaction.timestamp >= start_time,
                POSTransaction.timestamp <= end_time
            )
        ).all()

        # Match transactions to visitors (5-minute window correlation)
        converted_visitors = set()
        for txn in pos_transactions:
            # Find visitors in billing zone within 5 minutes before transaction
            window_start = txn.timestamp - timedelta(minutes=5)
            potential_visitors = self.db.query(EventRecord.visitor_id).filter(
                and_(
                    EventRecord.store_id == store_id,
                    EventRecord.zone_id.like('%BILLING%'),
                    EventRecord.timestamp >= window_start,
                    EventRecord.timestamp <= txn.timestamp,
                    EventRecord.is_staff == False
                )
            ).distinct().all()
            
            for (visitor_id,) in potential_visitors:
                converted_visitors.add(visitor_id)

        # Conversion rate
        conversion_rate = (
            len(converted_visitors) / unique_visitors
            if unique_visitors > 0
            else 0.0
        )

        # Average dwell per zone
        zone_dwell = defaultdict(list)
        dwell_events = base_query.filter(
            EventRecord.event_type == EventType.ZONE_DWELL.value
        ).all()

        for event in dwell_events:
            if event.zone_id:
                zone_dwell[event.zone_id].append(event.dwell_ms)

        avg_dwell_per_zone = {
            zone: sum(dwells) / len(dwells)
            for zone, dwells in zone_dwell.items()
        }

        # Current queue depth (most recent BILLING_QUEUE_JOIN event)
        latest_queue_event = base_query.filter(
            EventRecord.event_type == EventType.BILLING_QUEUE_JOIN.value
        ).order_by(EventRecord.timestamp.desc()).first()

        current_queue_depth = 0
        if latest_queue_event and latest_queue_event.event_metadata:
            current_queue_depth = latest_queue_event.event_metadata.get('queue_depth', 0)

        # Abandonment rate
        abandonment_count = base_query.filter(
            EventRecord.event_type == EventType.BILLING_QUEUE_ABANDON.value
        ).count()

        abandonment_rate = (
            abandonment_count / len(billing_visitors)
            if len(billing_visitors) > 0
            else 0.0
        )

        metrics = StoreMetrics(
            store_id=store_id,
            date=str(target_date),
            unique_visitors=unique_visitors,
            total_entries=total_entries,
            total_exits=total_exits,
            conversion_rate=round(conversion_rate, 4),
            avg_dwell_per_zone=avg_dwell_per_zone,
            current_queue_depth=current_queue_depth,
            abandonment_rate=round(abandonment_rate, 4),
            staff_excluded=staff_count
        )

        logger.info(
            "metrics_computed",
            store_id=store_id,
            unique_visitors=unique_visitors,
            conversion_rate=conversion_rate
        )

        return metrics
