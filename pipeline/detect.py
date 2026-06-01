"""
Main detection pipeline using YOLOv8 + ByteTrack.

This module processes CCTV footage and emits structured events.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import uuid

from ultralytics import YOLO
from filterpy.kalman import KalmanFilter

from pipeline.tracker import MultiCameraTracker
from pipeline.emit import EventEmitter


@dataclass
class Detection:
    """Single person detection."""
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float
    track_id: Optional[int] = None
    is_staff: bool = False


class PersonDetector:
    """
    Person detection using YOLOv8.
    
    Handles:
    - Person detection in each frame
    - Confidence thresholding
    - Staff classification (uniform detection)
    """
    
    def __init__(self, model_path: str = "yolov8n.pt", conf_threshold: float = 0.4):
        """
        Initialize detector.
        
        Args:
            model_path: Path to YOLO model weights
            conf_threshold: Minimum confidence for detections
        """
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        
        # Staff detection (simple heuristic - can be enhanced with VLM)
        self.staff_zones = set()  # Zones where staff typically operate
        
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Detect people in a frame.
        
        Args:
            frame: Input frame (BGR)
            
        Returns:
            List of Detection objects
        """
        # Run YOLO detection
        results = self.model(frame, conf=self.conf_threshold, classes=[0])  # class 0 = person
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                # Extract bbox coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                
                # Simple staff detection heuristic
                # Staff typically have consistent appearance and movement patterns
                # This can be enhanced with uniform color detection or VLM
                is_staff = self._classify_staff(frame, (x1, y1, x2, y2))
                
                detections.append(Detection(
                    bbox=(float(x1), float(y1), float(x2), float(y2)),
                    confidence=conf,
                    is_staff=is_staff
                ))
        
        return detections
    
    def _classify_staff(
        self,
        frame: np.ndarray,
        bbox: Tuple[float, float, float, float]
    ) -> bool:
        """
        Classify if detection is staff member.
        
        Simple heuristic: Check for uniform colors (can be enhanced).
        
        Args:
            frame: Input frame
            bbox: Bounding box coordinates
            
        Returns:
            True if likely staff member
        """
        x1, y1, x2, y2 = map(int, bbox)
        
        # Extract person region
        person_roi = frame[y1:y2, x1:x2]
        
        if person_roi.size == 0:
            return False
        
        # Calculate dominant color
        avg_color = person_roi.mean(axis=(0, 1))
        
        # Staff uniform heuristic: dark colors (black/navy)
        # This is a placeholder - should be calibrated per store
        is_dark = avg_color.mean() < 80
        
        return is_dark


class VideoProcessor:
    """
    Process video clips and generate events.
    """
    
    def __init__(
        self,
        detector: PersonDetector,
        tracker: MultiCameraTracker,
        emitter: EventEmitter,
        store_id: str,
        camera_id: str,
        zone_config: Dict
    ):
        """
        Initialize video processor.
        
        Args:
            detector: Person detector
            tracker: Multi-object tracker
            emitter: Event emitter
            store_id: Store identifier
            camera_id: Camera identifier
            zone_config: Zone configuration from store_layout.json
        """
        self.detector = detector
        self.tracker = tracker
        self.emitter = emitter
        self.store_id = store_id
        self.camera_id = camera_id
        self.zone_config = zone_config
        
        # Entry/exit line (for entry camera)
        self.entry_line_y = None
        if "entry" in camera_id.lower():
            self.entry_line_y = 0.5  # Middle of frame
        
        # Zone boundaries
        self.zones = self._parse_zones(zone_config)
        
        # Track state for event generation
        self.track_states = {}  # track_id -> state dict
        self.session_counters = {}  # visitor_id -> session counter
        
    def _parse_zones(self, zone_config: Dict) -> Dict[str, Dict]:
        """Parse zone boundaries from config."""
        zones = {}
        
        for zone in zone_config.get('zones', []):
            zone_id = zone['zone_id']
            zones[zone_id] = {
                'bbox': zone.get('bbox'),  # [x1, y1, x2, y2] normalized
                'name': zone.get('name', zone_id)
            }
        
        return zones
    
    def process_video(
        self,
        video_path: str,
        start_timestamp: datetime,
        fps: float = 15.0,
        realtime: bool = False
    ):
        """
        Process video file and emit events.
        
        Args:
            video_path: Path to video file
            start_timestamp: Timestamp of first frame
            fps: Frames per second
            realtime: If True, process at real-time speed
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        # Get frame dimensions
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        frame_count = 0
        frame_time_delta = timedelta(seconds=1.0 / fps)
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Calculate frame timestamp
            frame_timestamp = start_timestamp + (frame_count * frame_time_delta)
            
            # Detect people
            detections = self.detector.detect(frame)
            
            # Update tracker
            tracks = self.tracker.update(detections, frame_timestamp)
            
            # Generate events from tracks
            self._generate_events(tracks, frame, frame_timestamp, frame_height, frame_width)
            
            frame_count += 1
            
            # Realtime simulation
            if realtime:
                import time
                time.sleep(1.0 / fps)
        
        cap.release()
        
        # Emit any pending events
        self.emitter.flush()
    
    def _generate_events(
        self,
        tracks: List[Dict],
        frame: np.ndarray,
        timestamp: datetime,
        frame_height: int,
        frame_width: int
    ):
        """
        Generate events from current tracks.
        
        Args:
            tracks: List of active tracks
            frame: Current frame
            timestamp: Current timestamp
            frame_height: Frame height
            frame_width: Frame width
        """
        for track in tracks:
            track_id = track['track_id']
            visitor_id = track['visitor_id']
            bbox = track['bbox']
            is_staff = track['is_staff']
            confidence = track['confidence']
            
            # Get center point
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            
            # Normalize coordinates
            cx_norm = cx / frame_width
            cy_norm = cy / frame_height
            
            # Check for entry/exit events
            if self.entry_line_y is not None:
                self._check_entry_exit(
                    track_id,
                    visitor_id,
                    cy_norm,
                    is_staff,
                    confidence,
                    timestamp
                )
            
            # Check zone events
            self._check_zone_events(
                track_id,
                visitor_id,
                cx_norm,
                cy_norm,
                is_staff,
                confidence,
                timestamp
            )
    
    def _check_entry_exit(
        self,
        track_id: int,
        visitor_id: str,
        cy_norm: float,
        is_staff: bool,
        confidence: float,
        timestamp: datetime
    ):
        """Check if track crossed entry/exit line."""
        # Initialize track state if new
        if track_id not in self.track_states:
            self.track_states[track_id] = {
                'entered': False,
                'last_y': cy_norm,
                'current_zone': None,
                'zone_enter_time': None
            }
            
            # Initialize session counter for visitor
            if visitor_id not in self.session_counters:
                self.session_counters[visitor_id] = 0
        
        state = self.track_states[track_id]
        
        # Check for entry (crossing line from top to bottom)
        if not state['entered'] and state['last_y'] < self.entry_line_y and cy_norm >= self.entry_line_y:
            state['entered'] = True
            self.session_counters[visitor_id] += 1
            
            self.emitter.emit_entry(
                store_id=self.store_id,
                camera_id=self.camera_id,
                visitor_id=visitor_id,
                timestamp=timestamp,
                is_staff=is_staff,
                confidence=confidence,
                session_seq=self.session_counters[visitor_id]
            )
        
        # Check for exit (crossing line from bottom to top)
        elif state['entered'] and state['last_y'] > self.entry_line_y and cy_norm <= self.entry_line_y:
            self.emitter.emit_exit(
                store_id=self.store_id,
                camera_id=self.camera_id,
                visitor_id=visitor_id,
                timestamp=timestamp,
                is_staff=is_staff,
                confidence=confidence,
                session_seq=self.session_counters[visitor_id]
            )
            state['entered'] = False
        
        state['last_y'] = cy_norm
    
    def _check_zone_events(
        self,
        track_id: int,
        visitor_id: str,
        cx_norm: float,
        cy_norm: float,
        is_staff: bool,
        confidence: float,
        timestamp: datetime
    ):
        """Check if track entered/exited zones."""
        # Initialize track state if new
        if track_id not in self.track_states:
            self.track_states[track_id] = {
                'entered': False,
                'last_y': cy_norm,
                'current_zone': None,
                'zone_enter_time': None
            }
            
            # Initialize session counter for visitor
            if visitor_id not in self.session_counters:
                self.session_counters[visitor_id] = 0
        
        state = self.track_states[track_id]
        
        # Check which zone the person is in
        current_zone = None
        current_sku_zone = None
        
        for zone_id, zone_info in self.zones.items():
            bbox = zone_info.get('bbox')
            
            if bbox is None:
                continue
            
            # Check if point is in zone
            x1, y1, x2, y2 = bbox
            in_zone = (x1 <= cx_norm <= x2) and (y1 <= cy_norm <= y2)
            
            if in_zone:
                current_zone = zone_id
                current_sku_zone = zone_info.get('name', zone_id)
                break
        
        # Check for zone transitions
        if current_zone != state['current_zone']:
            # Exited previous zone (emit dwell if applicable)
            if state['current_zone'] is not None and state['zone_enter_time'] is not None:
                dwell_ms = int((timestamp - state['zone_enter_time']).total_seconds() * 1000)
                
                # Only emit dwell if person stayed for more than 2 seconds
                if dwell_ms > 2000:
                    self.emitter.emit_zone_dwell(
                        store_id=self.store_id,
                        camera_id=self.camera_id,
                        visitor_id=visitor_id,
                        timestamp=timestamp,
                        zone_id=state['current_zone'],
                        dwell_ms=dwell_ms,
                        is_staff=is_staff,
                        confidence=confidence,
                        session_seq=self.session_counters.get(visitor_id, 1),
                        sku_zone=state.get('current_sku_zone')
                    )
            
            # Entered new zone
            if current_zone is not None:
                self.emitter.emit_zone_enter(
                    store_id=self.store_id,
                    camera_id=self.camera_id,
                    visitor_id=visitor_id,
                    timestamp=timestamp,
                    zone_id=current_zone,
                    is_staff=is_staff,
                    confidence=confidence,
                    session_seq=self.session_counters.get(visitor_id, 1),
                    sku_zone=current_sku_zone
                )
                
                state['zone_enter_time'] = timestamp
            else:
                state['zone_enter_time'] = None
            
            state['current_zone'] = current_zone
            state['current_sku_zone'] = current_sku_zone


def main():
    """Main entry point for detection pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run detection pipeline")
    parser.add_argument("--input", required=True, help="Input video directory")
    parser.add_argument("--output", required=True, help="Output events file")
    parser.add_argument("--store-id", help="Store ID to process")
    parser.add_argument("--realtime", action="store_true", help="Simulate realtime")
    parser.add_argument("--stream-to", help="Stream events to API endpoint")
    
    args = parser.parse_args()
    
    # Initialize components
    detector = PersonDetector()
    tracker = MultiCameraTracker()
    emitter = EventEmitter(output_path=args.output, api_endpoint=args.stream_to)
    
    # Process videos
    # (Implementation would iterate through video files)
    
    print(f"Detection pipeline complete. Events written to {args.output}")


if __name__ == "__main__":
    main()
