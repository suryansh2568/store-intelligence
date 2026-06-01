"""
Zone heatmap generation.
"""
from datetime import datetime, date
from typing import Optional
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Heatmap, HeatmapZone, EventType
from app.database import EventRecord
from app.logging_config import get_logger

logger = get_logger(__name__)


class HeatmapService:
    """Service for generating zone visit heatmaps."""

    def __init__(self, db: Session):
        self.db = db

    def get_heatmap(
        self,
        store_id: str,
        target_date: Optional[date] = None
    ) -> Heatmap:
        """
        Generate zone visit heatmap with normalized scores.
        
        Args:
            store_id: Store identifier
            target_date: Date to analyze (default: today)
            
        Returns:
            Heatmap with zone visit frequencies and dwell times
        """
        if target_date is None:
            target_date = date.today()

        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = datetime.combine(target_date, datetime.max.time())

        logger.info(
            "generating_heatmap",
            store_id=store_id,
            date=str(target_date)
        )

        # Get all zone-related events (non-staff)
        zone_events = self.db.query(EventRecord).filter(
            and_(
                EventRecord.store_id == store_id,
                EventRecord.timestamp >= start_time,
                EventRecord.timestamp <= end_time,
                EventRecord.is_staff == False,
                EventRecord.zone_id.isnot(None)
            )
        ).all()

        # Aggregate by zone
        zone_data = defaultdict(lambda: {
            'visits': set(),  # Unique visitor IDs
            'dwell_times': []
        })

        for event in zone_events:
            zone_id = event.zone_id
            visitor_id = event.visitor_id

            # Count unique visits
            if event.event_type in [EventType.ZONE_ENTER.value, EventType.ZONE_DWELL.value]:
                zone_data[zone_id]['visits'].add(visitor_id)

            # Collect dwell times
            if event.event_type == EventType.ZONE_DWELL.value:
                zone_data[zone_id]['dwell_times'].append(event.dwell_ms)

        # Calculate metrics per zone
        zone_metrics = []
        max_visits = 0

        for zone_id, data in zone_data.items():
            visit_count = len(data['visits'])
            avg_dwell = (
                sum(data['dwell_times']) / len(data['dwell_times'])
                if data['dwell_times']
                else 0.0
            )

            zone_metrics.append({
                'zone_id': zone_id,
                'visit_count': visit_count,
                'avg_dwell_ms': avg_dwell
            })

            max_visits = max(max_visits, visit_count)

        # Normalize scores (0-100)
        zones = []
        for metric in zone_metrics:
            normalized_score = (
                int((metric['visit_count'] / max_visits) * 100)
                if max_visits > 0
                else 0
            )

            zones.append(HeatmapZone(
                zone_id=metric['zone_id'],
                visit_count=metric['visit_count'],
                avg_dwell_ms=round(metric['avg_dwell_ms'], 2),
                normalized_score=normalized_score
            ))

        # Sort by normalized score (descending)
        zones.sort(key=lambda z: z.normalized_score, reverse=True)

        # Check data confidence (need at least 20 unique sessions)
        unique_visitors = len(set(
            event.visitor_id
            for event in zone_events
        ))
        data_confidence = unique_visitors >= 20

        logger.info(
            "heatmap_generated",
            store_id=store_id,
            zones_count=len(zones),
            unique_visitors=unique_visitors,
            data_confidence=data_confidence
        )

        return Heatmap(
            store_id=store_id,
            date=str(target_date),
            zones=zones,
            data_confidence=data_confidence
        )
