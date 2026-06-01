#!/usr/bin/env python3
"""
Quick initialization script - loads sample events via API.
"""
import json
import requests
import time

API_URL = "http://localhost:8000"

def load_events():
    """Load sample events from file."""
    print("\n" + "="*60)
    print("Loading Sample Events")
    print("="*60)
    
    # Check if events file exists
    events_file = "data/events.jsonl"
    try:
        with open(events_file, 'r') as f:
            events = [json.loads(line) for line in f]
    except FileNotFoundError:
        print(f"✗ Events file not found: {events_file}")
        print("\nPlease run one of:")
        print("  python scripts/generate_realistic_events.py")
        print("  python pipeline/run.py --input data/clips/STORE_BLR_002 --output data/events.jsonl")
        return False
    
    print(f"\n✓ Found {len(events)} events")
    
    # Send events in batches
    batch_size = 100
    total_sent = 0
    
    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]
        
        try:
            response = requests.post(
                f"{API_URL}/events/ingest",
                json={"events": batch},
                timeout=30
            )
            
            if response.status_code == 200:
                total_sent += len(batch)
                print(f"  Sent batch {i//batch_size + 1}: {total_sent}/{len(events)} events")
            else:
                print(f"✗ Error sending batch: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
    
    print(f"\n✓ Successfully loaded {total_sent} events")
    return True


def verify_data():
    """Verify data was loaded."""
    print("\n" + "="*60)
    print("Verifying Data")
    print("="*60)
    
    try:
        # Check health
        response = requests.get(f"{API_URL}/health", timeout=10)
        health = response.json()
        
        print(f"\n✓ API Status: {health['status']}")
        
        if health.get('stores'):
            print(f"✓ Stores found: {len(health['stores'])}")
            for store in health['stores']:
                print(f"  - {store['store_id']}: {store['event_count']} events")
        else:
            print("✗ No stores found")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error verifying data: {e}")
        return False


def main():
    """Main entry point."""
    print("\n" + "="*60)
    print("Store Intelligence - Quick Initialization")
    print("="*60)
    
    # Wait for API
    print("\nWaiting for API...")
    for i in range(30):
        try:
            response = requests.get(f"{API_URL}/health", timeout=2)
            if response.status_code == 200:
                print("✓ API is ready")
                break
        except:
            pass
        
        if i == 29:
            print("✗ API not responding")
            return
        
        time.sleep(1)
    
    # Load events
    if not load_events():
        print("\n❌ Failed to load events")
        return
    
    # Verify
    if not verify_data():
        print("\n❌ Data verification failed")
        return
    
    print("\n" + "="*60)
    print("✓ Initialization Complete!")
    print("="*60)
    print("\nAccess the system:")
    print("  • API:       http://localhost:8000")
    print("  • API Docs:  http://localhost:8000/docs")
    print("  • Dashboard: http://localhost:8501")
    print()


if __name__ == "__main__":
    main()
