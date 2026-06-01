"""
Conversion funnel analysis with session deduplication.
"""
from datetime import datetime, date, timedelta
from typing import Optional, Set
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import ConversionFunnel, FunnelStage, EventType
from app.database import EventRecord, POSTransaction
from app.logging_config import get_logger

logger = get_logger(__name__)


class FunnelService:
    """Service for conversion funnel analysis."""

    def __init__(self, db: Session):
        self.db = db

    def get_conversion_funnel(
        self,
        store_id: str,
        target_date: Optional[date] = None
    ) -> ConversionFunnel:
        """
        Compute conversion funnel with session-based deduplication.
        
        Funnel stages:
        1. Entry - Visitor entered store
        2. Zone Visit - Visitor visited at least one product zone
        3. Billing Queue - Visitor entered billing area
        4. Purchase - Visitor completed transaction
        
        Args:
            store_id: Store identifier
            target_date: Date to analyze (default: today)
            
        Returns:
            ConversionFunnel with stage counts and drop-off percentages
        """
        if target_date is None:
            target_date = date.today()

        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = datetime.combine(target_date, datetime.max.time())

        logger.info(
            "computing_funnel",
            store_id=store_id,
            date=str(target_date)
        )

        # Get all non-staff events for the day
        events = self.db.query(EventRecord).filter(
            and_(
                EventRecord.store_id == store_id,
                EventRecord.timestamp >= start_time,
                EventRecord.timestamp <= end_time,
                EventRecord.is_staff == False
            )
        ).order_by(EventRecord.timestamp).all()

        # Build visitor sessions (deduplicate re-entries)
        visitor_sessions = defaultdict(lambda: {
            'entered': False,
            'visited_zone': False,
            'entered_billing': False,
            'purchased': False,
            'last_entry': None
        })

        for event in events:
            visitor_id = event.visitor_id
            session = visitor_sessions[visitor_id]

            if event.event_type == EventType.ENTRY.value:
                session['entered'] = True
                session['last_entry'] = event.timestamp

            elif event.event_type == EventType.REENTRY.value:
                # Re-entry: don't double-count the visitor
                session['last_entry'] = event.timestamp

            elif event.event_type in [
                EventType.ZONE_ENTER.value,
                EventType.ZONE_DWELL.value
            ]:
                if event.zone_id and 'BILLING' not in event.zone_id.upper():
                    session['visited_zone'] = True

            elif 'BILLING' in (event.zone_id or '').upper():
                session['entered_billing'] = True

        # Get POS transactions
        pos_transactions = self.db.query(POSTransaction).filter(
            and_(
                POSTransaction.store_id == store_id,
                POSTransaction.timestamp >= start_time,
                POSTransaction.timestamp <= end_time
            )
        ).all()

        # Match transactions to visitor sessions
        for txn in pos_transactions:
            window_start = txn.timestamp - timedelta(minutes=5)
            
            # Find visitors who were in billing zone before this transaction
            for visitor_id, session in visitor_sessions.items():
                if not session['entered_billing']:
                    continue
                
                # Check if visitor was in billing zone within window
                billing_events = [
                    e for e in events
                    if e.visitor_id == visitor_id
                    and 'BILLING' in (e.zone_id or '').upper()
                    and window_start <= e.timestamp <= txn.timestamp
                ]
                
                if billing_events:
                    session['purchased'] = True
                    break  # One transaction per visitor

        # Count funnel stages
        stage_1_entry = sum(1 for s in visitor_sessions.values() if s['entered'])
        stage_2_zone_visit = sum(
            1 for s in visitor_sessions.values()
            if s['entered'] and s['visited_zone']
        )
        stage_3_billing = sum(
            1 for s in visitor_sessions.values()
            if s['entered'] and s['visited_zone'] and s['entered_billing']
        )
        stage_4_purchase = sum(
            1 for s in visitor_sessions.values()
            if s['entered'] and s['visited_zone'] and s['entered_billing'] and s['purchased']
        )

        # Calculate drop-off percentages
        def calc_dropoff(current: int, previous: int) -> float:
            if previous == 0:
                return 0.0
            return round((1 - current / previous) * 100, 2)

        stages = [
            FunnelStage(
                stage="Entry",
                count=stage_1_entry,
                drop_off_pct=0.0
            ),
            FunnelStage(
                stage="Zone Visit",
                count=stage_2_zone_visit,
                drop_off_pct=calc_dropoff(stage_2_zone_visit, stage_1_entry)
            ),
            FunnelStage(
                stage="Billing Queue",
                count=stage_3_billing,
                drop_off_pct=calc_dropoff(stage_3_billing, stage_2_zone_visit)
            ),
            FunnelStage(
                stage="Purchase",
                count=stage_4_purchase,
                drop_off_pct=calc_dropoff(stage_4_purchase, stage_3_billing)
            ),
        ]

        logger.info(
            "funnel_computed",
            store_id=store_id,
            entry=stage_1_entry,
            zone_visit=stage_2_zone_visit,
            billing=stage_3_billing,
            purchase=stage_4_purchase
        )

        return ConversionFunnel(
            store_id=store_id,
            date=str(target_date),
            stages=stages
        )
