"""
Database models and connection management.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    JSON,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://store_user:store_pass@localhost:5432/store_intelligence"
)

# Create engine
if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class EventRecord(Base):
    """Database model for stored events."""
    __tablename__ = "events"

    event_id = Column(String, primary_key=True, index=True)
    store_id = Column(String, nullable=False, index=True)
    camera_id = Column(String, nullable=False)
    visitor_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    zone_id = Column(String, nullable=True, index=True)
    dwell_ms = Column(Integer, nullable=False, default=0)
    is_staff = Column(Boolean, nullable=False, default=False, index=True)
    confidence = Column(Float, nullable=False)
    event_metadata = Column(JSON, nullable=False)  # Renamed from 'metadata' to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_store_timestamp', 'store_id', 'timestamp'),
        Index('idx_store_visitor', 'store_id', 'visitor_id'),
        Index('idx_store_zone', 'store_id', 'zone_id'),
    )


class VisitorSession(Base):
    """Aggregated visitor session data."""
    __tablename__ = "visitor_sessions"

    session_id = Column(String, primary_key=True)
    store_id = Column(String, nullable=False, index=True)
    visitor_id = Column(String, nullable=False, index=True)
    entry_time = Column(DateTime, nullable=False, index=True)
    exit_time = Column(DateTime, nullable=True)
    is_staff = Column(Boolean, nullable=False, default=False)
    zones_visited = Column(JSON, nullable=False, default=list)
    entered_billing = Column(Boolean, nullable=False, default=False)
    completed_purchase = Column(Boolean, nullable=False, default=False)
    abandoned_queue = Column(Boolean, nullable=False, default=False)
    total_dwell_ms = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index('idx_session_store_entry', 'store_id', 'entry_time'),
    )


class POSTransaction(Base):
    """POS transaction records."""
    __tablename__ = "pos_transactions"

    transaction_id = Column(String, primary_key=True)
    store_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    basket_value_inr = Column(Float, nullable=False)

    __table_args__ = (
        Index('idx_pos_store_timestamp', 'store_id', 'timestamp'),
    )


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def reset_db():
    """Reset database (for testing)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
