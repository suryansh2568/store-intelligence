"""
Simple runner for the detection pipeline.

Usage:
    python pipeline/run.py --input data/clips/STORE_BLR_002 --output data/events.jsonl
"""
import sys
import os
from pathlib import Path
import argparse
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def check_video_files(input_dir: str) -> bool:
    """Check if video files exist."""
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"X Input directory does not exist: {input_dir}")
        return False
    
    # Look for video files
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(list(input_path.glob(f"*{ext}")))
    
    if len(video_files) == 0:
        print(f"X No video files found in {input_dir}")
        print(f"\nFound placeholder files:")
        for placeholder in input_path.glob("*.placeholder"):
            print(f"  - {placeholder.name}")
        print(f"\n!  Please replace placeholder files with actual CCTV footage:")
        print(f"  1. Obtain CCTV clips from challenge organizers")
        print(f"  2. Place them in {input_dir}/")
        print(f"  3. Expected files:")
        print(f"     - entry_camera.mp4")
        print(f"     - floor_camera.mp4")
        print(f"     - billing_camera.mp4")
        return False
    
    print(f"+ Found {len(video_files)} video file(s):")
    for video in video_files:
        print(f"  - {video.name}")
    
    return True


def generate_sample_events(output_file: str, store_id: str):
    """Generate sample events for demonstration."""
    print("\n" + "="*60)
    print("Generating Sample Events (No Video Available)")
    print("="*60)
    
    from uuid import uuid4
    import random
    
    # Generate a few sample events
    events = []
    visitor_id = f"VIS_{random.randint(100000, 999999)}"
    base_time = datetime.now()
    
    # Entry event
    events.append({
        "event_id": str(uuid4()),
        "store_id": store_id,
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": "ENTRY",
        "timestamp": base_time.isoformat() + "Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.95,
        "metadata": {
            "queue_depth": None,
            "sku_zone": None,
            "session_seq": 1
        }
    })
    
    # Zone visit
    events.append({
        "event_id": str(uuid4()),
        "store_id": store_id,
        "camera_id": "CAM_FLOOR_01",
        "visitor_id": visitor_id,
        "event_type": "ZONE_ENTER",
        "timestamp": (base_time + timedelta(seconds=30)).isoformat() + "Z",
        "zone_id": "LAKME",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.92,
        "metadata": {
            "queue_depth": None,
            "sku_zone": "LAKME",
            "session_seq": 2
        }
    })
    
    # Exit event
    events.append({
        "event_id": str(uuid4()),
        "store_id": store_id,
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": "EXIT",
        "timestamp": (base_time + timedelta(minutes=5)).isoformat() + "Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.94,
        "metadata": {
            "queue_depth": None,
            "sku_zone": None,
            "session_seq": 3
        }
    })
    
    # Write to file
    with open(output_file, 'w') as f:
        for event in events:
            f.write(json.dumps(event) + '\n')
    
    print(f"\n+ Generated {len(events)} sample events")
    print(f"+ Output: {output_file}")
    print(f"\n!  These are sample events for demonstration.")
    print(f"   For real detection, provide actual CCTV footage.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run detection pipeline on CCTV footage")
    parser.add_argument("--input", required=True, help="Input video directory")
    parser.add_argument("--output", default="data/events.jsonl", help="Output events file")
    parser.add_argument("--store-id", default="STORE_BLR_002", help="Store ID")
    parser.add_argument("--realtime", action="store_true", help="Simulate realtime processing")
    parser.add_argument("--stream-to", help="Stream events to API endpoint")
    
    args = parser.parse_args()
    
    print("="*60)
    print("Store Intelligence - Detection Pipeline")
    print("="*60)
    print(f"\nInput: {args.input}")
    print(f"Output: {args.output}")
    print(f"Store: {args.store_id}")
    
    # Check for video files
    has_videos = check_video_files(args.input)
    
    if not has_videos:
        print("\n" + "="*60)
        print("Alternative: Use Pre-Generated Events")
        print("="*60)
        print("\nSince no CCTV footage is available, you can:")
        print("\n1. Use the realistic event generator:")
        print("   python scripts/generate_realistic_events.py")
        print("\n2. Or generate sample events now:")
        
        response = input("\nGenerate sample events? (y/n): ").strip().lower()
        
        if response == 'y':
            generate_sample_events(args.output, args.store_id)
        else:
            print("\n+ No events generated")
            print("\nTo use realistic events based on POS data:")
            print("  python scripts/generate_realistic_events.py")
        
        return
    
    # If we have videos, run the actual detection pipeline
    print("\n" + "="*60)
    print("Running Detection Pipeline")
    print("="*60)
    
    try:
        # Import detection modules
        from pipeline.detect import PersonDetector, VideoProcessor
        from pipeline.tracker import MultiCameraTracker
        from pipeline.emit import EventEmitter
        
        # Load store layout
        import json
        with open("data/store_layout.json", 'r') as f:
            store_layout = json.load(f)
        
        # Find store config
        store_config = None
        for store in store_layout['stores']:
            if store['store_id'] == args.store_id:
                store_config = store
                break
        
        if not store_config:
            print(f"X Store {args.store_id} not found in store_layout.json")
            return
        
        # Initialize components
        print("\nInitializing detection components...")
        detector = PersonDetector()
        tracker = MultiCameraTracker()
        emitter = EventEmitter(
            output_path=args.output,
            api_endpoint=args.stream_to
        )
        
        # Process videos
        input_path = Path(args.input)
        video_files = list(input_path.glob("*.mp4")) + list(input_path.glob("*.avi"))
        
        print(f"\nProcessing {len(video_files)} video file(s)...")
        
        for video_file in video_files:
            print(f"\n  Processing: {video_file.name}")
            
            # Determine camera ID from filename
            camera_id = "CAM_FLOOR_01"
            if "entry" in video_file.name.lower():
                camera_id = "CAM_ENTRY_01"
            elif "billing" in video_file.name.lower():
                camera_id = "CAM_BILLING_01"
            
            # Create processor
            processor = VideoProcessor(
                detector=detector,
                tracker=tracker,
                emitter=emitter,
                store_id=args.store_id,
                camera_id=camera_id,
                zone_config=store_config
            )
            
            # Process video
            start_timestamp = datetime.now()
            processor.process_video(
                str(video_file),
                start_timestamp,
                realtime=args.realtime
            )
        
        # Close emitter
        emitter.close()
        
        print("\n" + "="*60)
        print("+ Detection Pipeline Complete")
        print("="*60)
        print(f"\nEvents written to: {args.output}")
        
        if args.stream_to:
            print(f"Events streamed to: {args.stream_to}")
        
    except Exception as e:
        print(f"\nX Error running detection pipeline: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    from datetime import timedelta
    main()
