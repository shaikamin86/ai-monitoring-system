"""
Social media ingestion pipeline.

Collectors: Twitter/X, TikTok, RSS, Facebook
Each collector is stateless between calls; checkpoints live in Redis.
"""
from app.ingestion.base import BaseCollector, RateLimiter, CircuitBreaker, IngestionState

__all__ = ["BaseCollector", "RateLimiter", "CircuitBreaker", "IngestionState"]
