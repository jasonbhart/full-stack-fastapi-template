"""Middleware package for FastAPI application."""

from app.middleware.correlation import CorrelationIDMiddleware

__all__ = ["CorrelationIDMiddleware"]
