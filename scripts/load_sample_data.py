"""
Load sample data into the API for testing.

This script generates synthetic events and POS transactions.
"""
import requests
import json
from datetime import datetime, timedelta
from uuid import uuid4
import random


API_URL = "http://localhost:8000"
STORE_ID = "STORE_BLR_002"


def generate_visitor_session(
    visitor_num: int,
    start_time: datetime,
    is_staff: bool = False
) -> list:
    """Generate a complete visitor session with events."""
    visitor_id = f"VIS_{visitor_num:06d}"
    events = []
    seq = 1
    
    # Entry event
    events.append({
        "event_id": str(uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": "ENTRY",
        "timestamp": start_time.isoformat() + "Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": is_staff,
        "confidence": random.uniform(0.85, 0.98),
        "metadata": {
            "queue_depth": None,
            "sku_zone": None,
            "session_seq": seq
        }
    })
    seq += 1
    
    # Zone visits (if not staff)
    if not is_staff:
        zones = ["SKINCARE", "HAIRCARE", "MAKEUP", "FRAGRANCE"]
        visited_zones = random.sample(zones, k=random.randint(1, 3))
        
        current_time = start_time + timedelta(seconds=30)
        
        for zone in visited_zones:
            # Zone enter
            events.append({
                "event_id": str(uuid4()),
                "store_id": STORE_ID,
                "camera_id": "CAM_FLOOR_01",
                "visitor_id": visitor_id,
                "event_type": "ZONE_ENTER",
                "timestamp": current_time.isoformat() + "Z",
                "zone_id": zone,
                "dwell_ms": 0,
                "is_staff": False,
                "confidence": random.uniform(0.80, 0.95),
                "metadata": {
                    "queue_depth": None,
                    "sku_zone": zone,
                    "session_seq": seq
                }
            })
            seq += 1
            
            # Zone dwell
            dwell_time = random.randint(30000, 120000)  # 30s to 2min
            current_time += timedelta(milliseconds=dwell_time)
            
            events.append({
                "event_id": str(uuid4()),
                "store_id": STORE_ID,
                "camera_id": "CAM_FLOOR_01",
                "visitor_id": visitor_id,
                "event_type": "ZONE_DWELL",
                "timestamp": current_time.isoformat() + "Z",
                "zone_id": zone,
                "dwell_ms": dwell_time,
                "is_staff": False,
                "confidence": random.uniform(0.80, 0.95),
                "metadata": {
                    "queue_depth": None,
                    "sku_zone": zone,
                    "session_seq": seq
                }
            })
            seq += 1
            
            current_time += timedelta(seconds=10)
        
        # Billing zone (50% of visitors)
        if random.random() < 0.5:
            current_time += timedelta(seconds=20)
            queue_depth = random.randint(0, 5)
            
            events.append({
                "event_id": str(uuid4()),
                "store_id": STORE_ID,
                "camera_id": "CAM_BILLING_01",
                "visitor_id": visitor_id,
                "event_type": "BILLING_QUEUE_JOIN",
                "timestamp": current_time.isoformat() + "Z",
                "zone_id": "BILLING",
                "dwell_ms": 0,
                "is_staff": False,
                "confidence": random.uniform(0.85, 0.98),
                "metadata": {
                    "queue_depth": queue_depth,
                    "sku_zone": None,
                    "session_seq": seq
                }
            })
            seq += 1
            
            current_time += timedelta(seconds=random.randint(60, 180))
    
    # Exit event
    exit_time = start_time + timedelta(minutes=random.randint(5, 20))
    events.append({
        "event_id": str(uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": "EXIT",
        "timestamp": exit_time.isoformat() + "Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": is_staff,
        "confidence": random.uniform(0.85, 0.98),
        "metadata": {
            "queue_depth": None,
            "sku_zone": None,
            "session_seq": seq
        }
    })
    
    return events


def generate_pos_transaction(txn_num: int, timestamp: datetime) -> dict:
    """Generate a POS transaction."""
    return {
        "transaction_id": f"TXN_{txn_num:06d}",
        "store_id": STORE_ID,
        "timestamp": timestamp.isoformat() + "Z",
        "basket_value_inr": random.uniform(200, 5000)
    }


def main():
    """Generate and load sample data."""
    print("Generating sample data...")
    
    # Generate events for today
    base_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    all_events = []
    
    # Generate 50 customer sessions
    for i in range(50):
        start_time = base_time + timedelta(minutes=i * 10)
        events = generate_visitor_session(i, start_time, is_staff=False)
        all_events.extend(events)
    
    # Generate 5 staff sessions
    for i in range(5):
        start_time = base_time + timedelta(minutes=i * 60)
        events = generate_visitor_session(100 + i, start_time, is_staff=True)
        all_events.extend(events)
    
    print(f"Generated {len(all_events)} events")
    
    # Send events in batches of 100
    batch_size = 100
    for i in range(0, len(all_events), batch_size):
        batch = all_events[i:i + batch_size]
        
        try:
            response = requests.post(
                f"{API_URL}/events/ingest",
                json={"events": batch},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Batch {i//batch_size + 1}: {result['accepted']} accepted, {result['rejected']} rejected")
            else:
                print(f"✗ Batch {i//batch_size + 1} failed: {response.status_code}")
                
        except Exception as e:
            print(f"✗ Error sending batch: {e}")
    
    print("\nSample data loaded successfully!")
    print(f"\nView metrics: {API_URL}/stores/{STORE_ID}/metrics")
    print(f"View funnel: {API_URL}/stores/{STORE_ID}/funnel")
    print(f"View heatmap: {API_URL}/stores/{STORE_ID}/heatmap")


if __name__ == "__main__":
    main()
