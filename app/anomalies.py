"""
Anomaly detection for operational issues.
"""
from datetime import datetime, date, timedelta
from typing import List, Optional
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models import (
    AnomalyResponse,
    Anomaly,
    AnomalySeverity,
    EventType
)
from app.database import EventRecord
from app.logging_config import get_logger

logger = get_logger(__name__)


class AnomalyDetectionService:
    """Service for detecting operational anomalies."""

    def __init__(self, db: Session):
        self.db = db

    def detect_anomalies(
        self,
        store_id: str,
        target_date: Optional[date] = None
    ) -> AnomalyResponse:
        """
        Detect active anomalies for a store.
        
        Detects:
        - Queue spikes (sudden increase in billing queue depth)
        - Conversion drops (vs 7-day average)
        - Dead zones (no visits in 30+ minutes during operating hours)
        
        Args:
            store_id: Store identifier
            target_date: Date to analyze (default: today)
            
        Returns:
            AnomalyResponse with list of detected anomalies
        """
        if target_date is None:
            target_date = date.today()

        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = datetime.combine(target_date, datetime.max.time())

        logger.info(
            "detecting_anomalies",
            store_id=store_id,
            date=str(target_date)
        )

        anomalies = []

        # 1. Queue Spike Detection
        queue_anomaly = self._detect_queue_spike(store_id, start_time, end_time)
        if queue_anomaly:
            anomalies.append(queue_anomaly)

        # 2. Conversion Drop Detection
        conversion_anomaly = self._detect_conversion_drop(store_id, target_date)
        if conversion_anomaly:
            anomalies.append(conversion_anomaly)

        # 3. Dead Zone Detection
        dead_zone_anomalies = self._detect_dead_zones(store_id, start_time, end_time)
        anomalies.extend(dead_zone_anomalies)

        logger.info(
            "anomalies_detected",
            store_id=store_id,
            count=len(anomalies)
        )

        return AnomalyResponse(
            store_id=store_id,
            anomalies=anomalies
        )

    def _detect_queue_spike(
        self,
        store_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Anomaly]:
        """Detect billing queue spikes."""
        
        # Get recent queue join events
        queue_events = self.db.query(EventRecord).filter(
            and_(
                EventRecord.store_id == store_id,
                EventRecord.timestamp >= start_time,
                EventRecord.timestamp <= end_time,
                EventRecord.event_type == EventType.BILLING_QUEUE_JOIN.value
            )
        ).order_by(EventRecord.timestamp.desc()).limit(10).all()

        if not queue_events:
            return None

        # Check for high queue depth
        recent_depths = [
            e.event_metadata.get('queue_depth', 0)
            for e in queue_events
            if e.event_metadata
        ]

        if not recent_depths:
            return None

        max_depth = max(recent_depths)
        avg_depth = sum(recent_depths) / len(recent_depths)

        # Spike if max > 10 or avg > 5
        if max_depth > 10:
            return Anomaly(
                anomaly_type="BILLING_QUEUE_SPIKE",
                severity=AnomalySeverity.CRITICAL,
                description=f"Billing queue depth reached {max_depth} customers",
                suggested_action="Open additional billing counters immediately",
                detected_at=queue_events[0].timestamp,
                metadata={
                    "max_depth": max_depth,
                    "avg_depth": round(avg_depth, 2)
                }
            )
        elif avg_depth > 5:
            return Anomaly(
                anomaly_type="BILLING_QUEUE_ELEVATED",
                severity=AnomalySeverity.WARN,
                description=f"Average queue depth is {avg_depth:.1f} customers",
                suggested_action="Monitor queue and consider opening additional counter",
                detected_at=queue_events[0].timestamp,
                metadata={
                    "avg_depth": round(avg_depth, 2)
                }
            )

        return None

    def _detect_conversion_drop(
        self,
        store_id: str,
        target_date: date
    ) -> Optional[Anomaly]:
        """Detect conversion rate drops vs 7-day average."""
        
        # Get today's conversion data
        today_start = datetime.combine(target_date, datetime.min.time())
        today_end = datetime.combine(target_date, datetime.max.time())

        today_entries = self.db.query(func.count(func.distinct(EventRecord.visitor_id))).filter(
            and_(
                EventRecord.store_id == store_id,
                EventRecord.timestamp >= today_start,
                EventRecord.timestamp <= today_end,
                EventRecord.event_type == EventType.ENTRY.value,
                EventRecord.is_staff == False
            )
        ).scalar() or 0

        # Get 7-day historical average
        week_ago = target_date - timedelta(days=7)
        week_start = datetime.combine(week_ago, datetime.min.time())

        historical_entries = self.db.query(func.count(func.distinct(EventRecord.visitor_id))).filter(
            and_(
                EventRecord.store_id == store_id,
                EventRecord.timestamp >= week_start,
                EventRecord.timestamp < today_start,
                EventRecord.event_type == EventType.ENTRY.value,
                EventRecord.is_staff == False
            )
        ).scalar() or 0

        if historical_entries == 0 or today_entries == 0:
            return None

        avg_daily_entries = historical_entries / 7
        drop_pct = ((avg_daily_entries - today_entries) / avg_daily_entries) * 100

        # Alert if drop > 30%
        if drop_pct > 30:
            return Anomaly(
                anomaly_type="CONVERSION_DROP",
                severity=AnomalySeverity.WARN,
                description=f"Visitor count down {drop_pct:.1f}% vs 7-day average",
                suggested_action="Review store operations and marketing activities",
                detected_at=datetime.now(),
                metadata={
                    "today_entries": today_entries,
                    "avg_daily_entries": round(avg_daily_entries, 2),
                    "drop_percentage": round(drop_pct, 2)
                }
            )

        return None

    def _detect_dead_zones(
        self,
        store_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Anomaly]:
        """Detect zones with no visits in 30+ minutes."""
        
        # Get all zone events
        zone_events = self.db.query(EventRecord).filter(
            and_(
                EventRecord.store_id == store_id,
                EventRecord.timestamp >= start_time,
                EventRecord.timestamp <= end_time,
                EventRecord.zone_id.isnot(None),
                EventRecord.is_staff == False
            )
        ).order_by(EventRecord.zone_id, EventRecord.timestamp).all()

        # Group by zone
        zone_last_visit = defaultdict(lambda: None)
        for event in zone_events:
            zone_id = event.zone_id
            if zone_last_visit[zone_id] is None or event.timestamp > zone_last_visit[zone_id]:
                zone_last_visit[zone_id] = event.timestamp

        # Check for dead zones (no visit in 30+ minutes)
        anomalies = []
        now = datetime.now()
        threshold = timedelta(minutes=30)

        for zone_id, last_visit in zone_last_visit.items():
            if last_visit and (now - last_visit) > threshold:
                minutes_ago = int((now - last_visit).total_seconds() / 60)
                
                anomalies.append(Anomaly(
                    anomaly_type="DEAD_ZONE",
                    severity=AnomalySeverity.INFO,
                    description=f"Zone '{zone_id}' has no visits in {minutes_ago} minutes",
                    suggested_action="Check zone lighting and product placement",
                    detected_at=now,
                    metadata={
                        "zone_id": zone_id,
                        "last_visit": last_visit.isoformat(),
                        "minutes_since_visit": minutes_ago
                    }
                ))

        return anomalies
