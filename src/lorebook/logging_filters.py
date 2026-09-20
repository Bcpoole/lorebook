"""Logging filters shared by the FastAPI app's logging configuration."""

from __future__ import annotations

import logging

# Paths polled frequently by the frontend that would otherwise flood the
# uvicorn access log with noise.
_HEALTH_CHECK_PATHS = ("/api/health", "/api/health/llm")


class HealthCheckAccessFilter(logging.Filter):
    """Drop uvicorn access log records for frequently-polled health checks."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 3:
            return True

        path = str(args[2]).split("?", 1)[0]
        return path not in _HEALTH_CHECK_PATHS
