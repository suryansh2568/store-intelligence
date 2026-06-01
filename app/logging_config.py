"""
Structured logging configuration.
"""
import logging
import sys
from contextvars import ContextVar
from typing import Any, Dict
import uuid

import structlog

# Context variable for trace ID
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """Get current trace ID or generate new one."""
    trace_id = trace_id_var.get()
    if not trace_id:
        trace_id = str(uuid.uuid4())
        trace_id_var.set(trace_id)
    return trace_id


def set_trace_id(trace_id: str):
    """Set trace ID for current context."""
    trace_id_var.set(trace_id)


def add_trace_id(logger, method_name, event_dict):
    """Add trace ID to log event."""
    event_dict["trace_id"] = get_trace_id()
    return event_dict


def configure_logging(log_level: str = "INFO"):
    """Configure structured logging."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            add_trace_id,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )


def get_logger(name: str):
    """Get a structured logger."""
    return structlog.get_logger(name)
