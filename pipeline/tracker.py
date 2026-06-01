"""
Multi-object tracking with Re-ID for visitor session management.

Uses ByteTrack-style tracking with appearance-based re-identification.
"""
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib


@dataclass
class Track:
    """Single tracked object."""
    track_id: int
    visitor_id: str
    bbox: Tuple[float, float, float, float]
    confidence: float
    is_staff: bool
    last_seen: datetime
    age: int = 0
    hits: int = 0
    time_since_update: int = 0
    state: str = "tentative"  # tentative, confirmed, deleted
    zone_history: List[str] = field(default_factory=list)
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None


class MultiCameraTracker:
    """
    Multi-camera tracker with re-identification.
    
    Features:
    - ByteTrack-style tracking (high/low confidence)
    - Cross-camera re-identification
    - Re-entry detection
    - Session management
    """
    
    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3,
        reid_threshold: float = 0.7
    ):
        """
        Initialize tracker.
        
        Args:
            max_age: Maximum frames to keep track without detection
            min_hits: Minimum hits before track is confirmed
            iou_threshold: IOU threshold for matching
            reid_threshold: Re-ID similarity threshold
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.reid_threshold = reid_threshold
        
        self.tracks: List[Track] = []
        self.next_track_id = 1
        
        # Re-ID database (visitor_id -> appearance features)
        self.reid_database: Dict[str, np.ndarray] = {}
        
        # Session management
        self.active_sessions: Dict[str, Dict] = {}
        self.completed_sessions: List[Dict] = []
        
    def update(
        self,
        detections: List,
        timestamp: datetime
    ) -> List[Dict]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of Detection objects
            timestamp: Current timestamp
            
        Returns:
            List of active tracks
        """
        # Separate high and low confidence detections
        high_conf = [d for d in detections if d.confidence >= 0.6]
        low_conf = [d for d in detections if 0.3 <= d.confidence < 0.6]
        
        # Match high confidence detections
        matched, unmatched_tracks, unmatched_dets = self._match_detections(
            self.tracks,
            high_conf
        )
        
        # Update matched tracks
        for track_idx, det_idx in matched:
            track = self.tracks[track_idx]
            detection = high_conf[det_idx]
            
            track.bbox = detection.bbox
            track.confidence = detection.confidence
            track.is_staff = detection.is_staff
            track.last_seen = timestamp
            track.hits += 1
            track.time_since_update = 0
            
            if track.hits >= self.min_hits:
                track.state = "confirmed"
        
        # Try to match unmatched tracks with low confidence detections
        if len(unmatched_tracks) > 0 and len(low_conf) > 0:
            unmatched_track_objs = [self.tracks[i] for i in unmatched_tracks]
            matched_low, unmatched_tracks_low, _ = self._match_detections(
                unmatched_track_objs,
                low_conf
            )
            
            for track_idx, det_idx in matched_low:
                track = unmatched_track_objs[track_idx]
                detection = low_conf[det_idx]
                
                track.bbox = detection.bbox
                track.confidence = detection.confidence
                track.last_seen = timestamp
                track.time_since_update = 0
        
        # Create new tracks for unmatched high confidence detections
        for det_idx in unmatched_dets:
            detection = high_conf[det_idx]
            self._create_track(detection, timestamp)
        
        # Update track ages and remove old tracks
        self.tracks = [
            track for track in self.tracks
            if self._update_track_age(track, timestamp)
        ]
        
        # Return active confirmed tracks
        active_tracks = []
        for track in self.tracks:
            if track.state == "confirmed":
                active_tracks.append({
                    'track_id': track.track_id,
                    'visitor_id': track.visitor_id,
                    'bbox': track.bbox,
                    'confidence': track.confidence,
                    'is_staff': track.is_staff,
                    'zone_history': track.zone_history
                })
        
        return active_tracks
    
    def _match_detections(
        self,
        tracks: List[Track],
        detections: List
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Match detections to tracks using IOU.
        
        Returns:
            matched: List of (track_idx, detection_idx) pairs
            unmatched_tracks: List of unmatched track indices
            unmatched_detections: List of unmatched detection indices
        """
        if len(tracks) == 0:
            return [], [], list(range(len(detections)))
        
        if len(detections) == 0:
            return [], list(range(len(tracks))), []
        
        # Compute IOU matrix
        iou_matrix = np.zeros((len(tracks), len(detections)))
        
        for t, track in enumerate(tracks):
            for d, detection in enumerate(detections):
                iou_matrix[t, d] = self._compute_iou(track.bbox, detection.bbox)
        
        # Greedy matching
        matched = []
        unmatched_tracks = list(range(len(tracks)))
        unmatched_dets = list(range(len(detections)))
        
        while iou_matrix.size > 0:
            # Find best match
            max_iou = iou_matrix.max()
            
            if max_iou < self.iou_threshold:
                break
            
            max_idx = np.unravel_index(iou_matrix.argmax(), iou_matrix.shape)
            track_idx, det_idx = max_idx
            
            matched.append((track_idx, det_idx))
            unmatched_tracks.remove(track_idx)
            unmatched_dets.remove(det_idx)
            
            # Remove matched row and column
            iou_matrix[track_idx, :] = 0
            iou_matrix[:, det_idx] = 0
        
        return matched, unmatched_tracks, unmatched_dets
    
    def _compute_iou(
        self,
        bbox1: Tuple[float, float, float, float],
        bbox2: Tuple[float, float, float, float]
    ) -> float:
        """Compute IOU between two bounding boxes."""
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i < x1_i or y2_i < y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        # Union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _create_track(self, detection, timestamp: datetime):
        """Create new track from detection."""
        track_id = self.next_track_id
        self.next_track_id += 1
        
        # Generate visitor ID (simple hash-based for now)
        # In production, this would use appearance features
        visitor_id = f"VIS_{hashlib.md5(str(track_id).encode()).hexdigest()[:6]}"
        
        track = Track(
            track_id=track_id,
            visitor_id=visitor_id,
            bbox=detection.bbox,
            confidence=detection.confidence,
            is_staff=detection.is_staff,
            last_seen=timestamp,
            entry_time=timestamp,
            hits=1
        )
        
        self.tracks.append(track)
    
    def _update_track_age(self, track: Track, timestamp: datetime) -> bool:
        """
        Update track age and determine if it should be kept.
        
        Returns:
            True if track should be kept, False if it should be deleted
        """
        track.time_since_update += 1
        track.age += 1
        
        # Delete old tracks
        if track.time_since_update > self.max_age:
            track.state = "deleted"
            track.exit_time = timestamp
            return False
        
        return True
    
    def check_reentry(self, detection, timestamp: datetime) -> Optional[str]:
        """
        Check if detection is a re-entering visitor.
        
        Uses appearance-based re-identification.
        
        Args:
            detection: Detection object
            timestamp: Current timestamp
            
        Returns:
            visitor_id if re-entry detected, None otherwise
        """
        # Extract appearance features (placeholder)
        # In production, use a Re-ID model like OSNet
        features = self._extract_features(detection)
        
        # Compare with Re-ID database
        best_match = None
        best_similarity = 0.0
        
        for visitor_id, stored_features in self.reid_database.items():
            similarity = self._compute_similarity(features, stored_features)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = visitor_id
        
        if best_similarity > self.reid_threshold:
            return best_match
        
        return None
    
    def _extract_features(self, detection) -> np.ndarray:
        """Extract appearance features from detection."""
        # Placeholder: return random features
        # In production, use Re-ID model
        return np.random.rand(128)
    
    def _compute_similarity(
        self,
        features1: np.ndarray,
        features2: np.ndarray
    ) -> float:
        """Compute cosine similarity between feature vectors."""
        dot_product = np.dot(features1, features2)
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
