# Store Intelligence System

A complete end-to-end pipeline for retail store analytics from CCTV footage to live metrics.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.10+
- Git

### Setup with Real Brigade Bangalore Data (3 commands)

```bash
# 1. Start the API and database
docker compose up -d

# 2. Run complete setup (loads POS data + generates events)
python scripts/setup_complete_system.py

# 3. View live dashboard
python dashboard/app.py --store-id STORE_BLR_002
```

### What This Does

The setup script:
1. ✅ Verifies Docker services are running
2. ✅ Loads real POS transaction data from Brigade Bangalore (April 10, 2026)
3. ✅ Generates realistic CCTV events based on actual purchases
4. ✅ Creates customer journeys with zone visits, dwell times, and billing queue events
5. ✅ Validates all API endpoints are working

**Real Data Included:**
- 📍 Store: Brigade Bangalore (Brigade Road)
- 📅 Date: April 10, 2026
- 💰 24 actual POS transactions
- 🛍️ 14+ product zones (Maybelline, Lakme, Faces, DermDoc, etc.)
- 👥 ~31 simulated visitors (24 purchasers + 7 browsers)

## Architecture Overview

```
CCTV Clips → Detection Pipeline → Event Stream → Intelligence API → Live Dashboard
```

### Components

1. **Detection Pipeline** (`pipeline/`)
   - Person detection using YOLOv8
   - Multi-object tracking with ByteTrack
   - Re-identification for visitor sessions
   - Event emission in structured schema

2. **Intelligence API** (`app/`)
   - FastAPI-based REST API
   - Real-time metrics computation
   - Anomaly detection
   - Conversion funnel analysis

3. **Live Dashboard** (`dashboard/`)
   - Real-time metric visualization
   - Web-based UI with auto-refresh

4. **Tests** (`tests/`)
   - >70% statement coverage
   - Edge case handling
   - Integration tests

## API Endpoints

- `POST /events/ingest` - Ingest event batches (up to 500 events)
- `GET /stores/{id}/metrics` - Real-time store metrics
- `GET /stores/{id}/funnel` - Conversion funnel analysis
- `GET /stores/{id}/heatmap` - Zone visit heatmap
- `GET /stores/{id}/anomalies` - Active anomalies
- `GET /health` - Service health status

## Running the Detection Pipeline

```bash
# Process all clips for a specific store
python pipeline/run.py --store STORE_BLR_002 --input data/clips/STORE_BLR_002

# Process with real-time simulation
python pipeline/run.py --input data/clips --realtime --speed 1.0

# Process and stream directly to API
python pipeline/run.py --input data/clips --stream-to http://localhost:8000/events/ingest
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ --cov=. --cov-report=html

# Run linting
ruff check .

# Format code
black .
```

## Dataset Structure

```
data/
├── clips/
│   ├── STORE_BLR_002/
│   │   ├── entry_camera.mp4
│   │   ├── floor_camera.mp4
│   │   └── billing_camera.mp4
│   └── ...
├── store_layout.json
├── pos_transactions.csv
└── sample_events.jsonl
```

## Event Schema

Events follow this structure:

```json
{
  "event_id": "uuid-v4",
  "store_id": "STORE_BLR_002",
  "camera_id": "CAM_ENTRY_01",
  "visitor_id": "VIS_c8a2f1",
  "event_type": "ZONE_DWELL",
  "timestamp": "2026-03-03T14:22:10Z",
  "zone_id": "SKINCARE",
  "dwell_ms": 8400,
  "is_staff": false,
  "confidence": 0.91,
  "metadata": {
    "queue_depth": null,
    "sku_zone": "MOISTURISER",
    "session_seq": 5
  }
}
```

## Production Features

- ✅ Containerized deployment
- ✅ Structured logging with trace IDs
- ✅ Idempotent event ingestion
- ✅ Graceful error handling
- ✅ Health monitoring
- ✅ >70% test coverage

## Documentation

- [DESIGN.md](docs/DESIGN.md) - Architecture and design decisions
- [CHOICES.md](docs/CHOICES.md) - Key technical choices and rationale

## License

Challenge use only. Not for redistribution.
