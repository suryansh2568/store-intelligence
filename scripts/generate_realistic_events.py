"""
Generate realistic store events based on actual POS transaction data.

This simulates what the detection pipeline would produce from CCTV footage.
"""
import json
import csv
from datetime import datetime, timedelta
from uuid import uuid4
import random
import requests


API_URL = "http://localhost:8000"
STORE_ID = "STORE_BLR_002"

# Load store layout
with open("data/store_layout.json", 'r') as f:
    store_layout = json.load(f)

zones = [z['zone_id'] for z in store_layout['stores'][0]['zones'] if z['zone_id'] not in ['ENTRY', 'BILLING']]


def generate_customer_journey(visitor_num: int, purchase_time: datetime, basket_value: float):
    """
    Generate a realistic customer journey ending in a purchase.
    
    Args:
        visitor_num: Visitor number for ID generation
        purchase_time: Time of POS transaction
        basket_value: Transaction amount
    
    Returns:
        List of events for this customer journey
    """
    visitor_id = f"VIS_{visitor_num:06d}"
    events = []
    seq = 1
    
    # Entry: 5-15 minutes before purchase
    entry_offset = timedelta(minutes=random.randint(5, 15))
    entry_time = purchase_time - entry_offset
    
    events.append({
        "event_id": str(uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": "ENTRY",
        "timestamp": entry_time.isoformat() + "Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": random.uniform(0.88, 0.98),
        "metadata": {
            "queue_depth": None,
            "sku_zone": None,
            "session_seq": seq
        }
    })
    seq += 1
    
    # Zone visits based on basket value (higher value = more zones)
    num_zones = min(int(basket_value / 200) + 1, 5)  # 1-5 zones
    visited_zones = random.sample(zones, k=num_zones)
    
    current_time = entry_time + timedelta(seconds=30)
    
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
            "confidence": random.uniform(0.82, 0.95),
            "metadata": {
                "queue_depth": None,
                "sku_zone": zone,
                "session_seq": seq
            }
        })
        seq += 1
        
        # Zone dwell (30s to 3min)
        dwell_time = random.randint(30000, 180000)
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
            "confidence": random.uniform(0.82, 0.95),
            "metadata": {
                "queue_depth": None,
                "sku_zone": zone,
                "session_seq": seq
            }
        })
        seq += 1
        
        # Zone exit
        current_time += timedelta(seconds=5)
        events.append({
            "event_id": str(uuid4()),
            "store_id": STORE_ID,
            "camera_id": "CAM_FLOOR_01",
            "visitor_id": visitor_id,
            "event_type": "ZONE_EXIT",
            "timestamp": current_time.isoformat() + "Z",
            "zone_id": zone,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": random.uniform(0.82, 0.95),
            "metadata": {
                "queue_depth": None,
                "sku_zone": zone,
                "session_seq": seq
            }
        })
        seq += 1
        
        current_time += timedelta(seconds=10)
    
    # Billing queue join (2-5 minutes before purchase)
    billing_time = purchase_time - timedelta(minutes=random.randint(2, 5))
    queue_depth = random.randint(0, 4)
    
    events.append({
        "event_id": str(uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_BILLING_01",
        "visitor_id": visitor_id,
        "event_type": "BILLING_QUEUE_JOIN",
        "timestamp": billing_time.isoformat() + "Z",
        "zone_id": "BILLING",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": random.uniform(0.88, 0.98),
        "metadata": {
            "queue_depth": queue_depth,
            "sku_zone": None,
            "session_seq": seq
        }
    })
    seq += 1
    
    # Exit (1-2 minutes after purchase)
    exit_time = purchase_time + timedelta(minutes=random.randint(1, 2))
    
    events.append({
        "event_id": str(uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": "EXIT",
        "timestamp": exit_time.isoformat() + "Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": random.uniform(0.88, 0.98),
        "metadata": {
            "queue_depth": None,
            "sku_zone": None,
            "session_seq": seq
        }
    })
    
    return events


def generate_browser_journey(visitor_num: int, entry_time: datetime):
    """Generate a journey for a customer who browses but doesn't purchase."""
    visitor_id = f"VIS_{visitor_num:06d}"
    events = []
    seq = 1
    
    # Entry
    events.append({
        "event_id": str(uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": "ENTRY",
        "timestamp": entry_time.isoformat() + "Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": random.uniform(0.88, 0.98),
        "metadata": {
            "queue_depth": None,
            "sku_zone": None,
            "session_seq": seq
        }
    })
    seq += 1
    
    # Visit 1-3 zones
    num_zones = random.randint(1, 3)
    visited_zones = random.sample(zones, k=num_zones)
    
    current_time = entry_time + timedelta(seconds=30)
    
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
            "confidence": random.uniform(0.82, 0.95),
            "metadata": {
                "queue_depth": None,
                "sku_zone": zone,
                "session_seq": seq
            }
        })
        seq += 1
        
        # Short dwell (15s to 1min)
        dwell_time = random.randint(15000, 60000)
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
            "confidence": random.uniform(0.82, 0.95),
            "metadata": {
                "queue_depth": None,
                "sku_zone": zone,
                "session_seq": seq
            }
        })
        seq += 1
        
        current_time += timedelta(seconds=10)
    
    # Exit (no purchase)
    exit_time = current_time + timedelta(seconds=30)
    
    events.append({
        "event_id": str(uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": "EXIT",
        "timestamp": exit_time.isoformat() + "Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": random.uniform(0.88, 0.98),
        "metadata": {
            "queue_depth": None,
            "sku_zone": None,
            "session_seq": seq
        }
    })
    
    return events


def main():
    """Generate events based on POS data."""
    
    print("Generating realistic store events from POS data...\n")
    
    # Load POS transactions
    with open("data/pos_transactions.csv", 'r') as f:
        reader = csv.DictReader(f)
        transactions = list(reader)
    
    print(f"Found {len(transactions)} POS transactions")
    
    all_events = []
    visitor_num = 1
    
    # Generate customer journeys for each transaction
    for txn in transactions:
        purchase_time = datetime.fromisoformat(txn['timestamp'].replace('Z', ''))
        basket_value = float(txn['basket_value_inr'])
        
        events = generate_customer_journey(visitor_num, purchase_time, basket_value)
        all_events.extend(events)
        visitor_num += 1
    
    print(f"✓ Generated {len(all_events)} events for {len(transactions)} purchases")
    
    # Generate browser journeys (non-purchasers) - 30% of purchasers
    num_browsers = int(len(transactions) * 0.3)
    
    # Distribute browsers throughout the day
    start_time = datetime(2026, 4, 10, 12, 0, 0)
    end_time = datetime(2026, 4, 10, 21, 0, 0)
    time_range = (end_time - start_time).total_seconds()
    
    for i in range(num_browsers):
        # Random entry time
        offset = random.uniform(0, time_range)
        entry_time = start_time + timedelta(seconds=offset)
        
        events = generate_browser_journey(visitor_num, entry_time)
        all_events.extend(events)
        visitor_num += 1
    
    print(f"✓ Generated events for {num_browsers} browsers (non-purchasers)")
    print(f"✓ Total events: {len(all_events)}")
    print(f"✓ Total unique visitors: {visitor_num - 1}")
    
    # Sort events by timestamp
    all_events.sort(key=lambda e: e['timestamp'])
    
    # Save to JSONL
    output_file = "data/events.jsonl"
    with open(output_file, 'w') as f:
        for event in all_events:
            f.write(json.dumps(event) + '\n')
    
    print(f"\n✓ Events saved to {output_file}")
    
    # Send to API in batches
    print("\nSending events to API...")
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
                print(f"  ✓ Batch {i//batch_size + 1}: {result['accepted']} accepted, {result['rejected']} rejected")
            else:
                print(f"  ✗ Batch {i//batch_size + 1} failed: {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ Error sending batch: {e}")
    
    print("\n" + "="*60)
    print("✓ Data generation complete!")
    print("="*60)
    print(f"\nStore: {STORE_ID}")
    print(f"Date: April 10, 2026")
    print(f"Transactions: {len(transactions)}")
    print(f"Total Visitors: {visitor_num - 1}")
    print(f"Conversion Rate: {len(transactions) / (visitor_num - 1) * 100:.1f}%")
    print(f"\nView metrics: {API_URL}/stores/{STORE_ID}/metrics?date=2026-04-10")
    print(f"View funnel: {API_URL}/stores/{STORE_ID}/funnel?date=2026-04-10")
    print(f"View heatmap: {API_URL}/stores/{STORE_ID}/heatmap?date=2026-04-10")


if __name__ == "__main__":
    main()
